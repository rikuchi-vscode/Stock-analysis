"""
Policy → STEP 0 結合テスト
STEP 2: 方針策定、アダプター変換、人間承認フロー、成果評価の検証
"""

import pytest
from unittest.mock import patch, MagicMock

from src.contracts.research_policy import ResearchPolicy, PolicyScope, PolicyLimits
from src.services.policy_service import (
    propose_policy,
    approve_policy,
    reject_policy,
    execute_policy,
    run_policy_workflow,
)
from src.repositories.policy_repository import get_research_policy
from src.state import AgentState


def test_policy_proposal_and_execution_mocked():
    """リサーチ方針策定から STEP 0 実行までの結合テスト（モック）"""
    mock_final_state: AgentState = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "sector": "自動車",
        "iteration_count": 0,
        "max_iterations": 2,
        "analysis_result": {
            "overall_score": 85,
            "investment_stance": "Buy",
            "executive_summary": "良好な業績",
            "core_investment_thesis": ["HEV好調"]
        },
        "risk_result": {
            "risk_level": "中",
            "primary_downside_risks": [],
            "bearish_counter_arguments": []
        },
        "verification_result": {"status": "OK"},
        "final_report": "# レポート",
        "report_path": "output/test.md",
        "analysis_id": 101,
        "logs": []
    }

    mock_app = MagicMock()
    mock_app.invoke.return_value = mock_final_state

    with patch("src.services.policy_service.create_stock_analysis_graph", return_value=mock_app):
        # 1. 提案 & 自動実行
        result = run_policy_workflow("トヨタを分析して")
        assert result["status"] == "COMPLETED"
        assert result["policy"] is not None
        assert result["outcome"] is not None
        assert result["outcome"].verification_status == "OK"

        # DB確認
        saved_policy = get_research_policy(result["policy"].strategy_id)
        assert saved_policy is not None
        assert saved_policy.status == "COMPLETED"


def test_policy_human_approval_flow():
    """人間承認が必要な方針の停止と承認実行フローのテスト"""
    # 4銘柄の比較方針（上限3銘柄を超えるため要承認）
    policy = ResearchPolicy(
        strategy_id="policy_appr_test_1",
        objective="大手自動車4社比較",
        mode="peer_comparison",
        scope=PolicyScope(
            primary_tickers=["7203.T"],
            peer_tickers=["7267.T", "7201.T", "7270.T"]
        ),
        analysis_depth="standard",
        limits=PolicyLimits(max_tickers=4, max_research_cycles=2, time_budget_minutes=20)
    )

    from src.agents.policy_guard_agent import evaluate_policy_guard
    from src.repositories.policy_repository import save_research_policy

    guarded, _ = evaluate_policy_guard(policy)
    save_research_policy(guarded)
    assert guarded.status == "WAITING_APPROVAL"

    # 1. 承認
    approved = approve_policy(guarded.strategy_id, approved_by="Owner")
    assert approved is not None
    assert approved.status == "APPROVED"
    assert not approved.approval_required

    # 2. 却下テスト
    policy_rej = ResearchPolicy(
        strategy_id="policy_rej_test_1",
        objective="却下テスト用方針",
        mode="single_stock",
        scope=PolicyScope(primary_tickers=["7203.T"], peer_tickers=[]),
        analysis_depth="deep"
    )
    save_research_policy(policy_rej)
    rejected = reject_policy(policy_rej.strategy_id, rejected_by="Owner", comment="予算超過のため却下")
    assert rejected is not None
    assert rejected.status == "REJECTED"
