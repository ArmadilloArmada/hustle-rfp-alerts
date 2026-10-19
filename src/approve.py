"""Human approval markers for alert packs under out/."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


def approval_path_for(alert_md: Path) -> Path:
    """Sidecar next to the alert pack: alerts-YYYY-MM-DD.approved.json."""
    return alert_md.with_suffix(".approved.json")


def is_approved(alert_md: Path) -> bool:
    marker = approval_path_for(alert_md)
    if not marker.is_file():
        return False
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return bool(data.get("approved")) and Path(data.get("source", "")) == alert_md.resolve()


def approve(alert_md: Path) -> Path:
    """Mark an alert pack as human-reviewed. Returns the marker path."""
    alert_md = alert_md.resolve()
    if not alert_md.is_file():
        raise FileNotFoundError(f"Alert pack not found: {alert_md}")
    if not alert_md.name.startswith("alerts-") or alert_md.suffix != ".md":
        raise ValueError(f"Expected out/alerts-*.md, got: {alert_md.name}")

    marker = approval_path_for(alert_md)
    payload = {
        "approved": True,
        "source": str(alert_md),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "note": "Human reviewed. Safe to export (HTML / mailto / Buttondown draft-only).",
    }
    marker.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return marker
