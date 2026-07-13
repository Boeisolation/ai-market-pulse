<div align="center">

# AI Market Pulse

**An AI + quant trading research cockpit for watchlist screening, portfolio risk, automated reports, and static publishing.**

[中文](README.zh-CN.md) · English

[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-0f766e)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-b45309.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-4f46e5.svg)](pyproject.toml)

</div>

---

## Why It Feels Different

AI Market Pulse is not just a scheduled stock script. It turns daily market data into a quant-oriented research product: technical factors, rule-based signals, benchmark-relative strength, portfolio attribution, risk findings, Markdown/HTML/JSON reports, a web dashboard, a static research site, and optional OpenAI-compatible summaries.

The project is designed for quant trading research workflows such as watchlist screening, signal review, portfolio risk checks, and pre-trade decision support. It does not connect to brokers, place orders, or promise returns.

It is an original implementation inspired by the demand for daily AI stock analysis tools. It is not a fork or copy of another repository.

![AI Market Pulse site preview](docs/assets/site-preview.png)

| Dashboard | Daily report |
|---|---|
| ![Dashboard preview](docs/assets/dashboard-preview.png) | ![Report preview](docs/assets/report-preview.png) |

## One Research Loop

1. **Input holdings** — type any supported symbol, add portfolio positions manually, or transcribe a brokerage screenshot with an OpenAI-compatible model.
2. **Run quant research** — calculate technical factors, rules-first scores, benchmark-relative strength, portfolio attribution, themes, and freshness checks.
3. **Review the evidence** — inspect the daily signal overview, risk board, contribution board, history lens, and report-grounded AI answers.
4. **Monitor and publish** — detect meaningful score/risk changes, push alerts, and publish the bilingual static site through GitHub Pages.

The interface is a real operating surface, not a mock dashboard: every score, matrix bar, freshness flag, and portfolio value is derived from generated report or JSONL history data.

## See It In 60 Seconds

Run the complete offline demo. It uses deterministic sample data, so no market API, news API, or LLM key is required.

```bash
pip install -e ".[dev]"
market-pulse demo --output demo
```

Then open:

- `demo/site/index.html`
- `demo/reports/dashboard.html`
- `demo/reports/market-pulse-20260708-0930.html`

## Product Surfaces

| Surface | What it shows | Output |
|---|---|---|
| Research console | Holdings input, screenshot import, theme research setup, report Q&A, alert checks | `http://127.0.0.1:8766` |
| Daily report | Signal overview, benchmark comparison, focus board, theme research, asset cards, news | `reports/market-pulse-*.html` |
| Web dashboard | Portfolio net value, risk/relative-strength/freshness matrix, score changes, contribution board | `reports/dashboard.html` |
| Static site | Dashboard link, latest report, archive, and navigation | `site/index.html` |
| JSONL history | Persistent local snapshots for trend rendering | `data/history.jsonl` |

## Highlights

- Unified dark quant-research UI with persistent light mode and EN / 中文 controls.
- Four-stage visual workflow: holdings input, theme research, report Q&A, and change alerts.
- Real-data signal overview and research matrix instead of decorative dashboard metrics.
- Watchlist-driven analysis for stocks, ETFs, crypto, and Yahoo Finance compatible symbols.
- Local visual console with arbitrary symbol input, editable AI screenshot import, report Q&A, dashboard refresh, and static-site links.
- One-command custom ticker analysis with `market-pulse run --symbols`.
- Quant research workflow for screening, signal review, benchmark comparison, portfolio attribution, and risk control.
- Technical snapshot: moving averages, RSI, MACD, Bollinger position, ATR, drawdown, volume ratio, 5/20/60-day returns.
- Rules-first signal score from 0 to 100 with readable reasons and risk labels.
- Portfolio mode with quantity, cost basis, allocation, day P/L, and unrealized P/L.
- Tag-driven theme research with grouped scores, returns, relative strength, allocation, contribution, and risk pressure.
- Focus Board for attention items, risk findings, contribution ranking, and daily checklist.
- Interactive dashboard exploration: symbol search, risk filter, relative-strength filter, history window, and symbol drilldown.
- Benchmark context for SPY, QQQ, CSI 300, Hang Seng Index, and configurable market baselines.
- Relative strength per symbol: 20/60-day performance versus its assigned benchmark.
- Data freshness checks: latest trading day, source, row count, and stale/missing data warnings.
- Provider registry with ordered fallback: yfinance by default, optional AkShare, Baostock, Tushare, and runtime extensions.
- Optional OpenAI-compatible asset/portfolio summaries, screenshot transcription, and report-grounded Q&A with local cache.
- Threshold alerts for score changes, risk upgrades, large daily moves, relative-strength deterioration, and stale data.
- Push notifications through Telegram, Slack, Discord, Feishu, WeCom, generic webhooks, or email.
- GitHub Actions and GitHub Pages workflows for zero-server daily publishing.

