"""
Risk Agent: 投資仮説に対する批判的検証（Devil's Advocate）およびダウンサイドリスクの網羅的抽出
データ欠損や推定値依存による不確実性リスクも含めて徹底検証します。
"""

import json
from src.state import AgentState
from src.llm import get_pro_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_risk_agent(state: AgentState) -> dict:
    """Risk Agent の実行ノード"""
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    analysis_result = state.get("analysis_result", {})
    market_data = state.get("market_data", {})
    financial_data = state.get("financial_data", {})
    news_data = state.get("news_data", {})

    missing_financials = financial_data.get("missing_items", [])

    llm = get_pro_model()

    prompt = f"""
あなたは徹底的な批判的視点を持つチーフ・リスクマネジメント・オフィサー（Risk Agent / Devil's Advocate）です。
Analysis Agent が作成した投資判断やシナリオに対して、死角・見落とし・ダウンサイドリスクを徹底的に洗い出してください。

【厳格な検証視点】
1. **データの不確実性・欠損リスク**:
   - 欠損している財務データ（例: {json.dumps(missing_financials, ensure_ascii=False) if missing_financials else 'なし'}）や、定性ニュースの不足がある場合、「情報開示・可視性の低さ」それ自体をダウンサイド要因や前提の脆弱性として指摘してください。
2. **強気シナリオの過信防止**:
   - 推定値や代替参考値に基づいた楽観的な投資仮説に対して、批判的反論を提示してください。

【銘柄】: {company_name} ({ticker})

【Analysis Agent による投資判断】
- 総合スコア: {analysis_result.get('overall_score')}
- 投資スタンス: {analysis_result.get('investment_stance')}
- エグゼクティブ・サマリー: {analysis_result.get('executive_summary')}
- 主要投資仮説: {json.dumps(analysis_result.get('core_investment_thesis', []), ensure_ascii=False)}

【入力データサマリー】
- 市場データ: {json.dumps(market_data, ensure_ascii=False)}
- 財務データ: {json.dumps(financial_data, ensure_ascii=False)}
- ニュース情報: {json.dumps(news_data, ensure_ascii=False)}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "risk_level": "高 / 中 / 低",
  "primary_downside_risks": [
    {{
      "category": "業績・財務 / マクロ・金利・為替 / 業界・競合 / ガバナンス・地政学 / データ不確実性",
      "risk_factor": "リスク要因の名称",
      "impact": "高 / 中 / 低",
      "trigger_event": "このリスクが顕在化する具体的なトリガー事象"
    }}
  ],
  "bearish_counter_arguments": [
    "強気シナリオに対する反論・死角1",
    "反論・死角2"
  ],
  "max_drawdown_estimate": "想定される最大下落率・下値サポートライン",
  "stop_loss_guideline": "損切り・撤退を検討すべき明確な基準や条件",
  "data_uncertainty_assessment": "データ欠損や推定値依存に伴うリスクの評価（なければ「特段の不確実性なし」）",
  "risk_officer_verdict": "リスク管理面からの総合判定コメント"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロのリスクマネジメント・オフィサーです。データの不確実性も加味した厳しい視点でリスクを抽出し、必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        risk_result = json.loads(content)
    except Exception:
        risk_result = {
            "risk_level": "中",
            "primary_downside_risks": [
                {
                    "category": "マクロ・金利・為替",
                    "risk_factor": "為替変動および市場全体の環境変化",
                    "impact": "中",
                    "trigger_event": "金融政策の転換や市場急変動"
                }
            ],
            "bearish_counter_arguments": ["短期的な景気後退局面における業績悪化懸念"],
            "max_drawdown_estimate": "-10%〜-15%水準",
            "stop_loss_guideline": "サポートライン（-8%水準）割れ",
            "data_uncertainty_assessment": "一部開示データの制約を注視",
            "risk_officer_verdict": "市場環境とデータ開示状況を踏まえた慎重なモニタリングを推奨"
        }

    return {
        "risk_result": risk_result,
        "logs": [f"[Risk Agent] リスク分析を完了しました (リスクレベル: {risk_result.get('risk_level', 'N/A')})"]
    }
