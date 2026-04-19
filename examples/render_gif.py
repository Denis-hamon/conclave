"""
examples/render_gif.py

Render an animated GIF of a Conclave dry-run to examples/demo.gif using Pillow.
No external terminal tooling (vhs / asciinema) required.

Produces a frame sequence that reveals the deliberation progressively, mimicking
a terminal recording. Color palette matches the site (warm coral on dark).

Run:
    python examples/render_gif.py
"""
from __future__ import annotations
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


# ---------- Canvas config ----------
W, H     = 1200, 720
PAD_X    = 40
PAD_Y    = 32
LINE_H   = 24
BG       = (20, 20, 19)         # #141413 — site's code-bg ink
FG       = (232, 228, 217)      # #E8E4D9
DIM      = (150, 148, 142)
FAINT    = (100, 98, 92)
ACCENT   = (204, 120, 92)       # #CC785C — Anthropic-style coral
GREEN    = (156, 180, 124)      # #9CB47C
PURPLE   = (139, 127, 184)      # #8B7FB8
BLUE     = (96, 156, 230)
YELLOW   = (220, 180, 100)

FONT_PATH = "/System/Library/Fonts/Menlo.ttc"
FONT_BOLD_PATH = "/System/Library/Fonts/Menlo.ttc"  # Menlo collection has bold faces
FONT_SIZE  = 15

font        = ImageFont.truetype(FONT_PATH, FONT_SIZE, index=0)   # Regular
font_bold   = ImageFont.truetype(FONT_PATH, FONT_SIZE, index=1)   # Bold
font_header = ImageFont.truetype(FONT_PATH, 17, index=1)


# ---------- Script ----------
# Each entry = (text, color, bold?)   OR   special "blank" line
ROLE_COLORS = {
    "CPO":         ACCENT,
    "TechLead":    GREEN,
    "QA":          PURPLE,
    "QA_Engineer": PURPLE,
    "user":        FG,
}

# Progressive script — each cumulative state becomes a frame.
# Grouped as (duration_ms, lines-to-add)
SCRIPT: list[tuple[int, list]] = [
    (500,  [("$ conclave run \"Spec the checkout API\" --dry-run", DIM, False)]),
    (200,  [("", FG, False)]),
    (400,  [("⚠  DRY RUN — no API calls made", YELLOW, True)]),
    (200,  [("", FG, False)]),
    (350,  [("╭───── ◆ Conclave · Deliberation started ─────╮", ACCENT, False),
            ("│ Spec the checkout API                        │", FG, False),
            ("╰──────────────────────────────────────────────╯", ACCENT, False),
            ("", FG, False)]),
    (700,  [("  [user] → [CPO]", None, True)]),
    (400,  [("    Spec the checkout API", DIM, False),
            ("", FG, False)]),
    (900,  [("  [CPO] → [TechLead]", None, True)]),
    (400,  [("    Scope: auth, idempotency, rollback. Budget: 2 sprints.", DIM, False),
            ("    ↳ Business value validated — delegating technical scope.", FAINT, False),
            ("", FG, False)]),
    (900,  [("  [TechLead] → [QA_Engineer]", None, True)]),
    (400,  [("    Spec attached. Prioritize payment flow edge cases.", DIM, False),
            ("    ↳ Haiku loop ×2 — templated handoff.", FAINT, False),
            ("", FG, False)]),
    (900,  [("  [QA_Engineer] → [CPO]", None, True)]),
    (400,  [("    3 blockers. payment-service v3 missing in staging.", DIM, False),
            ("    ↳ Escalation — requires executive decision.", FAINT, False),
            ("", FG, False)]),
    (400,  [("  ✓ Output from QA_Engineer", GREEN, True),
            ("", FG, False)]),
    (500,  [("╭───── ◆ Conclave · Deliberation complete ────╮", ACCENT, False),
            ("│ Trail →  .conclave/trail_20260420.jsonl      │", FG, False),
            ("│                                              │", FG, False),
            ("│ haiku     865 in    359 out   $0.0021        │", FG, False),
            ("│ sonnet    988 in    328 out   $0.0079        │", FG, False),
            ("│ ──────────────────────────────────────       │", FAINT, False),
            ("│ TOTAL                          $0.0100       │", FG, True),
            ("│ BASELINE (all-Sonnet)          $0.0159       │", DIM, False),
            ("│ SAVED   $0.0059   (36.9 %)                   │", GREEN, True),
            ("╰──────────────────────────────────────────────╯", ACCENT, False)]),
    (2200, []),   # hold final frame
]


# ---------- Renderer ----------
def render_frame(lines: list[tuple]) -> Image.Image:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Window chrome
    draw.rectangle([(0, 0), (W, 32)], fill=(30, 29, 27))
    for i, c in enumerate([(237, 108, 96), (247, 193, 81), (120, 194, 90)]):
        draw.ellipse([(18 + i*22, 11), (18 + i*22 + 11, 22)], fill=c)
    draw.text((W//2 - 50, 9), "conclave", font=font, fill=DIM)

    # Lines
    y = 42 + PAD_Y
    for text, color, bold in lines:
        if text == "":
            y += LINE_H // 2
            continue
        f = font_bold if bold else font
        c = color

        # Role-colored header line: "  [CPO] → [TechLead]"
        if c is None and text.lstrip().startswith("["):
            x = PAD_X
            # Render piece by piece with per-role colors
            raw = text
            # simple token scan
            buf = ""
            cursor_x = x
            i = 0
            while i < len(raw):
                ch = raw[i]
                if ch == '[':
                    if buf:
                        draw.text((cursor_x, y), buf, font=f, fill=FG)
                        cursor_x += f.getlength(buf)
                        buf = ""
                    end = raw.find(']', i)
                    if end < 0:
                        buf += ch; i += 1; continue
                    role = raw[i+1:end]
                    col = ROLE_COLORS.get(role, FG)
                    draw.text((cursor_x, y), f"[{role}]", font=font_bold, fill=col)
                    cursor_x += font_bold.getlength(f"[{role}]")
                    i = end + 1
                else:
                    buf += ch
                    i += 1
            if buf:
                draw.text((cursor_x, y), buf, font=f, fill=FG)
        else:
            draw.text((PAD_X, y), text, font=f, fill=c if c else FG)
        y += LINE_H

    # Footer watermark
    draw.text((W - 260, H - 28), "conclave-agents v0.1.0", font=font, fill=FAINT)
    draw.text((PAD_X, H - 28), "github.com/Denis-hamon/conclave", font=font, fill=FAINT)

    return img


def build_gif(out_path: Path) -> None:
    frames: list[Image.Image] = []
    durations: list[int] = []
    accum: list = []
    for dur_ms, new_lines in SCRIPT:
        accum.extend(new_lines)
        frames.append(render_frame(accum))
        durations.append(dur_ms)

    # Write optimized GIF
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        optimize=True,
        disposal=2,
    )
    print(f"Wrote {out_path}  ({len(frames)} frames, {sum(durations)/1000:.1f}s)")


if __name__ == "__main__":
    out = Path(__file__).parent / "demo.gif"
    build_gif(out)
