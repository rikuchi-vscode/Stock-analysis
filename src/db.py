"""
SQLite データベース永続化モジュール
分析結果、最終レポート、各エージェントのログ、スナップショットを永続化します。
"""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional

DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "stock_analysis.db")


def init_db():
    """データベースおよびテーブルの初期化"""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 1. 分析履歴テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT NOT NULL,
            company_name TEXT,
            sector TEXT,
            analysis_date TEXT NOT NULL,
            overall_score INTEGER,
            investment_stance TEXT,
            verification_status TEXT,
            iteration_count INTEGER,
            report_path TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 2. 最終レポートテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            ticker TEXT NOT NULL,
            report_content TEXT NOT NULL,
            summary TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    # 3. エージェントログ・検証履歴テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            agent_name TEXT NOT NULL,
            log_type TEXT,
            content TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    # 4. データスナップショットテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            analysis_id INTEGER NOT NULL,
            market_data TEXT,
            financial_data TEXT,
            news_data TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (analysis_id) REFERENCES analyses(id)
        )
    """)

    # 5. [STEP 1] CEO リクエストテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ceo_requests (
            request_id TEXT PRIMARY KEY,
            user_request TEXT NOT NULL,
            task_type TEXT,
            ticker TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 6. [STEP 1] CEO 実行ランテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ceo_runs (
            run_id TEXT PRIMARY KEY,
            request_id TEXT NOT NULL,
            analysis_run_id TEXT,
            verification_status TEXT,
            status TEXT,
            trace_id TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (request_id) REFERENCES ceo_requests(request_id)
        )
    """)

    # 7. [STEP 1] エージェント間委任監査テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_delegations (
            delegation_id TEXT PRIMARY KEY,
            run_id TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            to_agent TEXT NOT NULL,
            payload_ref TEXT,
            status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES ceo_runs(run_id)
        )
    """)

    # 8. [STEP 1] CEO サマリーテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ceo_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            summary_json TEXT NOT NULL,
            report_ref TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (run_id) REFERENCES ceo_runs(run_id)
        )
    """)

    # 9. [STEP 2] リサーチ方針テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS research_policies (
            strategy_id TEXT PRIMARY KEY,
            run_id TEXT,
            policy_json TEXT NOT NULL,
            status TEXT NOT NULL,
            version INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 10. [STEP 2] 方針決定・根拠テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_decisions (
            decision_id TEXT PRIMARY KEY,
            strategy_id TEXT NOT NULL,
            decision_type TEXT NOT NULL,
            rationale TEXT,
            actor TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES research_policies(strategy_id)
        )
    """)

    # 11. [STEP 2] 人間承認テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_approvals (
            approval_id TEXT PRIMARY KEY,
            strategy_id TEXT NOT NULL,
            requested_action TEXT NOT NULL,
            status TEXT NOT NULL,
            approved_by TEXT,
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES research_policies(strategy_id)
        )
    """)

    # 12. [STEP 2] 方針成果・達成度テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_outcomes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strategy_id TEXT NOT NULL,
            analysis_run_id TEXT,
            coverage TEXT,
            verification_status TEXT,
            outcome_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (strategy_id) REFERENCES research_policies(strategy_id)
        )
    """)

    # 13. [STEP 3] 監視対象銘柄テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watch_items (
            watch_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL UNIQUE,
            company_name TEXT,
            triggers_json TEXT NOT NULL,
            interval_minutes INTEGER DEFAULT 60,
            priority TEXT DEFAULT 'medium',
            active INTEGER DEFAULT 1,
            last_checked_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 14. [STEP 3] 市場・開示・ニュースイベントテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_events (
            event_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            company_name TEXT,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            raw_payload TEXT,
            detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 15. [STEP 3] イベントトリアージ結果テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_triages (
            triage_id TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            action TEXT NOT NULL,
            reason TEXT,
            suggested_mode TEXT,
            priority TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (event_id) REFERENCES market_events(event_id)
        )
    """)

    # 16. [STEP 3] 通知履歴テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            notification_id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT NOT NULL,
            metadata_json TEXT,
            delivered INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 17. [STEP 4] 意思決定ジャーナルテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_journals (
            journal_id TEXT PRIMARY KEY,
            run_id TEXT,
            strategy_id TEXT,
            decision_type TEXT NOT NULL,
            ticker TEXT,
            hypothesis TEXT NOT NULL,
            assumptions_json TEXT,
            expected_outcome TEXT NOT NULL,
            risk_assessment_json TEXT,
            actor TEXT DEFAULT 'AI CEO',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 18. [STEP 4] 自己反省 (Reflection) テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reflections (
            reflection_id TEXT PRIMARY KEY,
            journal_id TEXT NOT NULL,
            strategy_id TEXT,
            actual_outcome TEXT NOT NULL,
            accuracy_score INTEGER DEFAULT 80,
            success_factors_json TEXT,
            blindspots_json TEXT,
            lessons_learned_json TEXT,
            guardrail_updates_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (journal_id) REFERENCES decision_journals(journal_id)
        )
    """)

    # 19. [STEP 4] 人間フィードバックテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS human_feedbacks (
            feedback_id TEXT PRIMARY KEY,
            target_type TEXT NOT NULL,
            target_id TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comments TEXT,
            corrections_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 20. [STEP 4] ガードレール規則テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS guardrail_rules (
            rule_id TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            rule_text TEXT NOT NULL,
            source TEXT NOT NULL,
            status TEXT DEFAULT 'PROPOSED',
            proposed_by TEXT DEFAULT 'Reflection Agent',
            approved_by TEXT,
            approved_at TEXT,
            rejection_reason TEXT,
            active INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 21. [STEP 4/5] 分析時点の判断固定スナップショットテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS decision_snapshots (
            analysis_run_id TEXT PRIMARY KEY,
            ticker TEXT NOT NULL,
            company_name TEXT,
            as_of_date TEXT NOT NULL,
            initial_price REAL,
            initial_market_index_json TEXT,
            investment_stance TEXT,
            overall_score REAL,
            target_price REAL,
            target_calculation_basis TEXT,
            key_hypotheses_json TEXT,
            identified_risks_json TEXT,
            data_quality_json TEXT,
            verification_status TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 22. [STEP 4/5] 事後評価スケジュールテーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_schedules (
            schedule_id TEXT PRIMARY KEY,
            analysis_run_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            evaluation_type TEXT NOT NULL,
            target_date TEXT NOT NULL,
            status TEXT DEFAULT 'PENDING',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 23. [STEP 4/5] ルールベース事実評価テーブル
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS evaluation_facts (
            fact_id TEXT PRIMARY KEY,
            schedule_id TEXT NOT NULL,
            analysis_run_id TEXT NOT NULL,
            ticker TEXT NOT NULL,
            evaluation_date TEXT NOT NULL,
            initial_price REAL,
            current_price REAL,
            price_change_pct REAL,
            market_index_change_pct REAL,
            relative_return_pct REAL,
            hypothesis_maintained INTEGER,
            hypothesis_detail TEXT,
            risk_foresight_hit INTEGER,
            risk_foresight_detail TEXT,
            data_integrity_ok INTEGER,
            data_integrity_detail TEXT,
            rule_based_fact_score REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 既存テーブルへのカラム追加マイグレーション (guardrail_rules)
    try:
        cursor.execute("ALTER TABLE guardrail_rules ADD COLUMN status TEXT DEFAULT 'ACTIVE'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE guardrail_rules ADD COLUMN proposed_by TEXT DEFAULT 'Reflection Agent'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE guardrail_rules ADD COLUMN approved_by TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE guardrail_rules ADD COLUMN approved_at TEXT")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE guardrail_rules ADD COLUMN rejection_reason TEXT")
    except Exception:
        pass

    conn.commit()
    conn.close()


def save_analysis(
    ticker: str,
    company_name: str,
    sector: str,
    overall_score: Optional[int],
    investment_stance: Optional[str],
    verification_status: str,
    iteration_count: int,
    report_content: str,
    report_path: str,
    market_data: Dict[str, Any],
    financial_data: Dict[str, Any],
    news_data: Dict[str, Any],
    logs: List[str]
) -> int:
    """分析実行結果の全データをDBにトランザクション保存"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    analysis_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # analyses レコード挿入
    cursor.execute("""
        INSERT INTO analyses (
            ticker, company_name, sector, analysis_date,
            overall_score, investment_stance, verification_status,
            iteration_count, report_path
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        ticker, company_name, sector, analysis_date,
        overall_score, investment_stance, verification_status,
        iteration_count, report_path
    ))
    analysis_id = cursor.lastrowid

    # reports レコード挿入
    cursor.execute("""
        INSERT INTO reports (analysis_id, ticker, report_content, summary)
        VALUES (?, ?, ?, ?)
    """, (
        analysis_id, ticker, report_content,
        f"{company_name} ({ticker}) 分析レポート - スコア: {overall_score}/100"
    ))

    # snapshots レコード挿入
    cursor.execute("""
        INSERT INTO snapshots (analysis_id, market_data, financial_data, news_data)
        VALUES (?, ?, ?, ?)
    """, (
        analysis_id,
        json.dumps(market_data, ensure_ascii=False),
        json.dumps(financial_data, ensure_ascii=False),
        json.dumps(news_data, ensure_ascii=False)
    ))

    # agent_logs レコード挿入
    for log_entry in logs:
        cursor.execute("""
            INSERT INTO agent_logs (analysis_id, agent_name, log_type, content)
            VALUES (?, ?, ?, ?)
        """, (analysis_id, "System", "ExecutionLog", log_entry))

    conn.commit()
    conn.close()
    return analysis_id


def get_analysis_history(ticker: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
    """分析履歴の一覧を取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if ticker:
        cursor.execute(
            "SELECT * FROM analyses WHERE ticker = ? ORDER BY id DESC LIMIT ?",
            (ticker, limit)
        )
    else:
        cursor.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?",
            (limit,)
        )

    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def get_report_by_analysis_id(analysis_id: int) -> Optional[str]:
    """analysis_id に紐づく Markdown レポート本文を DB から取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT report_content FROM reports WHERE analysis_id = ?", (analysis_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_latest_report_content(ticker: str) -> Optional[str]:
    """特定銘柄の最新 Markdown レポート本文を DB から取得"""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.report_content FROM reports r
        JOIN analyses a ON r.analysis_id = a.id
        WHERE a.ticker = ?
        ORDER BY a.id DESC LIMIT 1
        """,
        (ticker,)
    )
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None
