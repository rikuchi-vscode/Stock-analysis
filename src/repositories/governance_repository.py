"""
ガバナンス & 反省リポジトリ (Governance Repository)
STEP 4 & STEP 5: 意思決定スナップショット、事後評価スケジュール、客観的事実評価、自己反省、人間フィードバック、ガードレール規則の永続化
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.db import DB_PATH, init_db
from src.contracts.decision_journal import (
    DecisionSnapshot,
    JournalEntry,
    EvaluationSchedule,
    EvaluationFact,
    ReflectionReport,
    HumanFeedback,
    GuardrailRule,
)


# --- 1. Decision Snapshots (分析時点の判断固定保存) ---

def save_decision_snapshot(snapshot: DecisionSnapshot) -> None:
    """分析時点の判断固定スナップショットの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = snapshot.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT OR REPLACE INTO decision_snapshots (
            analysis_run_id, ticker, company_name, as_of_date,
            initial_price, initial_market_index_json, investment_stance,
            overall_score, target_price, target_calculation_basis,
            key_hypotheses_json, identified_risks_json, data_quality_json,
            verification_status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        snapshot.analysis_run_id,
        snapshot.ticker,
        snapshot.company_name,
        snapshot.as_of_date,
        snapshot.initial_price,
        json.dumps(snapshot.initial_market_index, ensure_ascii=False),
        snapshot.investment_stance,
        snapshot.overall_score,
        snapshot.target_price,
        snapshot.target_calculation_basis,
        json.dumps(snapshot.key_hypotheses, ensure_ascii=False),
        json.dumps(snapshot.identified_risks, ensure_ascii=False),
        json.dumps(snapshot.data_quality_snapshot, ensure_ascii=False),
        snapshot.verification_status,
        created_at,
    ))

    # 互換性のための decision_journals への同期挿入
    cursor.execute("""
        INSERT OR REPLACE INTO decision_journals (
            journal_id, run_id, strategy_id, decision_type, ticker, hypothesis,
            assumptions_json, expected_outcome, risk_assessment_json, actor, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        f"jrnl_{snapshot.analysis_run_id}",
        snapshot.analysis_run_id,
        snapshot.analysis_run_id,
        "ANALYSIS_SNAPSHOT",
        snapshot.ticker,
        f"【{snapshot.company_name}】{snapshot.investment_stance}判断 (スコア: {snapshot.overall_score}) - {', '.join(snapshot.key_hypotheses[:2])}",
        json.dumps(snapshot.key_hypotheses, ensure_ascii=False),
        f"目標株価: {snapshot.target_price or 'N/A'} (根拠: {snapshot.target_calculation_basis or 'N/A'})",
        json.dumps(snapshot.identified_risks, ensure_ascii=False),
        "AI Analysis Team",
        created_at,
    ))

    conn.commit()
    conn.close()


def get_decision_snapshot(analysis_run_id: str) -> Optional[DecisionSnapshot]:
    """分析実行IDからスナップショットを取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM decision_snapshots WHERE analysis_run_id = ?", (analysis_run_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_decision_snapshot(row)
    return None


def list_decision_snapshots(limit: int = 20, unique_by_ticker: bool = False) -> List[DecisionSnapshot]:
    """スナップショット一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM decision_snapshots ORDER BY created_at DESC LIMIT ?", (limit * 2 if unique_by_ticker else limit,))
    rows = cursor.fetchall()
    results = [_row_to_decision_snapshot(r) for r in rows if r]
    conn.close()

    if unique_by_ticker:
        seen = set()
        uniques = []
        for s in results:
            if s.ticker not in seen:
                seen.add(s.ticker)
                uniques.append(s)
                if len(uniques) >= limit:
                    break
        return uniques
    return results


def _row_to_decision_snapshot(row: sqlite3.Row) -> DecisionSnapshot:
    return DecisionSnapshot(
        analysis_run_id=row["analysis_run_id"],
        ticker=row["ticker"],
        company_name=row["company_name"] or "",
        as_of_date=row["as_of_date"],
        initial_price=row["initial_price"] or 0.0,
        initial_market_index=json.loads(row["initial_market_index_json"]) if row["initial_market_index_json"] else {},
        investment_stance=row["investment_stance"] or "Hold",
        overall_score=row["overall_score"] or 0.0,
        target_price=row["target_price"],
        target_calculation_basis=row["target_calculation_basis"],
        key_hypotheses=json.loads(row["key_hypotheses_json"]) if row["key_hypotheses_json"] else [],
        identified_risks=json.loads(row["identified_risks_json"]) if row["identified_risks_json"] else [],
        data_quality_snapshot=json.loads(row["data_quality_json"]) if row["data_quality_json"] else {},
        verification_status=row["verification_status"] or "OK",
        created_at=row["created_at"]
    )


# --- 2. Evaluation Schedules (事後評価スケジュール) ---

def save_evaluation_schedule(schedule: EvaluationSchedule) -> None:
    """評価スケジュールの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = schedule.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT OR REPLACE INTO evaluation_schedules (
            schedule_id, analysis_run_id, ticker, evaluation_type, target_date, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        schedule.schedule_id,
        schedule.analysis_run_id,
        schedule.ticker,
        schedule.evaluation_type,
        schedule.target_date,
        schedule.status,
        created_at,
    ))

    conn.commit()
    conn.close()


