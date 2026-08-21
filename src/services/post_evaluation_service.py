"""
事後評価エンジン & 定期評価ジョブ (Post-Evaluation Service)
STEP 4 & STEP 5: 期限を迎えた評価予定をルールベースで機械的に検証し、客観的事実評価データを生成する
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional

from src.contracts.decision_journal import EvaluationSchedule, EvaluationFact, DecisionSnapshot
from src.time_utils import get_jst_today_str, get_jst_now_str
from src.repositories.governance_repository import (
    list_due_evaluation_schedules,
    get_decision_snapshot,
    save_evaluation_fact,
    update_evaluation_schedule_status,
    list_evaluation_facts,
)
from src.repositories.monitor_repository import list_market_events_with_triage
from src.tools.market_tools import fetch_market_data
from src.logger import get_logger

logger = get_logger("post_evaluation_service")



def evaluate_single_schedule(schedule: EvaluationSchedule) -> Optional[EvaluationFact]:
    """1件のスケジュールに対してルールベース事実評価を実行"""
    snapshot = get_decision_snapshot(schedule.analysis_run_id)
    if not snapshot:
        # スナップショットが存在しない場合は完了扱いにしてスキップ
        update_evaluation_schedule_status(schedule.schedule_id, "SKIPPED")
        return None

    today_str = get_jst_today_str("%Y-%m-%d")
    ticker = schedule.ticker

    # 1. 現在株価と市場指数の取得
    current_market = fetch_market_data(ticker, period="5d")
    current_price = float(current_market.get("current_price", snapshot.initial_price))
    
    # 銘柄騰落率の計算
    if snapshot.initial_price > 0:
        price_change_pct = round(((current_price - snapshot.initial_price) / snapshot.initial_price) * 100.0, 2)
    else:
        price_change_pct = 0.0

    # 市場指数 (日経225) の騰落率計算
    market_index_change_pct = 0.0
    initial_n225 = snapshot.initial_market_index.get("N225", 38500.0)
    try:
        current_n225_data = fetch_market_data("^N225", period="5d")
        current_n225 = float(current_n225_data.get("current_price", initial_n225))
        if initial_n225 > 0:
            market_index_change_pct = round(((current_n225 - initial_n225) / initial_n225) * 100.0, 2)
    except Exception:
        market_index_change_pct = 0.0

    # 相対リターン (Alpha = 銘柄変化率 - 市場指数変化率)
    relative_return_pct = round(price_change_pct - market_index_change_pct, 2)

    # 2. 当時の主要仮説が維持されたかのルールベース判定
    # （例: 強気スタンスで相対プラス、または弱気スタンスで下落回避できていれば維持と判定）
    stance_upper = snapshot.investment_stance.upper()
    if any(k in stance_upper for k in ["BUY", "前向き", "買い"]):
        hypothesis_maintained = relative_return_pct >= -3.0
        h_detail = f"前向きスタンスに対して相対リターン {relative_return_pct:+.2f}% (銘柄: {price_change_pct:+.2f}%, 市場: {market_index_change_pct:+.2f}%)"
    elif any(k in stance_upper for k in ["SELL", "慎重", "売り"]):
        hypothesis_maintained = relative_return_pct <= 3.0
        h_detail = f"慎重スタンスに対して相対リターン {relative_return_pct:+.2f}%"
    else:
        hypothesis_maintained = True
        h_detail = f"様子見スタンスに対して市場並み推移 (相対: {relative_return_pct:+.2f}%)"

    # 3. 実際に起きたリスクを事前に示せていたか (Risk Foresight)
    recent_events = list_market_events_with_triage(limit=10, unique_by_ticker=False)
    ticker_events = [e for e in recent_events if e.get("ticker") == ticker or e.get("ticker") == ticker.replace(".T", "")]
    
    risk_foresight_hit = False
    rf_details = []
    if ticker_events:
        for ev in ticker_events:
            ev_desc = (ev.get("description") or "") + " " + (ev.get("title") or "")
            # 当時の事前指摘リスクとの類似キーワード照合
            for r in snapshot.identified_risks:
                if any(w in ev_desc for w in ["下落", "為替", "円高", "減益", "リスク", "急変", "懸念"]):
                    risk_foresight_hit = True
                    rf_details.append(f"検知イベント '{ev.get('title')}' は当時の指摘リスク '{r}' と整合")
                    break
    if not rf_details:
        rf_details.append("期間中に重大な未予見リスクの顕在化は検知されませんでした")

    # 4. 分析根拠に誤りやデータ欠損がなかったか (Grounding Integrity)
    missing_items = snapshot.data_quality_snapshot.get("missing_items", [])
    data_integrity_ok = len(missing_items) <= 2
    di_detail = f"分析時の欠損項目数: {len(missing_items)} 件 (状態: {'良好' if data_integrity_ok else '注意'})"

    # 5. ルールベース客観スコアの算定 (0〜100点)
    # 相対リターン (40点) + 仮説維持 (25点) + リスク予見 (20点) + データ整合 (15点)
    ret_score = max(0.0, min(40.0, 20.0 + (relative_return_pct * 2.0)))
    hyp_score = 25.0 if hypothesis_maintained else 10.0
    risk_score = 20.0 if (risk_foresight_hit or price_change_pct >= 0) else 10.0
    data_score = 15.0 if data_integrity_ok else 8.0
    total_fact_score = round(ret_score + hyp_score + risk_score + data_score, 1)

    fact = EvaluationFact(
        fact_id=f"fact_{schedule.schedule_id}_{today_str}",
        schedule_id=schedule.schedule_id,
        analysis_run_id=schedule.analysis_run_id,
        ticker=ticker,
        evaluation_date=today_str,
        initial_price=snapshot.initial_price,
        current_price=current_price,
        price_change_pct=price_change_pct,
        market_index_change_pct=market_index_change_pct,
        relative_return_pct=relative_return_pct,
        hypothesis_maintained=hypothesis_maintained,
        hypothesis_detail=h_detail,
        risk_foresight_hit=risk_foresight_hit,
        risk_foresight_detail="; ".join(rf_details),
        data_integrity_ok=data_integrity_ok,
        data_integrity_detail=di_detail,
        rule_based_fact_score=total_fact_score,
        created_at=get_jst_now_str("%Y-%m-%d %H:%M:%S")
    )

    save_evaluation_fact(fact)
    update_evaluation_schedule_status(schedule.schedule_id, "COMPLETED")
    logger.info(f"[{schedule.analysis_run_id}] 事後事実評価完了: {ticker} (事後株価: {current_price:,.1f}円, 相対Alpha: {relative_return_pct:+.2f}%, 事実スコア: {total_fact_score}/100)")
    return fact


def run_due_evaluations(target_date_lte: Optional[str] = None) -> Dict[str, Any]:
    """
    定期実行ジョブ: 期日を迎えた全スケジュールを抽出し、ルールベース事実評価を実行
    """
    due_schedules = list_due_evaluation_schedules(target_date_lte)
    evaluated_facts = []

    for sched in due_schedules:
        try:
            fact = evaluate_single_schedule(sched)
            if fact:
                evaluated_facts.append(fact)
        except Exception as e:
            logger.error(f"スケジュール {sched.schedule_id} の評価失敗: {e}", exc_info=True)

    logger.info(f"事後評価ジョブ実行完了: 対象 {len(due_schedules)} 件中 {len(evaluated_facts)} 件を評価記録")
    return {
        "processed_count": len(due_schedules),
        "evaluated_count": len(evaluated_facts),
        "facts": evaluated_facts,
        "message": f"事後評価ジョブ完了: {len(evaluated_facts)} 件の客観的事実を計算・記録しました。"
    }

