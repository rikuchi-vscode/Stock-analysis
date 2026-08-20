"""
ダッシュボード メトリクス & KPI データ契約
STEP 5: 社長ダッシュボード・総合UI・統合運用基盤
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class SystemKPIMetrics(BaseModel):
    """組織全体の統合KPIメトリクス"""
    total_analyses: int = Field(default=0, description="総分析実施回数 (STEP 0)")
    unique_analyzed_stocks_count: int = Field(default=0, description="分析済み銘柄の種類数 (STEP 0)")
    total_ceo_runs: int = Field(default=0, description="AI CEO 統括実行回数 (STEP 1)")
    total_policies: int = Field(default=0, description="策定されたリサーチ方針数 (STEP 2)")
    pending_approvals: int = Field(default=0, description="人間承認待ち件数 (STEP 2)")
    watched_tickers_count: int = Field(default=0, description="アクティブ監視銘柄数 (STEP 3)")
    market_events_count: int = Field(default=0, description="検知された市場イベント総数 (STEP 3)")
    researches_triggered_count: int = Field(default=0, description="自律起動されたリサーチ回数 (STEP 3)")
    total_journals: int = Field(default=0, description="意思決定ジャーナル記録数 (STEP 4)")
    total_reflections: int = Field(default=0, description="自己反省レポート数 (STEP 4)")
    active_guardrails_count: int = Field(default=0, description="有効なガードレール規則数 (STEP 4)")
    average_accuracy_score: float = Field(default=0.0, description="自己反省における平均精度スコア")
    average_overall_score: float = Field(default=0.0, description="分析部門の平均総合評価スコア")


class DashboardSummary(BaseModel):
    """社長ダッシュボード全体の統合ビューモデル"""
    metrics: SystemKPIMetrics = Field(default_factory=SystemKPIMetrics)
    recent_ceo_summaries: List[Dict[str, Any]] = Field(default_factory=list)
    pending_approval_policies: List[Dict[str, Any]] = Field(default_factory=list)
    recent_market_events: List[Dict[str, Any]] = Field(default_factory=list)
    recent_reflections: List[Dict[str, Any]] = Field(default_factory=list)
    active_guardrails: List[Dict[str, Any]] = Field(default_factory=list)
    generated_at: Optional[str] = None
