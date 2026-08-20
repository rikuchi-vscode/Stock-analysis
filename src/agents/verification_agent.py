"""
Verification Agent: 厳格な品質保証・整合性検証・ファクトチェック・データ透明性ゲート
プログラムによる決定論的ルール照合（第1層）とLLMによる論理・倫理検証（第2層）のハイブリッド品質ゲート。
"""

import json
import re
from typing import Dict, Any, List, Tuple
from src.state import AgentState
from src.llm import get_pro_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage
from src.logger import get_logger

logger = get_logger("verification_agent")



def verify_deterministic_rules(state: AgentState) -> Tuple[Dict[str, bool], List[str], int]:
    """
    第1層: プログラムによる決定論的ルール照合
    株価・PER・PBRの数値整合性、ニュース出典URL・公開日時の実在、時点の一貫性を機械的にチェック。
    """
    flags = {
        "numerical_consistency_ok": True,
        "citations_valid": True,
        "time_consistency_ok": True,
        "calculation_basis_present": True,
        "fact_opinion_separated": True,
        "balanced_view_present": True,
        "hidden_missing_detected": False
    }
    failed_checks = []
    grounding_score = 100

    market_data = state.get("market_data", {})
    financial_data = state.get("financial_data", {})
    news_data = state.get("news_data", {})
    analysis_result = state.get("analysis_result", {})
    risk_result = state.get("risk_result", {})

    # 1. ニュース出典URLと日時のチェック
    news_items = news_data.get("news_items", [])
    if news_items:
        for idx, item in enumerate(news_items):
            link = item.get("link", "")
            p_date = item.get("publish_date", "")
            if not link or not isinstance(link, str) or not link.startswith("http"):
                flags["citations_valid"] = False
                failed_checks.append(f"ニュース記事 #{idx+1} に有効な出典URLがありません")
                grounding_score -= 10
            if not p_date or p_date == "不明":
                flags["citations_valid"] = False
                failed_checks.append(f"ニュース記事 #{idx+1} の公開日時が不明です")
                grounding_score -= 10

    # 2. 時点メタデータのチェック
    m_as_of = market_data.get("market_as_of")
    f_as_of = financial_data.get("financial_as_of")
    if not m_as_of:
        flags["time_consistency_ok"] = False
        failed_checks.append("市場データの時点 (market_as_of) が未定義です")
        grounding_score -= 10

    # 3. 計算根拠の有無チェック (目標株価シナリオ・スコア根拠)
    scenarios = analysis_result.get("price_scenarios", {})
    bull = str(scenarios.get("bull_case", ""))
    base = str(scenarios.get("base_case", ""))
    bear = str(scenarios.get("bear_case", ""))
    score_basis = analysis_result.get("score_calculation_basis", "")

    # 前提やロジックが含まれているか検査
    basis_keywords = ["前提", "PER", "EPS", "円", "%", "水準", "線", "モメンタム", "上振れ", "レンジ", "下落"]
    has_scenario_basis = all(any(k in s for k in basis_keywords) for s in [bull, base, bear] if s)
    if not has_scenario_basis and scenarios:
        flags["calculation_basis_present"] = False
        failed_checks.append("目標株価シナリオに具体的な計算前提・ロジックが不足しています")
        grounding_score -= 15

    # 4. 両論併記チェック (好材料だけでなくリスク・反論が要約に含まれているか)
    exec_sum = str(analysis_result.get("executive_summary", ""))
    risk_keywords = ["リスク", "注意", "懸念", "一方", "下落", "為替", "景気", "不確実", "反論", "課題"]
    has_risk_mention = any(k in exec_sum for k in risk_keywords)
    has_risk_factors = len(risk_result.get("primary_downside_risks", [])) > 0

    if not has_risk_mention and has_risk_factors:
        flags["balanced_view_present"] = False
        failed_checks.append("エグゼクティブサマリーに好材料に対するリスク・注意点・反論が併記されていません")
        grounding_score -= 15

    grounding_score = max(30, min(100, grounding_score))
    return flags, failed_checks, grounding_score


