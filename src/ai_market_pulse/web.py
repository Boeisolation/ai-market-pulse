from __future__ import annotations

import base64
import binascii
import json
import os
from dataclasses import dataclass, replace
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import quote, unquote

import yaml

from .alerts import evaluate_alerts, load_alert_state, write_alert_state
from .config import DEFAULT_PROVIDERS, LLMSettings, load_config_from_mapping
from .dashboard import write_dashboard
from .engine import run_analysis
from .history import append_history, attach_history, load_history
from .llm import answer_report_question, extract_portfolio_from_image
from .portfolio_import import normalize_portfolio_assets, resolve_fund_records
from .reporting import write_reports
from .sample import custom_watchlist_config, parse_symbols
from .site import build_site
from .ui import language_boot_script, language_runtime_script, language_toggle, ui_styles


@dataclass(frozen=True)
class ConsoleOptions:
    symbols: list[str]
    title: str
    timezone: str
    language: str
    providers: list[str]
    reports_dir: Path
    history_path: Path
    site_dir: Path
    include_news: bool
    use_ai: bool
    build_dashboard: bool
    build_site: bool
    assets: list[dict[str, Any]]
    check_alerts: bool


def run_console(host: str = "127.0.0.1", port: int = 8766, root: str | Path = ".") -> None:
    root_path = Path(root).resolve()
    server = _bind_server(host, port, root_path)
    actual_host, actual_port = server.server_address
    print(f"AI Market Pulse Console: http://{actual_host}:{actual_port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped AI Market Pulse Console.")
    finally:
        server.server_close()


