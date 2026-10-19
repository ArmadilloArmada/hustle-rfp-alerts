"""Export approved alert packs to email-draft HTML, mailto, optional Buttondown draft."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import markdown
import requests

from .approve import is_approved

logger = logging.getLogger(__name__)

BUTTONDOWN_URL = "https://api.buttondown.com/v1/emails"
MAILTO_BODY_MAX = 1800


@dataclass
class ExportResult:
    html_path: Path
    mailto_path: Path
    buttondown_id: str | None = None
    buttondown_url: str | None = None


def _stem_date(alert_md: Path) -> str:
    # alerts-YYYY-MM-DD.md → YYYY-MM-DD
    name = alert_md.stem  # alerts-YYYY-MM-DD
    if name.startswith("alerts-"):
        return name[len("alerts-") :]
    return name


def extract_subject(markdown_text: str, fallback_date: str) -> str:
    for line in markdown_text.splitlines():
        line = line.strip()
        if line.startswith("# "):
            return line[2:].strip()
    return f"RFP / job alert pack — {fallback_date}"


def md_to_html(markdown_text: str, subject: str) -> str:
    body = markdown.markdown(
        markdown_text,
        extensions=["extra", "sane_lists", "nl2br"],
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '  <meta charset="utf-8"/>\n'
        f"  <title>{_escape_html(subject)}</title>\n"
        "  <style>\n"
        "    body { font-family: Georgia, 'Times New Roman', serif; max-width: 42rem;\n"
        "           margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #1a1a1a; }\n"
        "    a { color: #0b5fff; }\n"
        "    hr { border: none; border-top: 1px solid #ccc; margin: 1.5rem 0; }\n"
        "    code { font-family: ui-monospace, monospace; font-size: 0.9em; }\n"
        "  </style>\n"
        "</head>\n"
        f"<body>\n{body}\n</body>\n"
        "</html>\n"
    )


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_mailto(subject: str, markdown_text: str, to: str = "") -> str:
    # Plain-text body for mail clients; truncate to stay under URL length limits.
    body = markdown_text.strip()
    if len(body) > MAILTO_BODY_MAX:
        body = (
            body[:MAILTO_BODY_MAX].rstrip()
            + "\n\n[…truncated — paste full HTML draft from email-draft-*.html…]"
        )
    # Collapse excessive blank lines for mailto readability
    body = re.sub(r"\n{3,}", "\n\n", body)
    params = f"subject={quote(subject)}&body={quote(body)}"
    if to:
        return f"mailto:{to}?{params}"
    return f"mailto:?{params}"


def create_buttondown_draft(subject: str, body_markdown: str, api_key: str) -> tuple[str, str | None]:
    """Create a Buttondown email with status=draft only. Never sends."""
    resp = requests.post(
        BUTTONDOWN_URL,
        headers={
            "Authorization": f"Token {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "subject": subject,
            "body": body_markdown,
            "status": "draft",
        },
        timeout=60,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"Buttondown draft failed ({resp.status_code}): {resp.text[:500]}")
    data = resp.json()
    email_id = str(data.get("id") or data.get("email_id") or "")
    if not email_id:
        raise RuntimeError(f"Buttondown response missing id: {data!r}")
    # Dashboard deep link when id is present
    dash = f"https://buttondown.com/emails/{email_id}"
    return email_id, dash


def export_alert_pack(
    alert_md: Path,
    *,
    approve_flag: bool,
    out_dir: Path | None = None,
    mailto_to: str = "",
    use_buttondown: bool = True,
) -> ExportResult:
    """
    Export an alert pack. Requires --approve (approve_flag=True).
    Never sends email; Buttondown path is draft-only when API key is set.
    """
    alert_md = alert_md.resolve()
    if not approve_flag:
        raise PermissionError(
            "Refusing to export without --approve. "
            "Review the alert pack, then re-run with --approve "
            "(optionally after: python -m src approve <path>)."
        )
    if not alert_md.is_file():
        raise FileNotFoundError(f"Alert pack not found: {alert_md}")
    if not alert_md.name.startswith("alerts-") or alert_md.suffix != ".md":
        raise ValueError(f"Expected out/alerts-*.md, got: {alert_md.name}")

    if not is_approved(alert_md):
        logger.warning(
            "No approval sidecar yet for %s — proceeding because --approve was passed. "
            "Tip: python -m src approve %s",
            alert_md.name,
            alert_md,
        )

    text = alert_md.read_text(encoding="utf-8")
    date_stem = _stem_date(alert_md)
    subject = extract_subject(text, date_stem)
    out_dir = out_dir or alert_md.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    html_path = out_dir / f"email-draft-{date_stem}.html"
    mailto_path = out_dir / f"email-draft-{date_stem}.mailto.txt"

    html_path.write_text(md_to_html(text, subject), encoding="utf-8")
    mailto_url = build_mailto(subject, text, to=mailto_to)
    mailto_path.write_text(mailto_url + "\n", encoding="utf-8")
    logger.info("Wrote %s", html_path)
    logger.info("Wrote %s", mailto_path)

    buttondown_id: str | None = None
    buttondown_url: str | None = None
    api_key = (os.environ.get("BUTTONDOWN_API_KEY") or "").strip()
    if use_buttondown and api_key:
        buttondown_id, buttondown_url = create_buttondown_draft(subject, text, api_key)
        logger.info("Buttondown draft created id=%s (not sent)", buttondown_id)
    elif use_buttondown:
        logger.info("BUTTONDOWN_API_KEY unset — skipped Buttondown draft")

    return ExportResult(
        html_path=html_path,
        mailto_path=mailto_path,
        buttondown_id=buttondown_id,
        buttondown_url=buttondown_url,
    )
