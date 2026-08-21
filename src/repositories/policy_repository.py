"""
リサーチ方針 (Research Policy) リポジトリ
STEP 2: データベース永続化・版管理・承認ステータス管理
"""

import json
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.db import DB_PATH, init_db
from src.time_utils import get_jst_now_str
from src.contracts.research_policy import (
    ResearchPolicy,
    PolicyDecision,
    PolicyApproval,
    PolicyOutcome,
)


def save_research_policy(policy: ResearchPolicy) -> None:
    """リサーチ方針の保存または更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    policy_json = json.dumps(policy.model_dump(), ensure_ascii=False)
    created_at = policy.created_at or get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO research_policies (
            strategy_id, run_id, policy_json, status, version, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        policy.strategy_id,
        policy.run_id,
        policy_json,
        policy.status,
        policy.version,
        created_at,
    ))

    conn.commit()
    conn.close()


def get_research_policy(strategy_id: str) -> Optional[ResearchPolicy]:
    """特定の方針を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM research_policies WHERE strategy_id = ?
    """, (strategy_id,))

    row = cursor.fetchone()
    conn.close()

    if row and row["policy_json"]:
        try:
            data = json.loads(row["policy_json"])
            data["status"] = row["status"]
            data["version"] = row["version"]
            data["created_at"] = row["created_at"]
            return ResearchPolicy(**data)
        except Exception:
            return None
    return None


def list_research_policies(limit: int = 15, status: Optional[str] = None) -> List[ResearchPolicy]:
    """方針一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if status:
        cursor.execute("""
            SELECT * FROM research_policies WHERE status = ? ORDER BY created_at DESC LIMIT ?
        """, (status, limit))
    else:
        cursor.execute("""
            SELECT * FROM research_policies ORDER BY created_at DESC LIMIT ?
        """, (limit,))

    rows = cursor.fetchall()
    results = []
    for r in rows:
        if r["policy_json"]:
            try:
                data = json.loads(r["policy_json"])
                data["status"] = r["status"]
                data["version"] = r["version"]
                data["created_at"] = r["created_at"]
                results.append(ResearchPolicy(**data))
            except Exception:
                continue

    conn.close()
    return results


def update_policy_status(strategy_id: str, status: str) -> None:
    """方針ステータスの更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE research_policies SET status = ? WHERE strategy_id = ?
    """, (status, strategy_id))

    conn.commit()
    conn.close()


def record_policy_decision(decision: PolicyDecision) -> None:
    """方針決定ログの記録"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO policy_decisions (
            decision_id, strategy_id, decision_type, rationale, actor, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        decision.decision_id,
        decision.strategy_id,
        decision.decision_type,
        decision.rationale,
        decision.actor,
        created_at,
    ))

    conn.commit()
    conn.close()


def save_policy_approval(approval: PolicyApproval) -> None:
    """人間承認レコードの保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO policy_approvals (
            approval_id, strategy_id, requested_action, status, approved_by, comment, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        approval.approval_id,
        approval.strategy_id,
        approval.requested_action,
        approval.status,
        approval.approved_by,
        approval.comment,
        created_at,
    ))

    conn.commit()
    conn.close()


def get_pending_approvals() -> List[Dict[str, Any]]:
    """未承認・承認待ち一覧の取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT a.*, p.policy_json
        FROM policy_approvals a
        JOIN research_policies p ON a.strategy_id = p.strategy_id
        WHERE a.status = 'PENDING'
        ORDER BY a.created_at DESC
    """)

    rows = cursor.fetchall()
    results = [dict(r) for r in rows]
    conn.close()
    return results


def save_policy_outcome(outcome: PolicyOutcome) -> None:
    """方針成果の記録"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    outcome_json = json.dumps(outcome.model_dump(), ensure_ascii=False)
    coverage_json = json.dumps(outcome.coverage, ensure_ascii=False)
    run_ids_str = ",".join(outcome.analysis_run_ids)
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT INTO policy_outcomes (
            strategy_id, analysis_run_id, coverage, verification_status, outcome_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (
        outcome.strategy_id,
        run_ids_str,
        coverage_json,
        outcome.verification_status,
        outcome_json,
        created_at,
    ))

    conn.commit()
    conn.close()