def render_console_html() -> str:
    return f"""<!doctype html>
<html lang="en" data-lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Market Pulse Console</title>
  {language_boot_script("en")}
  <style>
    {ui_styles()}
    .console-grid {{ display: grid; grid-template-columns: minmax(420px, 0.9fr) minmax(0, 1.1fr); gap: 14px; align-items: start; }}
    .console-header h1 {{ font-size: 38px; }}
    .console-meta {{ display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 8px; margin: 0; }}
    .console-meta div {{ min-width: 0; }}
    .console-meta dt {{ color: var(--muted); font-size: 10px; font-weight: 800; text-transform: uppercase; }}
    .console-meta dd {{ margin: 5px 0 0; color: var(--ink); font-size: 14px; font-weight: 780; }}
    .workflow-rail {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); margin: 14px 0; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; background: var(--canvas-soft); }}
    .workflow-step {{ min-width: 0; padding: 12px 14px; border-right: 1px solid var(--line); }}
    .workflow-step:last-child {{ border-right: 0; }}
    .workflow-step span {{ display: block; color: var(--brand); font-family: "SFMono-Regular", Consolas, monospace; font-size: 11px; font-weight: 800; }}
    .workflow-step strong {{ display: block; margin-top: 5px; font-size: 13px; }}
    .workflow-step small {{ display: block; margin-top: 2px; color: var(--muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
    .form-grid {{ display: grid; gap: 12px; }}
    /* Grid items default to min-width:auto and refuse to shrink below their
       content, so the wide holdings table would overflow the panel and paint
       underneath the results panel. */
    .form-grid > * {{ min-width: 0; }}
    .work-panel {{ border-top: 2px solid var(--brand); }}
    .panel-heading {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; padding-bottom: 11px; border-bottom: 1px solid var(--line); }}
    .panel-heading h2 {{ margin: 0; font-size: 17px; }}
    .panel-heading .mono {{ color: var(--muted); font-size: 11px; }}
    .field label {{ display: block; margin-bottom: 6px; color: var(--muted); font-size: 12px; font-weight: 760; }}
    .field input, .field textarea, .field select {{
      width: 100%; border: 1px solid var(--line-strong); border-radius: 8px; padding: 10px 11px;
      background: var(--canvas-soft); color: var(--ink); font: inherit;
    }}
    .field textarea {{ min-height: 118px; resize: vertical; }}
    .switch-row {{ display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }}
    .checkline {{ display: flex; gap: 8px; align-items: center; min-height: 36px; color: var(--ink); font-weight: 680; }}
    .checkline input {{ width: 16px; height: 16px; accent-color: var(--brand); }}
    .primary-button {{
      min-height: 42px; border: 1px solid var(--brand); border-radius: 8px; padding: 10px 13px;
      background: var(--brand); color: #04110b; font: inherit; font-weight: 820; cursor: pointer;
    }}
    .primary-button[disabled] {{ opacity: 0.62; cursor: wait; }}
    .secondary-button {{ min-height: 38px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 8px 11px; background: var(--canvas-soft); color: var(--ink); font: inherit; font-weight: 760; cursor: pointer; }}
    .import-tools {{ display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }}
    .import-tools input[type="file"] {{ min-width: 0; flex: 1; }}
    .portfolio-editor {{ display: none; overflow-x: auto; margin-top: 8px; }}
    .portfolio-editor.is-visible {{ display: block; }}
    .portfolio-editor table {{ min-width: 720px; box-shadow: none; }}
    .portfolio-editor input {{ min-width: 86px; padding: 7px 8px; }}
    .portfolio-editor .remove-row {{ width: 34px; min-height: 34px; border: 0; background: transparent; color: var(--red); font-size: 20px; cursor: pointer; }}
    .result-list {{ display: grid; gap: 10px; margin-top: 12px; }}
    .result-link {{ display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center; border-bottom: 1px solid var(--line); padding: 11px 2px; }}
    .result-link:last-child {{ border-bottom: 0; }}
    .result-link strong {{ color: var(--ink); }}
    .status-box {{ min-height: 250px; border-top: 2px solid var(--blue); }}
    .status-line {{ margin: 0; white-space: pre-wrap; word-break: break-word; }}
    .error-box {{ color: var(--red); }}
    .ask-box {{ display: none; margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--line); }}
    .ask-box.is-visible {{ display: grid; gap: 10px; }}
    .ask-box textarea {{ width: 100%; min-height: 78px; border: 1px solid var(--line-strong); border-radius: 8px; padding: 10px; background: var(--canvas); color: var(--ink); font: inherit; resize: vertical; }}
    .answer-box {{ white-space: pre-wrap; padding: 12px; border-left: 3px solid var(--brand); background: var(--canvas-soft); border-radius: 0 8px 8px 0; }}
    .alert-note {{ white-space: pre-wrap; padding: 12px; border: 1px solid var(--line); border-radius: 8px; background: var(--canvas-soft); }}
    @media (max-width: 900px) {{
      .console-grid, .switch-row {{ grid-template-columns: 1fr; }}
      .workflow-rail {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .workflow-step:nth-child(2) {{ border-right: 0; }}
      .workflow-step:nth-child(-n+2) {{ border-bottom: 1px solid var(--line); }}
    }}
    @media (max-width: 560px) {{ .console-meta {{ grid-template-columns: 1fr; }} .workflow-rail {{ grid-template-columns: 1fr; }} .workflow-step {{ border-right: 0; border-bottom: 1px solid var(--line); }} .workflow-step:last-child {{ border-bottom: 0; }} }}
  </style>
</head>
<body>
<main>
  <nav class="topbar">
    <div class="brand-mark">AI Market Pulse</div>
    {language_toggle()}
  </nav>
  <header class="hero console-header">
    <div>
      <div class="eyebrow"><span data-i18n-en>Research Workbench</span><span data-i18n-zh>量化研究工作台</span></div>
      <h1><span data-i18n-en>Build Today's Research Run</span><span data-i18n-zh>创建今日量化研究任务</span></h1>
      <p><span data-i18n-en>Configure holdings, data scope, and outputs from one deterministic research workflow.</span><span data-i18n-zh>在同一条确定性研究流程中配置持仓、数据范围与输出。</span></p>
    </div>
    <aside class="hero-panel">
      <dl class="console-meta">
        <div><dt><span data-i18n-en>Runtime</span><span data-i18n-zh>运行方式</span></dt><dd><span class="status-dot"></span> Local</dd></div>
        <div><dt><span data-i18n-en>Engine</span><span data-i18n-zh>研究引擎</span></dt><dd>Rules first</dd></div>
        <div><dt><span data-i18n-en>Output</span><span data-i18n-zh>输出</span></dt><dd>HTML · JSON</dd></div>
      </dl>
    </aside>
  </header>
  <section class="workflow-rail" aria-label="Research workflow">
    <div class="workflow-step"><span>01 / INPUT</span><strong><span data-i18n-en>Holdings</span><span data-i18n-zh>持仓输入</span></strong><small><span data-i18n-en>Manual or screenshot</span><span data-i18n-zh>手动或截图</span></small></div>
    <div class="workflow-step"><span>02 / RESEARCH</span><strong><span data-i18n-en>Theme Analysis</span><span data-i18n-zh>主题研究</span></strong><small><span data-i18n-en>Signals and benchmarks</span><span data-i18n-zh>信号与基准</span></small></div>
    <div class="workflow-step"><span>03 / REVIEW</span><strong><span data-i18n-en>Report Q&A</span><span data-i18n-zh>报告追问</span></strong><small><span data-i18n-en>Grounded answers</span><span data-i18n-zh>基于报告回答</span></small></div>
    <div class="workflow-step"><span>04 / MONITOR</span><strong><span data-i18n-en>Change Alerts</span><span data-i18n-zh>异动提醒</span></strong><small><span data-i18n-en>Risk and freshness</span><span data-i18n-zh>风险与新鲜度</span></small></div>
  </section>
  <section class="console-grid">
    <form class="panel form-grid work-panel" data-run-form>
      <div class="panel-heading"><h2><span data-i18n-en>Research Inputs</span><span data-i18n-zh>研究输入</span></h2><span class="mono">01—02</span></div>
      <div class="field">
        <label for="portfolio-image"><span data-i18n-en>Import brokerage / fund-app screenshot</span><span data-i18n-zh>导入券商或基金App持仓截图</span></label>
        <div class="import-tools">
          <input id="portfolio-image" type="file" accept="image/png,image/jpeg,image/webp" data-portfolio-image>
          <button class="secondary-button" type="button" data-import-portfolio><span data-i18n-en>Recognize holdings</span><span data-i18n-zh>识别持仓</span></button>
          <button class="secondary-button" type="button" data-add-position aria-label="Add position"><span data-i18n-en>Add row</span><span data-i18n-zh>新增持仓</span></button>
          <button class="secondary-button" type="button" data-clear-positions aria-label="Clear positions"><span data-i18n-en>Clear all</span><span data-i18n-zh>清空持仓</span></button>
        </div>
        <p class="fineprint" data-import-status><span data-i18n-en>The image is sent to your configured AI provider for transcription. OTC mutual funds are tagged with the .OF suffix; money-market funds are treated as cash and skipped. Remove private account details and review every field.</span><span data-i18n-zh>图片会发送给你配置的 AI 服务商进行抄录。场外基金会自动加 .OF 后缀，货币基金按现金处理不导入。请先遮盖账号等隐私信息，并逐项确认结果。</span></p>
        <div class="portfolio-editor" data-portfolio-editor></div>
      </div>
      <div class="field">
        <label for="symbols"><span data-i18n-en>Symbols</span><span data-i18n-zh>股票代码</span></label>
        <textarea id="symbols" name="symbols" placeholder="AAPL, MSFT, NVDA, 600519, 0700.HK, BTC-USD" required>AAPL, MSFT, NVDA, 600519</textarea>
      </div>
      <div class="field">
        <label for="title"><span data-i18n-en>Report title</span><span data-i18n-zh>报告标题</span></label>
        <input id="title" name="title" value="我的自选股每日分析报告" data-default-en="My Daily Stock Analysis Report" data-default-zh="我的自选股每日分析报告">
      </div>
      <div class="switch-row">
        <div class="field">
          <label for="providers"><span data-i18n-en>Data providers</span><span data-i18n-zh>数据源</span></label>
          <input id="providers" name="providers" value="akshare, akshare_fund, baostock, yfinance">
        </div>
        <div class="field">
          <label for="timezone"><span data-i18n-en>Timezone</span><span data-i18n-zh>时区</span></label>
          <input id="timezone" name="timezone" value="Asia/Shanghai">
        </div>
      </div>
      <div class="switch-row">
        <label class="checkline"><input type="checkbox" name="includeNews" checked> <span data-i18n-en>Include news</span><span data-i18n-zh>包含新闻</span></label>
        <label class="checkline"><input type="checkbox" name="buildDashboard" checked> <span data-i18n-en>Refresh dashboard</span><span data-i18n-zh>刷新 Dashboard</span></label>
        <label class="checkline"><input type="checkbox" name="buildSite" checked> <span data-i18n-en>Build static site</span><span data-i18n-zh>生成静态站点</span></label>
        <label class="checkline"><input type="checkbox" name="useAi"> <span data-i18n-en>Use AI summaries</span><span data-i18n-zh>启用 AI 总结</span></label>
        <label class="checkline"><input type="checkbox" name="checkAlerts"> <span data-i18n-en>Check threshold changes</span><span data-i18n-zh>检查阈值异动</span></label>
      </div>
      <button class="primary-button" type="submit"><span data-i18n-en>Run Analysis</span><span data-i18n-zh>开始分析</span></button>
    </form>
    <section class="panel status-box" aria-live="polite">
      <div class="panel-heading"><h2><span data-i18n-en>Research Output</span><span data-i18n-zh>研究输出</span></h2><span class="mono">03—04</span></div>
      <p class="muted status-line" data-status><span data-i18n-en>Ready.</span><span data-i18n-zh>就绪。</span></p>
      <div class="result-list" data-results></div>
      <form class="ask-box" data-ask-form>
        <h3><span data-i18n-en>Ask This Report</span><span data-i18n-zh>追问这份报告</span></h3>
        <textarea name="question" placeholder="为什么某只股票评分降低？ / Which positions are lagging their benchmark?" required></textarea>
        <button class="secondary-button" type="submit"><span data-i18n-en>Ask AI</span><span data-i18n-zh>询问 AI</span></button>
        <div class="answer-box muted" data-answer><span data-i18n-en>Answers stay grounded in the generated report.</span><span data-i18n-zh>回答仅依据已生成报告。</span></div>
      </form>
    </section>
  </section>
</main>
{language_runtime_script()}
<script>
  (function () {{
    var form = document.querySelector("[data-run-form]");
    var status = document.querySelector("[data-status]");
    var results = document.querySelector("[data-results]");
    var button = form.querySelector('button[type="submit"]');
    var titleInput = form.querySelector('input[name="title"]');
    var imageInput = document.querySelector("[data-portfolio-image]");
    var importButton = document.querySelector("[data-import-portfolio]");
    var addPositionButton = document.querySelector("[data-add-position]");
    var clearPositionsButton = document.querySelector("[data-clear-positions]");
    var importStatus = document.querySelector("[data-import-status]");
    var portfolioEditor = document.querySelector("[data-portfolio-editor]");
    var askForm = document.querySelector("[data-ask-form]");
    var answerBox = document.querySelector("[data-answer]");
    var latestReportPath = null;
    var titleEdited = false;
    function currentLang() {{ return document.documentElement.dataset.lang || "en"; }}
    function text(en, zh) {{ return currentLang() === "zh" ? zh : en; }}
    function defaultTitle(lang) {{
      return lang === "zh" ? titleInput.dataset.defaultZh : titleInput.dataset.defaultEn;
    }}
    function syncDefaultTitle() {{
      var lang = currentLang();
      var other = lang === "zh" ? titleInput.dataset.defaultEn : titleInput.dataset.defaultZh;
      if (!titleEdited || titleInput.value === other) {{
        titleInput.value = defaultTitle(lang);
        titleEdited = false;
      }}
    }}
    function esc(value) {{
      return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {{
        return {{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[char];
      }});
    }}
    function setStatus(message, isError) {{
      status.textContent = message;
      status.classList.toggle("error-box", Boolean(isError));
    }}
    function linkRow(label, href) {{
      if (!href) return "";
      return '<a class="result-link" href="' + esc(href) + '" target="_blank" rel="noopener"><strong>' + esc(label) + '</strong><span>' + esc(text("Open", "打开")) + '</span></a>';
    }}
    function renderPortfolioEditor(assets) {{
      if (!assets || !assets.length) {{
        portfolioEditor.classList.remove("is-visible");
        portfolioEditor.innerHTML = "";
        return;
      }}
      var rows = assets.map(function (asset) {{
        var tags = Array.isArray(asset.tags) ? asset.tags.join(", ") : (asset.tags || "");
        return '<tr data-portfolio-row>' +
          '<td><input data-field="symbol" value="' + esc(asset.symbol || "") + '" placeholder="' + text("fill in", "待填") + '"></td>' +
          '<td><input data-field="name" value="' + esc(asset.name || "") + '"></td>' +
          '<td><input data-field="market" value="' + esc(asset.market || "") + '"></td>' +
          '<td><input data-field="quantity" type="number" step="any" value="' + esc(asset.quantity == null ? "" : asset.quantity) + '"></td>' +
          '<td><input data-field="cost_basis" type="number" step="any" value="' + esc(asset.cost_basis == null ? "" : asset.cost_basis) + '"></td>' +
          '<td><input data-field="tags" value="' + esc(tags) + '"></td>' +
          '<td><button class="remove-row" type="button" data-remove-row aria-label="Remove">×</button></td>' +
        '</tr>';
      }}).join("");
      portfolioEditor.innerHTML = '<table><thead><tr><th>' + text("Symbol", "代码") + '</th><th>' + text("Name", "名称") + '</th><th>' + text("Market", "市场") + '</th><th>' + text("Quantity", "数量") + '</th><th>' + text("Cost", "成本") + '</th><th>' + text("Tags", "标签") + '</th><th></th></tr></thead><tbody>' + rows + '</tbody></table>';
      portfolioEditor.classList.add("is-visible");
      syncSymbolsFromEditor();
    }}
    function editorAssets(includeBlank) {{
      return Array.prototype.slice.call(portfolioEditor.querySelectorAll("[data-portfolio-row]")).map(function (row) {{
        function value(field) {{ var input = row.querySelector('[data-field="' + field + '"]'); return input ? input.value.trim() : ""; }}
        var asset = {{ symbol: value("symbol"), name: value("name"), market: value("market"), tags: value("tags").split(/[,，;；]/).map(function (tag) {{ return tag.trim(); }}).filter(Boolean) }};
        if (value("quantity") !== "") asset.quantity = Number(value("quantity"));
        if (value("cost_basis") !== "") asset.cost_basis = Number(value("cost_basis"));
        return asset;
      }}).filter(function (asset) {{ return includeBlank || asset.symbol; }});
    }}
    function mergeEditorAssets(existing, incoming) {{
      var merged = existing.slice();
      var seenSymbols = {{}};
      var seenNames = {{}};
      var appended = 0;
      existing.forEach(function (asset) {{
        var symbol = String(asset.symbol || "").trim().toUpperCase();
        var name = String(asset.name || "").trim();
        if (symbol) seenSymbols[symbol] = true;
        if (name) seenNames[name] = true;
      }});
      incoming.forEach(function (asset) {{
        var symbol = String(asset.symbol || "").trim().toUpperCase();
        var name = String(asset.name || "").trim();
        if (symbol ? seenSymbols[symbol] : (name && seenNames[name])) return;
        if (symbol) seenSymbols[symbol] = true;
        if (name) seenNames[name] = true;
        merged.push(asset);
        appended += 1;
      }});
      return {{ assets: merged, appended: appended, skipped: incoming.length - appended }};
    }}
    function syncSymbolsFromEditor() {{
      var assets = editorAssets();
      if (assets.length) form.symbols.value = assets.map(function (asset) {{ return asset.symbol; }}).join(", ");
    }}
    function readImage(file) {{
      return new Promise(function (resolve, reject) {{
        var reader = new FileReader();
        reader.onload = function () {{ resolve(reader.result); }};
        reader.onerror = function () {{ reject(new Error(text("Could not read image.", "无法读取图片。"))); }};
        reader.readAsDataURL(file);
      }});
    }}
    importButton.addEventListener("click", async function () {{
      var file = imageInput.files && imageInput.files[0];
      if (!file) {{ importStatus.textContent = text("Choose a screenshot first.", "请先选择持仓截图。"); return; }}
      importButton.disabled = true;
      importStatus.textContent = text("Recognizing holdings…", "正在识别持仓…");
      try {{
        var response = await fetch("/api/portfolio/extract", {{ method: "POST", headers: {{ "Content-Type": "application/json" }}, body: JSON.stringify({{ image: await readImage(file) }}) }});
        var body = await response.json();
        if (!response.ok) throw new Error(body.error || "Request failed");
        var merge = mergeEditorAssets(editorAssets(true), body.assets || []);
        renderPortfolioEditor(merge.assets);
        var summary = merge.skipped
          ? text("Appended " + merge.appended + " holdings, skipped " + merge.skipped + " duplicates. ", "已追加 " + merge.appended + " 项持仓，跳过重复 " + merge.skipped + " 项。")
          : text("Appended " + merge.appended + " holdings. ", "已追加 " + merge.appended + " 项持仓。");
        importStatus.textContent = summary + text("Review every recognized field before running analysis.", "请逐项确认识别结果，再开始分析。");
      }} catch (error) {{
        importStatus.textContent = error.message || String(error);
      }} finally {{ importButton.disabled = false; }}
    }});
    addPositionButton.addEventListener("click", function () {{
      var assets = editorAssets(true);
      assets.push({{ symbol: "", name: "", market: "US", quantity: "", cost_basis: "", tags: [] }});
      renderPortfolioEditor(assets);
    }});
    clearPositionsButton.addEventListener("click", function () {{
      renderPortfolioEditor([]);
      importStatus.textContent = text("Cleared all holdings.", "已清空全部持仓。");
    }});
    portfolioEditor.addEventListener("input", syncSymbolsFromEditor);
    portfolioEditor.addEventListener("click", function (event) {{
      var remove = event.target.closest("[data-remove-row]");
      if (!remove) return;
      remove.closest("[data-portfolio-row]").remove();
      syncSymbolsFromEditor();
      if (!editorAssets(true).length) portfolioEditor.classList.remove("is-visible");
    }});
    form.addEventListener("submit", async function (event) {{
      event.preventDefault();
      button.disabled = true;
      results.innerHTML = "";
      setStatus(text("Running analysis. This can take a minute when market/news data is fetched.", "正在分析。拉取行情和新闻时可能需要一点时间。"), false);
      var payload = {{
        symbols: form.symbols.value,
        assets: editorAssets(),
        title: form.title.value,
        timezone: form.timezone.value,
        providers: form.providers.value,
        includeNews: form.includeNews.checked,
        useAi: form.useAi.checked,
        buildDashboard: form.buildDashboard.checked,
        buildSite: form.buildSite.checked,
        checkAlerts: form.checkAlerts.checked
      }};
      try {{
        var response = await fetch("/api/analyze", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload)
        }});
        var body = await response.json();
        if (!response.ok) throw new Error(body.error || "Request failed");
        setStatus(text("Done. Generated " + body.symbols.join(", "), "完成。已生成 " + body.symbols.join(", ")), false);
        latestReportPath = body.links.json;
        askForm.classList.add("is-visible");
        var alertNote = body.alerts && body.alerts.length ? '<div class="alert-note"><strong>' + esc(text("New alerts", "新异动")) + '</strong><p>' + esc(body.alerts.join("\\n")) + '</p></div>' : '';
        results.innerHTML = [
          linkRow(text("HTML report", "HTML 报告"), body.links.html),
          linkRow(text("Dashboard", "Dashboard"), body.links.dashboard),
          linkRow(text("Static site", "静态站点"), body.links.site),
          linkRow(text("Saved watchlist", "已保存自选配置"), body.links.watchlist),
          linkRow("JSON", body.links.json),
          linkRow("Markdown", body.links.markdown),
          alertNote
        ].join("");
      }} catch (error) {{
        setStatus(error.message || String(error), true);
      }} finally {{
        button.disabled = false;
      }}
    }});
    askForm.addEventListener("submit", async function (event) {{
      event.preventDefault();
      if (!latestReportPath) return;
      var askButton = askForm.querySelector("button");
      askButton.disabled = true;
      answerBox.textContent = text("Reading the report…", "正在读取报告…");
      try {{
        var response = await fetch("/api/ask", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ reportPath: latestReportPath, question: askForm.question.value, language: currentLang() === "zh" ? "zh-CN" : "en-US" }})
        }});
        var body = await response.json();
        if (!response.ok) throw new Error(body.error || "Request failed");
        answerBox.textContent = body.answer;
        answerBox.classList.remove("muted");
        answerBox.classList.remove("error-box");
      }} catch (error) {{
        answerBox.textContent = error.message || String(error);
        answerBox.classList.add("error-box");
      }} finally {{ askButton.disabled = false; }}
    }});
    titleInput.addEventListener("input", function () {{
      titleEdited = titleInput.value !== defaultTitle(currentLang());
    }});
    document.querySelectorAll("[data-lang-choice]").forEach(function (langButton) {{
      langButton.addEventListener("click", function () {{
        window.setTimeout(syncDefaultTitle, 0);
      }});
    }});
    syncDefaultTitle();
  }}());
</script>
</body>
</html>
"""


