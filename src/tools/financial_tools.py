"""
財務諸表・企業業績データ収集ツール
実測値・推定値・前回値・欠損（取得不可）を明確に区別して返却します。
"""

import yfinance as yf
from typing import Dict, Any, List, Optional
from datetime import datetime
from src.tools.market_tools import normalize_ticker
from src.contracts.data_lineage import ValueStatus, DataField, FieldLineageItem


def fetch_financial_data(ticker: str) -> Dict[str, Any]:
    """
    主要財務指標（PER, PBR, ROE, 営業利益率等）および業績推移を取得
    各指標に実測値・予想値・欠損状態のメタデータを付与して返します。
    """
    normalized_ticker = normalize_ticker(ticker)
    stock = yf.Ticker(normalized_ticker)
    info = stock.info or {}

    if not info:
        return {
            "error": f"銘柄コード {ticker} の財務データを取得できませんでした。"
        }

    # 主要バリュエーション指標
    market_cap = info.get("marketCap")
    pe_trailing = info.get("trailingPE")
    pe_forward = info.get("forwardPE")
    pb_ratio = info.get("priceToBook")
    dividend_yield = info.get("dividendYield")
    
    # 収益性・健全性指標
    roe = info.get("returnOnEquity")
    roa = info.get("returnOnAssets")
    operating_margin = info.get("operatingMargins")
    profit_margin = info.get("profitMargins")
    debt_to_equity = info.get("debtToEquity")
    current_ratio = info.get("currentRatio")
    
    # 業績概要 (直近売上・利益)
    total_revenue = info.get("totalRevenue")
    operating_income = info.get("operatingIncome")
    net_income = info.get("netIncomeToCommon")
    revenue_growth = info.get("revenueGrowth")
    earnings_growth = info.get("earningsGrowth")
    
    # データ時点
    fiscal_year_end = info.get("lastFiscalYearEnd")
    if fiscal_year_end:
        try:
            financial_as_of = datetime.fromtimestamp(fiscal_year_end).strftime("%Y-%m-%d")
        except Exception:
            financial_as_of = "直近開示決算"
    else:
        financial_as_of = "直近開示決算"

    # ヘルパー: 金額フォーマット
    def format_yen(val: Optional[float]) -> str:
        if val is None:
            return "取得できませんでした（データ未提供）"
        if abs(val) >= 1_000_000_000_000:
            return f"{val / 1_000_000_000_000:.2f} 兆円"
        if abs(val) >= 100_000_000:
            return f"{val / 100_000_000:.2f} 億円"
        return f"{val:,} 円"

    def format_pct(val: Optional[float]) -> str:
        if val is None:
            return "取得できませんでした（データ未提供）"
        if abs(val) > 1.0:
            return f"{val:.2f}%"
        return f"{val * 100:.2f}%"

    # 個別指標のメタデータ生成
    fields_detail: List[Dict[str, Any]] = []

    def make_field_meta(name: str, raw_val: Any, formatted_val: str, default_status: ValueStatus, default_note: str = "", source: str = "yfinance") -> Dict[str, Any]:
        if raw_val is None:
            status = ValueStatus.UNAVAILABLE.value
            note = default_note or "データソース未提供または算出不能"
            display = "取得できませんでした"
        else:
            status = default_status.value
            note = default_note
            display = formatted_val
        
        item = {
            "field_name": name,
            "raw_value": raw_val,
            "formatted_value": display,
            "status": status,
            "source": source,
            "as_of": financial_as_of,
            "note": note
        }
        fields_detail.append(item)
        return item

    # 1. 時価総額
    mcap_formatted = format_yen(market_cap)
    make_field_meta("時価総額", market_cap, mcap_formatted, ValueStatus.ACTUAL, "取引所ベース実測値")

    # 2. 実績PER
    pe_t_str = f"{round(pe_trailing, 2)} 倍" if pe_trailing is not None else "取得できませんでした（赤字または未提供）"
    make_field_meta("実績PER", pe_trailing, pe_t_str, ValueStatus.ACTUAL, "直近決算実績ベース")

    # 3. 予想PER
    pe_f_str = f"{round(pe_forward, 2)} 倍" if pe_forward is not None else "取得できませんでした（会社予想未開示または赤字）"
    make_field_meta("予想PER", pe_forward, pe_f_str, ValueStatus.ESTIMATED, "会社予想/コンセンサスベース")

    # 4. PBR
    pb_str = f"{round(pb_ratio, 2)} 倍" if pb_ratio is not None else "取得できませんでした（純資産未開示またはデータ未提供）"
    make_field_meta("PBR", pb_ratio, pb_str, ValueStatus.ACTUAL, "直近実績BPSベース")

    # 5. 配当利回り
    div_str = format_pct(dividend_yield) if dividend_yield is not None else "取得できませんでした（無配または予想未公表）"
    make_field_meta("配当利回り", dividend_yield, div_str, ValueStatus.ESTIMATED, "会社予想年間配当ベース")

    # 6. ROE
    roe_str = format_pct(roe) if roe is not None else "取得できませんでした（データ未提供）"
    make_field_meta("ROE (自己資本利益率)", roe, roe_str, ValueStatus.ACTUAL, "直近決算実績ベース")

    # 7. ROA
    roa_str = format_pct(roa) if roa is not None else "取得できませんでした（データ未提供）"
    make_field_meta("ROA (総資産利益率)", roa, roa_str, ValueStatus.ACTUAL, "直近決算実績ベース")

    # 8. 営業利益率
    op_margin_str = format_pct(operating_margin) if operating_margin is not None else "取得できませんでした（データ未提供）"
    make_field_meta("営業利益率", operating_margin, op_margin_str, ValueStatus.ACTUAL, "直近決算実績ベース")

    # 9. 純利益率
    profit_margin_str = format_pct(profit_margin) if profit_margin is not None else "取得できませんでした（データ未提供）"
    make_field_meta("純利益率", profit_margin, profit_margin_str, ValueStatus.ACTUAL, "直近決算実績ベース")

    # 10. 負債比率 (D/E)
    de_str = f"{round(debt_to_equity, 2)}" if debt_to_equity is not None else "取得できませんでした（データ未提供）"
    make_field_meta("負債比率 (D/E)", debt_to_equity, de_str, ValueStatus.ACTUAL, "直近貸借対照表ベース")

    # 11. 流動比率
    cr_str = f"{round(current_ratio, 2)}" if current_ratio is not None else "取得できませんでした（データ未提供）"
    make_field_meta("流動比率", current_ratio, cr_str, ValueStatus.ACTUAL, "直近貸借対照表ベース")

    # 12. 売上成長率 YoY
    rev_growth_str = format_pct(revenue_growth) if revenue_growth is not None else "取得できませんでした（前年比較データ未提供）"
    make_field_meta("売上高成長率 (YoY)", revenue_growth, rev_growth_str, ValueStatus.ACTUAL, "前年同期比実績")

    # 13. 利益成長率 YoY
    earn_growth_str = format_pct(earnings_growth) if earnings_growth is not None else "取得できませんでした（前年比較データ未提供）"
    make_field_meta("利益成長率 (YoY)", earnings_growth, earn_growth_str, ValueStatus.ACTUAL, "前年同期比実績")

    # 14. 売上高
    rev_formatted = format_yen(total_revenue)
    make_field_meta("売上高", total_revenue, rev_formatted, ValueStatus.ACTUAL, "直近実績")

    # 15. 純利益
    ni_formatted = format_yen(net_income)
    make_field_meta("純利益", net_income, ni_formatted, ValueStatus.ACTUAL, "直近実績")

    # 欠損・推定アイテムの抽出
    missing_items = [f"{item['field_name']}: {item['note']}" for item in fields_detail if item["status"] == ValueStatus.UNAVAILABLE.value]
    estimated_items = [f"{item['field_name']}: {item['note']}" for item in fields_detail if item["status"] == ValueStatus.ESTIMATED.value]

    return {
        "ticker": normalized_ticker,
        "market_cap_raw": market_cap,
        "market_cap_formatted": mcap_formatted,
        "financial_as_of": financial_as_of,
        "valuation": {
            "pe_trailing": round(pe_trailing, 2) if pe_trailing is not None else "取得できませんでした（赤字または未提供）",
            "pe_forward": round(pe_forward, 2) if pe_forward is not None else "取得できませんでした（会社予想未開示）",
            "pb_ratio": round(pb_ratio, 2) if pb_ratio is not None else "取得できませんでした（データ未提供）",
            "dividend_yield": div_str if dividend_yield is not None else "取得できませんでした（無配または未公表）"
        },
        "profitability": {
            "roe": roe_str if roe is not None else "取得できませんでした（データ未提供）",
            "roa": roa_str if roa is not None else "取得できませんでした（データ未提供）",
            "operating_margin": op_margin_str if operating_margin is not None else "取得できませんでした（データ未提供）",
            "profit_margin": profit_margin_str if profit_margin is not None else "取得できませんでした（データ未提供）"
        },
        "financial_health": {
            "debt_to_equity": round(debt_to_equity, 2) if debt_to_equity is not None else "取得できませんでした（データ未提供）",
            "current_ratio": round(current_ratio, 2) if current_ratio is not None else "取得できませんでした（データ未提供）"
        },
        "growth": {
            "revenue_growth_yoy": rev_growth_str if revenue_growth is not None else "取得できませんでした（データ未提供）",
            "earnings_growth_yoy": earn_growth_str if earnings_growth is not None else "取得できませんでした（データ未提供）",
            "total_revenue_formatted": rev_formatted,
            "net_income_formatted": ni_formatted
        },
        "fields_lineage": fields_detail,
        "missing_items": missing_items,
        "estimated_items": estimated_items
    }
