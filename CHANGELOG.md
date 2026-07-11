# Changelog

## Unreleased

### Fixed

- Daily-report signal distribution now uses the scoring engine's stance categories,
  and missing freshness metadata is surfaced as a data-quality alert.
- Dashboard relative-strength matrices now account for symbols without benchmark
  data instead of silently dropping them from the distribution.
- History writes are now locked, atomic, and upserted by symbol/date, preventing duplicate or corrupted JSONL rows under concurrent runs.
- Long/short allocation now uses gross exposure, so offsetting positions retain meaningful signed allocation percentages.

- yfinance now requests a wider calendar window and trims to the trading-day target, so
  long moving averages such as SMA200 are actually computed (previously `lookback_days`
  calendar days yielded too few trading rows and SMA200 was always empty).
- Notifications no longer leak a local filesystem path; an optional public report URL
  (`MARKET_PULSE_REPORT_URL`) is included instead when provided.

### Added

- A unified dark quant-research design system across the local console, daily report,
  history dashboard, and static site, with a persistent light-theme option.
- A four-stage visual research workflow covering holdings input, theme research,
  report Q&A, and threshold monitoring.
- Real-data signal overviews in daily reports and a dashboard research matrix for
  risk, benchmark-relative strength, and data freshness.
- Tag-driven theme research in daily reports and the history dashboard, including grouped scores, returns, relative strength, allocation, contribution, and risk pressure.
- Visual brokerage screenshot import with AI transcription, editable confirmation, symbol normalization, and a saved console watchlist.
- Report-grounded single-turn AI Q&A in the local console.
- Plugin-style `ProviderSpec` registry for built-in and runtime market data providers.
- Deduplicated threshold alerts plus `market-pulse alert-check` and an opt-in intraday GitHub Actions workflow.

- Project positioning now explicitly includes AI-assisted quant trading research,
  including watchlist screening, signal review, benchmark comparison, portfolio
  attribution, and risk control while keeping the no-trading safety boundary.
- Circuit breaker: `market-pulse run` skips history append and notifications and exits
  non-zero when no symbol returns valid market data, so a broken empty report is never
  published or pushed.
- `ruff` lint gate in CI and dedicated tests for scoring, the analysis engine,
  notifications, the CLI circuit breaker, and the yfinance fetch window.

## 0.1.0 - Unreleased

Initial public release candidate.

- Daily stock/ETF/crypto watchlist reports.
- Portfolio mode with quantity, cost basis, allocation, day P/L, and unrealized P/L.
- Rule-based signal score, risk findings, focus board, and daily checklist.
- Benchmark context, per-symbol relative strength, and data freshness warnings.
- Multi-provider market data foundation with yfinance, optional AkShare, Baostock, and Tushare.
- Google News RSS aggregation.
- Optional OpenAI-compatible asset and portfolio summaries with cache and prompt templates.
- Static dashboard from history JSONL.
- Interactive dashboard filters and per-symbol drilldown.
- Local visual console with browser-based custom symbol analysis.
- Static research site with dashboard and report archive.
- Bilingual EN/中文 generated HTML pages with a polished research cockpit UI.
- Redesigned English README and added Chinese README for public project presentation.
- Offline demo generator with deterministic sample reports, dashboard, site, and README screenshots.
- One-command custom ticker analysis with `market-pulse run --symbols`.
- Custom watchlist initialization with `market-pulse init --symbols`, so users can start from their own tickers without editing YAML.
- CSV/TSV/XLSX portfolio import.
- GitHub Actions artifacts and GitHub Pages workflow.
- Docker and docker-compose quick start.
