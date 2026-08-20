"""
データ来歴 (Data Lineage) および値ステータス管理モデル
実測値、推定値、前回値、ルールベース代替値、欠損値を厳密に区別・管理します。
"""

from enum import Enum
from typing import Optional, Any, List, Dict
from pydantic import BaseModel, Field


class ValueStatus(str, Enum):
    ACTUAL = "ACTUAL"             # 実測値 / 取引所確定値 / 公式開示値
    ESTIMATED = "ESTIMATED"       # 会社予想値 / モデル推定値 / コンセンサス
    PREVIOUS = "PREVIOUS"         # 前回確定値 (直近値未発表時の過年度・過去四半期値)
    FALLBACK_RULE = "FALLBACK"    # ルールベース代替値 (テクニカル補完・標準参考値)
    UNAVAILABLE = "UNAVAILABLE"   # 取得不可 / 欠損 (データ元未提供・算出不能)


class DataField(BaseModel):
    """単一指標のメタデータ付きデータコンテナ"""
    raw_value: Optional[Any] = Field(default=None, description="元の生値 (数値/文字列)")
    formatted_value: str = Field(description="表示用テキスト (単位付き)")
    status: ValueStatus = Field(default=ValueStatus.ACTUAL, description="値の種別・出所状態")
    source: str = Field(default="yfinance", description="データ取得元 (yfinance, EDINET, 東証等)")
    as_of: Optional[str] = Field(default=None, description="データ時点 (YYYY-MM-DD HH:MM または 決算期)")
    note: Optional[str] = Field(default=None, description="欠損理由、代替値の根拠、または前提条件")

    def to_display(self) -> str:
        """ユーザー向け表示文字列を生成"""
        if self.status == ValueStatus.UNAVAILABLE:
            reason = f" ({self.note})" if self.note else ""
            return f"取得できませんでした{reason}"
        elif self.status == ValueStatus.FALLBACK_RULE:
            note_str = f" [参考値: {self.note}]" if self.note else " [参考値]"
            return f"{self.formatted_value}{note_str}"
        elif self.status == ValueStatus.PREVIOUS:
            note_str = f" [前回値: {self.note}]" if self.note else " [前回値]"
            return f"{self.formatted_value}{note_str}"
        elif self.status == ValueStatus.ESTIMATED:
            note_str = f" [推定/予想: {self.note}]" if self.note else " [予想]"
            return f"{self.formatted_value}{note_str}"
        return self.formatted_value

    def get_badge_text(self) -> str:
        """UI用バッジテキスト"""
        if self.status == ValueStatus.ACTUAL:
            return "実測"
        elif self.status == ValueStatus.ESTIMATED:
            return "予想/推定"
        elif self.status == ValueStatus.PREVIOUS:
            return "前回値"
        elif self.status == ValueStatus.FALLBACK_RULE:
            return "参考値"
        elif self.status == ValueStatus.UNAVAILABLE:
            return "取得不可"
        return "不明"


class FieldLineageItem(BaseModel):
    """データ品質レポート用の個別項目来歴"""
    field_name: str = Field(description="指標名 (例: 実績PER, 営業利益率)")
    value_display: str = Field(description="表示値")
    status: ValueStatus = Field(description="値ステータス")
    source: str = Field(default="yfinance", description="取得元")
    as_of: str = Field(default="最新", description="データ時点")
    note: str = Field(default="", description="注記・欠損理由")


class DataLineageSummary(BaseModel):
    """データ全体の来歴・鮮度・欠損サマリー"""
    market_as_of: str = Field(default="最新", description="市場データ時点")
    financial_as_of: str = Field(default="直近開示", description="財務データ時点")
    news_period: str = Field(default="直近7日間", description="ニュース収集期間")
    sources: List[str] = Field(default_factory=lambda: ["yfinance (Yahoo Finance API)"], description="使用データソース")
    
    total_fields: int = Field(default=0, description="総指標数")
    actual_count: int = Field(default=0, description="実測値数")
    estimated_count: int = Field(default=0, description="推定・予想値数")
    fallback_count: int = Field(default=0, description="代替・参考値数")
    unavailable_count: int = Field(default=0, description="欠損・取得不可数")
    
    missing_items: List[str] = Field(default_factory=list, description="欠損した主要指標名と理由")
    fallback_items: List[str] = Field(default_factory=list, description="代替値を使用した指標名と根拠")
    items_detail: List[FieldLineageItem] = Field(default_factory=list, description="全指標の詳細来歴リスト")
