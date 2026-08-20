"""
CEO レイヤー用データコントラクト・スキーマ定義
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field


class CEORequest(BaseModel):
    """ユーザーから受け付けるリクエスト"""
    request_id: str = Field(description="リクエストの一意なID")
    user_request: str = Field(description="ユーザーからの自然言語依頼本文")
    created_at: Optional[str] = Field(default=None, description="受付日時")


class NormalizedRequest(BaseModel):
    """CEO Agent が自然言語から正規化した構造化リクエスト"""
    task_type: Literal["stock_analysis", "market_inquiry", "unsupported"] = Field(
        default="stock_analysis", description="タスク種別"
    )
    ticker: Optional[str] = Field(default=None, description="正規化された銘柄コード (例: 7203.T)")
    company_name_hint: Optional[str] = Field(default=None, description="銘柄名ヒント (例: トヨタ自動車)")
    horizon: Literal["short", "medium", "long", "unspecified"] = Field(
        default="medium", description="投資・分析の時間軸"
    )
    focus_areas: List[str] = Field(default_factory=list, description="重点調査観点")
    constraints: Dict[str, Any] = Field(
        default_factory=lambda: {"execution": "research_only"},
        description="制約事項（例: 売買執行禁止、リサーチ限定）"
    )
    confidence: float = Field(default=1.0, description="銘柄・意図特定の信頼度 (0.0〜1.0)")
    clarification_needed: bool = Field(default=False, description="曖昧すぎて確認が必要か")
    clarification_message: Optional[str] = Field(default=None, description="確認が必要な場合のメッセージ")


class CEOSummary(BaseModel):
    """CEO が生成する経営者・投資家向けエグゼクティブサマリー"""
    headline: str = Field(description="1行の結論・ヘッドライン")
    key_takeaways: List[str] = Field(default_factory=list, description="重要ポイント（3〜5点）")
    key_risks: List[str] = Field(default_factory=list, description="注示すべき主要リスク")
    limitations: List[str] = Field(default_factory=list, description="本分析の限界事項・前提")
    disclaimer: str = Field(
        default="本出力はリサーチ目的の情報提供であり、投資助言や有価証券の売買を推奨するものではありません。",
        description="免責事項"
    )


class CEOState(BaseModel):
    """CEO ワークフローの全体状態"""
    request_id: str
    run_id: str
    user_request: str
    task_type: str = "stock_analysis"
    ticker: Optional[str] = None
    company_name: Optional[str] = None
    department: str = "stock_research"
    delegation: Dict[str, Any] = Field(default_factory=dict)
    analysis_run_id: Optional[str] = None
    verification_status: str = "PENDING"
    ceo_summary: Optional[CEOSummary] = None
    final_report: Optional[str] = None
    report_path: Optional[str] = None
    status: Literal["RECEIVED", "PLANNED", "DISPATCHED", "RUNNING", "VERIFIED", "REPORTED", "WAITING_APPROVAL", "RETRYING", "FAILED", "CANCELLED"] = "RECEIVED"
    trace_id: str
    error: Optional[str] = None
    logs: List[str] = Field(default_factory=list)
