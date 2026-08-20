"""
Event Triage Agent モジュール
STEP 3: 市場・開示・ニュースイベントの重要度・緊急度判定および自律調査トリガー決定
"""

import uuid
import json
import re
from typing import Dict, Any, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm import get_fast_model, extract_text_content
from src.contracts.watch_item import MarketEvent, TriageResult


TRIAGE_SYSTEM_PROMPT = """あなたはAI組織のイベントトリアージ責任者（Event Triage Agent）です。
市場で検知された急変イベント、決算発表、適時開示、ニュース速報を評価し、株価分析部門に対する自律調査タスクの起動要否を判定してください。

【アクションの選択肢】
- "TRIGGER_RESEARCH": 重要度が高く、直ちにリサーチ方針策定または分析を実行すべき重大イベント
- "QUEUE_RESEARCH": 優先度付きで調査キューに追加し、順次調査すべきイベント
- "NOTIFY_ONLY": 調査は不要だが、経営者/投資家への通知・ログ記録を行うべきイベント
- "IGNORE": 市場のノイズであり無視すべきイベント

【出力仕様】
必ず以下のJSONフォーマットのみを出力してください（Markdownコードブロックは不要です）。
{
  "action": "TRIGGER_RESEARCH", // "TRIGGER_RESEARCH" | "QUEUE_RESEARCH" | "NOTIFY_ONLY" | "IGNORE"
  "reason": "トリアージ判定の具体的な理由",
  "suggested_mode": "single_stock", // "single_stock" | "deep_dive_risk" | "peer_comparison"
  "priority": "high" // "low" | "medium" | "high" | "urgent"
}
"""


def triage_market_event(event: MarketEvent) -> TriageResult:
    """
    市場イベントを評価し、トリアージ結果を返す。
    ルールベースとLLMを併用し、高速・高堅牢に判定。
    """
    triage_id = f"trg_{uuid.uuid4().hex[:10]}"

    # 1. ルールベースによる基本判定
    action = "NOTIFY_ONLY"
    priority = "medium"
    suggested_mode = "single_stock"
    reason = f"{event.title} を検知しました。"

    if event.severity in ["CRITICAL", "HIGH"]:
        action = "TRIGGER_RESEARCH"
        priority = "urgent" if event.severity == "CRITICAL" else "high"
        suggested_mode = "deep_dive_risk" if "リスク" in event.title or "下落" in event.title else "single_stock"
        reason = f"重要度 {event.severity} のイベント ({event.event_type}) を検知したため、自律リサーチを即時起動します。"
    elif event.severity == "MEDIUM":
        action = "QUEUE_RESEARCH"
        priority = "medium"
        reason = f"中程度の市場変動 ({event.event_type}) を検知したため、調査キューに登録します。"
    elif event.severity == "LOW":
        action = "NOTIFY_ONLY"
        priority = "low"
        reason = "軽微なイベントのため通知のみ行います。"

    # 2. LLMによる文脈考慮トリアージの試行
    try:
        model = get_fast_model(temperature=0.0)
        messages = [
            SystemMessage(content=TRIAGE_SYSTEM_PROMPT),
            HumanMessage(content=f"イベント情報:\n種別: {event.event_type}\n銘柄: {event.ticker} ({event.company_name})\n重要度: {event.severity}\nタイトル: {event.title}\n詳細: {event.description}")
        ]
        response = model.invoke(messages)
        text = extract_text_content(response)

        clean_json = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"^```\s*", "", clean_json, flags=re.MULTILINE)
        data = json.loads(clean_json.strip())

        return TriageResult(
            triage_id=triage_id,
            event_id=event.event_id,
            action=data.get("action", action),
            reason=data.get("reason", reason),
            suggested_mode=data.get("suggested_mode", suggested_mode),
            priority=data.get("priority", priority)
        )

    except Exception:
        # LLM失敗時のルールベースフォールバック
        return TriageResult(
            triage_id=triage_id,
            event_id=event.event_id,
            action=action,
            reason=reason,
            suggested_mode=suggested_mode,
            priority=priority
        )
