"""
株価・市場データ収集およびテクニカル指標算出ツール
実測値・ルールベース代替値（参考値）・欠損を明確に区別して算出します。
"""

import os
from datetime import datetime
import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List
from src.contracts.data_lineage import ValueStatus

CHART_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "output", "charts")


def normalize_ticker(ticker: str) -> str:
    """日本株の銘柄コードを正規化 (4桁の数字なら .T を付与)"""
    ticker = ticker.strip().upper()
    if ticker.isdigit() and len(ticker) == 4:
        return f"{ticker}.T"
    return ticker


def fetch_market_data(ticker: str, period: str = "6mo") -> Dict[str, Any]:
    """
    株価履歴データと主要テクニカル指標を取得・計算
    実測値、算出値、代替参考値、欠損の来歴メタデータを付与して返します。
    """
    normalized_ticker = normalize_ticker(ticker)
    stock = yf.Ticker(normalized_ticker)
    
    # 履歴データ取得
    df = stock.history(period=period)
    if df.empty:
        # フォールバック (1y)
        df = stock.history(period="1y")
    
    if df.empty:
        return {
            "error": f"銘柄コード {ticker} の株価データを取得できませんでした。"
        }
        
    info = stock.info or {}
    company_name = info.get("longName") or info.get("shortName") or ticker
    sector = info.get("sector") or info.get("industry") or "不明"

    # テクニカル指標の計算
    df["SMA_25"] = df["Close"].rolling(window=25).mean()
    df["SMA_75"] = df["Close"].rolling(window=75).mean()
    
    # RSI (14日)
    delta = df["Close"].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df["RSI_14"] = 100 - (100 / (1 + rs))

    # ボリンジャーバンド (25日, 2σ)
    rolling_std = df["Close"].rolling(window=25).std()
    df["BB_Upper"] = df["SMA_25"] + (rolling_std * 2)
    df["BB_Lower"] = df["SMA_25"] - (rolling_std * 2)

    # 直近値の抽出
    latest = df.iloc[-1]
    prev = df.iloc[-2] if len(df) > 1 else latest
    
    latest_close = float(latest["Close"])
    prev_close = float(prev["Close"])
    change_pct = ((latest_close - prev_close) / prev_close) * 100

    # 取引日時の抽出
    last_date = df.index[-1]
    market_as_of = last_date.strftime("%Y-%m-%d") if hasattr(last_date, "strftime") else str(last_date)

    # 52週高値・安値
    high_52w = float(info.get("fiftyTwoWeekHigh", df["High"].max()))
    low_52w = float(info.get("fiftyTwoWeekLow", df["Low"].min()))

    # テクニカルシグナル判定
    has_sma25 = pd.notna(latest["SMA_25"])
    has_sma75 = pd.notna(latest["SMA_75"])
    if has_sma25 and has_sma75:
        sma_trend = "強気 (SMA25 > SMA75)" if latest["SMA_25"] > latest["SMA_75"] else "弱気 (SMA25 <= SMA75)"
    else:
        sma_trend = "判定不能（データ期間不足）"
    
    has_rsi = pd.notna(latest["RSI_14"])
    rsi_val = float(latest["RSI_14"]) if has_rsi else 50.0
    if not has_rsi:
        rsi_status = "中立水準 (算出データ不足)"
    elif rsi_val >= 70:
        rsi_status = f"買われすぎ水準 ({rsi_val:.1f})"
    elif rsi_val <= 30:
        rsi_status = f"売られすぎ水準 ({rsi_val:.1f})"
    else:
        rsi_status = f"中立水準 ({rsi_val:.1f})"

    # 自動テクニカル分析要約と支持・抵抗線の算出
    tech_signals = []
    if has_sma25 and has_sma75:
        if latest["SMA_25"] > latest["SMA_75"]:
            tech_signals.append(f"ゴールデンクロス基調 (25日線: {latest['SMA_25']:,.1f} 円 > 75日線: {latest['SMA_75']:,.1f} 円)")
        else:
            tech_signals.append(f"デッドクロス/調整基調 (25日線: {latest['SMA_25']:,.1f} 円 <= 75日線: {latest['SMA_75']:,.1f} 円)")
    else:
        tech_signals.append("移動平均線: 算出期間不足のため一部未確定")
    
    if has_rsi:
        if rsi_val >= 70:
            tech_signals.append(f"RSI買われすぎ警戒 ({rsi_val:.1f})")
        elif rsi_val <= 30:
            tech_signals.append(f"RSI売られすぎ反発期待 ({rsi_val:.1f})")
        else:
            tech_signals.append(f"RSI中立・安定推移 ({rsi_val:.1f})")
    else:
        tech_signals.append("RSI: 算出期間不足のため参考値")

    # サポート・レジスタンスの算出と来歴（実測 or ルールベース代替）
    res_val = latest["BB_Upper"] if pd.notna(latest["BB_Upper"]) else high_52w
    sup_val = latest["BB_Lower"] if pd.notna(latest["BB_Lower"]) else (latest["SMA_75"] if has_sma75 else low_52w)

    resistance_str = f"{res_val:,.1f} 円（※参考値: ボリンジャーバンド上限/直近高値）" if pd.notna(res_val) else "目先の上値抵抗線なし"
    support_str = f"{sup_val:,.1f} 円（※参考値: ボリンジャーバンド下限/75日線）" if pd.notna(sup_val) else "目先の下値支持線なし"

    trend_summary = (
        f"現在の株価 ({latest_close:,.1f} 円) は {sma_trend} の状態にあり、"
        f"RSIは {rsi_status} です。目先の上値抵抗線は {resistance_str}、"
        f"下値支持線は {support_str} が意識されるチャート形状となっています。"
    )

    base_score = 60
    if "強気" in sma_trend:
        base_score += 15
    if has_rsi:
        if 40 <= rsi_val <= 65:
            base_score += 10
        elif rsi_val < 35:
            base_score += 5

    default_analysis = {
        "trend_summary": trend_summary,
        "technical_signals": tech_signals,
        "support_resistance": {
            "resistance": resistance_str,
            "support": support_str
        },
        "technical_score": min(95, max(30, base_score)),
        "analyst_comment": f"{company_name} ({normalized_ticker}) はテクニカル面で {sma_trend} を維持しており、レンジ内での推移が継続しています。"
    }

    # 指標来歴メタデータリスト
    fields_detail = [
        {"field_name": "現在株価", "raw_value": latest_close, "formatted_value": f"{latest_close:,.1f} 円", "status": ValueStatus.ACTUAL.value, "source": "yfinance (東証)", "as_of": market_as_of, "note": "取引所終値/現在値"},
        {"field_name": "前日比変動率", "raw_value": change_pct, "formatted_value": f"{change_pct:+.2f}%", "status": ValueStatus.ACTUAL.value, "source": "yfinance", "as_of": market_as_of, "note": "前日終値比較"},
        {"field_name": "出来高", "raw_value": int(latest["Volume"]), "formatted_value": f"{int(latest['Volume']):,} 株", "status": ValueStatus.ACTUAL.value, "source": "yfinance", "as_of": market_as_of, "note": "取引高"},
        {"field_name": "25日移動平均 (SMA25)", "raw_value": float(latest["SMA_25"]) if has_sma25 else None, "formatted_value": f"{latest['SMA_25']:,.1f} 円" if has_sma25 else "取得できませんでした", "status": ValueStatus.ACTUAL.value if has_sma25 else ValueStatus.UNAVAILABLE.value, "source": "yfinance算出", "as_of": market_as_of, "note": "25日移動平均"},
        {"field_name": "75日移動平均 (SMA75)", "raw_value": float(latest["SMA_75"]) if has_sma75 else None, "formatted_value": f"{latest['SMA_75']:,.1f} 円" if has_sma75 else "取得できませんでした", "status": ValueStatus.ACTUAL.value if has_sma75 else ValueStatus.UNAVAILABLE.value, "source": "yfinance算出", "as_of": market_as_of, "note": "75日移動平均"},
        {"field_name": "RSI (14日)", "raw_value": rsi_val if has_rsi else None, "formatted_value": f"{rsi_val:.1f}" if has_rsi else "取得できませんでした", "status": ValueStatus.ACTUAL.value if has_rsi else ValueStatus.UNAVAILABLE.value, "source": "yfinance算出", "as_of": market_as_of, "note": "14日相対力指数"},
        {"field_name": "上値抵抗線 (Resistance)", "raw_value": float(res_val) if pd.notna(res_val) else None, "formatted_value": resistance_str, "status": ValueStatus.FALLBACK_RULE.value, "source": "ルールベース推定", "as_of": market_as_of, "note": "ボリンジャーバンド+2σ/直近高値からの代替参考値"},
        {"field_name": "下値支持線 (Support)", "raw_value": float(sup_val) if pd.notna(sup_val) else None, "formatted_value": support_str, "status": ValueStatus.FALLBACK_RULE.value, "source": "ルールベース推定", "as_of": market_as_of, "note": "ボリンジャーバンド-2σ/75日線からの代替参考値"},
    ]

    fallback_items = ["上値抵抗線: BB上限/直近高値からの代替参考値", "下値支持線: BB下限/75日線からの代替参考値"]
    missing_items = []
    if not has_sma25:
        missing_items.append("SMA25: データ期間不足のため算出不可")
    if not has_sma75:
        missing_items.append("SMA75: データ期間不足のため算出不可")
    if not has_rsi:
        missing_items.append("RSI14: データ期間不足のため算出不可")

    return {
        "ticker": normalized_ticker,
        "company_name": company_name,
        "sector": sector,
        "current_price": round(latest_close, 2),
        "price_change_pct": round(change_pct, 2),
        "daily_change_pct": round(change_pct, 2),
        "volume": int(latest["Volume"]),
        "market_as_of": market_as_of,
        "sma_25": round(float(latest["SMA_25"]), 2) if has_sma25 else "取得できませんでした（期間不足）",
        "sma_75": round(float(latest["SMA_75"]), 2) if has_sma75 else "取得できませんでした（期間不足）",
        "rsi_14": round(rsi_val, 2) if has_rsi else "取得できませんでした（期間不足）",
        "rsi_status": rsi_status,
        "bb_upper": round(float(latest["BB_Upper"]), 2) if pd.notna(latest["BB_Upper"]) else None,
        "bb_lower": round(float(latest["BB_Lower"]), 2) if pd.notna(latest["BB_Lower"]) else None,
        "high_52w": round(high_52w, 2),
        "low_52w": round(low_52w, 2),
        "sma_trend": sma_trend,
        "analysis": default_analysis,
        "fields_lineage": fields_detail,
        "fallback_items": fallback_items,
        "missing_items": missing_items,
        "historical_summary": {
            "start_date": df.index[0].strftime("%Y-%m-%d"),
            "end_date": df.index[-1].strftime("%Y-%m-%d"),
            "period_high": round(float(df["High"].max()), 2),
            "period_low": round(float(df["Low"].min()), 2),
            "average_volume": int(df["Volume"].mean())
        }
    }
