"""
conclave/certification/skillset.py

A Skillset is the distilled context package that enables Haiku
to match Sonnet's quality on a specific task.

It contains:
  - A system prompt distilled from Sonnet's observed patterns
  - Explicit rules extracted from gold-standard outputs
  - Reference documents relevant to the task
  - Curated examples (input → output pairs)

Skillsets are versioned, stored locally, and referenced by certificates.
They are the core organizational asset that Conclave produces —
the encoded expertise of the organization, made executable by Haiku.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import anthropic

from .observatory import ObservedAction

SKILLSETS_DIR = Path(".conclave/skillsets")

DISTILLATION_PROMPT = """
You are analyzing a set of high-quality agent outputs to extract a reusable skillset.

The outputs were produced by a {model} model acting as a {role}.
Your goal: distill these into a system prompt, rules, and examples that would
allow a smaller model (Haiku) to reproduce the same quality on future similar tasks.

OBSERVED OUTPUTS:
{samples}

Return a JSON object with exactly these fields:
{{
  "system_prompt": "<200-400 word system prompt for Haiku optimized for this task>",
  "rules": ["<rule 1>", "<rule 2>", ...],  // 5-10 specific, actionable rules
  "quality_signals": ["<what good looks like>", ...],  // 3-5 observable quality markers
  "failure_modes": ["<what to avoid>", ...]  // 3-5 common failure patterns
}}

The system prompt must be specific, not generic. It should encode the patterns,
tone, format, and implicit standards visible in the observed outputs.

Return ONLY the JSON. No markdown, no preamble.
""".strip()


@dataclass
class Skillset:
    role: str
    task_type: str
    version: str
    system_prompt: str
    rules: list[str]
    quality_signals: list[str]
    failure_modes: list[str]
    examples: list[dict]  # [{input, output}]
    ref_docs: list[str]  # filenames of reference documents
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))
    sample_size: int = 0

    def to_dict(self) -> dict:
        return asdict(self)

    def save(self) -> Path:
        d = SKILLSETS_DIR / self.role.lower() / self.task_type
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"v{self.version}.json"
        p.write_text(json.dumps(self.to_dict(), indent=2))
        return p

    @staticmethod
    def load(role: str, task_type: str, version: str = "latest") -> Skillset | None:
        d = SKILLSETS_DIR / role.lower() / task_type
        if not d.exists():
            return None
        if version == "latest":
            candidates = sorted(d.glob("v*.json"))
            if not candidates:
                return None
            path = candidates[-1]
        else:
            path = d / f"v{version}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return Skillset(**data)

    def as_system_prompt(self) -> str:
        """Full system prompt to inject into Haiku for this task."""
        rules_text = "\n".join(f"- {r}" for r in self.rules)
        return f"{self.system_prompt}\n\nRULES FOR THIS TASK:\n{rules_text}"


class SkillsetBuilder:
    """
    Distills a set of ObservedActions into a Skillset using the model itself.
    Runs on Sonnet (distillation requires reasoning about patterns).
    """

    def __init__(self, client: anthropic.Anthropic):
        self.client = client

    def build(
        self,
        role: str,
        task_type: str,
        actions: list[ObservedAction],
        ref_docs: list[str] | None = None,
        version: str = "1.0",
    ) -> Skillset:
        # Pick top-quality examples (score ≥ 0.85)
        gold = sorted(
            [a for a in actions if a.quality_score >= 0.85],
            key=lambda a: a.quality_score,
            reverse=True,
        )[:10]

        samples_text = "\n\n---\n\n".join(
            f"INPUT:\n{a.input}\n\nOUTPUT:\n{a.output}\n(quality: {a.quality_score:.2f})"
            for a in gold
        )

        resp = self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            messages=[
                {
                    "role": "user",
                    "content": DISTILLATION_PROMPT.format(
                        model=actions[0].model if actions else "Sonnet",
                        role=role,
                        samples=samples_text,
                    ),
                }
            ],
        )

        try:
            data = json.loads(resp.content[0].text.strip())
        except Exception:
            data = {
                "system_prompt": f"You are executing {task_type} tasks for the {role} role.",
                "rules": [],
                "quality_signals": [],
                "failure_modes": [],
            }

        # Best examples for the skillset (diverse, high-quality)
        examples = [{"input": a.input, "output": a.output} for a in gold[:5]]

        return Skillset(
            role=role,
            task_type=task_type,
            version=version,
            system_prompt=data.get("system_prompt", ""),
            rules=data.get("rules", []),
            quality_signals=data.get("quality_signals", []),
            failure_modes=data.get("failure_modes", []),
            examples=examples,
            ref_docs=ref_docs or [],
            sample_size=len(actions),
        )