## Quick Start

```bash
git clone <your-repo-url>
cd ai-market-pulse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
market-pulse serve
```

Open `http://127.0.0.1:8766`. Enter symbols directly, add editable position rows, or upload a brokerage screenshot before clicking **Run Analysis**. Quantity, cost, and theme tags can all be confirmed in the browser. The console saves the portfolio to `data/console-watchlist.yaml`.

Prefer terminal usage?

```bash
market-pulse run --symbols "AAPL,MSFT,NVDA,TSLA,600519" --output reports --no-notify
```

Open the generated HTML file in `reports/`. Replace the symbols with any Yahoo Finance compatible ticker, crypto pair, HK ticker, or mainland A-share code. Plain 6-digit A-share codes are normalized automatically, for example `600519` becomes `600519.SS`.

To build the full dashboard and static site for your own watchlist:

```bash
market-pulse run --symbols "AAPL,MSFT,NVDA,TSLA,600519" --output reports --history data/history.jsonl --no-notify
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "My Market Pulse"
```

To save a reusable watchlist file:

```bash
market-pulse init --symbols "AAPL,MSFT,NVDA,TSLA,600519" --path watchlist.yaml
market-pulse run --config watchlist.yaml --output reports --history data/history.jsonl --no-notify
```

## Starter Templates

Prefer a prebuilt starting point? Use a template instead of `--symbols`.

```bash
market-pulse init --list-templates
market-pulse init --template us-tech --path watchlist.yaml
market-pulse init --template cn-stock --path watchlist.yaml
market-pulse init --template crypto --path watchlist.yaml
```

## Portfolio Import

The visual console accepts PNG/JPEG/WebP brokerage screenshots when `OPENAI_API_KEY` and `OPENAI_MODEL` are configured. The image is sent to the configured AI provider, so redact account identifiers first. AI only transcribes the image; quantity, cost, market, and tags remain editable before they enter the deterministic analysis pipeline.

File import is also available from the CLI:

```bash
market-pulse import-portfolio --input examples/portfolio.csv --output watchlist.yaml --template default --force
```

Supported formats: `.csv`, `.tsv`, `.xlsx` with `pip install -e ".[excel]"`.

Recognized columns include `symbol`, `ticker`, `code`, `name`, `market`, `currency`, `quantity`, `qty`, `shares`, `cost_basis`, `avg_cost`, `tags`, and `note`. Chinese headers such as `股票代码`, `股票名称`, `持仓`, `成本价`, `标签`, and `备注` are also accepted.

## Dashboard And Site

```bash
market-pulse run --config watchlist.yaml --output reports --history data/history.jsonl --no-notify
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "AI Market Pulse"
```

Open `site/index.html`. The generated report, dashboard, and site include an EN / 中文 switch.

## Data Providers

```yaml
data:
  providers: ["akshare", "akshare_fund", "yfinance"]
```

### Mainland OTC Mutual Funds (场外基金)

Funds sold through Alipay, East Money / 天天基金, or bank apps are supported with the
Wind-style `.OF` suffix — six-digit fund code plus `.OF`:

```bash
market-pulse run --symbols "005827.OF,161725.OF" --output reports
```

Notes:

- NAV history comes from East Money (`akshare_fund` provider) and is
  dividend-adjusted (daily growth rates are compounded and anchored to the latest
  published unit NAV, so the last price matches what fund apps display).
