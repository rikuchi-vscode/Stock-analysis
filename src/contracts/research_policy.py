"""
リサーチ方針 (Research Policy) データ契約
STEP 2: CEO による分析方針決定・スコープ制御・承認状態
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field


class PolicyScope(BaseModel):
    """分析対象スコープ"""
    primary_tickers: List[str] = Field(default_factory=list, description="主要分析銘柄 (例: ['7203.T'])")
    peer_tickers: List[str] = Field(default_factory=list, description="比較対象銘柄 (例: ['7267.T'])")
    sector: Optional[str] = Field(default=None, description="対象セクター・業種")


class PolicyLimits(BaseModel):
    """分析リソース・実行上限"""
    max_tickers: int = Field(default=3, description="最大分析銘柄数")
    max_research_cycles: int = Field(default=2, description="最大再調査サイクル数")
    time_budget_minutes: int = Field(default=15, description="想定時間上限(分)")


class ResearchPolicy(BaseModel):
    """CEO が策定・決定するリサーチ方針"""
    strategy_id: str = Field(description="方針の一意なID (例: policy_...)")
    run_id: Optional[str] = Field(default=None, description="紐づくCEO Run ID")
    objective: str = Field(description="調査・分析の目的")
    mode: Literal["single_stock", "peer_comparison", "deep_dive_risk", "re_investigation"] = Field(
        default="single_stock", description="分析モード"
    )
    scope: PolicyScope = Field(default_factory=PolicyScope, description="分析対象銘柄・セクター")
    research_questions: List[str] = Field(default_factory=list, description="特に検証すべき論点・リサーチクエスチョン")
    analysis_depth: Literal["standard", "deep", "quick"] = Field(
        default="standard", description="分析の深度"
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(
        default="high", description="優先順位"
    )
    limits: PolicyLimits = Field(default_factory=PolicyLimits, description="実行上限")
    rationale: List[str] = Field(default_factory=list, description="方針決定の根拠")
    approval_required: bool = Field(default=False, description="人間承認が必要かどうか")
    approval_reason: Optional[str] = Field(default=None, description="承認が必要な場合の理由")
    status: Literal["PROPOSED", "WAITING_APPROVAL", "APPROVED", "REJECTED", "EXECUTING", "COMPLETED", "FAILED"] = Field(
        default="PROPOSED", description="方針のステータス"
    )
    version: int = Field(default=1, description="方針のバージョン番号")
    created_at: Optional[str] = Field(default=None, description="作成日時")


class PolicyDecision(BaseModel):
    """方針決定に関する意思決定ログ"""
    decision_id: str
    strategy_id: str
    decision_type: str = Field(description="決定種別 (例: 'CREATED', 'UPDATED', 'AUTO_APPROVED')")
    rationale: str = Field(description="決定の理由・根拠")
    actor: str = Field(default="CEO Agent", description="決定者 ('CEO Agent' | 'Policy Guard' | 'Human Owner')")
    created_at: Optional[str] = None


class PolicyApproval(BaseModel):
    """人間承認の記録"""
    approval_id: str
    strategy_id: str
    requested_action: str = Field(description="承認対象の操作")
    status: Literal["PENDING", "APPROVED", "REJECTED"] = "PENDING"
    approved_by: Optional[str] = None
    comment: Optional[str] = None
    created_at: Optional[str] = None


class PolicyOutcome(BaseModel):
    """方針実行後の実績・達成度"""
    strategy_id: str
    analysis_run_ids: List[str] = Field(default_factory=list, description="実行された分析IDリスト")
    coverage: Dict[str, Any] = Field(default_factory=dict, description="調査カバレッジ達成度")
    verification_status: str = Field(default="OK", description="総合検証結果")
    outcome_summary: str = Field(default="", description="方針に対する達成成果サマリー")
    next_recommendations: List[str] = Field(default_factory=list, description="次の調査候補・推奨アクション")
    created_at: Optional[str] = None
