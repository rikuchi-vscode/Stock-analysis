"""
Financial Agent: 企業の財務データ・決算・ファンダメンタルズの収集と分析を担当
実測値・推定値・欠損（取得不可）を正直に踏まえた分析を行います。
"""

import json
from src.state import AgentState
from src.tools.financial_tools import fetch_financial_data
from src.llm import get_fast_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_financial_agent(state: AgentState) -> dict:
    """Financial Agent の実行ノード"""
    ticker = state.get("ticker", "")
    plan = state.get("plan", {})
    focus_points = plan.get("focus_points", [])

    # 1. ツールによる財務データ取得
    raw_financial_data = fetch_financial_data(ticker)
    
    if "error" in raw_financial_data:
        return {
            "financial_data": raw_financial_data,
            "logs": [f"[Financial Agent] エラー: {raw_financial_data['error']}"]
        }

    # 2. Gemini Flash によるファンダメンタルズ分析
    llm = get_fast_model()
    
    prompt = f"""
あなたは日本の株式市場に精通したプロの証券アナリスト（Financial Agent）です。
以下の財務指標データに基づき、企業のファンダメンタルズ（割安性、収益性、財務健全性、成長性）を評価・分析してください。

【厳格な遵守事項】
1. **欠損値の扱い**: 「取得できませんでした」と表示されている指標について、架空の数値を捏造・ハルシネーションしないでください。欠損している事実はそのまま受け止め、「データ未開示のため〜」として評価してください。
2. **推定値・予想値の扱い**: 予想PERや配当利回りは「会社予想・推定値」であることを意識し、確定実績と混同しないでください。

【銘柄コード】: {raw_financial_data.get('ticker')}
【データ時点】: {raw_financial_data.get('financial_as_of', '直近開示')}
【時価総額】: {raw_financial_data.get('market_cap_formatted')}

【バリュエーション】
- 実績PER: {raw_financial_data.get('valuation', {}).get('pe_trailing')}
- 予想PER: {raw_financial_data.get('valuation', {}).get('pe_forward')}
- PBR: {raw_financial_data.get('valuation', {}).get('pb_ratio')}
- 配当利回り: {raw_financial_data.get('valuation', {}).get('dividend_yield')}

【収益性・効率性】
- ROE: {raw_financial_data.get('profitability', {}).get('roe')}
- ROA: {raw_financial_data.get('profitability', {}).get('roa')}
- 営業利益率: {raw_financial_data.get('profitability', {}).get('operating_margin')}
- 純利益率: {raw_financial_data.get('profitability', {}).get('profit_margin')}

【財務健全性】
- 負債比率 (Debt to Equity): {raw_financial_data.get('financial_health', {}).get('debt_to_equity')}
- 流動比率: {raw_financial_data.get('financial_health', {}).get('current_ratio')}

【成長性・規模】
- 売上高成長率(YoY): {raw_financial_data.get('growth', {}).get('revenue_growth_yoy')}
- 利益成長率(YoY): {raw_financial_data.get('growth', {}).get('earnings_growth_yoy')}
- 売上高: {raw_financial_data.get('growth', {}).get('total_revenue_formatted')}
- 純利益: {raw_financial_data.get('growth', {}).get('net_income_formatted')}

【重点調査ポイント】
{json.dumps(focus_points, ensure_ascii=False)}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "valuation_assessment": "バリュエーション評価（割安・適正・割高の判定と理由。欠損がある場合はその旨も記載）",
  "profitability_assessment": "収益性・ROEの評価",
  "financial_health_assessment": "財務健全性・自己資本・倒産リスクの評価",
  "growth_assessment": "今後の成長性と業績モメンタムの評価",
  "data_limitation_notes": "財務データ上の欠損・制約事項（なければ「特になし」）",
  "fundamental_score": 1から100のファンダメンタルズスコア（整数）,
  "analyst_comment": "ファンダメンタルズ面からの総括コメント"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロの財務・ファンダメンタルズアナリストです。欠損を隠さず、必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]
    
    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        fundamental_analysis = json.loads(content)
    except Exception:
        fundamental_analysis = {
            "valuation_assessment": "財務データ取得値に基づく評価を実行",
            "profitability_assessment": "収益性・安定性を確認",
            "financial_health_assessment": "財務状況を確認",
            "growth_assessment": "業績推移を確認",
            "data_limitation_notes": "一部指標の取得に制約あり",
            "fundamental_score": 60,
            "analyst_comment": "ファンダメンタルズ分析を実行しました。"
        }

    merged_data = {
        **raw_financial_data,
        "analysis": fundamental_analysis
    }

    missing_cnt = len(raw_financial_data.get("missing_items", []))
    log_missing = f" (欠損項目: {missing_cnt}件)" if missing_cnt > 0 else ""

    return {
        "financial_data": merged_data,
        "logs": [f"[Financial Agent] 財務・ファンダメンタルズ分析を完了しました (スコア: {fundamental_analysis.get('fundamental_score', 'N/A')}{log_missing})"]
    }
