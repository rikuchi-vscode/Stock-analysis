"""
Reflection Agent モジュール
STEP 4: 意思決定ジャーナルの初期仮説と実際の分析結果を対比し、自己反省・見落とし・改善教訓を導出
"""

import uuid
import json
import re
from typing import Dict, Any, Optional, List
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm import get_pro_model, extract_text_content, safe_invoke_llm
from src.contracts.decision_journal import JournalEntry, ReflectionReport
from src.contracts.research_policy import PolicyOutcome


REFLECTION_SYSTEM_PROMPT = """あなたはAI組織の最高内省責任者（Reflection Agent）です。
過去に記録された意思決定ジャーナル（初期仮説、前提、期待された成果）と、実際に得られた分析結果・成果を客観的に対比・検証し、
「自己反省レポート (ReflectionReport)」を生成してください。

【厳格な内省基準】
1. **初期仮説の妥当性評価**: 当初の仮説・方針と実際の結果の一致度を 0〜100 点のスコアで評価してください。
2. **うまくいった要因 (Success Factors)**: 正確に機能した点、強みを客観的に抽出してください。
3. **見落とし・盲点 (Blindspots & Gaps)**: 分析でカバーしきれなかった観点、過小評価していたリスクを具体的に指摘してください。
4. **教訓 (Lessons Learned)**: 次回以降の方針策定や分析で直ちに活用すべき教訓を言語化してください。
5. **ガードレール更新案**: 再発防止や精度向上のために追加・改善すべきルールを提示してください。

【出力仕様】
必ず以下のJSONフォーマットのみを出力してください（Markdownコードブロックは不要です）。
{
  "actual_outcome": "実際の分析結果・実績の客観的サマリー",
  "accuracy_score": 85, // 0〜100の整数
  "success_factors": [
    "うまくいった要因1",
    "うまくいった要因2"
  ],
  "blindspots": [
    "見落としていた盲点・不足点1"
  ],
  "lessons_learned": [
    "次回への具体的教訓1",
    "次回への具体的教訓2"
  ],
  "recommended_guardrails": [
    "推奨ガードレール更新ルール1"
  ]
}
"""


def perform_reflection(
    journal: JournalEntry,
    actual_outcome_text: str,
    outcome: Optional[PolicyOutcome] = None
) -> ReflectionReport:
    """
    ジャーナルと実績を比較し、自己反省レポートを生成する。
    """
    reflection_id = f"ref_{uuid.uuid4().hex[:10]}"

    # 1. ルールベースによる初期値
    score = 85
    success_factors = ["初期方針に従い、全検証ステップを完了できた点"]
    blindspots = []
    lessons = ["定期的な市場前提の再評価が必要"]
    recommended_rules = []

    if outcome:
        if outcome.verification_status == "OK":
            score = 90
            success_factors.append("全部門の整合性・品質検証をクリアした点")
        else:
            score = 70
            blindspots.append("一部の検証項目で警告または追加調査が発生した点")
            lessons.append("初期段階でより詳細な論点指定を行うべきである")

    # 2. LLM による高度な内省と教訓抽出
    try:
        model = get_pro_model(temperature=0.1)
        context = {
            "journal_id": journal.journal_id,
            "decision_type": journal.decision_type,
            "ticker": journal.ticker,
            "hypothesis": journal.hypothesis,
            "assumptions": journal.assumptions,
            "expected_outcome": journal.expected_outcome,
            "actual_outcome": actual_outcome_text,
            "verification_status": outcome.verification_status if outcome else "OK"
        }

        messages = [
            SystemMessage(content=REFLECTION_SYSTEM_PROMPT),
            HumanMessage(content=f"意思決定 vs 実績データ:\n{json.dumps(context, ensure_ascii=False, indent=2)}")
        ]
        response = safe_invoke_llm(model, messages)
        text = extract_text_content(response)

        clean_json = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"^```\s*", "", clean_json, flags=re.MULTILINE)
        data = json.loads(clean_json.strip())

        return ReflectionReport(
            reflection_id=reflection_id,
            journal_id=journal.journal_id,
            strategy_id=journal.strategy_id,
            actual_outcome=data.get("actual_outcome", actual_outcome_text),
            accuracy_score=data.get("accuracy_score", score),
            success_factors=data.get("success_factors", success_factors),
            blindspots=data.get("blindspots", blindspots),
            lessons_learned=data.get("lessons_learned", lessons),
            recommended_guardrails=data.get("recommended_guardrails", recommended_rules)
        )

    except Exception:
        # LLM失敗時の高信頼ルールベースフォールバック
        return ReflectionReport(
            reflection_id=reflection_id,
            journal_id=journal.journal_id,
            strategy_id=journal.strategy_id,
            actual_outcome=actual_outcome_text,
            accuracy_score=score,
            success_factors=success_factors,
            blindspots=blindspots or ["特段の致命的見落としなし"],
            lessons_learned=lessons,
            recommended_guardrails=recommended_rules or [f"{journal.ticker or '銘柄'} の四半期業績動向を継続注視すること"]
        )
