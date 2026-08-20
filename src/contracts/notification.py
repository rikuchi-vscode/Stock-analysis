"""
通知 (Notification) データ契約
STEP 3: アラート・進捗・成果通知
"""

from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field


class NotificationMessage(BaseModel):
    """通知メッセージモデル"""
    notification_id: str = Field(description="通知の一意なID (例: notif_...)")
    channel: Literal["CONSOLE", "LOG", "DB", "EMAIL", "SLACK"] = Field(
        default="CONSOLE", description="通知チャネル"
    )
    severity: Literal["INFO", "WARNING", "ALERT", "CRITICAL", "HIGH", "MEDIUM", "LOW"] = Field(
        default="INFO", description="通知重要度"
    )
    title: str = Field(description="通知件名")
    body: str = Field(description="通知本文")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="付随メタデータ")
    delivered: bool = Field(default=False, description="配信完了フラグ")
    created_at: Optional[str] = Field(default=None, description="作成日時")
