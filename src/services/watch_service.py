"""
Watch Service モジュール
STEP 3: 監視リストの管理および自律監視サイクルの実行（スキャン → トリアージ → リサーチ自動起動）
"""

import uuid
from typing import Dict, Any, List, Optional

from src.contracts.watch_item import WatchItem, WatchTriggers, MarketEvent, TriageResult
from src.tools.market_tools import normalize_ticker
from src.agents.event_triage_agent import triage_market_event
from src.services.monitor_service import scan_ticker_for_events, scan_all_watched_items
from src.services.notification_service import notify_market_alert, notify_research_triggered
from src.services.policy_service import run_policy_workflow
from src.repositories.monitor_repository import (
    save_watch_item,
    get_watch_item,
    list_watch_items,
    delete_watch_item,
    save_event_triage,
)


def add_to_watchlist(
    ticker: str,
    company_name: Optional[str] = None,
    price_change_pct: float = 3.0,
    volume_spike_ratio: float = 2.0,
    check_news: bool = True,
    interval_minutes: int = 60,
    priority: str = "medium"
) -> WatchItem:
    """監視対象銘柄を追加または更新"""
    norm_ticker = normalize_ticker(ticker)
    watch_id = f"watch_{norm_ticker.replace('.', '_')}"

    item = WatchItem(
        watch_id=watch_id,
        ticker=norm_ticker,
        company_name=company_name,
        triggers=WatchTriggers(
            price_change_pct=price_change_pct,
            volume_spike_ratio=volume_spike_ratio,
            check_news=check_news
        ),
        interval_minutes=interval_minutes,
        priority=priority,
        active=True
    )

    save_watch_item(item)
    return item


def remove_from_watchlist(ticker: str) -> bool:
    """監視対象から銘柄を削除"""
    norm_ticker = normalize_ticker(ticker)
    return delete_watch_item(norm_ticker)


def get_watchlist(active_only: bool = False) -> List[WatchItem]:
    """監視対象一覧を取得"""
    return list_watch_items(active_only=active_only)


def run_monitoring_cycle(auto_trigger_research: bool = True) -> Dict[str, Any]:
    """
    全監視銘柄の監視サイクルを1巡実行する。
    1. 市場・開示・ニュースのスキャン (MarketEvent 検知)
    2. Event Triage Agent による重要度判定・アクション決定
    3. TRIGGER_RESEARCH の場合は自律リサーチを自動起動
    4. 結果の通知・永続化
    """
    watched_items = list_watch_items(active_only=True)
    if not watched_items:
        return {
            "status": "NO_WATCH_ITEMS",
            "message": "監視対象の銘柄が登録されていません。(--watch-add で追加してください)",
            "events_detected": 0,
            "researches_triggered": 0,
            "events": []
        }

    detected_events: List[MarketEvent] = []
    triages: List[TriageResult] = []
    triggered_researches: List[Dict[str, Any]] = []

    # 1. 全監視銘柄のスキャン
    for item in watched_items:
        evts = scan_ticker_for_events(item)
        detected_events.extend(evts)

    # 2. イベントごとのトリアージ判定
    for evt in detected_events:
        triage = triage_market_event(evt)
        save_event_triage(triage)
        triages.append(triage)

        # 3. アクションの実行
        if triage.action == "TRIGGER_RESEARCH" and auto_trigger_research:
            notify_market_alert(
                ticker=evt.ticker,
                title=f"自律リサーチ起動: {evt.title}",
                description=f"トリアージ理由: {triage.reason}",
                severity=evt.severity
            )

            # 自律リサーチワークフローの自動起動
            research_query = f"{evt.ticker} の急変要因（{evt.title}）に関する自律調査"
            research_result = run_policy_workflow(research_query)
            triggered_researches.append({
                "ticker": evt.ticker,
                "event": evt,
                "triage": triage,
                "result": research_result
            })

            notify_research_triggered(
                ticker=evt.ticker,
                reason=triage.reason,
                strategy_id=research_result.get("policy", {}).strategy_id if hasattr(research_result.get("policy"), "strategy_id") else None
            )

        elif triage.action in ["QUEUE_RESEARCH", "NOTIFY_ONLY"]:
            notify_market_alert(
                ticker=evt.ticker,
                title=evt.title,
                description=f"トリアージ結果 ({triage.action}): {triage.reason}",
                severity=evt.severity
            )

    return {
        "status": "SUCCESS",
        "message": f"監視サイクル完了: {len(watched_items)}銘柄スキャン済み、{len(detected_events)}件のイベント検知、{len(triggered_researches)}件の自律リサーチ起動",
        "events_detected": len(detected_events),
        "researches_triggered": len(triggered_researches),
        "events": detected_events,
        "triages": triages,
        "triggered_researches": triggered_researches
    }
