# hustle-rfp-alerts

Job / RFP **alert packs** for WordPress and small-business web freelancers.

Poll free job boards and government RSS/API feeds → filter by keywords → summarize matches → write a Markdown digest under `out/`. **Human approve before any export.** Optional free send path: local HTML + `mailto:` + Buttondown **draft-only** (never auto-publishes).

Part of [Project Hustle](https://github.com/armadilloarmada) Tier 0 (§3 Job / RFP alert packs).

## Requirements

- Python 3.11+
- Network access to the configured feeds
- Optional: `OPENAI_API_KEY` for LLM summaries (template summaries work without it)
- Optional: `BUTTONDOWN_API_KEY` to create a Buttondown **draft** on export (still never sends)

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.yaml config.yaml
```

Edit `config.yaml` to tune keywords and feeds. Prefer official RSS/public APIs (Federal Register, Remotive, RemoteOK, We Work Remotely). Avoid ToS-breaking scrapers. SAM.gov Opportunities API needs a free API key if you add it later — the example config uses public RSS/APIs that work without keys.

## Operate path

```bash
# 1) Generate today's pack
python -m src
# → out/alerts-YYYY-MM-DD.md

# 2) Human review the Markdown (edit false positives, verify links/deadlines)

# 3) Record approval (sidecar marker)
python -m src approve out/alerts-YYYY-MM-DD.md
# → out/alerts-YYYY-MM-DD.approved.json

# 4) Export email draft artifacts (requires --approve; refuses without it)
python -m src export out/alerts-YYYY-MM-DD.md --approve
# → out/email-draft-YYYY-MM-DD.html
# → out/email-draft-YYYY-MM-DD.mailto.txt
# → Buttondown draft (only if BUTTONDOWN_API_KEY is set; status=draft, never sent)

# Optional: prefill mailto recipient
python -m src export out/alerts-YYYY-MM-DD.md --approve --mailto-to you@example.com

# Optional: skip Buttondown even when the key is present
python -m src export out/alerts-YYYY-MM-DD.md --approve --no-buttondown
```

**Send yourself:** open the HTML in a browser and paste into your mail client, or open the `mailto:` URL from the `.mailto.txt` file, or finish/send the draft in the Buttondown dashboard. This repo never sets Buttondown status to send.

Without `--approve`, `export` exits with an error and writes nothing.

## Commands

| Command | Purpose |
|---------|---------|
| `python -m src` / `python -m src run` | Fetch → filter → write `out/alerts-YYYY-MM-DD.md` |
| `python -m src approve PATH` | Write approval sidecar for an alert pack |
| `python -m src export PATH --approve` | HTML + mailto (+ optional Buttondown draft) |

## Pipeline

1. **Fetch** — RSS via `feedparser`; Remotive / RemoteOK JSON APIs
2. **Dedupe** — by URL
3. **Filter** — keyword match + simple fit score; deadline/budget heuristics
4. **Summarize** — OpenAI when `OPENAI_API_KEY` is set; otherwise deterministic templates
5. **Write** — `out/alerts-YYYY-MM-DD.md` for human review
6. **Approve + export** — human gate, then free email-draft artifacts (no auto-send)

## Config knobs

| Key | Purpose |
|-----|---------|
| `niche` | Label in the digest header |
| `keywords` | Case-insensitive substring filters |
| `location_hints` | Soft boost for fit score |
| `feeds` | List of `{name, url, type}` where `type` is `rss`, `remotive`, or `remoteok` |
| `max_items` | Cap on matches in the pack |
| `openai.model` | Model when using the API |
| `export.mailto_to` | Optional default recipient hint (CLI `--mailto-to` overrides) |

## Compliance notes

- Use public feeds/APIs only; respect robots/ToS of each source
- Digests may include short snippets for screening — do not republish full third-party postings
- Links go stale; verify deadlines and eligibility on the source page before bidding
- **No auto-send.** Export requires `--approve`. Buttondown integration creates **drafts only**
- CAN-SPAM / consent: only mail people who opted in to your list

## License

MIT
