"""
ガバナンス & 人間フィードバック結合テスト
STEP 4: ジャーナル自動記録、自己反省実行、フィードバック受付、ガードレール更新の検証
"""

import pytest
from src.contracts.research_policy import ResearchPolicy, PolicyScope, PolicyLimits
from src.services.policy_service import propose_policy
from src.services.journal_service import record_policy_journal
from src.services.reflection_service import run_reflection_on_journal, get_reflections_history
from src.services.feedback_service import submit_human_feedback, get_active_guardrails
from src.repositories.governance_repository import (
    get_journal_by_strategy,
    list_journal_entries,
    list_human_feedbacks,
)


def test_journal_creation_and_reflection():
    """リサーチ方針策定時のジャーナル自動記録と自己反省の実行"""
    # 1. 方針策定（ジャーナルが自動記録される）
    policy = propose_policy("トヨタを分析して")
    assert policy is not None

    journal = get_journal_by_strategy(policy.strategy_id)
    assert journal is not None
    assert journal.strategy_id == policy.strategy_id
    assert journal.decision_type == "POLICY_CREATION"

    # 2. 自己反省の実行
    reflection = run_reflection_on_journal(journal.journal_id)
    assert reflection is not None
    assert reflection.journal_id == journal.journal_id
    assert reflection.accuracy_score >= 50

    # 3. 反省レポート一覧
    reflections = get_reflections_history(limit=5)
    assert len(reflections) >= 1


def test_human_feedback_and_guardrail_rule():
    """人間フィードバック登録とガードレールルールの自動有効化"""
    target_id = "policy_test_feedback_1"
    fb = submit_human_feedback(
        target_type="POLICY",
        target_id=target_id,
        rating=2,  # 低評価
        comments="同業比較において日産自動車も含めるべきだった",
        corrections=["自動車セクター比較時は日産・ホンダ・トヨタの3社セットを必須とすること"]
    )

    assert fb.rating == 2
    assert fb.target_id == target_id

    # ガードレールルールが生成・登録されていること
    rules = get_active_guardrails()
    assert any("日産" in r.rule_text for r in rules)

    feedbacks = list_human_feedbacks(limit=5)
    assert any(f["feedback_id"] == fb.feedback_id for f in feedbacks)
