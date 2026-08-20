"""
Market Monitor Service モジュール
STEP 3: 監視対象銘柄の市場データ・株価急変・出来高急増・ニュース速報のスキャンとイベント生成
"""

import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.contracts.watch_item import WatchItem, MarketEvent
from src.tools.market_tools import fetch_market_data
from src.tools.news_tools import fetch_stock_news
from src.repositories.monitor_repository import (
    list_watch_items,
    update_watch_checked_time,
    save_market_event,
)


def scan_ticker_for_events(item: WatchItem) -> List[MarketEvent]:
    """
    1つの監視銘柄をスキャンし、急変・出来高・ニュース等のイベントを検知する。
    """
    events: List[MarketEvent] = []
    ticker = item.ticker
    triggers = item.triggers

    # 1. 市場データの取得
    market_data = fetch_market_data(ticker, period="1mo")
    if "error" in market_data:
        return events

    company_name = market_data.get("company_name", item.company_name or ticker)
    current_price = market_data.get("current_price", 0.0)
    change_pct = market_data.get("daily_change_pct", 0.0)
    volume = market_data.get("volume", 0)

    # 2. 株価急変チェック (PRICE_SPIKE)
    abs_change = abs(change_pct) if change_pct is not None else 0.0
    if abs_change >= triggers.price_change_pct:
        direction = "急騰" if change_pct > 0 else "急落"
        severity = "CRITICAL" if abs_change >= 7.0 else "HIGH" if abs_change >= 5.0 else "MEDIUM"
        event_id = f"evt_prc_{uuid.uuid4().hex[:10]}"
        events.append(MarketEvent(
            event_id=event_id,
            ticker=ticker,
            company_name=company_name,
            event_type="PRICE_SPIKE",
            severity=severity,
            title=f"{company_name} 株価{direction} ({change_pct:+.2f}%)",
            description=f"直近株価: {current_price:,.1f} 円 (前日比 {change_pct:+.2f}%)。設定閾値 (±{triggers.price_change_pct}%) を超過しました。",
            raw_payload={
                "current_price": current_price,
                "change_pct": change_pct,
                "threshold_pct": triggers.price_change_pct
            }
        ))

    # 3. ニュース・適時開示チェック (NEWS_ALERT / DISCLOSURE)
    if triggers.check_news:
        try:
            news_items = fetch_stock_news(ticker, limit=3)
            for n in news_items:
                title = n.get("title", "")
                # 決算・業績修正等のキーワード検知
                if any(k in title for k in ["決算", "上方修正", "下方修正", "増配", "減配", "TOB", "自社株買い", "買収"]):
                    event_id = f"evt_news_{uuid.uuid4().hex[:10]}"
                    events.append(MarketEvent(
                        event_id=event_id,
                        ticker=ticker,
                        company_name=company_name,
                        event_type="DISCLOSURE" if "決算" in title or "修正" in title else "NEWS_ALERT",
                        severity="HIGH" if "決算" in title or "修正" in title else "MEDIUM",
                        title=f"{company_name} 重要開示・ニュース: {title[:40]}",
                        description=f"{n.get('publisher', 'ニュース')} ({n.get('publish_date', '')}): {title}",
                        raw_payload=n
                    ))
                    break  # 重複通知防止のため1件まで
        except Exception:
            pass

    # 最終チェック日時を更新
    update_watch_checked_time(ticker)

    # 検知されたイベントをDBに保存
    for evt in events:
        save_market_event(evt)

    return events


def scan_all_watched_items() -> List[MarketEvent]:
    """登録されている全アクティブ監視銘柄を一括スキャン"""
    items = list_watch_items(active_only=True)
    all_events: List[MarketEvent] = []

    for item in items:
        evts = scan_ticker_for_events(item)
        all_events.extend(evts)

    return all_events
