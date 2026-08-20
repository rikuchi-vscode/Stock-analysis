"""
AnalysisPlan contract
STEP 2: ResearchPolicy から生成される Planner 向けの実行計画
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class TargetStockPlan(BaseModel):
    """単一銘柄に対する分析タスク計画"""
    ticker: str
    role: str = Field(default="primary", description="'primary' (主要銘柄) または 'peer' (比較銘柄)")
    focus_points: List[str] = Field(default_factory=list)
    max_iterations: int = Field(default=2)


class DetailedAnalysisPlan(BaseModel):
    """方針から展開された具体的な実行計画"""
    strategy_id: str
    mode: str
    targets: List[TargetStockPlan] = Field(default_factory=list)
    comparative_questions: List[str] = Field(default_factory=list)
    time_limit_minutes: int = Field(default=15)
    execution_order: List[str] = Field(default_factory=list, description="実行順序 (tickerリスト)")
