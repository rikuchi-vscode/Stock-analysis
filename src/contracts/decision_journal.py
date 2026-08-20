"""
意思決定ガバナンス (Decision Governance) データ契約
STEP 4: 意思決定ジャーナル、自己反省 (Reflection)、人間フィードバック、ガードレール規則
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field


class DecisionSnapshot(BaseModel):
    """分析時点の判断固定スナップショット (Immutable Decision Snapshot)"""
    analysis_run_id: str = Field(description="主軸となる分析実行ID (例: run_...)")
    ticker: str = Field(description="銘柄コード")
    company_name: str = Field(default="", description="企業名")
    as_of_date: str = Field(description="分析実行日 (YYYY-MM-DD)")
    initial_price: float = Field(default=0.0, description="分析時点の株価")
    initial_market_index: Dict[str, float] = Field(default_factory=dict, description="当時の市場指数 (N225, TOPIX等)")
    investment_stance: str = Field(default="Hold", description="投資スタンス (Buy/Hold/Sell等)")
    overall_score: float = Field(default=0.0, description="総合評価スコア (0〜100)")
    target_price: Optional[float] = Field(default=None, description="目標株価")
    target_calculation_basis: Optional[str] = Field(default=None, description="目標株価・シナリオの計算根拠")
    key_hypotheses: List[str] = Field(default_factory=list, description="当時の主要仮説")
    identified_risks: List[str] = Field(default_factory=list, description="当時事前に指摘したリスク一覧")
    data_quality_snapshot: Dict[str, Any] = Field(default_factory=dict, description="データ欠損・来歴状態")
    verification_status: str = Field(default="OK", description="検証ゲートステータス")
    created_at: Optional[str] = Field(default=None, description="記録日時")


class JournalEntry(BaseModel):
    """意思決定ジャーナル エントリ (互換性維持)"""
    journal_id: str = Field(description="ジャーナルの一意なID (例: jrnl_...)")
    run_id: Optional[str] = Field(default=None, description="紐づくCEO Run ID")
    strategy_id: Optional[str] = Field(default=None, description="紐づくリサーチ方針ID")
    decision_type: Literal["POLICY_CREATION", "EVENT_TRIAGE", "DELEGATION", "VERIFICATION_REVIEW", "ANALYSIS_SNAPSHOT"] = Field(
        description="意思決定種別"
    )
    ticker: Optional[str] = Field(default=None, description="対象銘柄")
    hypothesis: str = Field(description="初期仮説 (なぜこの調査/アクションが必要と考えたか)")
    assumptions: List[str] = Field(default_factory=list, description="前提条件・環境想定")
    expected_outcome: str = Field(description="期待された分析成果・アウトプット")
    risk_assessment: List[str] = Field(default_factory=list, description="想定されたリスク・不確実性")
    actor: str = Field(default="AI CEO", description="意思決定エージェント")
    created_at: Optional[str] = Field(default=None, description="記録日時")


class EvaluationSchedule(BaseModel):
    """評価対象日の自動登録スケジュール"""
    schedule_id: str = Field(description="スケジュールID (例: sched_...)")
    analysis_run_id: str = Field(description="紐づく分析実行ID")
    ticker: str = Field(description="対象銘柄")
    evaluation_type: Literal["T+7", "T+30", "EARNINGS", "MANUAL"] = Field(
        default="T+7", description="評価タイミング種別"
    )
    target_date: str = Field(description="評価予定日 (YYYY-MM-DD)")
    status: Literal["PENDING", "DUE", "COMPLETED", "SKIPPED"] = Field(
        default="PENDING", description="スケジュール状態"
    )
    created_at: Optional[str] = Field(default=None, description="登録日時")


class EvaluationFact(BaseModel):
    """ルールベースで計算された客観的事実評価データ (Deterministic Fact)"""
    fact_id: str = Field(description="事実評価ID (例: fact_...)")
    schedule_id: str = Field(description="紐づくスケジュールID")
    analysis_run_id: str = Field(description="紐づく分析実行ID")
    ticker: str = Field(description="対象銘柄")
    evaluation_date: str = Field(description="事後評価実施日 (YYYY-MM-DD)")
    
    # 1. 株価・市場指数に対する相対変化
    initial_price: float = Field(default=0.0, description="分析当時株価")
    current_price: float = Field(default=0.0, description="事後評価時株価")
    price_change_pct: float = Field(default=0.0, description="銘柄騰落率 (%)")
    market_index_change_pct: float = Field(default=0.0, description="市場指数騰落率 (%)")
    relative_return_pct: float = Field(default=0.0, description="市場指数対比の相対リターン (Alpha %)")

    # 2. 主要仮説が維持されたか
    hypothesis_maintained: bool = Field(default=True, description="当時の主要仮説が維持されたか")
    hypothesis_detail: str = Field(default="", description="主要仮説の検証詳細")

    # 3. 実際に起きたリスクを事前に示せていたか
    risk_foresight_hit: bool = Field(default=False, description="発生したリスクを事前に指摘できていたか")
    risk_foresight_detail: str = Field(default="", description="リスク予見の詳細")

    # 4. 分析根拠に誤りやデータ欠損がなかったか
    data_integrity_ok: bool = Field(default=True, description="分析根拠に欠損や破綻がなかったか")
    data_integrity_detail: str = Field(default="", description="データ完全性の詳細")

    # ルールベース客観スコア (0〜100)
    rule_based_fact_score: float = Field(default=80.0, description="客観的事実に基づく算定スコア")
    created_at: Optional[str] = Field(default=None, description="評価記録日時")


class ReflectionReport(BaseModel):
    """自己反省 (Self Reflection) レポート"""
    reflection_id: str = Field(description="反省レポートの一意なID (例: ref_...)")
    journal_id: Optional[str] = Field(default=None, description="対象ジャーナルID")
    analysis_run_id: Optional[str] = Field(default=None, description="対象分析実行ID")
    strategy_id: Optional[str] = Field(default=None, description="方針ID")
    actual_outcome: str = Field(description="事後評価事実の要約")
    accuracy_score: int = Field(default=80, ge=0, le=100, description="仮説妥当性・精度スコア (0〜100)")
    success_factors: List[str] = Field(default_factory=list, description="うまくいった要因 (What went well)")
    blindspots: List[str] = Field(default_factory=list, description="見落とし・不足点 (Blindspots & Gaps)")
    lessons_learned: List[str] = Field(default_factory=list, description="次回への改善教訓 (Lessons Learned)")
    recommended_guardrails: List[str] = Field(default_factory=list, description="提案するガードレール改善規則案 (PROPOSED)")
    created_at: Optional[str] = Field(default=None, description="反省実施日時")


class HumanFeedback(BaseModel):
    """人間オーナーからのフィードバック"""
    feedback_id: str = Field(description="フィードバックの一意なID (例: fb_...)")
    target_type: Literal["POLICY", "REPORT", "SUMMARY", "TRIAGE", "EVALUATION"] = Field(
        description="フィードバック対象種別"
    )
    target_id: str = Field(description="対象ID (strategy_id, run_id 等)")
    rating: int = Field(default=5, ge=1, le=5, description="評価スコア (1〜5)")
    comments: str = Field(default="", description="人間からの定性指摘・コメント")
    corrections: List[str] = Field(default_factory=list, description="具体的な修正・改善指示")
    created_at: Optional[str] = Field(default=None, description="登録日時")


class GuardrailRule(BaseModel):
    """ガードレール規則 (PROPOSED → APPROVED/REJECTED → ACTIVE)"""
    rule_id: str = Field(description="ルールの一意なID (例: gr_...)")
    category: Literal["RESOURCE", "RISK", "FOCUS", "PROMPT", "ACCURACY"] = Field(
        default="FOCUS", description="ルールカテゴリ"
    )
    rule_text: str = Field(description="具体的な指示・制約テキスト")
    source: Literal["HUMAN_FEEDBACK", "REFLECTION", "POLICY_GUARD"] = Field(
        default="REFLECTION", description="ルールの出所"
    )
    status: Literal["PROPOSED", "APPROVED", "ACTIVE", "REJECTED"] = Field(
        default="PROPOSED", description="承認ガバナンス状態"
    )
    proposed_by: str = Field(default="Reflection Agent", description="提案者")
    approved_by: Optional[str] = Field(default=None, description="承認者")
    approved_at: Optional[str] = Field(default=None, description="承認日時")
    rejection_reason: Optional[str] = Field(default=None, description="却下理由")
    active: bool = Field(default=False, description="現在有効かどうか (ACTIVE時のみTrue)")
    created_at: Optional[str] = Field(default=None, description="作成日時")

