"""
日時・タイムゾーン共通ユーティリティ (Time & Timezone Utilities)
日本標準時 (JST: Asia/Tokyo, UTC+9) の統一管理を提供します。
Streamlit Cloud (Linux UTC環境) を含むあらゆる環境で正確に日本時間で日時を生成・フォーマットします。
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union, Any

# 日本標準時 (JST: UTC+9) のタイムゾーン定義（依存パッケージ不要で全環境動作保証）
JST = timezone(timedelta(hours=9))


def get_jst_now() -> datetime:
    """日本標準時 (JST) の現在日時 (datetime オブジェクト) を取得"""
    return datetime.now(JST)


def get_jst_now_str(format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """日本標準時 (JST) の現在日時文字列を取得 (デフォルト: YYYY-MM-DD HH:MM:SS)"""
    return get_jst_now().strftime(format_str)


def get_jst_today_str(format_str: str = "%Y-%m-%d") -> str:
    """日本標準時 (JST) の本日の日付文字列を取得 (デフォルト: YYYY-MM-DD)"""
    return get_jst_now().strftime(format_str)


def format_to_jst_str(
    val: Optional[Union[datetime, int, float, str]],
    format_str: str = "%Y-%m-%d %H:%M:%S",
    fallback: str = ""
) -> str:
    """
    様々な形式の入力（Unixタイムスタンプ、datetime、ISO文字列、SQLite文字列等）を
    日本標準時 (JST) の日時文字列に変換して返します。

    :param val: 変換対象の値（int/floatのUnix秒またはミリ秒、datetime、ISO8601文字列等）
    :param format_str: 出力フォーマット文字列
    :param fallback: 変換失敗時またはNone/空文字時のフォールバック文字列
    :return: JST日時文字列
    """
    if val is None or val == "":
        return fallback

    # 1. 数値型 (Unix Timestamp: 秒またはミリ秒)
    if isinstance(val, (int, float)):
        try:
            # 13桁ミリ秒タイムスタンプの考慮 (1e11以上はmsと判定)
            ts = val / 1000.0 if val > 1e11 else float(val)
            dt = datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(JST)
            return dt.strftime(format_str)
        except Exception:
            return str(val)

    # 2. datetime オブジェクト
    if isinstance(val, datetime):
        try:
            if val.tzinfo is None:
                # タイムゾーン情報がない場合はJSTを付与
                dt = val.replace(tzinfo=JST)
            else:
                # タイムゾーン情報がある場合はJSTに変換
                dt = val.astimezone(JST)
            return dt.strftime(format_str)
        except Exception:
            return str(val)

    # 3. 文字列
    if isinstance(val, str):
        s = val.strip()
        if not s:
            return fallback

        # ISO形式 (例: 2026-08-21T05:58:12Z, 2026-08-21T05:58:12+00:00)
        if "T" in s or s.endswith("Z") or ("+" in s and ":" in s):
            try:
                iso_clean = s.replace("Z", "+00:00")
                dt = datetime.fromisoformat(iso_clean)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(JST).strftime(format_str)
            except Exception:
                pass

        # 一般的な YYYY-MM-DD または YYYY-MM-DD HH:MM:SS 文字列はそのまま返す
        return s

    return str(val)
