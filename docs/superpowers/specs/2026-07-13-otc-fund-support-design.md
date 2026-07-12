# 场外公募基金（OTC Fund）支持设计

日期：2026-07-13 ｜ 状态：已批准（用户确认 .OF 后缀方案 + 只做公募基金）

## 目标

让 ai-market-pulse 能分析支付宝 / 东方财富（天天基金）/ 银行**代销**的场外公募基金：
拉净值历史 → 技术指标 → 评分 → 报告/Dashboard/回测全链路打通，
并让 Web 控制台的持仓截图识别能正确区分基金与 A 股。

**明确不做**：银行自营理财产品（无公开行情 API）；货币基金（净值恒为 1，
技术面分析无意义，按现金处理并明确拒绝）。

## 符号约定

- 场外基金 = 6 位代码 + `.OF` 后缀（Wind/东财通用惯例），如 `005827.OF`。
- 识别完全基于后缀（`models.is_otc_fund_symbol`），与 `market` 字段解耦。
- `market` 统一为 `CN`（配置解析和截图导入自动推断），基准对比落到沪深 300。

## 数据源：`akshare_fund` provider

- 底层：akshare `fund_open_fund_info_em` → `fund.eastmoney.com/pingzhongdata/{code}.js`。
  单个静态 JS 一次性返回**全量**净值历史（单位净值 + 日增长率 + 累计净值），
  故不实现 `fetch_since` 增量拉取——TTL 缓存已覆盖重复调用场景。
- 名称/类型：`fund_name_em`（`fundcode_search.js`，全部 ~2 万只基金的
  代码/简称/类型），进程级缓存一次；失败时降级为无名称继续，不阻断取数。
- 类型含"货币"或"理财"→ 抛 `MarketDataError`，错误信息说明按现金处理。
- 注册表：`ProviderSpec("akshare_fund", aliases=("fund",), markets=("CN",))`，
  `can_handle` 只认 `.OF`；yfinance 的 `can_handle` 反向排除 `.OF`（Yahoo 无此数据，
  避免浪费一次必败请求）。`DataSettings.providers` 默认值加入 `akshare_fund`。

## 复权净值（关键正确性设计）

单位净值在分红除息日会跳水，直接喂指标会把分红误判为暴跌。方案：

```
adj_nav[t] = latest_unit_nav × cumprod(1+g)[t] / cumprod(1+g)[-1]
```

其中 `g` = 日增长率/100（缺失填单位净值 pct_change）。锚定最新单位净值，
使报告里显示的最新价与支付宝/天天基金界面一致，历史序列则分红连续。
前提"日增长率在除息日已含分红"须在实现期用真实分红基金（如 161725）实证；
若不成立，回退公式：用 `累计净值-单位净值` 差分还原分红额再算复权因子。

## 净值 → OHLCV 适配（指标引擎零改动）

Open=High=Low=Close=复权净值，Volume=NaN。后果（已核实代码）：

- `volume_ratio_20d` → None → 评分的量能确认项自动跳过（scoring 全部指标缺失即跳过）。
- True Range 退化为 |Δclose|，ATR 变为"日收益波幅"的 Wilder 均值——合理的波动代理，
  不失真；股票阈值（4.5%）对基金天然保守。
- 均线/RSI/MACD/回撤/动量/布林全部正常；缓存、离线降级、backtest、Dashboard 自动生效。

## 截图识别提示词（用户核心诉求）

`llm.py extract_portfolio_from_image` 系统提示词新增规则：

1. 场外基金（支付宝基金页/天天基金/银行理财 App 里名称含 混合/债券/指数/联接/QDII/FOF/持有期 等
   的 6 位代码持仓）→ 输出 `代码.OF`，market=CN。
2. 货币基金（余额宝等）视为现金，直接跳过不输出。
3. A 股股票保持裸 6 位代码（现有行为）。

配套修复导入链路的陷阱：`portfolio_import._normalize_symbol` 现在会把裸 6 位码
补成 `.SS/.SZ`（股票惯例）——`.OF` 后缀符号必须原样通过（`.upper()` 已保证大小写），
`_infer_market` 增加 `.OF → CN`。Web 控制台文案更新为"券商/基金 App 持仓截图"。

## 基金新闻

`_a_share_code` 不认 `.OF`（正确），现状会落到 Google News 查 "005827.OF stock"（垃圾结果）。
改为：基金符号有中文名称时用 `名称 + 基金` 作为查询词；无名称则跳过新闻。

## 测试

- mock akshare：.OF 路由、复权数学（含合成分红日）、锚定最新净值、货基拒绝、
  名称查询失败降级、yfinance 排除 .OF。
- portfolio_import：`.OF` 原样通过、`of` 小写归一、market 推断。
- llm：提示词含 `.OF` 规则的回归断言。
- 真实冒烟：`run --symbols "005827.OF,161725.OF" --providers akshare_fund`（东财直连，无需代理）
  + 分红日实证脚本。

## 部署

推送 fork → rsync NAS → recreate 容器 → NAS watchlist providers 更新
（`["akshare","akshare_fund","baostock","yfinance"]`）→ 容器内验证基金取数
（pingzhongdata 是 CDN 静态文件，反爬风险低于此前挂掉的 push2his 股票接口，需实测）。
