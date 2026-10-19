# hustle-rfp-alerts

Job / RFP **alert packs** for WordPress and small-business web freelancers.

Poll free job boards and government RSS/API feeds → filter by keywords → summarize matches → write a Markdown digest under `out/`. **No auto-email** in v1 — you review and send yourself.

Part of [Project Hustle](https://github.com/armadilloarmada) Tier 0 (§3 Job / RFP alert packs).

## Requirements

- Python 3.11+
- Network access to the configured feeds
- Optional: `OPENAI_API_KEY` for LLM summaries (template summaries work without it)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml` to tune keywords and feeds. Prefer official RSS/public APIs (Federal Register, Remotive, RemoteOK, We Work Remotely). Avoid ToS-breaking scrapers. SAM.gov Opportunities API needs a free API key if you add it later — the example config uses public RSS/APIs that work without keys.

## Run

```bash
python -m src
# or
python -m src -c config.yaml -o out -v
```

Output:

```text
out/alerts-YYYY-MM-DD.md
```

## Pipeline

1. **Fetch** — RSS via `feedparser`; Remotive / RemoteOK JSON APIs
2. **Dedupe** — by URL
3. **Filter** — keyword match + simple fit score; deadline/budget heuristics
4. **Summarize** — OpenAI when `OPENAI_API_KEY` is set; otherwise deterministic templates
5. **Write** — `out/alerts-YYYY-MM-DD.md` for human review

## Config knobs

| Key | Purpose |
|-----|---------|
| `niche` | Label in the digest header |
| `keywords` | Case-insensitive substring filters |
| `location_hints` | Soft boost for fit score |
| `feeds` | List of `{name, url, type}` where `type` is `rss`, `remotive`, or `remoteok` |
| `max_items` | Cap on matches in the pack |
| `openai.model` | Model when using the API |

## Compliance notes

- Use public feeds/APIs only; respect robots/ToS of each source
- Digests may include short snippets for screening — do not republish full third-party postings
- Links go stale; verify deadlines and eligibility on the source page before bidding
- No outbound email automation in this repo (CAN-SPAM / spam risk)

## License

MIT
