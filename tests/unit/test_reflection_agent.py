"""
Reflection Agent 単体テスト
STEP 4: 初期仮説と実績の照合、自己反省・改善教訓導出テスト
"""

import pytest
from src.contracts.decision_journal import JournalEntry
from src.contracts.research_policy import PolicyOutcome
from src.agents.reflection_agent import perform_reflection


def test_perform_reflection_basic():
    """意思決定ジャーナルに対する基本的な自己反省レポート生成"""
    journal = JournalEntry(
        journal_id="jrnl_test_1",
        strategy_id="policy_test_1",
        decision_type="POLICY_CREATION",
        ticker="7203.T",
        hypothesis="トヨタ自動車の業績堅調とHEV需要継続を検証する",
        assumptions=["為替1ドル150円前後", "グローバル販売好調"],
        expected_outcome="総合評価80点以上、Buy推奨",
        risk_assessment=["急激な円高", "認証不正問題"]
    )

    outcome = PolicyOutcome(
        strategy_id="policy_test_1",
        analysis_run_ids=["101"],
        coverage={"coverage_rate": 1.0, "all_verified": True},
        verification_status="OK",
        outcome_summary="トヨタ自動車の分析が完了。総合評価82点、Strong Buy推奨。"
    )

    reflection = perform_reflection(
        journal=journal,
        actual_outcome_text=outcome.outcome_summary,
        outcome=outcome
    )

    assert reflection.journal_id == "jrnl_test_1"
    assert reflection.strategy_id == "policy_test_1"
    assert reflection.accuracy_score >= 70
    assert len(reflection.success_factors) > 0
    assert len(reflection.lessons_learned) > 0
