"""
Dashboard Service 単体テスト
STEP 5: 統合KPI集計・サマリー生成のテスト
"""

import pytest
from src.services.dashboard_service import get_dashboard_summary
from src.contracts.dashboard_metrics import DashboardSummary, SystemKPIMetrics


def test_get_dashboard_summary_structure():
    """ダッシュボードサマリーが正しい型とメトリクスで生成されること"""
    summary = get_dashboard_summary()

    assert isinstance(summary, DashboardSummary)
    assert isinstance(summary.metrics, SystemKPIMetrics)
    assert summary.metrics.total_analyses >= 0
    assert summary.metrics.total_ceo_runs >= 0
    assert summary.metrics.average_accuracy_score >= 0.0
    assert summary.generated_at is not None
    assert isinstance(summary.pending_approval_policies, list)
    assert isinstance(summary.recent_market_events, list)
    assert isinstance(summary.active_guardrails, list)
