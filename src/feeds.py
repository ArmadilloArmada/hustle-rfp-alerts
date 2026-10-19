"""Fetch and normalize free board / government feed items."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

logger = logging.getLogger(__name__)

USER_AGENT = "hustle-rfp-alerts/0.1 (+https://github.com/armadilloarmada/hustle-rfp-alerts)"
TIMEOUT = 30


@dataclass
class FeedItem:
    id: str
    title: str
    url: str
    summary: str
    source: str
    published: str | None = None
    tags: list[str] = field(default_factory=list)
    raw_text: str = ""

    def haystack(self) -> str:
        parts = [self.title, self.summary, self.raw_text, " ".join(self.tags)]
        return " ".join(p for p in parts if p).lower()


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json, application/rss+xml, */*"})
    return s


def _stable_id(source: str, url: str, title: str) -> str:
    key = (url or title or "").strip().lower()
    return f"{source}:{key}"[:240]


def fetch_rss(name: str, url: str) -> list[FeedItem]:
    logger.info("Fetching RSS: %s", name)
    parsed = feedparser.parse(url, agent=USER_AGENT)
    items: list[FeedItem] = []
    for entry in parsed.entries:
        link = getattr(entry, "link", "") or ""
        title = getattr(entry, "title", "") or "(untitled)"
        summary = getattr(entry, "summary", "") or getattr(entry, "description", "") or ""
        published = None
        if getattr(entry, "published", None):
            published = entry.published
        elif getattr(entry, "updated", None):
            published = entry.updated
        tags = []
        for t in getattr(entry, "tags", []) or []:
            term = getattr(t, "term", None) or str(t)
            if term:
                tags.append(term)
        items.append(
            FeedItem(
                id=_stable_id(name, link, title),
                title=title.strip(),
                url=link,
                summary=_strip_html(summary)[:2000],
                source=name,
                published=published,
                tags=tags,
                raw_text=_strip_html(summary),
            )
        )
    return items


def fetch_remotive(name: str, url: str) -> list[FeedItem]:
    logger.info("Fetching Remotive API: %s", name)
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs") or []
    items: list[FeedItem] = []
    for job in jobs:
        title = job.get("title") or "(untitled)"
        link = job.get("url") or ""
        desc = job.get("description") or ""
        tags = list(job.get("tags") or [])
        if job.get("category"):
            tags.append(job["category"])
        if job.get("job_type"):
            tags.append(job["job_type"])
        items.append(
            FeedItem(
                id=_stable_id(name, link, title),
                title=title.strip(),
                url=link,
                summary=_strip_html(desc)[:2000],
                source=name,
                published=job.get("publication_date"),
                tags=tags,
                raw_text=_strip_html(desc),
            )
        )
    return items


def fetch_remoteok(name: str, url: str) -> list[FeedItem]:
    logger.info("Fetching RemoteOK API: %s", name)
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    items: list[FeedItem] = []
    for row in data:
        if not isinstance(row, dict) or "id" not in row:
            # First element is often metadata
            continue
        title = row.get("position") or row.get("title") or "(untitled)"
        link = row.get("url") or row.get("apply_url") or ""
        if link and link.startswith("/"):
            link = "https://remoteok.com" + link
        desc = row.get("description") or ""
        tags = list(row.get("tags") or [])
        company = row.get("company") or ""
        if company:
            title = f"{title} @ {company}"
        epoch = row.get("epoch") or row.get("date")
        published = None
        if isinstance(epoch, (int, float)):
            published = datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()
        elif isinstance(epoch, str):
            published = epoch
        items.append(
            FeedItem(
                id=_stable_id(name, link or str(row.get("id")), title),
                title=title.strip(),
                url=link,
                summary=_strip_html(desc)[:2000],
                source=name,
                published=published,
                tags=tags,
                raw_text=_strip_html(desc),
            )
        )
    return items


def fetch_jobicy(name: str, url: str) -> list[FeedItem]:
    """Jobicy public remote-jobs JSON API (no key)."""
    logger.info("Fetching Jobicy API: %s", name)
    resp = _session().get(url, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    jobs = data.get("jobs") or []
    items: list[FeedItem] = []
    for job in jobs:
        title = job.get("jobTitle") or "(untitled)"
        company = job.get("companyName") or ""
        if company:
            title = f"{title} @ {company}"
        link = job.get("url") or ""
        desc = job.get("jobDescription") or job.get("jobExcerpt") or ""
        tags: list[str] = []
        industry = job.get("jobIndustry")
        if isinstance(industry, list):
            tags.extend(str(x) for x in industry if x)
        elif industry:
            tags.append(str(industry))
        for key in ("jobType", "jobLevel", "jobGeo"):
            val = job.get(key)
            if isinstance(val, list):
                tags.extend(str(x) for x in val if x)
            elif val:
                tags.append(str(val))
        items.append(
            FeedItem(
                id=_stable_id(name, link or str(job.get("id") or ""), title),
                title=title.strip(),
                url=link,
                summary=_strip_html(desc)[:2000],
                source=name,
                published=job.get("pubDate"),
                tags=tags,
                raw_text=_strip_html(desc),
            )
        )
    return items


FETCHERS = {
    "rss": fetch_rss,
    "remotive": fetch_remotive,
    "remoteok": fetch_remoteok,
    "jobicy": fetch_jobicy,
}


def fetch_all(feeds: list[dict[str, Any]]) -> list[FeedItem]:
    all_items: list[FeedItem] = []
    for feed in feeds:
        name = feed.get("name") or urlparse(feed.get("url", "")).netloc or "feed"
        ftype = (feed.get("type") or "rss").lower()
        url = feed.get("url")
        if not url:
            logger.warning("Skipping feed with no url: %s", name)
            continue
        fetcher = FETCHERS.get(ftype)
        if not fetcher:
            logger.warning("Unknown feed type %r for %s; treating as rss", ftype, name)
            fetcher = fetch_rss
        try:
            items = fetcher(name, url)
            logger.info("%s \u2192 %d items", name, len(items))
            all_items.extend(items)
        except Exception as exc:  # noqa: BLE001 — keep pipeline resilient
            logger.error("Failed to fetch %s: %s", name, exc)
    return all_items


def dedupe(items: list[FeedItem]) -> list[FeedItem]:
    seen: set[str] = set()
    out: list[FeedItem] = []
    for item in items:
        key = (item.url or item.id).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _strip_html(text: str) -> str:
    if not text:
        return ""
    # Lightweight strip; good enough for matching + template summaries
    import re

    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()
