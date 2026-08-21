"""
Dashboard Service モジュール
STEP 5: 全レイヤー (STEP 0〜STEP 4) のデータ・KPI・最新アクティビティの統合集計
"""

import sqlite3
import json
from datetime import datetime
from typing import Dict, Any, List

from src.db import DB_PATH, init_db
from src.contracts.dashboard_metrics import SystemKPIMetrics, DashboardSummary
from src.time_utils import get_jst_now_str
from src.repositories.ceo_repository import get_ceo_history
from src.repositories.policy_repository import list_research_policies
from src.repositories.monitor_repository import (
    list_watch_items,
    list_market_events_with_triage,
)
from src.repositories.governance_repository import (
    list_journal_entries,
    list_reflections,
    list_active_guardrail_rules,
)


def get_dashboard_summary() -> DashboardSummary:
    """
    システム全体の統合KPIと直近データを集計してダッシュボードサマリーを返す。
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. STEP 0: 分析済みユニーク銘柄数 & 総分析数 & 平均スコア
    cursor.execute("SELECT COUNT(DISTINCT ticker), COUNT(*), AVG(overall_score) FROM analyses WHERE overall_score IS NOT NULL")
    analyses_row = cursor.fetchone()
    unique_analyzed_stocks = analyses_row[0] if analyses_row else 0
    total_analyses = analyses_row[1] if analyses_row else 0
    avg_overall_score = round(analyses_row[2], 1) if (analyses_row and analyses_row[2] is not None) else 0.0

    # 2. STEP 1: CEO 実行総数
    cursor.execute("SELECT COUNT(*) FROM ceo_runs")
    total_ceo_runs = cursor.fetchone()[0]

    # 3. STEP 2: リサーチ方針数 & 承認待ち数
    cursor.execute("SELECT COUNT(*) FROM research_policies")
    total_policies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM research_policies WHERE status = 'WAITING_APPROVAL'")
    pending_approvals = cursor.fetchone()[0]

    # 4. STEP 3: 監視銘柄数 & イベント数 & 自律リサーチ起動数
    cursor.execute("SELECT COUNT(*) FROM watch_items WHERE active = 1")
    watched_tickers_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM market_events")
    market_events_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM event_triages WHERE action = 'TRIGGER_RESEARCH'")
    researches_triggered_count = cursor.fetchone()[0]

    # 5. STEP 4: ジャーナル数 & 反省数 & ガードレール数 & 平均反省スコア
    cursor.execute("SELECT COUNT(*) FROM decision_journals")
    total_journals = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*), AVG(accuracy_score) FROM reflections WHERE accuracy_score IS NOT NULL")
    ref_row = cursor.fetchone()
    total_reflections = ref_row[0] if ref_row else 0
    avg_accuracy_score = round(ref_row[1], 1) if (ref_row and ref_row[1] is not None) else 0.0

    cursor.execute("SELECT COUNT(DISTINCT rule_text) FROM guardrail_rules WHERE active = 1")
    active_guardrails_count = cursor.fetchone()[0]

    conn.close()

    metrics = SystemKPIMetrics(
        total_analyses=total_analyses,
        unique_analyzed_stocks_count=unique_analyzed_stocks,
        total_ceo_runs=total_ceo_runs,
        total_policies=total_policies,
        pending_approvals=pending_approvals,
        watched_tickers_count=watched_tickers_count,
        market_events_count=market_events_count,
        researches_triggered_count=researches_triggered_count,
        total_journals=total_journals,
        total_reflections=total_reflections,
        active_guardrails_count=active_guardrails_count,
        average_accuracy_score=avg_accuracy_score,
        average_overall_score=avg_overall_score
    )

    # 直近データの取得
    recent_ceo = get_ceo_history(limit=5)
    pending_policies = [p.model_dump() for p in list_research_policies(limit=5, status="WAITING_APPROVAL")]
    recent_events = list_market_events_with_triage(limit=5)
    recent_reflections = [r.model_dump() for r in list_reflections(limit=5)]
    active_guardrails = [g.model_dump() for g in list_active_guardrail_rules()]

    now_str = get_jst_now_str("%Y-%m-%d %H:%M:%S")

    return DashboardSummary(
        metrics=metrics,
        recent_ceo_summaries=recent_ceo,
        pending_approval_policies=pending_policies,
        recent_market_events=recent_events,
        recent_reflections=recent_reflections,
        active_guardrails=active_guardrails,
        generated_at=now_str
    )
