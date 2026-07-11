from __future__ import annotations

import html


def lang(en: str, zh: str) -> str:
    return (
        f'<span data-i18n-en>{html.escape(en)}</span>'
        f'<span data-i18n-zh>{html.escape(zh)}</span>'
    )


def language_boot_script(default_lang: str = "en") -> str:
    safe_default = "zh" if default_lang.startswith("zh") else "en"
    return f"""<script>
    (function () {{
      var stored = localStorage.getItem("amp-lang");
      var browserLang = (navigator.language || "").toLowerCase().indexOf("zh") === 0 ? "zh" : "{safe_default}";
      var lang = stored || browserLang;
      document.documentElement.dataset.lang = lang;
      document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
      document.documentElement.dataset.theme = localStorage.getItem("amp-theme") || "dark";
    }})();
  </script>"""


def language_toggle() -> str:
    return """
<div class="display-controls">
  <div class="theme-switch" aria-label="Theme">
    <button type="button" data-theme-choice="dark">DARK</button>
    <button type="button" data-theme-choice="light">LIGHT</button>
  </div>
  <div class="language-switch" aria-label="Language">
    <button type="button" data-lang-choice="en">EN</button>
    <button type="button" data-lang-choice="zh">中文</button>
  </div>
</div>
"""


def language_runtime_script() -> str:
    return """<script>
    (function () {
      function setLang(lang) {
        document.documentElement.dataset.lang = lang;
        document.documentElement.lang = lang === "zh" ? "zh-CN" : "en";
        localStorage.setItem("amp-lang", lang);
        document.querySelectorAll("[data-lang-choice]").forEach(function (button) {
          button.setAttribute("aria-pressed", button.dataset.langChoice === lang ? "true" : "false");
        });
      }
      document.querySelectorAll("[data-lang-choice]").forEach(function (button) {
        button.addEventListener("click", function () { setLang(button.dataset.langChoice); });
      });
      function setTheme(theme) {
        document.documentElement.dataset.theme = theme;
        localStorage.setItem("amp-theme", theme);
        document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
          button.setAttribute("aria-pressed", button.dataset.themeChoice === theme ? "true" : "false");
        });
      }
      document.querySelectorAll("[data-theme-choice]").forEach(function (button) {
        button.addEventListener("click", function () { setTheme(button.dataset.themeChoice); });
      });
      setLang(document.documentElement.dataset.lang || "en");
      setTheme(document.documentElement.dataset.theme || "dark");
    }());
  </script>"""


