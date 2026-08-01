#!/usr/bin/env python3
"""Generate remaining chapters + foreshadowing ledger."""
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

WRITER_MODEL = os.environ.get("AUTONOVEL_WRITER_MODEL", "claude-sonnet-4-6")
API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
API_BASE = os.environ.get("AUTONOVEL_API_BASE_URL", "https://api.anthropic.com")

def call_writer(prompt, max_tokens=16000):
    import httpx
    headers = {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": WRITER_MODEL,
        "max_tokens": max_tokens,
        "temperature": 0.5,
        "system": (
            "You are a novel architect continuing an outline. Write in the same format "
            "as the preceding chapters. Every chapter needs: POV, Location, Save the Cat beat, "
            "% mark, Emotional arc, Try-fail cycle, Beats, Plants, Payoffs, Character movement, "
            "The lie, Word count target."
        ),
        "messages": [{"role": "user", "content": prompt}],
    }
    resp = httpx.post(f"{API_BASE}/v1/messages", headers=headers, json=payload, timeout=600)
    resp.raise_for_status()
    return resp.json()["content"][0]["text"]

def build_prompt(part1, mystery):
    return f"""Here are the first 17 chapters of a 24-chapter outline for "The Second Son of the House of Bells."
The outline was cut off mid-chapter-17. Continue from where it left off, then complete chapters 18-24,
then write the Foreshadowing Ledger.

THE OUTLINE SO FAR:
{part1}

THE CENTRAL MYSTERY (for reference):
{mystery}

REMAINING STRUCTURE NEEDED:

Ch 17 (complete it): Maret confrontation -- she reveals the truth about the void
Ch 18: Dark Night of the Soul -- Cass processes what he's learned
Ch 19: Break Into Three -- new information or perspective changes everything  
Ch 20-21: Gathering forces, making a plan
Ch 22: The climax at the Bell Tower -- Cass answers the question
Ch 23: Aftermath and resolution
Ch 24: Final Image (mirror of Opening Image)

Then write:

## Foreshadowing Ledger

| # | Thread | Planted (Ch) | Reinforced (Ch) | Payoff (Ch) | Type |
|---|--------|-------------|-----------------|-------------|------|

Include at LEAST 15 threads. Types: object, dialogue, action, symbolic, structural.
Plant-to-payoff distance must be at least 3 chapters.

REMEMBER:
- The climax uses the fourth option: Cass amplifies the question into audible range
  so the city can hear and answer for themselves
- This doesn't free Perin directly (Stability Trap -- not everything resolves cleanly)
- Cass's lie must be fully shattered by the climax
- Final Image should mirror Ch 1's Opening Image but show transformation
- At least one quiet chapter in the back half
"""


def main(base_dir=None):
    base_dir = base_dir or BASE_DIR

    outline_path = base_dir / "outline.md"
    part1_snapshot = base_dir / ".outline_part1.md"
    if not part1_snapshot.exists():
        sys.exit(
            f"ERROR: {part1_snapshot} not found. Run gen_outline.py first — "
            "outline.md may already hold merged part1+part2 content and can't "
            "be reliably reused as a fresh part-1 input."
        )
    # Read from the stable part-1 snapshot gen_outline.py writes alongside
    # outline.md (rather than outline.md itself), so a re-run of this script
    # never appends onto its own previous merged output.
    part1 = part1_snapshot.read_text(encoding="utf-8")
    mystery = (base_dir / "MYSTERY.md").read_text(encoding="utf-8")

    prompt = build_prompt(part1, mystery)

    print("Calling writer model...", file=sys.stderr)
    result = call_writer(prompt)

    # Merge part1 + part2 into outline.md once per run — never append onto a
    # previous merge — so rerunning part 2 cannot duplicate chapters.
    merged = part1 + "\n\n" + result
    outline_path.write_text(merged, encoding="utf-8")
    print(f"Saved to {outline_path}", file=sys.stderr)
    print(result)
    return merged


if __name__ == "__main__":
    main()