def list_due_evaluation_schedules(target_date_lte: Optional[str] = None) -> List[EvaluationSchedule]:
    """期日を迎えた (PENDING または DUE) 評価スケジュール一覧を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    today_str = target_date_lte or datetime.now().strftime("%Y-%m-%d")

    cursor.execute("""
        SELECT * FROM evaluation_schedules
        WHERE status IN ('PENDING', 'DUE') AND target_date <= ?
        ORDER BY target_date ASC
    """, (today_str,))
    rows = cursor.fetchall()
    conn.close()

    return [
        EvaluationSchedule(
            schedule_id=r["schedule_id"],
            analysis_run_id=r["analysis_run_id"],
            ticker=r["ticker"],
            evaluation_type=r["evaluation_type"],
            target_date=r["target_date"],
            status=r["status"],
            created_at=r["created_at"]
        ) for r in rows
    ]


def list_all_evaluation_schedules(limit: int = 30) -> List[EvaluationSchedule]:
    """すべての評価スケジュール一覧を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM evaluation_schedules ORDER BY target_date DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [
        EvaluationSchedule(
            schedule_id=r["schedule_id"],
            analysis_run_id=r["analysis_run_id"],
            ticker=r["ticker"],
            evaluation_type=r["evaluation_type"],
            target_date=r["target_date"],
            status=r["status"],
            created_at=r["created_at"]
        ) for r in rows
    ]


def update_evaluation_schedule_status(schedule_id: str, status: str) -> None:
    """評価スケジュールのステータス更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("UPDATE evaluation_schedules SET status = ? WHERE schedule_id = ?", (status, schedule_id))
    conn.commit()
    conn.close()


# --- 3. Evaluation Facts (ルールベース事実評価データ) ---

def save_evaluation_fact(fact: EvaluationFact) -> None:
    """ルールベース事実評価データの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = fact.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT OR REPLACE INTO evaluation_facts (
            fact_id, schedule_id, analysis_run_id, ticker, evaluation_date,
            initial_price, current_price, price_change_pct, market_index_change_pct,
            relative_return_pct, hypothesis_maintained, hypothesis_detail,
            risk_foresight_hit, risk_foresight_detail, data_integrity_ok,
            data_integrity_detail, rule_based_fact_score, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        fact.fact_id,
        fact.schedule_id,
        fact.analysis_run_id,
        fact.ticker,
        fact.evaluation_date,
        fact.initial_price,
        fact.current_price,
        fact.price_change_pct,
        fact.market_index_change_pct,
        fact.relative_return_pct,
        1 if fact.hypothesis_maintained else 0,
        fact.hypothesis_detail,
        1 if fact.risk_foresight_hit else 0,
        fact.risk_foresight_detail,
        1 if fact.data_integrity_ok else 0,
        fact.data_integrity_detail,
        fact.rule_based_fact_score,
        created_at,
    ))

    conn.commit()
    conn.close()


def list_evaluation_facts(limit: int = 20) -> List[EvaluationFact]:
    """事実評価データ一覧を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM evaluation_facts ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_evaluation_fact(r) for r in rows if r]


def get_evaluation_fact(fact_id: str) -> Optional[EvaluationFact]:
    """特定の事実評価データを取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM evaluation_facts WHERE fact_id = ?", (fact_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_evaluation_fact(row)
    return None


