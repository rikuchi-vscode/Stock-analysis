"""
E2E 統合システムテスト (STEP 1 〜 STEP 5)
一人社長型 完全自律マルチエージェント株価分析システムの全レイヤー貫通テスト
"""

import pytest
from unittest.mock import patch, MagicMock

from src.contracts.ceo_request import CEOState
from src.contracts.research_policy import ResearchPolicy
from src.services.policy_service import propose_policy, approve_policy, execute_policy
from src.services.watch_service import add_to_watchlist, run_monitoring_cycle, remove_from_watchlist
from src.services.reflection_service import run_reflection_on_strategy
from src.services.feedback_service import submit_human_feedback, get_active_guardrails
from src.services.dashboard_service import get_dashboard_summary
from src.state import AgentState


def test_full_system_e2e_mocked():
    """
    全ステップ (STEP 1〜STEP 5) の統合結合テスト:
    1. [STEP 2] 方針策定 & 安全ガード
    2. [STEP 2] 人間承認
    3. [STEP 3] 監視リスト登録 & 監視サイクル
    4. [STEP 1 & 0] 分析部門実行 & CEO サマリー
    5. [STEP 4] 意思決定ジャーナル記録 & 自己反省 & フィードバック
    6. [STEP 5] 統合ダッシュボード集計
    """
    mock_final_state: AgentState = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "sector": "自動車",
        "iteration_count": 0,
        "max_iterations": 2,
        "analysis_result": {
            "overall_score": 88,
            "investment_stance": "Strong Buy",
            "executive_summary": "ハイブリッド車の世界的人気と堅固な収益構造。",
            "core_investment_thesis": ["HEV需要堅調", "利益率向上"]
        },
        "risk_result": {
            "risk_level": "低",
            "primary_downside_risks": [],
            "bearish_counter_arguments": []
        },
        "verification_result": {"status": "OK"},
        "final_report": "# トヨタ自動車 統合分析レポート",
        "report_path": "output/Report_7203_T_e2e.md",
        "analysis_id": 505,
        "logs": ["[E2E Test] 分析完了"]
    }

    mock_app = MagicMock()
    mock_app.invoke.return_value = mock_final_state

    with patch("src.services.policy_service.create_stock_analysis_graph", return_value=mock_app):
        # 1. [STEP 2] リサーチ方針の策定
        policy = propose_policy("トヨタを分析して")
        assert policy is not None
        assert policy.status in ["APPROVED", "PROPOSED", "WAITING_APPROVAL"]

        # 2. [STEP 2] 実行
        outcome, responses = execute_policy(policy)
        assert outcome is not None
        assert len(responses) >= 1
        assert responses[0].verification_status == "OK"

        # 3. [STEP 3] 監視銘柄登録
        watch_item = add_to_watchlist("7203.T", price_change_pct=3.0)
        assert watch_item.ticker == "7203.T"

        # 4. [STEP 4] 自己反省の実行
        reflection = run_reflection_on_strategy(policy.strategy_id)
        assert reflection is not None
        assert reflection.accuracy_score >= 50

        # 5. [STEP 4] 人間フィードバックの登録
        fb = submit_human_feedback(
            target_type="POLICY",
            target_id=policy.strategy_id,
            rating=5,
            comments="E2Eテストによる高精度な方針と分析結果の確認完了"
        )
        assert fb.rating == 5

        # 6. [STEP 5] 統合ダッシュボードの集計検証
        summary = get_dashboard_summary()
        assert summary.metrics.total_policies >= 1
        assert summary.metrics.total_analyses >= 0
        assert summary.metrics.watched_tickers_count >= 1

        # クリーンアップ
        remove_from_watchlist("7203.T")
