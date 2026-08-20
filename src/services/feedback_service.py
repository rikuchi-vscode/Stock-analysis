"""
Human Feedback & Guardrails Service モジュール
STEP 4: 人間評価の収集・改善指示の反映・ガードレールルールの動的蓄積と適用
"""

import uuid
from typing import Dict, Any, List, Optional

from src.contracts.decision_journal import HumanFeedback, GuardrailRule, ReflectionReport
from src.repositories.governance_repository import (
    save_human_feedback,
    list_human_feedbacks,
    save_guardrail_rule,
    list_active_guardrail_rules,
)


def submit_human_feedback(
    target_type: str,
    target_id: str,
    rating: int,
    comments: str = "",
    corrections: Optional[List[str]] = None
) -> HumanFeedback:
    """
    人間オーナーからのフィードバックを登録し、必要に応じて改善ガードレールルールを発行する。
    """
    feedback_id = f"fb_{uuid.uuid4().hex[:10]}"
    corrections_list = corrections or []

    fb = HumanFeedback(
        feedback_id=feedback_id,
        target_type=target_type,
        target_id=target_id,
        rating=rating,
        comments=comments,
        corrections=corrections_list
    )

    save_human_feedback(fb)

    # 評価が低い場合や具体的な指示がある場合、ガードレールルールを自動発行
    if rating <= 2 or corrections_list:
        for idx, corr in enumerate(corrections_list):
            rule_id = f"gr_fb_{uuid.uuid4().hex[:8]}"
            rule = GuardrailRule(
                rule_id=rule_id,
                category="FOCUS",
                rule_text=f"【人間指摘事項】{corr}",
                source="HUMAN_FEEDBACK",
                active=True
            )
            save_guardrail_rule(rule)

        if not corrections_list and comments:
            rule_id = f"gr_fb_{uuid.uuid4().hex[:8]}"
            rule = GuardrailRule(
                rule_id=rule_id,
                category="FOCUS",
                rule_text=f"【人間指摘事項 ({target_id})】{comments}",
                source="HUMAN_FEEDBACK",
                active=True
            )
            save_guardrail_rule(rule)

    return fb


def apply_reflection_guardrails(reflection: ReflectionReport) -> List[GuardrailRule]:
    """
    自己反省レポートで推奨された改善案を PROPOSED ステータスでDBに登録する (即時反映はしない)
    """
    created_rules: List[GuardrailRule] = []
    for g_text in reflection.recommended_guardrails:
        rule_id = f"gr_ref_{uuid.uuid4().hex[:8]}"
        rule = GuardrailRule(
            rule_id=rule_id,
            category="RISK" if "リスク" in g_text else "FOCUS",
            rule_text=g_text,
            source="REFLECTION",
            status="PROPOSED",
            proposed_by="Reflection Agent",
            active=False
        )
        save_guardrail_rule(rule)
        created_rules.append(rule)

    return created_rules


def approve_rule(rule_id: str, approved_by: str = "Human Owner") -> bool:
    """提案ルールを承認して ACTIVE にする"""
    from src.repositories.governance_repository import approve_guardrail_rule
    return approve_guardrail_rule(rule_id, approved_by=approved_by)


def reject_rule(rule_id: str, rejected_by: str = "Human Owner", reason: str = "") -> bool:
    """提案ルールを却下する"""
    from src.repositories.governance_repository import reject_guardrail_rule
    return reject_guardrail_rule(rule_id, rejected_by=rejected_by, reason=reason)


def get_active_guardrails() -> List[GuardrailRule]:
    """現在有効なガードレールルール一覧の取得 (ACTIVE のみ)"""
    return list_active_guardrail_rules()
