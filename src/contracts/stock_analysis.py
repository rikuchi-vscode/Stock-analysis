"""
株価分析部門（STEP 0）とのインターフェース契約
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class StockAnalysisRequest(BaseModel):
    """株価分析部門（Manager Agent）へ渡す分析要求"""
    ticker: str = Field(description="正規化された銘柄コード (例: 7203.T)")
    horizon: str = Field(default="medium", description="投資期間視点")
    focus_areas: List[str] = Field(default_factory=list, description="重点調査項目")
    max_iterations: int = Field(default=2, description="品質検証時の最大再調査反復回数")
    correlation_id: Optional[str] = Field(default=None, description="追跡用相関ID")


class StockAnalysisResponse(BaseModel):
    """株価分析部門からの分析完了レスポンス"""
    analysis_id: Optional[int] = Field(default=None, description="DB保存時の分析ID")
    ticker: str = Field(description="銘柄コード")
    company_name: str = Field(description="企業名")
    sector: str = Field(default="不明", description="セクター")
    overall_score: Optional[int] = Field(default=None, description="総合スコア (0-100)")
    investment_stance: Optional[str] = Field(default=None, description="推奨投資スタンス")
    verification_status: str = Field(default="OK", description="品質検証結果 ('OK' | 'NG')")
    iteration_count: int = Field(default=0, description="実行された再調査サイクル数")
    final_report: str = Field(description="生成されたMarkdownレポート本文")
    report_path: str = Field(description="保存先ファイルパス")
    analysis_result: Dict[str, Any] = Field(default_factory=dict, description="統合分析の詳細")
    risk_result: Dict[str, Any] = Field(default_factory=dict, description="リスク評価の詳細")
    market_data: Dict[str, Any] = Field(default_factory=dict, description="市場・株価データ")
    financial_data: Dict[str, Any] = Field(default_factory=dict, description="財務データ")
    news_data: Dict[str, Any] = Field(default_factory=dict, description="ニュースデータ")
    data_lineage: Optional[Dict[str, Any]] = Field(default=None, description="データ来歴・鮮度・品質サマリー")
    logs: List[str] = Field(default_factory=list, description="実行ログ一覧")
