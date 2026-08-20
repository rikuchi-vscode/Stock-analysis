"""
Reflection Service モジュール
STEP 4: 意思決定ジャーナルに対する自己反省サイクルの実行と教訓の蓄積
"""

from typing import Optional, List, Dict, Any

from src.contracts.decision_journal import ReflectionReport, JournalEntry
from src.agents.reflection_agent import perform_reflection
from src.services.feedback_service import apply_reflection_guardrails
from src.repositories.governance_repository import (
    get_journal_entry,
    get_journal_by_strategy,
    save_reflection,
    list_reflections,
)
from src.repositories.policy_repository import get_research_policy


def run_reflection_on_journal(journal_id: str) -> Optional[ReflectionReport]:
    """
    指定されたジャーナルIDに対して自己反省を実行する。
    """
    journal = get_journal_entry(journal_id)
    if not journal:
        return None

    # 方針情報の取得
    policy = get_research_policy(journal.strategy_id) if journal.strategy_id else None
    actual_summary = f"方針ステータス: {policy.status if policy else '完了'}"

    reflection = perform_reflection(
        journal=journal,
        actual_outcome_text=actual_summary
    )

    save_reflection(reflection)
    apply_reflection_guardrails(reflection)

    return reflection


def run_reflection_on_snapshot(analysis_run_id: str) -> Optional[ReflectionReport]:
    """
    固定された判断スナップショットと客観的事実評価データに基づいて自己反省を実行する。
    """
    from src.repositories.governance_repository import get_decision_snapshot, get_evaluation_fact_by_run_id
    from src.services.post_evaluation_service import evaluate_single_schedule
    from src.contracts.decision_journal import EvaluationSchedule

    snapshot = get_decision_snapshot(analysis_run_id)
    if not snapshot:
        return None

    # 事実評価データの取得（無ければオンデマンドで計算）
    fact = get_evaluation_fact_by_run_id(analysis_run_id)
    if not fact:
        temp_sched = EvaluationSchedule(
            schedule_id=f"sched_{analysis_run_id}_ondemand",
            analysis_run_id=analysis_run_id,
            ticker=snapshot.ticker,
            evaluation_type="MANUAL",
            target_date=snapshot.as_of_date,
            status="PENDING"
        )
        fact = evaluate_single_schedule(temp_sched)

    # 客観的事実のサマリーテキスト
    actual_summary = (
        f"【事後評価客観事実】事後株価: {fact.current_price if fact else 0:,.1f} 円 "
        f"(銘柄騰落: {fact.price_change_pct if fact else 0:+.2f}%, 市場指数: {fact.market_index_change_pct if fact else 0:+.2f}%, 相対Alpha: {fact.relative_return_pct if fact else 0:+.2f}%). "
        f"主要仮説維持: {'Yes' if fact and fact.hypothesis_maintained else 'No'} ({fact.hypothesis_detail if fact else ''}). "
        f"事前リスク的中: {'Yes' if fact and fact.risk_foresight_hit else 'No'} ({fact.risk_foresight_detail if fact else ''}). "
        f"ルールベース事実スコア: {fact.rule_based_fact_score if fact else 80}/100 点."
    )

    # ジャーナル互換オブジェクトの作成
    journal_compat = JournalEntry(
        journal_id=f"jrnl_{snapshot.analysis_run_id}",
        run_id=snapshot.analysis_run_id,
        strategy_id=snapshot.analysis_run_id,
        decision_type="ANALYSIS_SNAPSHOT",
        ticker=snapshot.ticker,
        hypothesis=f"【{snapshot.company_name}】{snapshot.investment_stance}判断 (スコア: {snapshot.overall_score}) - {', '.join(snapshot.key_hypotheses[:2])}",
        assumptions=snapshot.key_hypotheses,
        expected_outcome=f"目標株価: {snapshot.target_price or 'N/A'} (根拠: {snapshot.target_calculation_basis or 'N/A'})",
        risk_assessment=snapshot.identified_risks,
        actor="AI Analysis Team",
        created_at=snapshot.created_at
    )

    reflection = perform_reflection(
        journal=journal_compat,
        actual_outcome_text=actual_summary
    )
    reflection.analysis_run_id = analysis_run_id

    save_reflection(reflection)
    apply_reflection_guardrails(reflection)

    return reflection


def run_reflection_on_strategy(strategy_id: str) -> Optional[ReflectionReport]:
    """
    指定された方針IDに関連するジャーナルから自己反省を実行する。
    """
    # スナップショットとしての検索を優先
    snapshot_res = run_reflection_on_snapshot(strategy_id)
    if snapshot_res:
        return snapshot_res

    journal = get_journal_by_strategy(strategy_id)
    if not journal:
        from src.services.journal_service import record_policy_journal
        policy = get_research_policy(strategy_id)
        if not policy:
            return None
        journal = record_policy_journal(policy)

    return run_reflection_on_journal(journal.journal_id)


def get_reflections_history(limit: int = 15) -> List[ReflectionReport]:
    """反省レポート履歴の取得"""
    return list_reflections(limit=limit)
