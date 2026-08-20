"""
Market Agent: 市場データ・株価推移・テクニカル指標の収集と分析を担当
実測値とルールベース代替参考値を明確に区別して分析します。
"""

import json
from src.state import AgentState
from src.tools.market_tools import fetch_market_data
from src.llm import get_fast_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_market_agent(state: AgentState) -> dict:
    """Market Agent の実行ノード"""
    ticker = state.get("ticker", "")
    plan = state.get("plan", {})
    focus_points = plan.get("focus_points", [])

    # 1. ツールによる市場データ取得
    raw_market_data = fetch_market_data(ticker)
    
    if "error" in raw_market_data:
        return {
            "market_data": raw_market_data,
            "logs": [f"[Market Agent] エラー: {raw_market_data['error']}"]
        }

    # 2. Gemini Flash によるテクニカル分析要約
    llm = get_fast_model()
    
    prompt = f"""
あなたは日本の株式市場に精通したプロのテクニカルアナリスト（Market Agent）です。
以下の取得データおよび分析計画に基づき、客観的かつ論理的なテクニカル分析要約を作成してください。

【厳格な遵守事項】
1. **実測値と代替値の区別**: 上値抵抗線や下値支持線がボリンジャーバンドや移動平均線による代替値（参考値）である場合は、その旨（参考水準であること）を明記してください。
2. **欠損値・算出不能の扱い**: データ期間不足等で指標が「取得できませんでした」となっている場合は、無理に架空の数値を補完しないでください。

【銘柄情報】
- 銘柄コード: {raw_market_data.get('ticker')}
- 会社名: {raw_market_data.get('company_name')}
- 業種: {raw_market_data.get('sector')}
- データ時点: {raw_market_data.get('market_as_of', '最新')}
- 現在値: {raw_market_data.get('current_price')} 円 (前日比: {raw_market_data.get('price_change_pct')}%)
- 出来高: {raw_market_data.get('volume'):,} 株
- 移動平均線 (SMA25 / SMA75): {raw_market_data.get('sma_25')} / {raw_market_data.get('sma_75')}
- トレンド判定: {raw_market_data.get('sma_trend')}
- RSI(14): {raw_market_data.get('rsi_14')} ({raw_market_data.get('rsi_status')})
- ボリンジャーバンド: 上限 {raw_market_data.get('bb_upper')} 円 / 下限 {raw_market_data.get('bb_lower')} 円
- 52週高値/安値: {raw_market_data.get('high_52w')} 円 / {raw_market_data.get('low_52w')} 円

【重点調査ポイント（Plannerからの指示）】
{json.dumps(focus_points, ensure_ascii=False)}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "trend_summary": "短期・中期のトレンド分析（強気/弱気/保ち合いとその根拠）",
  "technical_signals": ["主要なテクニカルシグナル1", "シグナル2", "シグナル3"],
  "support_resistance": {{
    "resistance": "想定される上値抵抗線（価格帯と参考値の根拠）",
    "support": "想定される下値支持線（価格帯と参考値の根拠）"
  }},
  "technical_score": 1から100のテクニカルスコア（整数）,
  "analyst_comment": "テクニカル面からの総括コメント"
}}
"""

    messages = [
        SystemMessage(content="あなたはプロのテクニカルアナリストです。実測値と参考値を区別し、必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)
        
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
            
        technical_analysis = json.loads(content)
    except Exception:
        # LLM失敗時は market_tools が算出した高品質なデフォルトテクニカル分析を採用
        default_analysis = raw_market_data.get("analysis", {})
        technical_analysis = {
            "trend_summary": default_analysis.get("trend_summary", f"株価は {raw_market_data.get('sma_trend', '横ばい')} の基調で推移しています。"),
            "technical_signals": default_analysis.get("technical_signals", [f"RSI: {raw_market_data.get('rsi_status', '中立')}"]),
            "support_resistance": default_analysis.get("support_resistance", {
                "resistance": f"{raw_market_data.get('bb_upper', '目先抵抗線なし')} 円（参考値）",
                "support": f"{raw_market_data.get('bb_lower', '目先支持線なし')} 円（参考値）"
            }),
            "technical_score": default_analysis.get("technical_score", 65),
            "analyst_comment": default_analysis.get("analyst_comment", "テクニカル指標に基づくレンジ内推移")
        }

    merged_data = {
        **raw_market_data,
        "analysis": technical_analysis
    }

    company_name = raw_market_data.get("company_name", state.get("company_name", ticker))
    sector = raw_market_data.get("sector", state.get("sector", "不明"))

    return {
        "company_name": company_name,
        "sector": sector,
        "market_data": merged_data,
        "logs": [f"[Market Agent] 市場データ・テクニカル分析を完了しました (スコア: {technical_analysis.get('technical_score', 'N/A')})"]
    }
