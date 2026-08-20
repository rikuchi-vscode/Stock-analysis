"""
事後評価エンジン & ガバナンス承認フロー ユニットテスト
"""

import pytest
from datetime import datetime, timedelta
from src.contracts.decision_journal import DecisionSnapshot, EvaluationSchedule, EvaluationFact, GuardrailRule
from src.repositories.governance_repository import (
    save_decision_snapshot,
    get_decision_snapshot,
    save_evaluation_schedule,
    list_due_evaluation_schedules,
    save_evaluation_fact,
    get_evaluation_fact_by_run_id,
    save_guardrail_rule,
    approve_guardrail_rule,
    reject_guardrail_rule,
    list_active_guardrail_rules,
    list_proposed_guardrail_rules,
)
from src.services.snapshot_service import capture_analysis_snapshot_and_schedule
from src.services.post_evaluation_service import run_due_evaluations, evaluate_single_schedule


def test_decision_snapshot_and_schedules_creation():
    """スナップショット固定保存と T+7, T+30 評価スケジュール自動登録のテスト"""
    run_id = f"test_run_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    snapshot = capture_analysis_snapshot_and_schedule(
        analysis_run_id=run_id,
        ticker="7203.T",
        company_name="トヨタ自動車",
        market_data={"current_price": 3000.0, "market_as_of": "2026-08-20"},
        financial_data={"missing_items": [], "financial_as_of": "2026-03"},
        analysis_result={
            "investment_stance": "Buy",
            "overall_score": 85,
            "target_price": 3300.0,
            "target_calculation_basis": "予想EPS 280円 × PER 11.8倍",
            "executive_summary": "強固なHEV収益基盤と為替恩恵",
            "downside_risks": ["急激な円高リスク"]
        },
        verification_result={"status": "OK"}
    )

    assert snapshot.analysis_run_id == run_id
    assert snapshot.ticker == "7203.T"
    assert snapshot.initial_price == 3000.0
    assert snapshot.overall_score == 85.0
    assert "急激な円高リスク" in snapshot.identified_risks

    # DBから取得検証
    fetched = get_decision_snapshot(run_id)
    assert fetched is not None
    assert fetched.company_name == "トヨタ自動車"


def test_rule_based_fact_evaluation():
    """ルールベース事実評価の計算ロジック検証 (相対Alpha, 仮説維持, 事前リスク的中)"""
    run_id = f"test_eval_run_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 1. スナップショット作成
    save_decision_snapshot(DecisionSnapshot(
        analysis_run_id=run_id,
        ticker="7203.T",
        company_name="トヨタ自動車",
        as_of_date="2026-08-01",
        initial_price=3000.0,
        initial_market_index={"N225": 38000.0},
        investment_stance="Buy",
        overall_score=85,
        target_price=3300.0,
        key_hypotheses=["HEV需要堅調"],
        identified_risks=["円高リスク", "為替変動"],
        data_quality_snapshot={"missing_items": []},
        verification_status="OK"
    ))

    # 2. スケジュール作成 (期日到来状態)
    schedule = EvaluationSchedule(
        schedule_id=f"sched_{run_id}_t7",
        analysis_run_id=run_id,
        ticker="7203.T",
        evaluation_type="T+7",
        target_date="2026-08-08",
        status="PENDING"
    )
    save_evaluation_schedule(schedule)

    # 3. 事実評価実行
    fact = evaluate_single_schedule(schedule)
    assert fact is not None
    assert fact.analysis_run_id == run_id
    assert fact.current_price > 0
    assert fact.rule_based_fact_score >= 0.0
    assert fact.rule_based_fact_score <= 100.0

    # 4. DB永続化の確認
    saved_fact = get_evaluation_fact_by_run_id(run_id)
    assert saved_fact is not None
    assert saved_fact.fact_id == fact.fact_id


def test_guardrail_governance_approval_flow():
    """ガードレール規則の PROPOSED → APPROVED/REJECTED → ACTIVE ガバナンス承認フロー検証"""
    rule_id = f"gr_test_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 1. PROPOSED で登録 (即時反映されない)
    save_guardrail_rule(GuardrailRule(
        rule_id=rule_id,
        category="RISK",
        rule_text="為替感応度の高い輸出企業では為替レート前提を必ず開示すること",
        source="REFLECTION",
        status="PROPOSED",
        proposed_by="Reflection Agent",
        active=False
    ))

    proposed_list = list_proposed_guardrail_rules()
    assert any(r.rule_id == rule_id for r in proposed_list)

    # 有効リストにはまだ入っていないことを確認
    active_before = list_active_guardrail_rules()
    assert not any(r.rule_id == rule_id for r in active_before)

    # 2. 人間オーナーによる承認 (APPROVED -> ACTIVE)
    success = approve_guardrail_rule(rule_id, approved_by="CEO Owner")
    assert success is True

    # 承認後は ACTIVE リストに含まれることを確認
    active_after = list_active_guardrail_rules()
    matched = [r for r in active_after if r.rule_id == rule_id]
    assert len(matched) == 1
    assert matched[0].status == "ACTIVE"
    assert matched[0].approved_by == "CEO Owner"

    # 3. 却下テスト
    rule_rej_id = f"gr_rej_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    save_guardrail_rule(GuardrailRule(
        rule_id=rule_rej_id,
        category="FOCUS",
        rule_text="テスト却下ルール",
        status="PROPOSED",
        active=False
    ))
    reject_guardrail_rule(rule_rej_id, rejected_by="CEO Owner", reason="不要な制約")
    active_final = list_active_guardrail_rules()
    assert not any(r.rule_id == rule_rej_id for r in active_final)
