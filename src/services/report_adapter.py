"""
STEP 0 (株価分析部門) の実行結果を CEO レイヤー向けレスポンスへ変換・適合するアダプター
"""

from typing import Dict, Any
from src.contracts.stock_analysis import StockAnalysisResponse


def adapt_step0_to_response(final_state: Dict[str, Any]) -> StockAnalysisResponse:
    """AgentState の最終辞書から StockAnalysisResponse DTO を構築"""
    ticker = final_state.get("ticker", "")
    company_name = final_state.get("company_name", ticker)
    sector = final_state.get("sector", "不明")
    
    analysis_result = final_state.get("analysis_result", {})
    risk_result = final_state.get("risk_result", {})
    verification_result = final_state.get("verification_result", {})
    market_data = final_state.get("market_data", {})
    financial_data = final_state.get("financial_data", {})
    news_data = final_state.get("news_data", {})
    
    overall_score = analysis_result.get("overall_score")
    if isinstance(overall_score, str) and overall_score.isdigit():
        overall_score = int(overall_score)
    elif not isinstance(overall_score, int):
        overall_score = None

    return StockAnalysisResponse(
        analysis_id=final_state.get("analysis_id"),
        ticker=ticker,
        company_name=company_name,
        sector=sector,
        overall_score=overall_score,
        investment_stance=analysis_result.get("investment_stance"),
        verification_status=verification_result.get("status", "OK"),
        iteration_count=final_state.get("iteration_count", 0),
        final_report=final_state.get("final_report", ""),
        report_path=final_state.get("report_path", ""),
        analysis_result=analysis_result,
        risk_result=risk_result,
        market_data=market_data,
        financial_data=financial_data,
        news_data=news_data,
        logs=final_state.get("logs", [])
    )
