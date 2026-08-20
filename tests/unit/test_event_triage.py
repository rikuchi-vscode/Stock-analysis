"""
Event Triage Agent 単体テスト
STEP 3: 市場イベント重要度判定・アクション決定テスト
"""

import pytest
from src.contracts.watch_item import MarketEvent
from src.agents.event_triage_agent import triage_market_event


def test_triage_critical_price_spike():
    """株価急変 (CRITICAL) イベントは TRIGGER_RESEARCH と判定されること"""
    event = MarketEvent(
        event_id="evt_test_1",
        ticker="7203.T",
        company_name="トヨタ自動車",
        event_type="PRICE_SPIKE",
        severity="CRITICAL",
        title="トヨタ自動車 株価急落 (-8.5%)",
        description="直近株価が前日比 -8.5% と大幅下落",
        raw_payload={"change_pct": -8.5}
    )

    triage = triage_market_event(event)
    assert triage.event_id == "evt_test_1"
    assert triage.action == "TRIGGER_RESEARCH"
    assert triage.priority in ["urgent", "high"]


def test_triage_medium_news_alert():
    """中程度のニュースイベントは QUEUE_RESEARCH または NOTIFY_ONLY と判定されること"""
    event = MarketEvent(
        event_id="evt_test_2",
        ticker="6758.T",
        company_name="ソニーグループ",
        event_type="NEWS_ALERT",
        severity="MEDIUM",
        title="新製品発表に関する観測報道",
        description="新型センサーの量産計画に関するニュース",
        raw_payload={}
    )

    triage = triage_market_event(event)
    assert triage.event_id == "evt_test_2"
    assert triage.action in ["QUEUE_RESEARCH", "NOTIFY_ONLY"]


def test_triage_low_event():
    """軽微なイベントは NOTIFY_ONLY または IGNORE と判定されること"""
    event = MarketEvent(
        event_id="evt_test_3",
        ticker="9984.T",
        company_name="ソフトバンクグループ",
        event_type="NEWS_ALERT",
        severity="LOW",
        title="役員の定例異動",
        description="人事異動のお知らせ",
        raw_payload={}
    )

    triage = triage_market_event(event)
    assert triage.event_id == "evt_test_3"
    assert triage.action in ["NOTIFY_ONLY", "IGNORE"]
