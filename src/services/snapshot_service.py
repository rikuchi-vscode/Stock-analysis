"""
意思決定スナップショット & 評価スケジュール登録サービス
STEP 4/5: Verification OK レポート生成時に、分析時点の判断を固定保存し、後日の評価スケジュールを自動登録する
"""

import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from src.contracts.decision_journal import DecisionSnapshot, EvaluationSchedule
from src.repositories.governance_repository import (
    save_decision_snapshot,
    save_evaluation_schedule,
)
from src.tools.market_tools import fetch_market_data
from src.logger import get_logger

logger = get_logger("snapshot_service")



def _get_val(obj: Any, key: str, default: Any = None) -> Any:
    """辞書またはオブジェクトから安全に値を取得"""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def capture_analysis_snapshot_and_schedule(
    analysis_run_id: str,
    ticker: str,
    company_name: str,
    market_data: Dict[str, Any],
    financial_data: Dict[str, Any],
    analysis_result: Any,
    verification_result: Any
) -> DecisionSnapshot:
    """
    Verification OK 時に分析時点の判断を固定スナップショットとして保存し、
    T+7日後、T+30日後の評価スケジュールを自動登録する。
    """
    today_dt = datetime.now()
    today_str = today_dt.strftime("%Y-%m-%d")

    initial_price = float(_get_val(market_data, "current_price", 0.0) or 0.0)
    
    # 指数情報の取得 (日経225等)
    market_index = {}
    try:
        n225_data = fetch_market_data("^N225", period="1d")
        if n225_data.get("current_price"):
            market_index["N225"] = float(n225_data.get("current_price", 0.0))
    except Exception:
        market_index["N225"] = 38500.0

    # スタンス & スコア
    stance = str(_get_val(analysis_result, "investment_stance", "Hold"))
    score_raw = _get_val(analysis_result, "overall_score", 80)
    try:
        overall_score = float(score_raw)
    except Exception:
        overall_score = 80.0

    target_price = _get_val(analysis_result, "target_price", None)
    calc_basis = _get_val(analysis_result, "target_calculation_basis", None)

    # 主要仮説と事前指摘リスク
    hypotheses = []
    exec_summary = _get_val(analysis_result, "executive_summary", "")
    if exec_summary:
        hypotheses.append(str(exec_summary)[:200])
    rationale = _get_val(analysis_result, "recommendation_rationale", "")
    if rationale:
        hypotheses.append(str(rationale)[:200])
    if not hypotheses:
        hypotheses = [f"{company_name} の事業成長性と現在の株価水準に基づく投資判断"]

    risks = []
    d_risks = _get_val(analysis_result, "downside_risks", [])
    if isinstance(d_risks, list):
        risks.extend([str(r) for r in d_risks])
    if not risks:
        risks = ["為替・マクロ経済の急変リスク", "市場全体の調整リスク"]

    # データ品質サマリー
    data_quality = {
        "missing_items": _get_val(financial_data, "missing_items", []),
        "financial_as_of": _get_val(financial_data, "financial_as_of", "直近決算"),
        "market_as_of": _get_val(market_data, "market_as_of", today_str),
    }

    # 1. 意思決定スナップショットの固定保存
    v_status = str(_get_val(verification_result, "status", "OK"))
    snapshot = DecisionSnapshot(
        analysis_run_id=analysis_run_id,
        ticker=ticker,
        company_name=company_name,
        as_of_date=today_str,
        initial_price=initial_price,
        initial_market_index=market_index,
        investment_stance=stance,
        overall_score=overall_score,
        target_price=target_price,
        target_calculation_basis=calc_basis,
        key_hypotheses=hypotheses,
        identified_risks=risks,
        data_quality_snapshot=data_quality,
        verification_status=v_status,
        created_at=today_dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    save_decision_snapshot(snapshot)
    logger.info(f"[{analysis_run_id}] 判断スナップショットを固定保存しました (銘柄: {ticker}, スタンス: {stance}, スコア: {overall_score:.0f})")

    # 2. 評価対象日の自動登録 (T+7日後, T+30日後)
    sched_t7 = EvaluationSchedule(
        schedule_id=f"sched_{analysis_run_id}_t7",
        analysis_run_id=analysis_run_id,
        ticker=ticker,
        evaluation_type="T+7",
        target_date=(today_dt + timedelta(days=7)).strftime("%Y-%m-%d"),
        status="PENDING",
        created_at=today_dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    save_evaluation_schedule(sched_t7)

    sched_t30 = EvaluationSchedule(
        schedule_id=f"sched_{analysis_run_id}_t30",
        analysis_run_id=analysis_run_id,
        ticker=ticker,
        evaluation_type="T+30",
        target_date=(today_dt + timedelta(days=30)).strftime("%Y-%m-%d"),
        status="PENDING",
        created_at=today_dt.strftime("%Y-%m-%d %H:%M:%S")
    )
    save_evaluation_schedule(sched_t30)
    logger.info(f"[{analysis_run_id}] 評価期日 (T+7: {sched_t7.target_date}, T+30: {sched_t30.target_date}) を自動登録しました")

    return snapshot
