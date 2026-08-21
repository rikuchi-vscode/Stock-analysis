"""
Time Utils 単体テスト
JSTタイムゾーン生成・変換・フォールバック機能の検証
"""

import pytest
from datetime import datetime, timezone, timedelta
from src.time_utils import (
    JST,
    get_jst_now,
    get_jst_now_str,
    get_jst_today_str,
    format_to_jst_str,
)


def test_get_jst_now():
    """JSTのdatetimeオブジェクトが正しく取得できること"""
    now = get_jst_now()
    assert isinstance(now, datetime)
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(hours=9)


def test_get_jst_now_str():
    """JSTの日時文字列が正しく生成されること"""
    now_str = get_jst_now_str("%Y-%m-%d %H:%M:%S")
    assert len(now_str) == 19
    assert now_str[4] == "-"
    assert now_str[7] == "-"
    assert now_str[10] == " "
    assert now_str[13] == ":"
    assert now_str[16] == ":"


def test_get_jst_today_str():
    """本日のJST日付文字列が生成されること"""
    today_str = get_jst_today_str()
    assert len(today_str) == 10
    assert today_str[4] == "-"
    assert today_str[7] == "-"


def test_format_to_jst_str_with_unix_timestamp():
    """Unixタイムスタンプ (秒/ミリ秒) がJSTに変換されること"""
    # 2026-08-21 00:00:00 UTC = 2026-08-21 09:00:00 JST
    utc_epoch = 1787270400  # 2026-08-21 00:00:00 UTC
    jst_str = format_to_jst_str(utc_epoch, format_str="%Y-%m-%d %H:%M:%S")
    assert jst_str == "2026-08-21 09:00:00"

    # ミリ秒タイムスタンプ
    jst_str_ms = format_to_jst_str(utc_epoch * 1000, format_str="%Y-%m-%d %H:%M:%S")
    assert jst_str_ms == "2026-08-21 09:00:00"


def test_format_to_jst_str_with_iso_string():
    """ISO8601文字列 (UTC) がJSTに変換されること"""
    iso_utc = "2026-08-21T00:00:00Z"
    jst_str = format_to_jst_str(iso_utc, format_str="%Y-%m-%d %H:%M:%S")
    assert jst_str == "2026-08-21 09:00:00"

    iso_utc_offset = "2026-08-21T00:00:00+00:00"
    jst_str2 = format_to_jst_str(iso_utc_offset, format_str="%Y-%m-%d %H:%M:%S")
    assert jst_str2 == "2026-08-21 09:00:00"


def test_format_to_jst_str_with_datetime():
    """datetime オブジェクトがJSTに変換されること"""
    dt_utc = datetime(2026, 8, 21, 0, 0, 0, tzinfo=timezone.utc)
    jst_str = format_to_jst_str(dt_utc, format_str="%Y-%m-%d %H:%M:%S")
    assert jst_str == "2026-08-21 09:00:00"


def test_format_to_jst_str_fallback():
    """Noneや空文字の場合にフォールバックが返ること"""
    assert format_to_jst_str(None, fallback="未設定") == "未設定"
    assert format_to_jst_str("", fallback="不明") == "不明"