def get_evaluation_fact_by_run_id(analysis_run_id: str) -> Optional[EvaluationFact]:
    """分析実行IDから最新の事実評価データを取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM evaluation_facts WHERE analysis_run_id = ? ORDER BY created_at DESC LIMIT 1", (analysis_run_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_evaluation_fact(row)
    return None


def _row_to_evaluation_fact(row: sqlite3.Row) -> EvaluationFact:
    return EvaluationFact(
        fact_id=row["fact_id"],
        schedule_id=row["schedule_id"],
        analysis_run_id=row["analysis_run_id"],
        ticker=row["ticker"],
        evaluation_date=row["evaluation_date"],
        initial_price=row["initial_price"] or 0.0,
        current_price=row["current_price"] or 0.0,
        price_change_pct=row["price_change_pct"] or 0.0,
        market_index_change_pct=row["market_index_change_pct"] or 0.0,
        relative_return_pct=row["relative_return_pct"] or 0.0,
        hypothesis_maintained=bool(row["hypothesis_maintained"]),
        hypothesis_detail=row["hypothesis_detail"] or "",
        risk_foresight_hit=bool(row["risk_foresight_hit"]),
        risk_foresight_detail=row["risk_foresight_detail"] or "",
        data_integrity_ok=bool(row["data_integrity_ok"]),
        data_integrity_detail=row["data_integrity_detail"] or "",
        rule_based_fact_score=row["rule_based_fact_score"] or 80.0,
        created_at=row["created_at"]
    )


# --- 4. Decision Journals (互換用) ---

def save_journal_entry(entry: JournalEntry) -> None:
    """意思決定ジャーナルの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    assumptions_json = json.dumps(entry.assumptions, ensure_ascii=False)
    risks_json = json.dumps(entry.risk_assessment, ensure_ascii=False)

    cursor.execute("""
        INSERT OR REPLACE INTO decision_journals (
            journal_id, run_id, strategy_id, decision_type, ticker, hypothesis,
            assumptions_json, expected_outcome, risk_assessment_json, actor, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        entry.journal_id,
        entry.run_id,
        entry.strategy_id,
        entry.decision_type,
        entry.ticker,
        entry.hypothesis,
        assumptions_json,
        entry.expected_outcome,
        risks_json,
        entry.actor,
        entry.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def get_journal_entry(journal_id: str) -> Optional[JournalEntry]:
    """特定のジャーナルエントリを取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM decision_journals WHERE journal_id = ?", (journal_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_journal_entry(row)
    return None


def get_journal_by_strategy(strategy_id: str) -> Optional[JournalEntry]:
    """方針IDからジャーナルを取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM decision_journals WHERE strategy_id = ? ORDER BY created_at DESC LIMIT 1", (strategy_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        return _row_to_journal_entry(row)
    return None


def list_journal_entries(limit: int = 15, unique_by_ticker: bool = True) -> List[JournalEntry]:
    """ジャーナル一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM decision_journals ORDER BY created_at DESC LIMIT ?", (limit * 3 if unique_by_ticker else limit,))
    rows = cursor.fetchall()
    results = [_row_to_journal_entry(r) for r in rows if r]
    conn.close()

    if unique_by_ticker:
        seen_tickers = set()
        unique_results = []
        for j in results:
            t = j.ticker or "ALL"
            if t not in seen_tickers:
                seen_tickers.add(t)
                unique_results.append(j)
                if len(unique_results) >= limit:
                    break
        return unique_results

    return results


def _row_to_journal_entry(row: sqlite3.Row) -> JournalEntry:
    assumptions = json.loads(row["assumptions_json"]) if row["assumptions_json"] else []
    risks = json.loads(row["risk_assessment_json"]) if row["risk_assessment_json"] else []
    return JournalEntry(
        journal_id=row["journal_id"],
        run_id=row["run_id"],
        strategy_id=row["strategy_id"],
        decision_type=row["decision_type"],
        ticker=row["ticker"],
        hypothesis=row["hypothesis"],
        assumptions=assumptions,
        expected_outcome=row["expected_outcome"],
        risk_assessment=risks,
        actor=row["actor"],
        created_at=row["created_at"]
    )


# --- 5. Reflections ---

def save_reflection(reflection: ReflectionReport) -> None:
    """自己反省レポートの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO reflections (
            reflection_id, journal_id, strategy_id, actual_outcome, accuracy_score,
            success_factors_json, blindspots_json, lessons_learned_json, guardrail_updates_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        reflection.reflection_id,
        reflection.journal_id or "",
        reflection.strategy_id or reflection.analysis_run_id or "",
        reflection.actual_outcome,
        reflection.accuracy_score,
        json.dumps(reflection.success_factors, ensure_ascii=False),
        json.dumps(reflection.blindspots, ensure_ascii=False),
        json.dumps(reflection.lessons_learned, ensure_ascii=False),
        json.dumps(reflection.recommended_guardrails, ensure_ascii=False),
        reflection.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def list_reflections(limit: int = 15) -> List[ReflectionReport]:
    """自己反省レポート一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = []
    for r in rows:
        results.append(ReflectionReport(
            reflection_id=r["reflection_id"],
            journal_id=r["journal_id"],
            strategy_id=r["strategy_id"],
            analysis_run_id=r["strategy_id"],
            actual_outcome=r["actual_outcome"],
            accuracy_score=r["accuracy_score"],
            success_factors=json.loads(r["success_factors_json"]) if r["success_factors_json"] else [],
            blindspots=json.loads(r["blindspots_json"]) if r["blindspots_json"] else [],
            lessons_learned=json.loads(r["lessons_learned_json"]) if r["lessons_learned_json"] else [],
            recommended_guardrails=json.loads(r["guardrail_updates_json"]) if r["guardrail_updates_json"] else [],
            created_at=r["created_at"]
        ))

    conn.close()
    return results


# --- 6. Human Feedback ---

def save_human_feedback(feedback: HumanFeedback) -> None:
    """人間フィードバックの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO human_feedbacks (
            feedback_id, target_type, target_id, rating, comments, corrections_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        feedback.feedback_id,
        feedback.target_type,
        feedback.target_id,
        feedback.rating,
        feedback.comments,
        json.dumps(feedback.corrections, ensure_ascii=False),
        feedback.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))

    conn.commit()
    conn.close()


def list_human_feedbacks(limit: int = 15) -> List[Dict[str, Any]]:
    """人間フィードバック一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM human_feedbacks ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


# --- 7. Guardrail Rules (PROPOSED → APPROVED/REJECTED → ACTIVE) ---

def save_guardrail_rule(rule: GuardrailRule) -> None:
    """ガードレールルールの保存・更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    created_at = rule.created_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute(
        "SELECT rule_id, status, active FROM guardrail_rules WHERE category = ? AND rule_text = ?",
        (rule.category, rule.rule_text)
    )
    existing = cursor.fetchone()

    if existing:
        cursor.execute("""
            UPDATE guardrail_rules
            SET source = ?, status = ?, proposed_by = ?, approved_by = ?,
                approved_at = ?, rejection_reason = ?, active = ?
            WHERE rule_id = ?
        """, (
            rule.source,
            rule.status,
            rule.proposed_by,
            rule.approved_by,
            rule.approved_at,
            rule.rejection_reason,
            1 if (rule.active or rule.status == "ACTIVE") else 0,
            existing[0]
        ))
    else:
        cursor.execute("""
            INSERT OR REPLACE INTO guardrail_rules (
                rule_id, category, rule_text, source, status, proposed_by,
                approved_by, approved_at, rejection_reason, active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            rule.rule_id,
            rule.category,
            rule.rule_text,
            rule.source,
            rule.status,
            rule.proposed_by,
            rule.approved_by,
            rule.approved_at,
            rule.rejection_reason,
            1 if (rule.active or rule.status == "ACTIVE") else 0,
            created_at,
        ))

    conn.commit()
    conn.close()


