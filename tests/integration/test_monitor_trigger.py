"""
市場監視 & 自律トリガー結合テスト
STEP 3: 監視リスト管理、イベント検知、トリアージ、自律調査トリガーの結合検証
"""

import pytest
from unittest.mock import patch, MagicMock

from src.contracts.watch_item import MarketEvent, WatchItem, WatchTriggers
from src.services.watch_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    run_monitoring_cycle,
)
from src.repositories.monitor_repository import (
    get_watch_item,
    list_market_events_with_triage,
    list_notifications,
)


def test_watchlist_crud():
    """監視リストの追加・取得・削除の検証"""
    item = add_to_watchlist(ticker="7203", price_change_pct=4.0)
    assert item.ticker == "7203.T"
    assert item.triggers.price_change_pct == 4.0

    fetched = get_watch_item("7203.T")
    assert fetched is not None
    assert fetched.ticker == "7203.T"

    watchlist = get_watchlist()
    assert any(w.ticker == "7203.T" for w in watchlist)

    deleted = remove_from_watchlist("7203.T")
    assert deleted is True
    assert get_watch_item("7203.T") is None


def test_monitor_cycle_and_autonomous_trigger_mocked():
    """監視サイクルと自律リサーチ自動トリガーの結合テスト（モック）"""
    # 監視銘柄を登録
    add_to_watchlist(ticker="7203.T", price_change_pct=3.0)

    mock_market_data = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "current_price": 3000.0,
        "daily_change_pct": -6.5,  # 閾値 ±3.0% を超過（急落イベント）
        "volume": 25000000
    }

    mock_research_result = {
        "status": "COMPLETED",
        "policy": MagicMock(strategy_id="policy_auto_123"),
        "outcome": MagicMock(verification_status="OK"),
        "responses": []
    }

    with patch("src.services.monitor_service.fetch_market_data", return_value=mock_market_data), \
         patch("src.services.watch_service.run_policy_workflow", return_value=mock_research_result):

        cycle_res = run_monitoring_cycle(auto_trigger_research=True)

        assert cycle_res["status"] == "SUCCESS"
        assert cycle_res["events_detected"] >= 1
        assert cycle_res["researches_triggered"] >= 1

        # DB確認 (イベントと通知が記録されていること)
        events = list_market_events_with_triage(limit=5)
        assert len(events) >= 1

        notifs = list_notifications(limit=5)
        assert len(notifs) >= 1

    # テスト後クリーンアップ
    remove_from_watchlist("7203.T")
