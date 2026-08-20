"""
Planner Adapter モジュール
STEP 2: ResearchPolicy を Planner Agent 向けの DetailedAnalysisPlan / 実行計画へ変換
"""

from typing import List, Dict, Any
from src.contracts.research_policy import ResearchPolicy
from src.contracts.analysis_plan import DetailedAnalysisPlan, TargetStockPlan
from src.contracts.stock_analysis import StockAnalysisRequest


def adapt_policy_to_analysis_plan(policy: ResearchPolicy) -> DetailedAnalysisPlan:
    """ResearchPolicy から詳細な実行計画 DetailedAnalysisPlan を構築"""
    targets: List[TargetStockPlan] = []
    execution_order: List[str] = []

    # 1. 主要銘柄の追加
    for ticker in policy.scope.primary_tickers:
        targets.append(TargetStockPlan(
            ticker=ticker,
            role="primary",
            focus_points=policy.research_questions,
            max_iterations=policy.limits.max_research_cycles
        ))
        execution_order.append(ticker)

    # 2. 比較銘柄の追加
    for ticker in policy.scope.peer_tickers:
        if ticker not in execution_order:
            targets.append(TargetStockPlan(
                ticker=ticker,
                role="peer",
                focus_points=policy.research_questions,
                max_iterations=min(1, policy.limits.max_research_cycles)
            ))
            execution_order.append(ticker)

    return DetailedAnalysisPlan(
        strategy_id=policy.strategy_id,
        mode=policy.mode,
        targets=targets,
        comparative_questions=policy.research_questions,
        time_limit_minutes=policy.limits.time_budget_minutes,
        execution_order=execution_order
    )


def build_stock_analysis_requests(plan: DetailedAnalysisPlan) -> List[StockAnalysisRequest]:
    """DetailedAnalysisPlan から個別の STEP 0 実行リクエストリストを生成"""
    requests: List[StockAnalysisRequest] = []
    for target in plan.targets:
        requests.append(StockAnalysisRequest(
            ticker=target.ticker,
            horizon="medium",
            focus_areas=target.focus_points,
            max_iterations=target.max_iterations,
            correlation_id=plan.strategy_id
        ))
    return requests