def approve_guardrail_rule(rule_id: str, approved_by: str = "Human Owner") -> bool:
    """提案されたガードレールルールを承認して ACTIVE にする"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        UPDATE guardrail_rules
        SET status = 'ACTIVE', active = 1, approved_by = ?, approved_at = ?
        WHERE rule_id = ?
    """, (approved_by, now_str, rule_id))

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def reject_guardrail_rule(rule_id: str, rejected_by: str = "Human Owner", reason: str = "") -> bool:
    """提案されたガードレールルールを却下する"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE guardrail_rules
        SET status = 'REJECTED', active = 0, approved_by = ?, rejection_reason = ?
        WHERE rule_id = ?
    """, (rejected_by, reason, rule_id))

    affected = cursor.rowcount
    conn.commit()
    conn.close()
    return affected > 0


def list_active_guardrail_rules(unique_by_text: bool = True) -> List[GuardrailRule]:
    """現在有効なガードレールルール一覧 (status='ACTIVE' または active=1)"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM guardrail_rules
        WHERE active = 1 OR status = 'ACTIVE'
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    results = []
    seen_texts = set()
    for r in rows:
        text = r["rule_text"]
        if unique_by_text:
            if text in seen_texts:
                continue
            seen_texts.add(text)

        results.append(_row_to_guardrail_rule(r))

    return results


def list_proposed_guardrail_rules() -> List[GuardrailRule]:
    """承認待ちの提案ルール一覧 (status='PROPOSED')"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM guardrail_rules
        WHERE status = 'PROPOSED'
        ORDER BY created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()

    return [_row_to_guardrail_rule(r) for r in rows if r]


def _row_to_guardrail_rule(row: sqlite3.Row) -> GuardrailRule:
    status = row["status"] if "status" in row.keys() and row["status"] else ("ACTIVE" if row["active"] else "PROPOSED")
    proposed_by = row["proposed_by"] if "proposed_by" in row.keys() and row["proposed_by"] else "Reflection Agent"
    approved_by = row["approved_by"] if "approved_by" in row.keys() else None
    approved_at = row["approved_at"] if "approved_at" in row.keys() else None
    rejection_reason = row["rejection_reason"] if "rejection_reason" in row.keys() else None

    return GuardrailRule(
        rule_id=row["rule_id"],
        category=row["category"],
        rule_text=row["rule_text"],
        source=row["source"],
        status=status,
        proposed_by=proposed_by,
        approved_by=approved_by,
        approved_at=approved_at,
        rejection_reason=rejection_reason,
        active=bool(row["active"]),
        created_at=row["created_at"]
    )
