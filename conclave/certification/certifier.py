"""
conclave/certification/certifier.py + policy.py combined

Certifier: reads a SimulationReport and emits a Certificate.
Policy: the routing lookup table built from all valid certificates.
"""
from __future__ import annotations
import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

from .simulator import SimulationReport

CERTS_DIR   = Path(".conclave/certificates")
POLICY_FILE = Path(".conclave/routing_policy.json")

# Certification thresholds
CERTIFIED_PASS_RATE    = 0.85   # ≥ 85% of runs pass
CONDITIONAL_PASS_RATE  = 0.70   # 70-85% → CONDITIONAL
# < 70% → REJECTED

CERT_TTL_DAYS = 90              # re-certify every 90 days


class CertStatus(str, Enum):
    CERTIFIED   = "CERTIFIED"    # route to Haiku in prod
    CONDITIONAL = "CONDITIONAL"  # Haiku + 10% human validation sample
    REJECTED    = "REJECTED"     # keep on Sonnet


@dataclass
class Certificate:
    cert_id:          str
    role:             str
    task_type:        str
    skillset_version: str
    haiku_model:      str
    sample_size:      int
    pass_rate:        float
    avg_quality:      float
    avg_structural:   float
    avg_completeness: float
    avg_coherence:    float
    cost_saving_pct:  float
    status:           CertStatus
    certified_at:     str
    expires_at:       str
    notes:            str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    def is_valid(self) -> bool:
        ts = time.strptime(self.expires_at, "%Y-%m-%d")
        return time.mktime(ts) > time.time()

    def save(self) -> Path:
        CERTS_DIR.mkdir(parents=True, exist_ok=True)
        p = CERTS_DIR / f"{self.cert_id}.json"
        p.write_text(json.dumps(self.to_dict(), indent=2))
        return p

    @staticmethod
    def load(cert_id: str) -> Optional["Certificate"]:
        p = CERTS_DIR / f"{cert_id}.json"
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        data["status"] = CertStatus(data["status"])
        return Certificate(**data)

    @staticmethod
    def load_all() -> list["Certificate"]:
        if not CERTS_DIR.exists():
            return []
        certs = []
        for p in CERTS_DIR.glob("*.json"):
            try:
                data = json.loads(p.read_text())
                data["status"] = CertStatus(data["status"])
                certs.append(Certificate(**data))
            except Exception:
                continue
        return certs


class Certifier:
    """Reads a SimulationReport and emits a Certificate."""

    def certify(self, report: SimulationReport) -> Certificate:
        if report.pass_rate >= CERTIFIED_PASS_RATE:
            status = CertStatus.CERTIFIED
        elif report.pass_rate >= CONDITIONAL_PASS_RATE:
            status = CertStatus.CONDITIONAL
        else:
            status = CertStatus.REJECTED

        now        = time.strftime("%Y-%m-%d")
        expires    = time.strftime(
            "%Y-%m-%d",
            time.gmtime(time.time() + CERT_TTL_DAYS * 86400)
        )
        cert_id    = f"{report.role.lower()}_{report.task_type}_{now}"

        notes = ""
        if status == CertStatus.REJECTED:
            notes = (
                f"Pass rate {report.pass_rate:.0%} below threshold {CONDITIONAL_PASS_RATE:.0%}. "
                f"Improve skillset and re-simulate."
            )
        elif status == CertStatus.CONDITIONAL:
            notes = (
                f"Pass rate {report.pass_rate:.0%} — routed to Haiku with 10% human validation."
            )

        cert = Certificate(
            cert_id=cert_id,
            role=report.role,
            task_type=report.task_type,
            skillset_version=report.skillset_version,
            haiku_model="claude-haiku-4-5-20251001",
            sample_size=report.total_runs,
            pass_rate=report.pass_rate,
            avg_quality=report.avg_overall,
            avg_structural=report.avg_structural,
            avg_completeness=report.avg_completeness,
            avg_coherence=report.avg_coherence,
            cost_saving_pct=report.cost_meter.savings_pct,
            status=status,
            certified_at=now,
            expires_at=expires,
            notes=notes,
        )
        cert.save()
        return cert


# ---------------------------------------------------------------------------
# Routing policy
# ---------------------------------------------------------------------------

class RoutingPolicy:
    """
    Lookup table: (role, task_type) → CertStatus + skillset version.
    Rebuilt from all valid certificates. Persisted to disk.
    Consulted by the TaskRouter at agent call time.
    """

    def __init__(self):
        self._table: dict[str, dict] = {}
        self._load()

    def _key(self, role: str, task_type: str) -> str:
        return f"{role.lower()}::{task_type}"

    def _load(self):
        if POLICY_FILE.exists():
            self._table = json.loads(POLICY_FILE.read_text())

    def rebuild(self):
        """Rebuild from all valid certificates on disk."""
        self._table = {}
        for cert in Certificate.load_all():
            if not cert.is_valid():
                continue
            if cert.status == CertStatus.REJECTED:
                continue
            key = self._key(cert.role, cert.task_type)
            # Keep the most recent cert per (role, task_type)
            existing = self._table.get(key)
            if not existing or cert.certified_at > existing["certified_at"]:
                self._table[key] = {
                    "status":           cert.status.value,
                    "skillset_version": cert.skillset_version,
                    "cost_saving_pct":  cert.cost_saving_pct,
                    "certified_at":     cert.certified_at,
                    "expires_at":       cert.expires_at,
                }
        POLICY_FILE.parent.mkdir(parents=True, exist_ok=True)
        POLICY_FILE.write_text(json.dumps(self._table, indent=2))

    def lookup(self, role: str, task_type: str) -> Optional[dict]:
        """Returns cert info if the task is Haiku-certified, None otherwise."""
        return self._table.get(self._key(role, task_type))

    def status_table(self) -> list[dict]:
        """All entries for display in `conclave status`."""
        rows = []
        for key, info in self._table.items():
            role, task_type = key.split("::")
            rows.append({
                "role": role,
                "task_type": task_type,
                **info,
            })
        return sorted(rows, key=lambda r: (r["role"], r["task_type"]))