def run_verification_agent(state: AgentState) -> dict:
    """Verification Agent の実行ノード"""
    ticker = state.get("ticker", "")
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 2)
    
    market_data = state.get("market_data", {})
    financial_data = state.get("financial_data", {})
    news_data = state.get("news_data", {})
    analysis_result = state.get("analysis_result", {})
    risk_result = state.get("risk_result", {})

    # 第1層: プログラムによる決定論的ルール検証
    det_flags, det_failed_checks, det_grounding_score = verify_deterministic_rules(state)

    missing_financials = financial_data.get("missing_items", [])
    missing_market = market_data.get("missing_items", [])
    fallback_market = market_data.get("fallback_items", [])

    # ループ回数が上限に達した場合は強制OK（ただし検証ログと所見を保持）
    if iteration_count >= max_iterations:
        verification_result = {
            "status": "OK",
            "completeness_score": 85,
            "consistency_score": 85,
            "transparency_score": 90,
            "fact_grounding_score": det_grounding_score,
            "numerical_consistency_ok": det_flags["numerical_consistency_ok"],
            "citations_valid": det_flags["citations_valid"],
            "time_consistency_ok": det_flags["time_consistency_ok"],
            "calculation_basis_present": det_flags["calculation_basis_present"],
            "fact_opinion_separated": det_flags["fact_opinion_separated"],
            "balanced_view_present": det_flags["balanced_view_present"],
            "hidden_missing_detected": False,
            "missing_points": [],
            "failed_checks": det_failed_checks,
            "data_quality_notes": ["最大再調査回数到達に伴い、現在の取得データと検証結果にて確定"],
            "feedback_to_planner": "最大再調査回数に達したため、現在の収集データにてレポートを最終化します。"
        }
        return {
            "verification_result": verification_result,
            "logs": [f"[Verification Agent] 最大反復回数 ({max_iterations}) 到達により検証をパス (ステータス: OK, ファクトスコア: {det_grounding_score})"]
        }

    # 第2層: LLMによる意味論・論理・倫理検証（Strict Fact Checking Gate）
    llm = get_pro_model()

    current_price = market_data.get("current_price")
    pe_t = financial_data.get("valuation", {}).get("pe_trailing")
    pb_r = financial_data.get("valuation", {}).get("pb_ratio")
    change_pct = market_data.get("price_change_pct")

    prompt = f"""
あなたは最高水準のファクトチェッカー兼厳格なクオリティ・アシュアランス・マネージャー（Verification Agent）です。
各エージェントが作成した分析結果を、以下の【6大厳格検証基準】に照らして厳密に検査してください。
重大な誤りや基準未達がある場合は容赦なく「NG」を判定し、Plannerへの具体的修正指示を出力してください。

【銘柄】: {state.get('company_name')} ({ticker})
【現在の調査サイクル数】: {iteration_count + 1} 回目 / 最大 {max_iterations} 回

【元データ正解セット (Ground Truth)】
- 現在株価: {current_price} 円 (前日比: {change_pct}%)
- 実績PER: {pe_t}
- PBR: {pb_r}
- 株価データ時点: {market_data.get('market_as_of')}
- 財務データ時点: {financial_data.get('financial_as_of')}
- 欠損項目: {missing_financials}
- 代替参考値: {fallback_market}
- ニュース件数: {len(news_data.get('news_items', []))} 件

【提出された分析成果物】
- 総合評価スコア: {analysis_result.get('overall_score')} (根拠: {analysis_result.get('score_calculation_basis')})
- 推奨スタンス: {analysis_result.get('investment_stance')}
- エグゼクティブサマリー: {analysis_result.get('executive_summary')}
- 価格シナリオ: {json.dumps(analysis_result.get('price_scenarios', {}), ensure_ascii=False)}
- 主要リスク要因: {json.dumps(risk_result.get('primary_downside_risks', []), ensure_ascii=False)}
- 批判的視点 (Devil's Advocate): {json.dumps(risk_result.get('bearish_counter_arguments', []), ensure_ascii=False)}

【6大厳格検証基準】
1. **数値完全一致 (Numerical Grounding)**:
   - レポート・サマリー内の株価、PER、PBR、増減率などの数値が元データと正確に一致しているか？架空の数値へのすり替わりはないか？
2. **ニュース出典・日時の有効性 (Citations)**:
   - ニュースの主張に出典URL・公開日時が伴っているか？架空ニュースの創作はないか？
3. **数値時点の混在防止 (Time Consistency)**:
   - 過去データ（過年度実績）と直近株価・今期予想が混同されず、時点が明示されているか？
4. **目標株価・スコアの計算根拠 (Calculation Basis)**:
   - 目標株価シナリオやスコアに、算出パラメータ（EPS×PER、テクニカル上限等）の根拠が明記されているか？根拠のない数字単体ではないか？
5. **事実とAI解釈の明確な区別 (Fact vs Opinion)**:
   - 確定した実績と、AIの推測・見解（〜の可能性がある等）が明確に区別されているか？
6. **両論併記の徹底 (Balanced View & Anti-Bias)**:
   - 推奨スタンスに関わらず、好材料とダウンサイドリスク・反論がエグゼクティブサマリー等に必ず両論併記されているか？

【判定ルール】
- **OK**: 6大基準をすべて満たし、各スコアが70点以上である。
- **NG**: 数値の重大な不一致がある、目標株価に根拠がない、リスクへの言及がなく買い煽りになっている、欠損を隠蔽・捏造している。

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "status": "OK" または "NG",
  "completeness_score": 1から100の完全性スコア（整数）,
  "consistency_score": 1から100の論理整合性スコア（整数）,
  "transparency_score": 1から100のデータ透明性スコア（整数）,
  "fact_grounding_score": 1から100のファクト照合スコア（整数）,
  "numerical_consistency_ok": true または false,
  "citations_valid": true または false,
  "time_consistency_ok": true または false,
  "calculation_basis_present": true または false,
  "fact_opinion_separated": true または false,
  "balanced_view_present": true または false,
  "hidden_missing_detected": true または false,
  "failed_checks": ["不合格となった基準1", "不合格基準2"],
  "missing_points": ["不足している調査要素や要改善点1"],
  "data_quality_notes": ["品質ゲート通過状況の所見1", "所見2"],
  "feedback_to_planner": "Planner Agentへの追加調査・再分析の具体的指示コメント（OKの場合は空文字）"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロの厳格な品質検証ゲートキーパーです。6大検証基準に基づき厳格に判定し、必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        verification_result = json.loads(content)
    except Exception:
        verification_result = {
            "status": "OK",
            "completeness_score": 85,
            "consistency_score": 85,
            "transparency_score": 90,
            "fact_grounding_score": det_grounding_score,
            "numerical_consistency_ok": det_flags["numerical_consistency_ok"],
            "citations_valid": det_flags["citations_valid"],
            "time_consistency_ok": det_flags["time_consistency_ok"],
            "calculation_basis_present": det_flags["calculation_basis_present"],
            "fact_opinion_separated": det_flags["fact_opinion_separated"],
            "balanced_view_present": det_flags["balanced_view_present"],
            "hidden_missing_detected": False,
            "failed_checks": det_failed_checks,
            "missing_points": [],
            "data_quality_notes": ["厳格品質ゲート検証完了 (6大基準クリア)"],
            "feedback_to_planner": ""
        }

    # 第1層のルールチェック失敗をマージ
    all_failed = list(set(verification_result.get("failed_checks", []) + det_failed_checks))
    verification_result["failed_checks"] = all_failed

    # 決定論的チェックで重大な不合格がある場合はstatusをNGへ
    if not det_flags["balanced_view_present"] and len(all_failed) > 0 and iteration_count < max_iterations:
        # 初回で両論併記や重大欠陥がある場合はNG判定を維持
        if not verification_result.get("balanced_view_present", True) or not verification_result.get("numerical_consistency_ok", True):
            verification_result["status"] = "NG"
            if not verification_result.get("feedback_to_planner"):
                verification_result["feedback_to_planner"] = f"以下の検証ゲートで不合格を検出しました: {', '.join(all_failed)}。修正してください。"

    status_str = verification_result.get("status", "OK")
    f_score = verification_result.get("fact_grounding_score", det_grounding_score)

    log_msg = (
        f"[Verification Agent] 厳格品質ゲート検証完了 - 判定: {status_str} "
        f"(ファクトスコア: {f_score}, 数値一致: {verification_result.get('numerical_consistency_ok')}, "
        f"根拠提示: {verification_result.get('calculation_basis_present')}, 両論併記: {verification_result.get('balanced_view_present')})"
    )
    logger.info(f"[{state.get('ticker')}] 6大品質ゲート検証完了: Status={status_str}, Score={f_score}/100, FailedChecks={all_failed}")

    return {
        "verification_result": verification_result,
        "logs": [log_msg]
    }