def ui_styles() -> str:
    return """
    :root {
      color-scheme: dark;
      --bg: #07100e;
      --canvas: #111a18;
      --canvas-soft: #0b1412;
      --canvas-raised: #16211e;
      --ink: #f3f7f5;
      --muted: #87958f;
      --line: #22312c;
      --line-strong: #385048;
      --brand: #31d283;
      --brand-strong: #63e6a0;
      --blue: #4aa3ff;
      --indigo: #4aa3ff;
      --amber: #f4bd45;
      --rose: #ff6b77;
      --green: #45db91;
      --red: #ff6269;
      --top: #050a09;
      --shadow: 0 16px 42px rgba(0, 0, 0, 0.24);
      --grid-line: rgba(70, 112, 96, 0.09);
    }
    html[data-theme="light"] {
      color-scheme: light;
      --bg: #f2f5f3;
      --canvas: #ffffff;
      --canvas-soft: #f7faf8;
      --canvas-raised: #eef5f1;
      --ink: #111916;
      --muted: #617069;
      --line: #d7e1db;
      --line-strong: #b5c8be;
      --brand: #0d9f63;
      --brand-strong: #087b4c;
      --blue: #2563eb;
      --indigo: #2563eb;
      --amber: #a96906;
      --rose: #be123c;
      --green: #087b4c;
      --red: #b42318;
      --top: #111916;
      --shadow: 0 14px 32px rgba(17, 25, 22, 0.08);
      --grid-line: rgba(21, 72, 52, 0.055);
    }
    html[data-lang="en"] [data-i18n-zh],
    html[data-lang="zh"] [data-i18n-en] {
      display: none !important;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background-color: var(--bg);
      background-image:
        linear-gradient(var(--grid-line) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
      background-size: 48px 48px;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
      text-rendering: geometricPrecision;
    }
    a { color: var(--brand-strong); text-decoration: none; }
    a:hover { text-decoration: underline; text-underline-offset: 3px; }
    main { width: min(1380px, calc(100% - 40px)); margin: 0 auto; padding: 18px 0 56px; }
    h1, h2, h3 { letter-spacing: 0; }
    h1 { margin: 0; font-size: 46px; line-height: 1.04; }
    h2 { margin: 30px 0 12px; font-size: 24px; line-height: 1.2; }
    h3 { margin: 0 0 10px; font-size: 15px; line-height: 1.3; }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      min-height: 48px;
      padding-bottom: 12px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--line);
      color: var(--muted);
    }
    .brand-mark {
      display: inline-flex;
      align-items: center;
      gap: 10px;
      font-weight: 760;
      color: var(--ink);
      letter-spacing: 0;
    }
    .brand-mark::before {
      content: "";
      width: 10px;
      height: 10px;
      border-radius: 2px;
      background: var(--brand);
      box-shadow: 12px 0 0 var(--amber), 24px 0 0 var(--blue);
    }
    .display-controls { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; justify-content: flex-end; }
    .theme-switch,
    .language-switch {
      display: inline-flex;
      gap: 3px;
      padding: 3px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--canvas-soft);
    }
    .theme-switch button,
    .language-switch button {
      min-width: 44px;
      min-height: 32px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: var(--muted);
      font: inherit;
      font-size: 11px;
      font-weight: 720;
      cursor: pointer;
    }
    html[data-theme="dark"] .theme-switch button[data-theme-choice="dark"],
    html[data-theme="light"] .theme-switch button[data-theme-choice="light"],
    html[data-lang="en"] .language-switch button[data-lang-choice="en"],
    html[data-lang="zh"] .language-switch button[data-lang-choice="zh"] {
      color: var(--top);
      background: var(--brand);
    }
    .hero {
      color: var(--ink);
      padding: 18px 0 24px;
      display: grid;
      grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.7fr);
      gap: 28px;
      align-items: center;
      border-bottom: 1px solid var(--line);
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 14px;
      color: var(--muted);
      font-size: 13px;
      font-weight: 760;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .eyebrow::before {
      content: "";
      width: 22px;
      height: 2px;
      border-radius: 2px;
      background: var(--brand);
    }
    .hero p {
      max-width: 760px;
      margin: 12px 0 0;
      color: var(--muted);
      font-size: 16px;
    }
    .hero-panel {
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      padding: 16px;
      background: var(--canvas-soft);
    }
    .hero-panel strong {
      display: block;
      font-size: 28px;
      line-height: 1;
      margin-top: 6px;
      color: var(--ink);
    }
    .muted { color: var(--muted); }
    .fineprint { font-size: 13px; color: var(--muted); }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }
    .wide-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 14px; }
    .panel,
    .card,
    .summary,
    .brief,
    table {
      background: var(--canvas);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
    }
    .panel,
    .card,
    .summary,
    .brief {
      padding: 16px;
      min-width: 0;
    }
    .section-note {
      margin: -8px 0 14px;
      color: var(--muted);
      max-width: 760px;
    }
    .kpi span,
    .summary span {
      display: block;
      font-size: 13px;
      font-weight: 700;
      color: var(--muted);
    }
    .kpi strong,
    .summary strong {
      display: block;
      font-size: 28px;
      line-height: 1.05;
      margin-top: 8px;
    }
    .metric {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 0;
      border-bottom: 1px solid var(--line);
    }
    .metric:last-child { border-bottom: 0; }
    .metric span { color: var(--muted); }
    .spark { width: 100%; height: 96px; margin-top: 10px; }
    .score-spark { width: 100%; height: 48px; margin-top: 8px; }
    table {
      width: 100%;
      border-collapse: separate;
      border-spacing: 0;
      overflow: hidden;
      box-shadow: var(--shadow);
    }
    th, td {
      text-align: left;
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    th {
      color: var(--muted);
      font-size: 12px;
      font-weight: 760;
      background: var(--canvas-soft);
    }
    tr:last-child td { border-bottom: 0; }
    .gain { color: var(--green); }
    .loss { color: var(--red); }
    .risk-high { color: var(--rose); font-weight: 760; }
    .risk-medium { color: var(--amber); font-weight: 760; }
    .risk-low { color: var(--green); font-weight: 760; }
    .pill {
      display: inline-flex;
      align-items: center;
      border: 1px solid var(--line-strong);
      border-radius: 6px;
      padding: 4px 9px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      white-space: nowrap;
    }
    .button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      border: 1px solid var(--brand);
      border-radius: 8px;
      padding: 8px 12px;
      color: var(--brand-strong);
      font-weight: 760;
    }
    .button:hover { background: #e9f6f2; text-decoration: none; }
    html[data-theme="dark"] .button:hover { background: rgba(49, 210, 131, 0.1); }
    .section-kicker {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }
    .section-kicker::before { content: ""; width: 7px; height: 7px; border-radius: 2px; background: var(--brand); }
    .status-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: var(--brand); box-shadow: 0 0 12px rgba(49, 210, 131, 0.55); }
    .mono { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; }
    .data-blue { color: var(--blue); }
    .data-amber { color: var(--amber); }
    .data-red { color: var(--red); }
    .brief { margin-top: 14px; }
    .brief > strong:first-child { display: block; margin-bottom: 8px; font-size: 15px; }
    .brief table { margin: 12px -16px -16px; width: calc(100% + 32px); border: 0; border-top: 1px solid var(--line); border-radius: 0 0 8px 8px; box-shadow: none; }
    ul { padding-left: 18px; }
    li + li { margin-top: 4px; }
    :focus-visible { outline: 3px solid rgba(15, 118, 110, 0.28); outline-offset: 2px; }
    @media (max-width: 760px) {
      main { width: min(100% - 24px, 1380px); padding-top: 12px; }
      h1 { font-size: 34px; }
      h2 { font-size: 21px; }
      .hero { grid-template-columns: 1fr; padding-bottom: 24px; }
      .topbar { align-items: flex-start; }
      .display-controls { gap: 5px; }
      .theme-switch button, .language-switch button { min-width: 40px; }
      .wide-grid { grid-template-columns: 1fr; }
      table { display: block; overflow-x: auto; }
      th, td { white-space: nowrap; }
    }
  """
