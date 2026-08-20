"""
Notification Service モジュール
STEP 3: アラート・トリガー・分析完了通知の配信および永続化
"""

import uuid
from typing import Dict, Any, Optional, List
from rich.console import Console
from rich.panel import Panel

from src.contracts.notification import NotificationMessage
from src.repositories.monitor_repository import save_notification, list_notifications

console = Console(force_terminal=True, legacy_windows=False)


def send_notification(
    title: str,
    body: str,
    severity: str = "INFO",
    channel: str = "CONSOLE",
    metadata: Optional[Dict[str, Any]] = None
) -> NotificationMessage:
    """
    通知を作成し、コンソール出力およびデータベースに永続化する。
    """
    notif_id = f"notif_{uuid.uuid4().hex[:10]}"
    norm_severity = severity.upper()
    if norm_severity not in ["INFO", "WARNING", "ALERT", "CRITICAL", "HIGH", "MEDIUM", "LOW"]:
        norm_severity = "INFO"

    message = NotificationMessage(
        notification_id=notif_id,
        channel=channel,
        severity=norm_severity,
        title=title,
        body=body,
        metadata=metadata or {},
        delivered=True
    )

    # 1. DB永続化
    save_notification(message)

    # 2. コンソール出力 (Windows CP932 等のエンコード例外を防ぐ安全ガード付き)
    try:
        color = "red" if norm_severity in ["CRITICAL", "ALERT", "HIGH"] else "yellow" if norm_severity in ["WARNING", "MEDIUM"] else "cyan"
        icon = "🚨" if norm_severity in ["CRITICAL", "ALERT", "HIGH"] else "⚠️" if norm_severity in ["WARNING", "MEDIUM"] else "📢"

        console.print(Panel(
            f"[bold]{message.body}[/bold]",
            title=f"{icon} [{color}][{norm_severity}] {message.title}[/{color}]",
            border_style=color
        ))
    except Exception:
        try:
            print(f"[{norm_severity}] {message.title}: {message.body}")
        except Exception:
            pass

    return message


def notify_market_alert(ticker: str, title: str, description: str, severity: str = "WARNING") -> NotificationMessage:
    """市場急変アラート通知"""
    return send_notification(
        title=f"市場アラート [{ticker}] - {title}",
        body=description,
        severity=severity,
        metadata={"ticker": ticker, "type": "market_alert"}
    )


def notify_research_triggered(ticker: str, reason: str, strategy_id: Optional[str] = None) -> NotificationMessage:
    """自律調査タスク起動通知"""
    return send_notification(
        title=f"自律リサーチ起動 [{ticker}]",
        body=f"トリガー理由: {reason}\n方針ID: {strategy_id or 'N/A'}",
        severity="INFO",
        metadata={"ticker": ticker, "strategy_id": strategy_id, "type": "research_triggered"}
    )
