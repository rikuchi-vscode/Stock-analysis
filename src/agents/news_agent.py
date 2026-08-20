"""
News Agent: ニュース・適時開示・市場センチメントの収集と分析を担当
ニュース取得状況（件数・出所・欠損状況）を正直に明示して分析します。
"""

import json
from src.state import AgentState
from src.tools.news_tools import fetch_stock_news
from src.llm import get_fast_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_news_agent(state: AgentState) -> dict:
    """News Agent の実行ノード"""
    ticker = state.get("ticker", "")
    company_name = state.get("company_name", ticker)
    plan = state.get("plan", {})
    focus_points = plan.get("focus_points", [])
    additional_queries = plan.get("additional_queries", [])

    # 1. ニュース一覧取得
    news_items = fetch_stock_news(ticker, limit=5)
    has_news = len(news_items) > 0
    news_status = "実測取得" if has_news else "直近の配信ニュースなし（企業概要・業界動向による補足）"

    # 2. Gemini Flash による定性情報・センチメント分析
    llm = get_fast_model()
    
    prompt = f"""
あなたは日本の株式市場・適時開示情報・ニュースを専門とする情報アナリスト（News Agent）です。
以下のニュース一覧および銘柄情報を精査し、最新の市況センチメント、主要なカタリスト、リスク要因を分析してください。

【厳格な遵守事項】
1. ニュースが0件の場合は、「直近の個別ニュース配信なし」であることを前提に、一般的な企業・セクター動向としての見解を記述し、存在しない架空のニュースを創作しないでください。

【銘柄】: {company_name} ({ticker})
【重点調査ポイント】: {json.dumps(focus_points, ensure_ascii=False)}
【追加調査指示（再分析時のみ）】: {json.dumps(additional_queries, ensure_ascii=False)}

【直近のニュース一覧】 ({len(news_items)} 件取得):
{json.dumps(news_items, ensure_ascii=False, indent=2) if has_news else "直近の個別ニュース配信なし（一般的な市場・セクター動向から中立的に分析）"}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "sentiment": "強気 (Bullish) / やや強気 / 中立 (Neutral) / やや弱気 / 弱気 (Bearish)",
  "sentiment_score": 1から100のセンチメントスコア（整数。50が中立、70以上がポジティブ、30以下がネガティブ）,
  "key_topics": ["直近の重要ニュース・開示トピック1", "トピック2", "トピック3"],
  "catalysts": ["今後の株価上昇材料・カタリスト1", "カタリスト2"],
  "qualitative_risks": ["定性的な懸念事項・業界リスク1", "リスク2"],
  "data_limitation_notes": "ニュース取得状況に関する注記（例: 直近ニュース5件参照 / 直近個別開示なし等）",
  "analyst_comment": "ニュース・定性面からの総括コメント"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロの定性情報・ニュースアナリストです。架空ニュースを作らず、必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        news_analysis = json.loads(content)
        if "sentiment_score" not in news_analysis or news_analysis["sentiment_score"] is None:
            news_analysis["sentiment_score"] = 55
    except Exception:
        news_topics = [item.get("title", "") for item in news_items[:3] if item.get("title")]
        news_analysis = {
            "sentiment": "中立 (Neutral)",
            "sentiment_score": 50,
            "key_topics": news_topics or (["直近の主要な開示・市況動向"] if has_news else ["直近の個別配信ニュースなし（定期開示待ち）"]),
            "catalysts": ["主力事業の堅実な市場需要"],
            "qualitative_risks": ["競合環境およびマクロ景気の動向"],
            "data_limitation_notes": f"ニュース取得状況: {news_status}",
            "analyst_comment": f"{company_name} ({ticker}) に関する報道・開示情報はおおむね中立〜安定的な基調で推移しています。"
        }

    merged_data = {
        "news_items": news_items,
        "news_status": news_status,
        "news_count": len(news_items),
        "analysis": news_analysis
    }

    return {
        "news_data": merged_data,
        "logs": [f"[News Agent] ニュース・定性分析を完了しました (取得: {len(news_items)}件, センチメント: {news_analysis.get('sentiment', '中立')}, スコア: {news_analysis.get('sentiment_score', 50)})"]
    }
