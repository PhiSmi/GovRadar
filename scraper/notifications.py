"""Optional run summaries and notifications."""

from __future__ import annotations

import os
from pathlib import Path

import requests


def build_run_summary(rows: list[dict], new_count: int, errors: list[str]) -> str:
    total = len(rows)
    high = sum(1 for row in rows if int(row.get("relevance_score", 0) or 0) >= 70)
    open_count = sum(1 for row in rows if row.get("status") == "open")
    top_rows = sorted(rows, key=lambda row: int(row.get("relevance_score", 0) or 0), reverse=True)[:5]

    lines = [
        "# GovRadar scrape summary",
        "",
        f"- Tenders processed: {total}",
        f"- New tenders: {new_count}",
        f"- Open tenders: {open_count}",
        f"- High relevance (70+): {high}",
        f"- Errors: {len(errors)}",
        "",
    ]

    if top_rows:
        lines.extend(["## Highest relevance tenders", ""])
        for row in top_rows:
            title = row.get("title", "Untitled")
            agency = row.get("agency", "Unknown agency")
            score = row.get("relevance_score", 0)
            timeline = row.get("estimated_seek_timeline", "Unspecified")
            lines.append(f"- {title} | {agency} | score {score} | {timeline}")
        lines.append("")

    if errors:
        lines.extend(["## Errors", ""])
        for error in errors[:10]:
            lines.append(f"- {error}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def write_run_summary(summary: str, path: str = "reports/latest_run_summary.md") -> str:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(summary, encoding="utf-8")
    return str(report_path)


def send_slack_summary(summary: str) -> bool:
    webhook = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not webhook:
        return False

    response = requests.post(
        webhook,
        json={"text": summary[:3500]},
        timeout=30,
    )
    response.raise_for_status()
    return True
