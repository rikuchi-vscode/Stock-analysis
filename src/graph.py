"""
LangGraph オーケストレーションワークフロー定義
マルチエージェントの実行フロー、並行データ収集、Verification Agent による再帰ループを構築します。
"""

from langgraph.graph import StateGraph, START, END
from src.state import AgentState
from src.agents.planner_agent import run_planner_agent
from src.agents.market_agent import run_market_agent
from src.agents.financial_agent import run_financial_agent
from src.agents.news_agent import run_news_agent
from src.agents.analysis_agent import run_analysis_agent
from src.agents.risk_agent import run_risk_agent
from src.agents.verification_agent import run_verification_agent
from src.report import run_report_generator


def route_after_verification(state: AgentState) -> str:
    """
    Verification Agent の判定結果に基づく条件分岐ルーター
    - status == 'NG' かつ iteration_count < max_iterations: Plannerへ戻り再調査
    - status == 'OK' または 上限到達: レポート生成ノードへ進む
    """
    verification_result = state.get("verification_result", {})
    status = verification_result.get("status", "OK")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 2)

    if status == "NG" and iteration_count < max_iterations:
        return "replan"
    return "finalize"


def create_stock_analysis_graph():
    """LangGraph ワークフローグラフを構築・コンパイル"""
    builder = StateGraph(AgentState)

    # ノード登録
    builder.add_node("planner", run_planner_agent)
    builder.add_node("market_agent", run_market_agent)
    builder.add_node("financial_agent", run_financial_agent)
    builder.add_node("news_agent", run_news_agent)
    builder.add_node("analysis_agent", run_analysis_agent)
    builder.add_node("risk_agent", run_risk_agent)
    builder.add_node("verification_agent", run_verification_agent)
    builder.add_node("report_generator", run_report_generator)

    # エッジ接続
    # 1. 開始 -> Planner
    builder.add_edge(START, "planner")

    # 2. Planner -> データ収集エージェント群（並行実行）
    builder.add_edge("planner", "market_agent")
    builder.add_edge("planner", "financial_agent")
    builder.add_edge("planner", "news_agent")

    # 3. データ収集完了 -> Analysis Agent (統合分析)
    builder.add_edge("market_agent", "analysis_agent")
    builder.add_edge("financial_agent", "analysis_agent")
    builder.add_edge("news_agent", "analysis_agent")

    # 4. Analysis -> Risk -> Verification
    builder.add_edge("analysis_agent", "risk_agent")
    builder.add_edge("risk_agent", "verification_agent")

    # 5. Verification -> 条件分岐（OKならレポート生成、NGならPlannerへ再調査フィードバック）
    builder.add_conditional_edges(
        "verification_agent",
        route_after_verification,
        {
            "replan": "planner",
            "finalize": "report_generator"
        }
    )

    # 6. レポート生成 -> 完了
    builder.add_edge("report_generator", END)

    return builder.compile()