- Volume-based signals are skipped automatically (funds have no volume); the ATR
  reading degrades to a close-to-close volatility proxy.
- Money-market funds (货币基金, e.g. 余额宝) are rejected on purpose — their NAV is
  pinned near 1 and technical analysis is meaningless; treat them as cash.
- Bank-issued wealth-management products (银行自营理财) have no public NAV API and
  cannot be supported.
- The web console's screenshot import recognizes fund-app holdings and appends
  `.OF` automatically.

## Benchmarks And Freshness

```yaml
benchmarks:
  enabled: true
  symbols: ["SPY", "QQQ", "000300.SS", "^HSI"]
  default_by_market:
    US: "SPY"
    CN: "000300.SS"
    HK: "^HSI"
  compare:
    AAPL: "QQQ"
    NVDA: "QQQ"
  stale_after_days: 4
```

Reports show benchmark context, per-symbol relative strength, latest trading day, data source, and stale/missing data warnings.

Optional mainland China providers:

```bash
pip install -e ".[cn]"
pip install -e ".[tushare]"
export TUSHARE_TOKEN="..."
```

Providers are tried in order; if one is missing or cannot serve a symbol, the app falls back to the next provider.

Custom providers can be registered with `ProviderSpec` and `register_provider()` without editing the core fallback dispatcher.

## Enable AI Summaries

```yaml
llm:
  enabled: true
  base_url: "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
  api_key_env: "OPENAI_API_KEY"
  model: "${OPENAI_MODEL:-}"
  temperature: 0.2
  prompts_dir: "prompts"
  cache_enabled: true
  cache_dir: "data/ai-cache"
  # Screenshot import needs a vision-capable model. If your main provider is
  # text-only (e.g. DeepSeek), route image requests elsewhere; unset fields
  # fall back to the main settings.
  vision_base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
  vision_model: "gemini-2.5-flash"
  vision_api_key_env: "VISION_API_KEY"
```

The web console reads the same split from environment variables:
`OPENAI_BASE_URL` / `OPENAI_MODEL` / `OPENAI_API_KEY` for text, plus optional
`VISION_BASE_URL` / `VISION_MODEL` / `VISION_API_KEY` for screenshot import.

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="your-model-name"
market-pulse run --config watchlist.yaml --output reports
```

Useful switches:

```bash
market-pulse run --config watchlist.yaml --output reports --no-ai
market-pulse run --config watchlist.yaml --output reports --ai-only
market-pulse doctor --config watchlist.yaml
```

The same environment variables enable screenshot transcription and the console's **Ask This Report** box. Answers are grounded in the generated report JSON and do not call market tools or alter signal scores.

## Intraday Threshold Alerts

```yaml
alerts:
  enabled: true
  score_change: 10
  daily_move: 0.05
  relative_20d_drop: 0.05
  risk_upgrade: true
  stale_data: true
```

```bash
market-pulse alert-check --config watchlist.yaml --state data/alert-state.json
```

The first run creates a baseline. Later runs only emit new threshold events and reuse the existing notification channels. `.github/workflows/intraday-alert.yml` is opt-in: set repository variable `ENABLE_INTRADAY_ALERTS=true` after configuring data and notification credentials.

## Docker

```bash
docker compose up --build
```

This generates `reports/`, `data/history.jsonl`, and `site/`.

## Publishing

This repository includes:

- `.github/workflows/ci.yml`
- `.github/workflows/daily-report.yml`
- `.github/workflows/pages.yml`
- `.github/workflows/intraday-alert.yml`
- [docs/PUBLISHING.md](docs/PUBLISHING.md)

After pushing to GitHub, add optional secrets such as `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `TUSHARE_TOKEN`.

## Roadmap

See [CHANGELOG.md](CHANGELOG.md) and [ROADMAP.md](ROADMAP.md).

## Safety

This software is for quant trading research automation only. It does not provide financial advice, does not guarantee returns, does not connect to brokers, and does not place trades. Always verify market data, news, model outputs, and corporate actions before making decisions.
