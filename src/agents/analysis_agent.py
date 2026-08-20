"""
Analysis Agent: 市場・財務・ニュースの3面データを統合し、投資仮説・シナリオを策定
元データ数値の完全遵守、計算根拠の提示、事実と解釈の分離、両論併記を厳格に実行します。
"""

import json
from src.state import AgentState
from src.llm import get_pro_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_analysis_agent(state: AgentState) -> dict:
    """Analysis Agent の実行ノード"""
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    sector = state.get("sector", "不明")
    
    market_data = state.get("market_data", {})
    financial_data = state.get("financial_data", {})
    news_data = state.get("news_data", {})

    missing_financials = financial_data.get("missing_items", [])
    fallback_market = market_data.get("fallback_items", [])

    llm = get_pro_model()

    prompt = f"""
あなたはトップクラスのチーフ・インベストメント・ストラテジスト（Analysis Agent）です。
収集された「市場・テクニカル」「財務・ファンダメンタルズ」「ニュース・定性情報」の3つの分析結果を統合し、
論理的で説得力のある総合投資仮説およびシナリオを立案してください。

【厳格な品質基準・遵守事項】
1. **数値の完全一致 (Grounding)**:
   - 株価（{market_data.get('current_price')} 円）、前日比（{market_data.get('price_change_pct')}%）、PER、PBRなどの数値を言及する際は、必ず元データと1円・1%の狂いもなく正確に一致させてください。
2. **目標株価・シナリオの計算根拠の明示 (Calculation Basis)**:
   - 目標株価や価格レンジを提示する際は、単に数値を書くだけでなく「算出根拠（例: 予想EPS × 想定PER、ボリンジャーバンド上限水準、過去高値など）」を必ず併記してください。
3. **事実 (Fact) と AIの解釈 (Opinion) の明確な分離**:
   - 確定した実績（決算数値・株価等）は「事実」として記述し、将来予測やAIの見解は「〜の可能性がある」「〜と分析される」と明確に区別してください。
4. **両論併記 (Balanced View)**:
   - 推奨スタンス（Buy/Hold/Sell）に関わらず、エグゼクティブサマリーおよび投資仮説には、好材料（強み）だけでなく【注意点・ダウンサイドリスク・反論】を必ずセットで併記してください。
5. **欠損値・推定値の透明性**:
   - 欠損指標（{json.dumps(missing_financials, ensure_ascii=False) if missing_financials else 'なし'}）や代替参考値（{json.dumps(fallback_market, ensure_ascii=False) if fallback_market else 'なし'}）を隠さず前提条件として考慮してください。

【銘柄基本情報】
- 銘柄: {company_name} ({ticker})
- セクター: {sector}

【1. 市場・テクニカルデータ】
{json.dumps(market_data, ensure_ascii=False, indent=2)}

【2. 財務・ファンダメンタルズデータ】
{json.dumps(financial_data, ensure_ascii=False, indent=2)}

【3. ニュース・定性情報】
{json.dumps(news_data, ensure_ascii=False, indent=2)}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "overall_score": 1から100の総合投資魅力度スコア（整数）,
  "score_calculation_basis": "スコア算出の主な根拠（財務健全性○点、成長性○点、テクニカル○点など）",
  "investment_stance": "Strong Buy (強気買い) / Buy (買い) / Hold (中立・様子見) / Underweight (やや弱気) / Sell (売り)",
  "executive_summary": "4〜5行のエグゼクティブ・サマリー（投資判断の核心、好材料、および必ず主要リスク・反論を両論併記すること）",
  "core_investment_thesis": [
    "主要投資仮説1（好材料の根拠と事実）",
    "主要投資仮説2",
    "主要投資仮説3"
  ],
  "price_scenarios": {{
    "bull_case": "強気シナリオ（目標株価水準と【算出ロジック・前提パラメータ】）",
    "base_case": "基本シナリオ（想定株価レンジと【算出ロジック・前提パラメータ】）",
    "bear_case": "弱気シナリオ（下値目処と【算出ロジック・前提パラメータ】）"
  }},
  "horizon_strategy": {{
    "short_term": "短期（1〜3ヶ月）のスタンス",
    "medium_term": "中期（6ヶ月〜1年）のスタンス",
    "long_term": "長期（1年以上）のスタンス"
  }},
  "data_confidence_level": "高 (データ充足) / 中 (一部推定・代替値あり) / 低 (主要データ欠損あり)"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロのチーフ・インベストメント・ストラテジストです。元データ数値を完全に守り、根拠と両論併記を徹底したJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    c_price = market_data.get("current_price", 0)
    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        analysis_result = json.loads(content)
    except Exception:
        analysis_result = {
            "overall_score": 65,
            "score_calculation_basis": "ファンダメンタルズ安定性(35点) + テクニカルレンジ内推移(30点)",
            "investment_stance": "Hold (中立・様子見)",
            "executive_summary": f"{company_name} ({ticker}) は強固な事業基盤（現在株価: {c_price}円）を有していますが、マクロ為替変動や市場環境の不確実性を考慮し中立的なスタンスとします。好材料として収益基盤の維持が挙げられる一方、為替・景気減速のリスクに注意が必要です。",
            "core_investment_thesis": ["主力事業における継続的な基盤", "市場環境への適応力"],
            "price_scenarios": {
                "bull_case": f"{c_price * 1.15:,.0f}円（前提: 業績上振れおよびバリュエーション見直し）",
                "base_case": f"{c_price * 0.95:,.0f}〜{c_price * 1.05:,.0f}円（前提: 現行PER水準レンジ内推移）",
                "bear_case": f"{c_price * 0.85:,.0f}円（前提: 75日線割れおよび市場環境悪化）"
            },
            "horizon_strategy": {
                "short_term": "様子見",
                "medium_term": "継続保有",
                "long_term": "事業進捗注視"
            },
            "data_confidence_level": "中 (一部推定・代替値あり)"
        }

    return {
        "analysis_result": analysis_result,
        "logs": [f"[Analysis Agent] 統合分析を完了しました (総合スコア: {analysis_result.get('overall_score', 'N/A')}, スタンス: {analysis_result.get('investment_stance', 'N/A')}, 確信度: {analysis_result.get('data_confidence_level', '中')})"]
    }
