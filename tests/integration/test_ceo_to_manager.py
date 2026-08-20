"""
CEO → Manager 結合テスト
"""

import os
import pytest
from unittest.mock import patch, MagicMock

from src.orchestration.ceo_graph import run_ceo_workflow
from src.repositories.ceo_repository import get_ceo_run, get_ceo_history
from src.contracts.ceo_request import CEOState
from src.state import AgentState


def test_ceo_workflow_integration_mocked():
    """CEOワークフローの結合テスト（STEP 0のグラフをモック化して状態遷移とDB保存を検証）"""
    mock_final_state: AgentState = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "sector": "自動車・輸送機",
        "iteration_count": 0,
        "max_iterations": 2,
        "plan": {"tasks": ["市場調査", "財務調査"]},
        "market_data": {"current_price": 3100.0},
        "financial_data": {"market_cap": "50兆円"},
        "news_data": {"analysis": {"sentiment": "やや強気"}},
        "analysis_result": {
            "overall_score": 82,
            "investment_stance": "押し目買い",
            "executive_summary": "ハイブリッド車の好調と堅実な業績。",
            "core_investment_thesis": ["グローバル販売好調"]
        },
        "risk_result": {
            "risk_level": "中",
            "primary_downside_risks": [
                {"category": "為替", "risk_factor": "円高", "impact": "中", "trigger_event": "利上げ"}
            ],
            "bearish_counter_arguments": ["競争激化"]
        },
        "verification_result": {
            "status": "OK",
            "completeness_score": 90,
            "consistency_score": 90,
            "missing_points": []
        },
        "final_report": "# トヨタ自動車 分析レポート",
        "report_path": "output/Report_7203_T_test.md",
        "analysis_id": 999,
        "logs": ["[STEP 0] 分析完了"]
    }

    mock_app = MagicMock()
    mock_app.invoke.return_value = mock_final_state

    with patch("src.orchestration.ceo_graph.create_stock_analysis_graph", return_value=mock_app):
        ceo_state = run_ceo_workflow(
            user_request="7203を中期視点で分析して",
            max_iterations=1
        )

        assert ceo_state.status == "REPORTED"
        assert ceo_state.ticker == "7203.T"
        assert ceo_state.verification_status == "OK"
        assert ceo_state.ceo_summary is not None
        assert ceo_state.ceo_summary.headline != ""
        assert ceo_state.analysis_run_id == "999"

        # DB確認
        run_record = get_ceo_run(ceo_state.run_id)
        assert run_record is not None
        assert run_record["status"] == "REPORTED"
        assert run_record["verification_status"] == "OK"
        assert run_record["ticker"] == "7203.T"
