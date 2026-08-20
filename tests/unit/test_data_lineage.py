"""
データ来歴・欠損開示・値ステータス管理のユニットテスト
"""

import pytest
from src.contracts.data_lineage import ValueStatus, DataField, DataLineageSummary
from src.tools.financial_tools import fetch_financial_data
from src.tools.market_tools import fetch_market_data


def test_data_field_display():
    # 1. 実測値
    f_actual = DataField(
        raw_value=3000.0,
        formatted_value="3,000 円",
        status=ValueStatus.ACTUAL,
        source="yfinance (東証)",
        as_of="2026-08-20"
    )
    assert f_actual.to_display() == "3,000 円"
    assert f_actual.get_badge_text() == "実測"

    # 2. 推定値 (会社予想)
    f_est = DataField(
        raw_value=12.5,
        formatted_value="12.5 倍",
        status=ValueStatus.ESTIMATED,
        note="会社予想ベース"
    )
    assert "予想" in f_est.to_display()
    assert f_est.get_badge_text() == "予想/推定"

    # 3. 代替値 (参考値)
    f_fall = DataField(
        raw_value=2800.0,
        formatted_value="2,800 円",
        status=ValueStatus.FALLBACK_RULE,
        note="75日移動平均線"
    )
    assert "参考値: 75日移動平均線" in f_fall.to_display()
    assert f_fall.get_badge_text() == "参考値"

    # 4. 欠損値 (取得不可)
    f_unavail = DataField(
        raw_value=None,
        formatted_value="",
        status=ValueStatus.UNAVAILABLE,
        note="赤字のため算出対象外"
    )
    assert "取得できませんでした" in f_unavail.to_display()
    assert "赤字のため算出対象外" in f_unavail.to_display()
    assert f_unavail.get_badge_text() == "取得不可"


def test_financial_tools_data_lineage():
    # 7203.T のデータ取得
    data = fetch_financial_data("7203")
    assert "error" not in data
    assert "fields_lineage" in data
    assert "financial_as_of" in data
    assert len(data["fields_lineage"]) > 0

    # 各フィールドに status が設定されていること
    statuses = [f["status"] for f in data["fields_lineage"]]
    assert any(s in [ValueStatus.ACTUAL.value, ValueStatus.ESTIMATED.value] for s in statuses)

    # 欠損時にも "N/A" 単体ではなく親切なテキストまたは理由が返ること
    val = data.get("valuation", {})
    for k, v in val.items():
        assert v != "N/A", f"Key {k} should not be simple 'N/A'"


def test_market_tools_fallback_distinction():
    data = fetch_market_data("7203")
    assert "error" not in data
    assert "market_as_of" in data
    assert "fields_lineage" in data
    assert "fallback_items" in data

    # 上値抵抗線・下値支持線が参考値として扱われていること
    sup_res = data.get("analysis", {}).get("support_resistance", {})
    assert "参考値" in sup_res.get("resistance", "")
    assert "参考値" in sup_res.get("support", "")
