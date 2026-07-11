# XF1 Handoff - AI Market Pulse

This folder is a handoff copy for final review, branding polish, and GitHub deployment.

## Project Purpose

AI Market Pulse is an open-source AI-assisted quant trading research cockpit.

It lets a user enter any watchlist, then generates:

- daily stock/ETF/crypto market analysis reports
- quant-style watchlist screening and signal review
- rule-based risk scores and readable reasons
- benchmark comparison versus SPY, QQQ, CSI 300, Hang Seng Index, etc.
- data freshness warnings
- portfolio/risk/contribution dashboard from JSONL history
- local static site for publishing
- optional OpenAI-compatible AI summaries

It is not an auto-trading bot, does not connect to brokers, and does not place orders. It is quant trading research automation only.

## Current Local Entry Points

Project path on XF1:

```text
/Users/carbonsilicon/ai-market-pulse
```

Run the visual local console:

```bash
cd /Users/abbywong/XF1/ai-market-pulse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
market-pulse serve
```

Then open:

```text
http://127.0.0.1:8766/
```

CLI fallback:

```bash
market-pulse run --symbols "AAPL,MSFT,NVDA,TSLA,600519" --output reports --history data/history.jsonl --no-notify
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "My Market Pulse"
```

Offline demo:

```bash
market-pulse demo --output demo
```

## What Already Works

- Visual local console at `market-pulse serve`
- Custom ticker input from the browser UI
- Editable AI brokerage screenshot import
- Tag-driven theme research in reports and Dashboard
- Report-grounded AI Q&A
- Provider registry and deduplicated threshold alerts
- One-command CLI custom ticker analysis with `run --symbols`
- Reusable custom watchlist creation with `init --symbols`
- HTML / Markdown / JSON report generation
- Dashboard generation from history JSONL
- Static site generation
- EN / 中文 UI switch
- README and README.zh-CN with screenshots
- GitHub Actions workflows for CI, daily artifact, and Pages publishing
- Docker and docker-compose
- Tests currently pass locally

## Important Files

- `src/ai_market_pulse/web.py` - local browser console
- `src/ai_market_pulse/cli.py` - CLI entrypoints
- `src/ai_market_pulse/engine.py` - analysis pipeline
- `src/ai_market_pulse/dashboard.py` - static dashboard
- `src/ai_market_pulse/reporting.py` - report rendering
- `src/ai_market_pulse/site.py` - static site builder
- `README.md` / `README.zh-CN.md` - public project presentation
- `.github/workflows/` - CI and deployment workflows
- `docs/assets/` - README screenshots

## Suggested Final Claude Tasks

1. Run full verification:

```bash
python -m compileall src tests -q
pytest -q
python -m pip wheel . --no-deps -w /tmp/amp-wheel
```

2. Review the browser console UX:

- default Chinese title should be clear: `我的自选股每日分析报告`
- user can type arbitrary symbols
- result links open correctly
- error states are understandable

3. Brand polish:

- tighten README headline and opening paragraphs
- refine GitHub repo description and topics
- prepare social launch copy
- optionally rename screenshots after final UI polish

4. GitHub deployment:

- initialize or move into the target GitHub repo
- commit source files, docs, tests, examples, prompts, workflows
- do not commit generated `reports/`, `data/`, `site/`, `demo/`, `.venv/`, caches, or secrets
- enable GitHub Pages with GitHub Actions
- add optional secrets only if needed:
  - `OPENAI_API_KEY`
  - `OPENAI_MODEL`
  - `OPENAI_BASE_URL`
  - `TUSHARE_TOKEN`
  - notification webhook secrets

5. Release:

- tag `v0.1.0`
- release title suggestion: `AI Market Pulse v0.1.0 - Turn any watchlist into a daily AI market research site`

## Safety Positioning

Keep this wording consistent:

```text
Research automation only. Not financial advice. No automated order placement.
```

## Current Product One-Liner

Turn any watchlist into a daily AI quant trading research report, risk dashboard, and static site.
