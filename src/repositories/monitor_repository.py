"""
監視 & イベントリポジトリ (Monitor Repository)
STEP 3: 監視銘柄・市場イベント・トリアージ結果・通知履歴のDB永続化
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.db import DB_PATH, init_db
from src.time_utils import get_jst_now_str
from src.contracts.watch_item import WatchItem, WatchTriggers, MarketEvent, TriageResult
from src.contracts.notification import NotificationMessage


# --- Watch Items ---

def save_watch_item(item: WatchItem) -> None:
    """監視対象銘柄の登録・更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    triggers_json = json.dumps(item.triggers.model_dump(), ensure_ascii=False)
    created_at = item.created_at or get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO watch_items (
            watch_id, ticker, company_name, triggers_json, interval_minutes, priority, active, last_checked_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        item.watch_id,
        item.ticker,
        item.company_name,
        triggers_json,
        item.interval_minutes,
        item.priority,
        1 if item.active else 0,
        item.last_checked_at,
        created_at
    ))

    conn.commit()
    conn.close()


def get_watch_item(ticker: str) -> Optional[WatchItem]:
    """特定銘柄の監視設定を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM watch_items WHERE ticker = ?", (ticker,))
    row = cursor.fetchone()
    conn.close()

    if row:
        triggers_dict = json.loads(row["triggers_json"]) if row["triggers_json"] else {}
        return WatchItem(
            watch_id=row["watch_id"],
            ticker=row["ticker"],
            company_name=row["company_name"],
            triggers=WatchTriggers(**triggers_dict),
            interval_minutes=row["interval_minutes"],
            priority=row["priority"],
            active=bool(row["active"]),
            last_checked_at=row["last_checked_at"],
            created_at=row["created_at"]
        )
    return None


def list_watch_items(active_only: bool = False) -> List[WatchItem]:
    """監視対象銘柄の一覧取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if active_only:
        cursor.execute("SELECT * FROM watch_items WHERE active = 1 ORDER BY created_at ASC")
    else:
        cursor.execute("SELECT * FROM watch_items ORDER BY created_at ASC")

    rows = cursor.fetchall()
    results = []
    for r in rows:
        triggers_dict = json.loads(r["triggers_json"]) if r["triggers_json"] else {}
        results.append(WatchItem(
            watch_id=r["watch_id"],
            ticker=r["ticker"],
            company_name=r["company_name"],
            triggers=WatchTriggers(**triggers_dict),
            interval_minutes=r["interval_minutes"],
            priority=r["priority"],
            active=bool(r["active"]),
            last_checked_at=r["last_checked_at"],
            created_at=r["created_at"]
        ))

    conn.close()
    return results


def delete_watch_item(ticker: str) -> bool:
    """監視対象銘柄の削除"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("DELETE FROM watch_items WHERE ticker = ?", (ticker,))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


def update_watch_checked_time(ticker: str) -> None:
    """最終チェック日時の更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now_str = get_jst_now_str("%Y-%m-%d %H:%M:%S")
    cursor.execute("UPDATE watch_items SET last_checked_at = ? WHERE ticker = ?", (now_str, ticker))
    conn.commit()
    conn.close()


# --- Market Events & Triages ---

def save_market_event(event: MarketEvent) -> None:
    """検知された市場イベントの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    payload_json = json.dumps(event.raw_payload, ensure_ascii=False)
    detected_at = event.detected_at or get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO market_events (
            event_id, ticker, company_name, event_type, severity, title, description, raw_payload, detected_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        event.event_id,
        event.ticker,
        event.company_name,
        event.event_type,
        event.severity,
        event.title,
        event.description,
        payload_json,
        detected_at,
    ))

    conn.commit()
    conn.close()


def save_event_triage(triage: TriageResult) -> None:
    """イベントトリアージ結果の保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = triage.created_at or get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO event_triages (
            triage_id, event_id, action, reason, suggested_mode, priority, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        triage.triage_id,
        triage.event_id,
        triage.action,
        triage.reason,
        triage.suggested_mode,
        triage.priority,
        created_at,
    ))

    conn.commit()
    conn.close()


def list_market_events_with_triage(limit: int = 20, unique_by_ticker: bool = True) -> List[Dict[str, Any]]:
    """市場イベントとトリアージ結果の一覧取得（unique_by_ticker=True で同一銘柄・同一イベントの重複を最新1件に集約）"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT e.*, t.action as triage_action, t.reason as triage_reason,
               t.suggested_mode, t.priority as triage_priority
        FROM market_events e
        LEFT JOIN event_triages t ON e.event_id = t.event_id
        ORDER BY e.detected_at DESC
        LIMIT ?
    """, (limit * 3 if unique_by_ticker else limit,))

    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()

    if unique_by_ticker:
        seen = set()
        unique_results = []
        for r in results:
            # (ticker, event_type, title) の組み合わせで重複判定
            key = (r.get("ticker"), r.get("event_type"), r.get("title"))
            if key not in seen:
                seen.add(key)
                unique_results.append(r)
                if len(unique_results) >= limit:
                    break
        return unique_results

    return results


# --- Notifications ---

def save_notification(notif: NotificationMessage) -> None:
    """通知メッセージの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    meta_json = json.dumps(notif.metadata, ensure_ascii=False)
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO notifications (
            notification_id, channel, severity, title, body, metadata_json, delivered, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        notif.notification_id,
        notif.channel,
        notif.severity,
        notif.title,
        notif.body,
        meta_json,
        1 if notif.delivered else 0,
        created_at
    ))

    conn.commit()
    conn.close()


def list_notifications(limit: int = 20) -> List[Dict[str, Any]]:
    """通知履歴の一覧取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results
