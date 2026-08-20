"""
Planner Agent: 分析計画の策定、各エージェントへのタスク割り当て、および再調査計画の再設計を担当
"""

import json
from src.state import AgentState
from src.llm import get_pro_model, extract_text_content, safe_invoke_llm
from langchain_core.messages import SystemMessage, HumanMessage


def run_planner_agent(state: AgentState) -> dict:
    """Planner Agent の実行ノード"""
    ticker = state.get("ticker", "")
    iteration_count = state.get("iteration_count", 0)
    verification_result = state.get("verification_result")

    llm = get_pro_model()

    # 初回計画策定
    if not verification_result or verification_result.get("status") == "OK":
        prompt = f"""
あなたはチーフ・アナリシス・プランナー（Planner Agent）です。
対象の日本株銘柄（銘柄コード: {ticker}）に対して、多角的で高精度な自律分析を行うための「分析計画」を策定してください。

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "tasks": [
    "Market Agent: 株価推移、出来高、移動平均線・RSI等のテクニカル指標算出",
    "Financial Agent: PER/PBR等のバリュエーション、ROE・財務健全性・直近業績の抽出",
    "News Agent: 適時開示・直近ニュース・業界センチメントの収集"
  ],
  "focus_points": [
    "重点調査ポイント1（例: 業績の進捗率と利益率の推移）",
    "重点調査ポイント2（例: 直近の株価レンジとサポートラインの確認）",
    "重点調査ポイント3（例: 業界全体の外部環境・為替影響等）"
  ]
}}
"""
        log_msg = f"[Planner Agent] 初回分析計画を策定しました (銘柄: {ticker})"
    else:
        # 再調査・フィードバック計画の策定
        missing_points = verification_result.get("missing_points", [])
        feedback = verification_result.get("feedback_to_planner", "")
        
        prompt = f"""
あなたはチーフ・アナリシス・プランナー（Planner Agent）です。
前回の分析結果に対して Verification Agent から以下の不足点・改善要求（差し戻し）がありました。
これらの不足を埋めるための「追加調査計画」を立案してください。

【銘柄】: {ticker}
【差し戻し理由・フィードバック】:
{feedback}

【不足ポイント一覧】:
{json.dumps(missing_points, ensure_ascii=False, indent=2)}

【出力要件】
以下の項目を含むJSONフォーマットのみを出力してください:
{{
  "tasks": [
    "不足点を補完するための具体的タスク1",
    "タスク2"
  ],
  "focus_points": [
    "再調査において特に深掘りすべきポイント1",
    "ポイント2"
  ],
  "additional_queries": [
    "ニュースや開示情報で追加検索すべきキーワード1",
    "キーワード2"
  ]
}}
"""
        iteration_count += 1
        log_msg = f"[Planner Agent] Verification Agent からのフィードバックに基づき、第 {iteration_count + 1} 次の追加調査計画を策定しました"

    messages = [
        SystemMessage(content="あなたはプロの分析プランナーです。必ず指定されたJSONフォーマットのみを返してください。"),
        HumanMessage(content=prompt)
    ]

    try:
        response = safe_invoke_llm(llm, messages)
        content = extract_text_content(response)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        plan_data = json.loads(content)
    except Exception:
        plan_data = {
            "tasks": ["データ収集・統合分析の実行"],
            "focus_points": ["財務基盤と市場動向の確認"]
        }

    return {
        "analysis_plan": plan_data,
        "iteration_count": iteration_count,
        "logs": [log_msg]
    }
