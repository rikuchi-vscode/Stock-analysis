"""
システムの共有状態（State）モデル定義
LangGraph を介して各エージェント間で受け渡されるデータ構造を定義します。
"""

import operator
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from pydantic import BaseModel, Field


class PlanModel(BaseModel):
    """Planner Agent が策定する分析計画"""
    tasks: List[str] = Field(default_factory=list, description="データ収集・分析タスクのリスト")
    focus_points: List[str] = Field(default_factory=list, description="特に重点を置く調査ポイント")
    additional_queries: Optional[List[str]] = Field(default_factory=list, description="再調査時の追加クエリ")


class VerificationResult(BaseModel):
    """Verification Agent による厳格な品質ゲート・整合性・透明性判定結果"""
    status: str = Field(description="'OK' (全ゲート通過) または 'NG' (差し戻し)")
    
    # 総合スコア群 (0-100)
    completeness_score: int = Field(default=85, description="情報の完全性スコア (0-100)")
    consistency_score: int = Field(default=85, description="論理整合性スコア (0-100)")
    transparency_score: int = Field(default=90, description="データ透明性・欠損開示スコア (0-100)")
    fact_grounding_score: int = Field(default=90, description="元データ照合・ファクトスコア (0-100)")
    
    # 6大品質ゲート判定フラグ
    numerical_consistency_ok: bool = Field(default=True, description="株価/PER/PBR/増減率の元データ完全一致")
    citations_valid: bool = Field(default=True, description="ニュース主張の出典URL・公開日時の有効性")
    time_consistency_ok: bool = Field(default=True, description="数値時点・タイムスタンプ整合性")
    calculation_basis_present: bool = Field(default=True, description="目標株価・スコアの計算根拠の有無")
    fact_opinion_separated: bool = Field(default=True, description="事実とAI解釈の明確な区別")
    balanced_view_present: bool = Field(default=True, description="推奨結論に対する好材料と反証・リスクの両論併記")
    hidden_missing_detected: bool = Field(default=False, description="欠損隠蔽・架空数値捏造の検知")
    
    # 指摘事項とフィードバック
    missing_points: List[str] = Field(default_factory=list, description="不足している情報や改善すべき点")
    failed_checks: List[str] = Field(default_factory=list, description="不合格となった検証ゲート一覧")
    data_quality_notes: List[str] = Field(default_factory=list, description="データ品質・欠損・代替値に関する検証所見")
    feedback_to_planner: Optional[str] = Field(default="", description="Plannerへの再調査指示コメント")


class AgentState(TypedDict, total=False):
    """LangGraph全体で共有・更新されるステート"""
    # 基本情報
    ticker: str                  # 銘柄コード (例: "7203.T")
    company_name: str            # 銘柄名 (例: "トヨタ自動車")
    sector: str                  # セクター・業種
    data_lineage: Dict[str, Any] # データ来歴・鮮度・品質サマリー
    
    # 進行制御 & リトライ管理
    iteration_count: int         # フィードバックループの実行回数
    max_iterations: int          # 最大再調査ループ回数 (デフォルト: 2)
    
    # 各エージェントの成果物
    plan: Dict[str, Any]         # Planner の分析計画
    market_data: Dict[str, Any]   # Market Agent の収集データ (株価, 指標, テクニカル分析)
    financial_data: Dict[str, Any] # Financial Agent の収集データ (財務諸表, 業績, 指標)
    news_data: Dict[str, Any]     # News Agent の収集データ (最新ニュース, 適時開示, センチメント)
    
    analysis_result: Dict[str, Any] # Analysis Agent の統合分析 (投資仮説, スコア, シナリオ)
    risk_result: Dict[str, Any]     # Risk Agent のリスク分析 (ダウンサイドリスク, 懸念事項)
    verification_result: Dict[str, Any] # Verification Agent の検証結果 (OK/NG, 不足リスト)
    
    # 最終成果物
    final_report: str            # 生成された Markdown 形式の最終レポート
    report_path: str             # 保存先ファイルパス
    analysis_id: Optional[int]   # DB保存時のレコードID
    
    # 実行ログ (並行更新を安全にマージするリデューサーを設定)
    logs: Annotated[List[str], operator.add]
