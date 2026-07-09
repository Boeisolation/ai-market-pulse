# Publishing Guide

## Local Static Site

```bash
market-pulse run --config examples/watchlist.yaml --output reports
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "AI Market Pulse"
```

Open `site/index.html`.

## GitHub Pages

1. Push the repository to GitHub.
2. Open repository settings.
3. Enable GitHub Pages with GitHub Actions as the source.
4. Add optional secrets:
   - `OPENAI_API_KEY`
   - `OPENAI_MODEL`
   - `OPENAI_BASE_URL`
   - `TUSHARE_TOKEN`
5. Run `Publish Market Pulse Site`.

The workflow generates reports, dashboard, and the static site before deploying.

## Suggested Repository Metadata

Description:

```text
AI portfolio research site: daily stock analysis, risk board, portfolio P/L, dashboard, and GitHub Pages publishing.
```

Topics:

```text
ai, stock-analysis, portfolio, quant, yfinance, akshare, llm, github-pages, investment-research
```
