"""
初心者向け UI ヘルパー単体テスト
Beginner_Friendly_Stock_Dashboard_UI_UX_Policy.md 準拠テスト
"""

import pytest
from dashboard_app import format_stance_for_beginner, format_verification_for_beginner


def test_format_stance_for_beginner():
    """投資スタンスが初心者向けラベルに適切に変換されること"""
    # Buy系 -> 前向き
    label, color, desc = format_stance_for_beginner("Strong Buy")
    assert label == "前向き（AIの見方）"
    assert color == "green"

    label, color, desc = format_stance_for_beginner("BUY")
    assert label == "前向き（AIの見方）"

    # Neutral/Hold系 -> 様子見
    label, color, desc = format_stance_for_beginner("Hold")
    assert label == "様子見（AIの見方）"
    assert color == "orange"

    # Sell系 -> 慎重
    label, color, desc = format_stance_for_beginner("Sell")
    assert label == "慎重（AIの見方）"
    assert color == "red"


def test_format_verification_for_beginner():
    """検証ステータスがやさしい表現に変換されること"""
    label, color = format_verification_for_beginner("OK")
    assert "完了" in label
    assert color == "green"

    label, color = format_verification_for_beginner("NG")
    assert "追加確認" in label
    assert color == "orange"
