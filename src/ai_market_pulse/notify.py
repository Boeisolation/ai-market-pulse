from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.parse
import urllib.request
from email.message import EmailMessage
from pathlib import Path

from .config import NotificationTarget
from .models import DailyReport
from .reporting import render_markdown


def send_notifications(
    report: DailyReport,
    targets: list[NotificationTarget],
    html_path: Path | None = None,
    report_url: str | None = None,
) -> list[str]:
    results: list[str] = []
    message = _compact_message(report, report_url)
    for target in targets:
        if not target.enabled:
            continue
        try:
            _send_target(target, message, report, html_path)
            results.append(f"{target.type}:{target.name or 'default'} sent")
        except Exception as exc:
            results.append(f"{target.type}:{target.name or 'default'} failed: {exc}")
    return results


def send_text_notifications(message: str, targets: list[NotificationTarget]) -> list[str]:
    results: list[str] = []
    for target in targets:
        if not target.enabled:
            continue
        try:
            _send_target(target, message, None, None)
            results.append(f"{target.type}:{target.name or 'default'} sent")
        except Exception as exc:
            results.append(f"{target.type}:{target.name or 'default'} failed: {exc}")
    return results


def _send_target(
    target: NotificationTarget,
    message: str,
    report: DailyReport | None,
    html_path: Path | None,
) -> None:
    kind = target.type.lower()
    settings = target.settings
    if kind == "telegram":
        token = _setting(settings, "token", "token_env")
        chat_id = _setting(settings, "chat_id", "chat_id_env")
        if not token or not chat_id:
            raise ValueError("telegram requires token/token_env and chat_id/chat_id_env")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        _post_json(url, {"chat_id": chat_id, "text": message[:3900], "disable_web_page_preview": True})
    elif kind in {"webhook", "slack", "discord"}:
        url = _setting(settings, "url", "url_env")
        if not url:
            raise ValueError(f"{kind} requires url/url_env")
        payload = {"content": message[:1900]} if kind == "discord" else {"text": message[:3900]}
        _post_json(url, payload)
    elif kind == "feishu":
        url = _setting(settings, "url", "url_env")
        if not url:
            raise ValueError("feishu requires url/url_env")
        _post_json(url, {"msg_type": "text", "content": {"text": message[:3900]}})
    elif kind == "wecom":
        url = _setting(settings, "url", "url_env")
        if not url:
            raise ValueError("wecom requires url/url_env")
        _post_json(url, {"msgtype": "text", "text": {"content": message[:3900]}})
    elif kind == "email":
        markdown = render_markdown(report) if report else message
        _send_email(settings, markdown, html_path)
    else:
        raise ValueError(f"Unsupported notification type: {kind}")


def _compact_message(report: DailyReport, report_url: str | None = None) -> str:
    lines = [
        report.title,
        report.generated_at.strftime("%Y-%m-%d %H:%M:%S %Z"),
        report.market_brief,
        "",
    ]
    if report.portfolio_ai_summary:
        lines.extend(["AI portfolio brief:", report.portfolio_ai_summary[:900], ""])
    if report.portfolio:
        for summary in report.portfolio:
            lines.append(
                f"{summary.currency} portfolio: value {summary.market_value:,.2f}, "
                f"day P/L {_signed(summary.day_pnl)}, unrealized {_signed(summary.unrealized_pnl)}"
            )
        lines.append("")
    for item in report.analyses[:12]:
        lines.append(
            f"{item.asset.symbol} {item.snapshot.name}: "
            f"score {item.signal.score}/100, {item.signal.stance}, risk {item.signal.risk_level}"
        )
    # Only include a link when it is a public URL. Never leak a local filesystem path,
    # which is meaningless to notification recipients.
    if report_url and str(report_url).startswith("http"):
        lines.extend(["", f"Report: {report_url}"])
    lines.extend(["", "Research automation only. Not financial advice."])
    return "\n".join(lines)


def _signed(value: float | int | None) -> str:
    if value is None:
        return "n/a"
    sign = "+" if value > 0 else ""
    return f"{sign}{float(value):,.2f}"


def _post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "ai-market-pulse/0.1"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")


def _send_email(settings: dict, markdown: str, html_path: Path | None) -> None:
    host = _setting(settings, "smtp_host", "smtp_host_env")
    port = int(_setting(settings, "smtp_port", "smtp_port_env") or "465")
    username = _setting(settings, "username", "username_env")
    password = _setting(settings, "password", "password_env")
    sender = _setting(settings, "sender", "sender_env") or username
    recipients = _setting(settings, "to", "to_env")
    if not host or not sender or not recipients:
        raise ValueError("email requires smtp_host, sender, and to")

    message = EmailMessage()
    message["Subject"] = settings.get("subject", "AI Market Pulse")
    message["From"] = sender
    message["To"] = recipients
    message.set_content(markdown)
    if html_path and html_path.exists():
        message.add_attachment(
            html_path.read_text(encoding="utf-8"),
            subtype="html",
            filename=html_path.name,
        )

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        if username and password:
            server.login(username, password)
        server.send_message(message)


def _setting(settings: dict, literal_key: str, env_key: str) -> str | None:
    literal = settings.get(literal_key)
    if literal:
        return str(literal)
    env_name = settings.get(env_key)
    if env_name:
        return os.getenv(str(env_name))
    return None