def options_from_payload(payload: dict[str, Any]) -> ConsoleOptions:
    raw_assets = payload.get("assets") if isinstance(payload.get("assets"), list) else []
    assets = normalize_portfolio_assets([item for item in raw_assets if isinstance(item, dict)])
    symbols = [item["symbol"] for item in assets] or parse_symbols(str(payload.get("symbols", "")))
    if not symbols:
        raise ValueError("Enter at least one symbol.")
    providers = parse_symbols(str(payload.get("providers") or ", ".join(DEFAULT_PROVIDERS)))
    return ConsoleOptions(
        symbols=symbols,
        title=str(payload.get("title") or "我的自选股每日分析报告"),
        timezone=str(payload.get("timezone") or "Asia/Shanghai"),
        language=str(payload.get("language") or "zh-CN"),
        providers=providers or list(DEFAULT_PROVIDERS),
        reports_dir=_relative_path(payload.get("reportsDir"), "reports"),
        history_path=_relative_path(payload.get("historyPath"), "data/history.jsonl"),
        site_dir=_relative_path(payload.get("siteDir"), "site"),
        include_news=bool(payload.get("includeNews", True)),
        use_ai=bool(payload.get("useAi", False)),
        build_dashboard=bool(payload.get("buildDashboard", True)),
        build_site=bool(payload.get("buildSite", True)),
        assets=assets,
        check_alerts=bool(payload.get("checkAlerts", False)),
    )


