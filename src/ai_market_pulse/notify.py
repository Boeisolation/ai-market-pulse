from __future__ import annotations

import ipaddress
import json
import os
import smtplib
import socket
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


def _send_target(
    target: NotificationTarget,
    message: str,
    report: DailyReport,
    html_path: Path | None,
) -> None:
    kind = target.type.lower()
    settings = target.settings
    if kind == "telegram":
        token = resolve_setting(settings, "token", "token_env")
        chat_id = resolve_setting(settings, "chat_id", "chat_id_env")
        if not token or not chat_id:
            raise ValueError("telegram requires token/token_env and chat_id/chat_id_env")
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        _post_json(url, {"chat_id": chat_id, "text": message[:3900], "disable_web_page_preview": True})
    elif kind in {"webhook", "slack", "discord"}:
        url = resolve_setting(settings, "url", "url_env")
        if not url:
            raise ValueError(f"{kind} requires url/url_env")
        _assert_safe_url(url)
        payload = {"content": message[:1900]} if kind == "discord" else {"text": message[:3900]}
        _post_json(url, payload)
    elif kind == "feishu":
        url = resolve_setting(settings, "url", "url_env")
        if not url:
            raise ValueError("feishu requires url/url_env")
        _assert_safe_url(url)
        _post_json(url, {"msg_type": "text", "content": {"text": message[:3900]}})
    elif kind == "wecom":
        url = resolve_setting(settings, "url", "url_env")
        if not url:
            raise ValueError("wecom requires url/url_env")
        _assert_safe_url(url)
        _post_json(url, {"msgtype": "text", "text": {"content": message[:3900]}})
    elif kind == "email":
        _send_email(settings, render_markdown(report), html_path)
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


def _assert_safe_url(url: str) -> None:
    # Resolves and checks the hostname once at call time, immediately before
    # connecting. A sophisticated attacker controlling DNS for an
    # already-configured webhook host could in principle rebind the name to an
    # unsafe address between this check and the connection (TOCTOU); fully
    # closing that gap would require pinning the validated IP at the
    # connection layer, which this stdlib-only client does not do. The
    # practical, easily-reachable bypass — a validated URL redirecting to an
    # unsafe address — is closed separately by _NoRedirectHandler below.
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https":
        raise ValueError(f"Unsafe notification URL scheme: {parsed.scheme!r}")
    if not parsed.hostname:
        raise ValueError("Notification URL is missing a hostname")
    resolved_ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
    # `is_global` is the complete "definitely publicly routable" check — unlike
    # enumerating is_private/is_loopback/is_link_local/is_reserved, it also
    # correctly rejects ranges like 100.64.0.0/10 (carrier-grade NAT) that
    # is_private leaves unflagged. Multicast addresses report is_global=True
    # in Python's ipaddress module despite not being valid unicast targets,
    # so they're rejected separately.
    if not resolved_ip.is_global or resolved_ip.is_multicast:
        raise ValueError(f"Unsafe notification URL host resolves to {resolved_ip}")


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # A validated public URL could still redirect to an internal/loopback/
        # metadata address; refusing to follow closes that _assert_safe_url bypass.
        return None


def _urlopen(request: urllib.request.Request, timeout: int):
    opener = urllib.request.build_opener(_NoRedirectHandler())
    return opener.open(request, timeout=timeout)


def _post_json(url: str, payload: dict) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": "ai-market-pulse/0.1"},
        method="POST",
    )
    with _urlopen(request, timeout=20) as response:
        if response.status >= 400:
            raise RuntimeError(f"HTTP {response.status}")


def _send_email(settings: dict, markdown: str, html_path: Path | None) -> None:
    host = resolve_setting(settings, "smtp_host", "smtp_host_env")
    port = int(resolve_setting(settings, "smtp_port", "smtp_port_env") or "465")
    username = resolve_setting(settings, "username", "username_env")
    password = resolve_setting(settings, "password", "password_env")
    sender = resolve_setting(settings, "sender", "sender_env") or username
    recipients = resolve_setting(settings, "to", "to_env")
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


def resolve_setting(settings: dict, literal_key: str, env_key: str) -> str | None:
    literal = settings.get(literal_key)
    if literal:
        return str(literal)
    env_name = settings.get(env_key)
    if env_name:
        return os.getenv(str(env_name))
    return None
