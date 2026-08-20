"""
監視対象 (WatchItem) & 市場イベント (MarketEvent) データ契約
STEP 3: 自律市場監視・イベント駆動トリガー
"""

from typing import Dict, Any, List, Optional, Literal
from pydantic import BaseModel, Field


class WatchTriggers(BaseModel):
    """監視トリガー条件"""
    price_change_pct: float = Field(default=3.0, description="株価急変トリガー閾値 (前日比±%)")
    volume_spike_ratio: float = Field(default=2.0, description="出来高急増トリガー閾値 (過去平均比倍率)")
    check_disclosures: bool = Field(default=True, description="適時開示・決算発表の監視フラグ")
    check_news: bool = Field(default=True, description="重要ニュース・センチメント急変の監視フラグ")


class WatchItem(BaseModel):
    """監視対象銘柄の設定"""
    watch_id: str = Field(description="監視アイテムの一意なID")
    ticker: str = Field(description="銘柄コード (例: 7203.T)")
    company_name: Optional[str] = Field(default=None, description="企業名")
    triggers: WatchTriggers = Field(default_factory=WatchTriggers, description="トリガー設定")
    interval_minutes: int = Field(default=60, description="監視ポーリング間隔(分)")
    priority: Literal["low", "medium", "high", "urgent"] = Field(default="medium", description="監視優先度")
    active: bool = Field(default=True, description="監視が有効かどうか")
    last_checked_at: Optional[str] = Field(default=None, description="最終チェック日時")
    created_at: Optional[str] = Field(default=None, description="登録日時")


class MarketEvent(BaseModel):
    """検知された市場・開示・ニュースイベント"""
    event_id: str = Field(description="イベントの一意なID (例: evt_...)")
    ticker: str = Field(description="銘柄コード")
    company_name: Optional[str] = Field(default=None, description="企業名")
    event_type: Literal["PRICE_SPIKE", "VOLUME_SURGE", "DISCLOSURE", "NEWS_ALERT", "EARNINGS_RELEASE"] = Field(
        description="イベント種別"
    )
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        default="MEDIUM", description="イベントの重要度"
    )
    title: str = Field(description="イベントタイトル")
    description: str = Field(description="イベント詳細内容")
    raw_payload: Dict[str, Any] = Field(default_factory=dict, description="生データペイロード")
    detected_at: Optional[str] = Field(default=None, description="検知日時")


class TriageResult(BaseModel):
    """Event Triage Agent による判定結果"""
    triage_id: str = Field(description="トリアージの一意なID")
    event_id: str = Field(description="対象イベントID")
    action: Literal["TRIGGER_RESEARCH", "QUEUE_RESEARCH", "NOTIFY_ONLY", "IGNORE"] = Field(
        description="決定アクション"
    )
    reason: str = Field(description="トリアージ判定の理由")
    suggested_mode: Optional[str] = Field(
        default="single_stock", description="推奨されるリサーチモード (single_stock, deep_dive_risk 等)"
    )
    priority: Literal["low", "medium", "high", "urgent"] = Field(default="high", description="タスク優先度")
    created_at: Optional[str] = Field(default=None, description="判定日時")
