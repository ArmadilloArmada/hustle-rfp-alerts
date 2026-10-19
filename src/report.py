"""Write Markdown alert packs under out/."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from .filter import Match
from .summarize import summarize_match


def render_report(
    niche: str,
    matches: list[Match],
    openai_cfg: dict | None = None,
    run_date: date | None = None,
) -> str:
    run_date = run_date or date.today()
    lines: list[str] = [
        f"# RFP / job alert pack — {run_date.isoformat()}",
        "",
        f"**Niche:** {niche}",
        f"**Matches:** {len(matches)}",
        "",
        "_Human review required. Do not auto-email. Links may go stale; verify on the source page._",
        "",
        "---",
        "",
    ]
    if not matches:
        lines.append("No keyword matches in this run. Widen keywords or check feed health.")
        lines.append("")
        return "\n".join(lines)

    for i, match in enumerate(matches, start=1):
        item = match.item
        lines.append(f"## {i}. {item.title}")
        lines.append("")
        lines.append(f"- **Source:** {item.source}")
        if item.published:
            lines.append(f"- **Published:** {item.published}")
        if item.url:
            lines.append(f"- **Link:** {item.url}")
        lines.append("")
        lines.append(summarize_match(match, openai_cfg=openai_cfg))
        lines.append("")
        lines.append("---")
        lines.append("")
    return "\n".join(lines)


def write_report(out_dir: Path, markdown: str, run_date: date | None = None) -> Path:
    run_date = run_date or date.today()
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"alerts-{run_date.isoformat()}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
