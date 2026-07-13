<div align="center">

# AI Market Pulse

**一个 AI + 量化交易研究驾驶舱：自选股筛选、组合风控、自动报告与静态发布。**

中文 · [English](README.md)

[![CI](https://img.shields.io/badge/CI-GitHub%20Actions-0f766e)](.github/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-b45309.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-4f46e5.svg)](pyproject.toml)

</div>

---

## 它不只是一个定时脚本

AI Market Pulse 把每日行情、技术指标、规则信号、相对强弱、持仓盈亏、风险规则、新闻和可选 AI 总结整理成一个偏量化交易研究的本地产品：日报、Dashboard、静态站点、JSON 历史、组合归因、风险榜、收益贡献榜，形成可本地查看和静态发布的完整研究界面。

项目面向自选股筛选、交易信号复盘、组合风险检查、盘前/盘后研究等量化交易研究流程。它不连接券商、不自动下单、不承诺收益。

本项目是原创实现，灵感来自“AI 股票每日分析工具”的真实需求，不是 fork，也不是复制其他仓库。

![AI Market Pulse 站点预览](docs/assets/site-preview.png)

| Dashboard | 每日研究报告 |
|---|---|
| ![Dashboard 预览](docs/assets/dashboard-preview.png) | ![报告预览](docs/assets/report-preview.png) |

## 一条完整的量化研究闭环

1. **输入持仓**：输入任意受支持的股票代码、手动添加组合持仓，或通过 OpenAI 兼容模型识别券商持仓截图。
2. **执行量化研究**：计算技术因子、规则评分、相对基准强弱、组合归因、主题分组和数据新鲜度。
3. **审阅研究证据**：在日报信号总览、风险榜、收益贡献榜、历史透镜和报告追问中交叉验证。
4. **监控与发布**：检测评分和风险异动，自动推送提醒，并通过 GitHub Pages 发布中英文静态研究站点。

界面不是装饰性 Dashboard：评分、矩阵比例、新鲜度警报和组合数据全部来自实际生成的报告或 JSONL 历史。

## 60 秒体验完整产品

运行离线 demo。它使用确定性的示例数据，不需要行情 API、新闻 API 或 LLM Key。

```bash
pip install -e ".[dev]"
market-pulse demo --output demo
```

然后打开：

- `demo/site/index.html`
- `demo/reports/dashboard.html`
- `demo/reports/market-pulse-20260708-0930.html`

## 产品界面

| 界面 | 展示内容 | 输出 |
|---|---|---|
| 量化研究控制台 | 持仓输入、截图导入、主题研究配置、报告追问、异动检查 | `http://127.0.0.1:8766` |
| 每日研究报告 | 信号总览、基准对比、焦点看板、主题研究、单股卡片、新闻 | `reports/market-pulse-*.html` |
| Web Dashboard | 组合净值、风险/相对强弱/新鲜度矩阵、评分变化、收益贡献榜 | `reports/dashboard.html` |
| 静态研究站点 | Dashboard 入口、最新报告、历史归档、导航入口 | `site/index.html` |
| JSONL 历史 | 用于趋势渲染的本地持久化快照 | `data/history.jsonl` |

## 核心能力

- 全产品统一的深色量化研究界面，支持持久化浅色模式与 EN / 中文切换。
- 四阶段可视化流程：持仓输入、主题研究、报告追问、异动提醒。
- 日报信号总览与 Dashboard 研究矩阵全部由真实历史数据计算，不使用装饰性假指标。
- 支持股票、ETF、加密资产，以及 Yahoo Finance 兼容代码。
- 本地可视化控制台：任意代码输入、AI 持仓截图识别与确认、报告追问、刷新 Dashboard、打开静态站点。
- 支持 `market-pulse run --symbols` 一条命令查询自定义股票池。
- 量化交易研究流程：股票池筛选、信号复盘、基准对比、组合归因、风险控制。
- 技术指标：均线、RSI、MACD、布林位置、ATR、回撤、量比、5/20/60 日收益。
- 规则优先的 0-100 信号评分，带风险标签和可读原因。
- 组合模式：数量、成本、市值、仓位占比、当日盈亏、浮动盈亏。
- 标签驱动的主题研究：分组评分、收益、相对强弱、仓位、贡献和风险压力。
- Focus Board：重点关注、风险发现、贡献排序、每日检查清单。
- 交互式 Dashboard：代码搜索、风险筛选、相对强弱筛选、历史窗口、单股详情钻取。
- 基准对比：SPY、QQQ、沪深300、恒生指数，以及可配置的市场基准。
- 单股相对强弱：展示 20/60 日收益相对基准的跑赢或跑输。
- 数据新鲜度：最新交易日、数据源、历史行数、滞后或缺失风险提示。
- 插件式数据源注册与顺序降级：默认 yfinance，可选 AkShare、Baostock、Tushare，也可运行时扩展。
- 可选 OpenAI 兼容模型：单股/组合总结、截图抄录、基于报告的追问、prompt 模板、本地缓存。
- 阈值异动：评分变化、风险升级、单日大幅波动、相对强弱恶化和数据滞后。
- 推送通知：Telegram、Slack、Discord、飞书、企业微信、通用 webhook、邮件。
- GitHub Actions 与 GitHub Pages：无需服务器也能每日发布。

## 快速开始

```bash
git clone <your-repo-url>
cd ai-market-pulse
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
market-pulse serve
```

打开 `http://127.0.0.1:8766`。可以直接输入股票代码、手动新增持仓行，也可以上传券商持仓截图；数量、成本、市场和主题标签都能在浏览器中确认。点击 **开始分析** 后，组合会保存到 `data/console-watchlist.yaml`。

如果偏好命令行，也可以直接运行：

```bash
market-pulse run --symbols "AAPL,MSFT,NVDA,TSLA,600519" --output reports --no-notify
```

打开 `reports/` 里的 HTML 文件即可查看报告。把示例代码换成你自己的股票池即可，支持 Yahoo Finance 兼容代码、加密资产、港股代码和 A 股代码。纯 6 位 A 股代码会自动补后缀，例如 `600519` 会变成 `600519.SS`。

为自己的股票池生成完整 Dashboard 和静态站点：

```bash
market-pulse run --symbols "AAPL,MSFT,NVDA,TSLA,600519" --output reports --history data/history.jsonl --no-notify
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "My Market Pulse"
```

如果想保存一个可复用股票池文件：

```bash
market-pulse init --symbols "AAPL,MSFT,NVDA,TSLA,600519" --path watchlist.yaml
market-pulse run --config watchlist.yaml --output reports --history data/history.jsonl --no-notify
```

## 配置模板

如果想从预设行业/市场模板开始，也可以不用 `--symbols`。

```bash
market-pulse init --list-templates
market-pulse init --template us-tech --path watchlist.yaml
market-pulse init --template cn-stock --path watchlist.yaml
market-pulse init --template crypto --path watchlist.yaml
```

## 导入持仓

配置 `OPENAI_API_KEY` 和 `OPENAI_MODEL` 后，可视化控制台支持 PNG/JPEG/WebP 券商截图。图片会发送给配置的 AI 服务商，因此应先遮盖账号等隐私信息。AI 只负责抄录，识别结果必须经过用户确认，后续评分仍使用确定性规则。

命令行也保留文件导入：

```bash
market-pulse import-portfolio --input examples/portfolio.csv --output watchlist.yaml --template default --force
```

支持 `.csv`、`.tsv`、`.xlsx`。XLSX 需要安装：

```bash
pip install -e ".[excel]"
```

可识别字段包括 `symbol`、`ticker`、`code`、`name`、`market`、`currency`、`quantity`、`qty`、`shares`、`cost_basis`、`avg_cost`、`tags`、`note`，也支持 `股票代码`、`股票名称`、`持仓`、`成本价`、`标签`、`备注`。

## Dashboard 与静态站点

```bash
market-pulse run --config watchlist.yaml --output reports --history data/history.jsonl --no-notify
market-pulse dashboard --history data/history.jsonl --output reports/dashboard.html
market-pulse site --reports reports --output site --title "AI Market Pulse"
```

打开 `site/index.html`。生成的日报、Dashboard 和站点首页都支持 EN / 中文切换。

## 数据源

```yaml
data:
  providers: ["akshare", "akshare_fund", "yfinance"]
```

### 场外公募基金（支付宝 / 天天基金 / 银行代销）

场外基金使用 Wind 惯例的 `.OF` 后缀（6 位基金代码 + `.OF`）：

```bash
market-pulse run --symbols "005827.OF,161725.OF" --output reports
```

说明：

- 净值历史来自东方财富天天基金（`akshare_fund` 数据源），并做了**分红复权**：
  按日增长率累乘、锚定最新披露单位净值，报告里的最新价与基金 App 显示一致，
  历史序列在分红除息日保持连续，均线/RSI/回撤不会被分红砸出假暴跌。
- 基金没有成交量，量能类信号自动跳过；ATR 退化为"日收益波幅"的代理指标。
- **货币基金（如余额宝）会被明确拒绝**——净值恒定在 1 元附近，技术面分析无意义，
  请当作现金处理。
- **银行自营理财产品不支持**——各银行只在自家 App 内披露净值，没有公开行情 API。
- Web 控制台的持仓截图识别会自动区分基金与 A 股，为场外基金补上 `.OF` 后缀。

## 基准与数据新鲜度

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

报告会展示基准概览、单股相对强弱、最新交易日、数据源，以及数据滞后或缺失风险。

可选 A 股增强数据源：

```bash
pip install -e ".[cn]"
pip install -e ".[tushare]"
export TUSHARE_TOKEN="..."
```

数据源按顺序尝试；某个数据源缺失或不支持该标的时，会自动尝试下一个。

开发者可以通过 `ProviderSpec` 和 `register_provider()` 注册自定义数据源，不需要修改核心 fallback 分发器。

## 启用 AI 总结

```yaml
llm:
  enabled: true
  # 截图识别需要能识图的模型。主服务商是纯文本（如 DeepSeek）时，
  # 用 vision_* 三个字段把图片请求路由到另一家；不设则回落主配置。
  # vision_base_url: "https://generativelanguage.googleapis.com/v1beta/openai"
  # vision_model: "gemini-2.5-flash"
  # vision_api_key_env: "VISION_API_KEY"
  base_url: "${OPENAI_BASE_URL:-https://api.openai.com/v1}"
  api_key_env: "OPENAI_API_KEY"
  model: "${OPENAI_MODEL:-}"
  temperature: 0.2
  prompts_dir: "prompts"
  cache_enabled: true
  cache_dir: "data/ai-cache"
```

```bash
export OPENAI_API_KEY="..."
export OPENAI_MODEL="your-model-name"
market-pulse run --config watchlist.yaml --output reports
```

常用开关：

```bash
market-pulse run --config watchlist.yaml --output reports --no-ai
market-pulse run --config watchlist.yaml --output reports --ai-only
market-pulse doctor --config watchlist.yaml
```

同样的环境变量也会启用截图识别和控制台里的“追问这份报告”。回答只读取生成的报告 JSON，不调用行情工具，也不会改变信号评分。

## 盘中阈值异动

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

第一次运行只建立基线，后续只推送新事件，并复用现有通知渠道。`.github/workflows/intraday-alert.yml` 默认不自动运行；配置数据源与通知凭据后，将仓库变量 `ENABLE_INTRADAY_ALERTS` 设为 `true` 即可开启。

## Docker

```bash
docker compose up --build
```

这会生成 `reports/`、`data/history.jsonl` 和 `site/`。

## 发布

项目内置：

- `.github/workflows/ci.yml`
- `.github/workflows/daily-report.yml`
- `.github/workflows/pages.yml`
- `.github/workflows/intraday-alert.yml`
- [docs/PUBLISHING.md](docs/PUBLISHING.md)

推到 GitHub 后，可以配置 `OPENAI_API_KEY`、`OPENAI_MODEL`、`OPENAI_BASE_URL`、`TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`、`TUSHARE_TOKEN` 等 secrets。

## 路线图

查看 [CHANGELOG.md](CHANGELOG.md) 和 [ROADMAP.md](ROADMAP.md)。

## 风险提示

本软件仅用于量化交易研究自动化，不提供投资建议，不承诺收益，不连接券商，也不会自动交易或下单。做任何决策前，请自行核验行情、新闻、模型输出、公司行动和风险。
