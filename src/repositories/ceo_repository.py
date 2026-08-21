import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from src.db import DB_PATH, init_db
from src.time_utils import get_jst_now_str
from src.contracts.ceo_request import NormalizedRequest, CEOSummary


def save_ceo_request(
    request_id: str,
    user_request: str,
    normalized: Optional[NormalizedRequest] = None,
    status: str = "RECEIVED"
) -> None:
    """ユーザー依頼の登録"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    task_type = normalized.task_type if normalized else "stock_analysis"
    ticker = normalized.ticker if normalized else None
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO ceo_requests (
            request_id, user_request, task_type, ticker, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
    """, (request_id, user_request, task_type, ticker, status, created_at))

    conn.commit()
    conn.close()


def save_ceo_run(
    run_id: str,
    request_id: str,
    trace_id: str,
    analysis_run_id: Optional[str] = None,
    verification_status: str = "PENDING",
    status: str = "RUNNING",
    error: Optional[str] = None
) -> None:
    """CEO実行ランの登録"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO ceo_runs (
            run_id, request_id, analysis_run_id, verification_status, status, trace_id, error, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (run_id, request_id, analysis_run_id, verification_status, status, trace_id, error, created_at))

    conn.commit()
    conn.close()


def save_agent_delegation(
    delegation_id: str,
    run_id: str,
    from_agent: str,
    to_agent: str,
    payload_ref: str,
    status: str = "DISPATCHED"
) -> None:
    """エージェント間委任の監査ログ登録"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    created_at = get_jst_now_str()

    cursor.execute("""
        INSERT OR REPLACE INTO agent_delegations (
            delegation_id, run_id, from_agent, to_agent, payload_ref, status, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (delegation_id, run_id, from_agent, to_agent, payload_ref, status, created_at))

    conn.commit()
    conn.close()


def save_ceo_summary(
    run_id: str,
    summary: CEOSummary,
    report_ref: Optional[str] = None
) -> None:
    """CEOサマリーの永続化"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    summary_json = json.dumps(summary.model_dump(), ensure_ascii=False)
    created_at = get_jst_now_str()

    # 既存のサマリーがあれば削除して最新版を保存
    cursor.execute("DELETE FROM ceo_summaries WHERE run_id = ?", (run_id,))
    cursor.execute("""
        INSERT INTO ceo_summaries (
            run_id, summary_json, report_ref, created_at
        ) VALUES (?, ?, ?, ?)
    """, (run_id, summary_json, report_ref, created_at))

    conn.commit()
    conn.close()


def update_ceo_run_status(
    run_id: str,
    status: str,
    verification_status: Optional[str] = None,
    error: Optional[str] = None,
    analysis_run_id: Optional[str] = None
) -> None:
    """CEO実行ランの状態更新"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    updates = ["status = ?"]
    params = [status]

    if verification_status is not None:
        updates.append("verification_status = ?")
        params.append(verification_status)
    if error is not None:
        updates.append("error = ?")
        params.append(error)
    if analysis_run_id is not None:
        updates.append("analysis_run_id = ?")
        params.append(analysis_run_id)

    params.append(run_id)
    sql = f"UPDATE ceo_runs SET {', '.join(updates)} WHERE run_id = ?"

    cursor.execute(sql, tuple(params))
    conn.commit()
    conn.close()


def get_ceo_run(run_id: str) -> Optional[Dict[str, Any]]:
    """特定のCEO実行ランの詳細取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.*, req.user_request, req.ticker, s.summary_json, s.report_ref
        FROM ceo_runs r
        LEFT JOIN ceo_requests req ON r.request_id = req.request_id
        LEFT JOIN (
            SELECT run_id, summary_json, report_ref, MAX(id)
            FROM ceo_summaries
            GROUP BY run_id
        ) s ON r.run_id = s.run_id
        WHERE r.run_id = ?
    """, (run_id,))

    row = cursor.fetchone()
    conn.close()
    if row:
        data = dict(row)
        if data.get("summary_json"):
            try:
                data["summary"] = json.loads(data["summary_json"])
            except Exception:
                data["summary"] = None
        return data
    return None


def get_ceo_history(limit: int = 15) -> List[Dict[str, Any]]:
    """CEO実行履歴の一覧取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT r.run_id, r.request_id, r.analysis_run_id, r.verification_status,
               r.status, r.created_at, req.user_request, req.ticker, s.summary_json, s.report_ref
        FROM ceo_runs r
        LEFT JOIN ceo_requests req ON r.request_id = req.request_id
        LEFT JOIN (
            SELECT run_id, summary_json, report_ref, MAX(id)
            FROM ceo_summaries
            GROUP BY run_id
        ) s ON r.run_id = s.run_id
        ORDER BY r.created_at DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()
    results = []
    for row in rows:
        d = dict(row)
        if d.get("summary_json"):
            try:
                d["summary"] = json.loads(d["summary_json"])
            except Exception:
                d["summary"] = None
        results.append(d)

    conn.close()
    return results