def run_console_analysis(options: ConsoleOptions, root: str | Path = ".") -> dict[str, Any]:
    root_path = Path(root).resolve()
    reports_dir = _resolve_under_root(root_path, options.reports_dir)
    history_path = _resolve_under_root(root_path, options.history_path)
    site_dir = _resolve_under_root(root_path, options.site_dir)
    config_text = custom_watchlist_config(
        options.symbols,
        title=options.title,
        timezone=options.timezone,
        language=options.language,
        providers=options.providers,
    )
    config_mapping = yaml.safe_load(config_text) or {}
    if options.assets:
        config_mapping["assets"] = options.assets
    config = load_config_from_mapping(config_mapping)
    config = replace(config, news=replace(config.news, enabled=options.include_news))
    config = replace(config, llm=replace(config.llm, enabled=options.use_ai))

    watchlist_path = _resolve_under_root(root_path, Path("data/console-watchlist.yaml"))
    watchlist_path.parent.mkdir(parents=True, exist_ok=True)
    watchlist_path.write_text(yaml.safe_dump(config_mapping, allow_unicode=True, sort_keys=False), encoding="utf-8")

    report = run_analysis(config, "web console")
    existing_history = load_history(history_path)
    report = attach_history(report, existing_history)
    paths = write_reports(report, reports_dir)
    append_history(history_path, report)

    alert_messages: list[str] = []
    if options.check_alerts:
        alert_path = _resolve_under_root(root_path, Path("data/alert-state.json"))
        events, next_state = evaluate_alerts(report, load_alert_state(alert_path), config.alerts)
        write_alert_state(alert_path, next_state)
        alert_messages = [event.message for event in events]

    dashboard_path = None
    if options.build_dashboard:
        dashboard_path = write_dashboard(load_history(history_path), reports_dir / "dashboard.html")

    site_result = None
    if options.build_site:
        site_result = build_site(reports_dir, site_dir, title=options.title)

    return {
        "symbols": [analysis.asset.symbol for analysis in report.analyses],
        "alerts": alert_messages,
        "links": {
            "html": _href(root_path, paths["html"]),
            "markdown": _href(root_path, paths["markdown"]),
            "json": _href(root_path, paths["json"]),
            "dashboard": _href(root_path, dashboard_path) if dashboard_path else None,
            "site": _href(root_path, site_result.index_path) if site_result else None,
            "watchlist": _href(root_path, watchlist_path),
        },
    }


class ConsoleHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, root: Path, **kwargs):
        self.root = root
        super().__init__(*args, directory=str(root), **kwargs)

    def do_GET(self) -> None:
        if self.path in {"/", "/console"}:
            self._send_html(render_console_html())
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path not in {"/api/analyze", "/api/portfolio/extract", "/api/ask"}:
            self.send_error(404)
            return
        try:
            payload = self._read_json()
            if self.path == "/api/analyze":
                result = run_console_analysis(options_from_payload(payload), self.root)
            elif self.path == "/api/portfolio/extract":
                result = _extract_portfolio_payload(payload)
            else:
                result = _answer_payload(payload, self.root)
            self._send_json(result)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=400)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length > 12 * 1024 * 1024:
            raise ValueError("Request is too large. Use an image under 8 MB.")
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object.")
        return payload

    def _send_html(self, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _send_json(self, body: dict[str, Any], status: int = 200) -> None:
        encoded = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def _bind_server(host: str, port: int, root: Path) -> ThreadingHTTPServer:
    handler = partial(ConsoleHandler, root=root)
    for candidate in range(port, port + 20):
        try:
            return ThreadingHTTPServer((host, candidate), handler)
        except OSError:
            continue
    raise OSError(f"No available port found from {port} to {port + 19}.")


def _relative_path(value: object, default: str) -> Path:
    path = Path(str(value or default))
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("Output paths must stay inside the project directory.")
    return path


def _resolve_under_root(root: Path, path: Path) -> Path:
    resolved = (root / path).resolve()
    if root != resolved and root not in resolved.parents:
        raise ValueError("Output paths must stay inside the project directory.")
    return resolved


def _href(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    return "/" + quote(path.resolve().relative_to(root).as_posix())


def _console_llm_settings() -> LLMSettings:
    return LLMSettings(
        enabled=True,
        base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        model=os.getenv("OPENAI_MODEL") or None,
        cache_dir="data/ai-cache",
        # Screenshot import needs a vision-capable model; when the main
        # provider is text-only (e.g. DeepSeek), point these at another one.
        vision_base_url=os.getenv("VISION_BASE_URL") or None,
        vision_model=os.getenv("VISION_MODEL") or None,
        vision_api_key_env="VISION_API_KEY" if os.getenv("VISION_API_KEY") else None,
    )


def _extract_portfolio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data_url = str(payload.get("image") or "")
    if not data_url.startswith("data:image/") or ";base64," not in data_url:
        raise ValueError("Upload a PNG, JPEG, or WebP portfolio screenshot.")
    header, encoded = data_url.split(",", 1)
    media_type = header[5:].split(";", 1)[0].lower()
    try:
        image = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("The uploaded image could not be decoded.") from exc
    if not image or len(image) > 8 * 1024 * 1024:
        raise ValueError("Use a non-empty image under 8 MB.")
    records = extract_portfolio_from_image(image, media_type, _console_llm_settings())
    # Fund apps rarely show codes; resolve them from the transcribed names and
    # keep unmatched funds as blank-symbol rows for the user to complete.
    records, unresolved = resolve_fund_records(records)
    assets = normalize_portfolio_assets(records) + unresolved
    if not assets:
        raise ValueError("No holdings were recognized. Try a clearer screenshot or enter symbols manually.")
    return {"assets": assets}


def _answer_payload(payload: dict[str, Any], root: Path) -> dict[str, Any]:
    raw_path = unquote(str(payload.get("reportPath") or "")).split("?", 1)[0].lstrip("/")
    path = _resolve_under_root(root, _relative_path(raw_path, ""))
    if path.suffix.lower() != ".json" or not path.exists():
        raise ValueError("Select a generated JSON report before asking a question.")
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        raise ValueError("The selected report is invalid.")
    answer = answer_report_question(
        report,
        str(payload.get("question") or ""),
        _console_llm_settings(),
        str(payload.get("language") or report.get("language") or "zh-CN"),
    )
    return {"answer": answer}
