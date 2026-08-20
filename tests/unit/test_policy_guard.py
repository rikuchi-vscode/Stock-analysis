"""
Policy Guard Agent 単体テスト
STEP 2: 安全制約、リソース上限、承認要否判定のテスト
"""

import pytest
from src.contracts.research_policy import ResearchPolicy, PolicyScope, PolicyLimits
from src.agents.policy_guard_agent import evaluate_policy_guard


def test_guard_auto_approved_single_stock():
    """通常の単一銘柄・標準深度の方針は自動承認されること"""
    policy = ResearchPolicy(
        strategy_id="policy_test_1",
        objective="7203.Tの分析",
        mode="single_stock",
        scope=PolicyScope(primary_tickers=["7203.T"], peer_tickers=[]),
        analysis_depth="standard",
        limits=PolicyLimits(max_tickers=1, max_research_cycles=2, time_budget_minutes=15)
    )

    guarded, decisions = evaluate_policy_guard(policy)
    assert not guarded.approval_required
    assert guarded.status == "APPROVED"
    assert any(d.decision_type == "AUTO_APPROVED" for d in decisions)


def test_guard_requires_approval_for_many_tickers():
    """銘柄数が上限(3銘柄)を超える場合は人間承認が必要になること"""
    policy = ResearchPolicy(
        strategy_id="policy_test_2",
        objective="自動車セクター4社比較",
        mode="peer_comparison",
        scope=PolicyScope(
            primary_tickers=["7203.T"],
            peer_tickers=["7267.T", "7201.T", "7270.T"]  # 計4銘柄
        ),
        analysis_depth="standard",
        limits=PolicyLimits(max_tickers=4, max_research_cycles=2, time_budget_minutes=20)
    )

    guarded, decisions = evaluate_policy_guard(policy)
    assert guarded.approval_required
    assert guarded.status == "WAITING_APPROVAL"
    assert "上限" in guarded.approval_reason
    assert any(d.decision_type == "APPROVAL_REQUIRED" for d in decisions)


def test_guard_requires_approval_for_deep_analysis():
    """deep (深掘り) 分析が指定された場合は承認が必要になること"""
    policy = ResearchPolicy(
        strategy_id="policy_test_3",
        objective="7203.Tの深掘りリスク分析",
        mode="deep_dive_risk",
        scope=PolicyScope(primary_tickers=["7203.T"], peer_tickers=[]),
        analysis_depth="deep",
        limits=PolicyLimits(max_tickers=1, max_research_cycles=2, time_budget_minutes=15)
    )

    guarded, decisions = evaluate_policy_guard(policy)
    assert guarded.approval_required
    assert guarded.status == "WAITING_APPROVAL"
    assert "深掘り分析" in guarded.approval_reason


def test_guard_rejects_empty_tickers():
    """銘柄が1つも指定されていない場合は拒絶されること"""
    policy = ResearchPolicy(
        strategy_id="policy_test_4",
        objective="空の方針",
        mode="single_stock",
        scope=PolicyScope(primary_tickers=[], peer_tickers=[]),
        analysis_depth="standard"
    )

    guarded, decisions = evaluate_policy_guard(policy)
    assert guarded.status == "FAILED"
    assert any(d.decision_type == "GUARD_REJECTED" for d in decisions)
