"""
レポート生成のデータ透明性・来歴セクション出力テスト
"""

import pytest
from src.report import generate_markdown_report
from src.state import AgentState


def test_generate_markdown_report_includes_data_lineage():
    # モックStateの作成
    state: AgentState = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "sector": "自動車・輸送用機器",
        "iteration_count": 0,
        "market_data": {
            "current_price": 3150.0,
            "price_change_pct": 1.2,
            "market_as_of": "2026-08-20",
            "sma_trend": "強気 (SMA25 > SMA75)",
            "sma_25": 3100.0,
            "sma_75": 2980.0,
            "rsi_14": 58.5,
            "rsi_status": "中立水準 (58.5)",
            "bb_upper": 3250.0,
            "bb_lower": 2950.0,
            "high_52w": 3300.0,
            "low_52w": 2500.0,
            "missing_items": [],
            "fallback_items": ["上値抵抗線: BB上限からの代替参考値"],
            "analysis": {
                "trend_summary": "テクニカル堅調",
                "support_resistance": {
                    "resistance": "3,250 円（参考値）",
                    "support": "2,950 円（参考値）"
                }
            }
        },
        "financial_data": {
            "market_cap_formatted": "45.00 兆円",
            "financial_as_of": "2026-03-31",
            "valuation": {
                "pe_trailing": 10.5,
                "pe_forward": 11.2,
                "pb_ratio": 1.1,
                "dividend_yield": "3.20%"
            },
            "profitability": {
                "roe": "12.00%",
                "roa": "6.50%",
                "operating_margin": "10.20%"
            },
            "growth": {
                "total_revenue_formatted": "45.00 兆円",
                "net_income_formatted": "4.50 兆円",
                "revenue_growth_yoy": "8.50%",
                "earnings_growth_yoy": "12.00%"
            },
            "missing_items": [],
            "estimated_items": ["予想PER: 会社予想ベース", "配当利回り: 予想配当ベース"]
        },
        "news_data": {
            "news_items": [
                {"title": "トヨタ、次世代EVバッテリー投資を加速", "publisher": "日経新聞", "link": "https://example.com/1", "publish_date": "2026-08-19 10:00"}
            ],
            "news_count": 1,
            "analysis": {
                "sentiment": "やや強気",
                "sentiment_score": 70,
                "analyst_comment": "事業展開は順調"
            }
        },
        "analysis_result": {
            "overall_score": 85,
            "investment_stance": "Buy (買い)",
            "executive_summary": "強固な事業基盤を評価する一方、為替リスクに注意。",
            "core_investment_thesis": ["世界トップの販売シェア", "高い利益率"],
            "price_scenarios": {
                "bull_case": "3,500円（前提: EPS成長）",
                "base_case": "3,200円（前提: 現行PER）",
                "bear_case": "2,800円（前提: サポート割れ）"
            },
            "horizon_strategy": {
                "short_term": "押し目買い",
                "medium_term": "継続保有",
                "long_term": "成長享受"
            }
        },
        "risk_result": {
            "risk_level": "中",
            "primary_downside_risks": [
                {"category": "マクロ", "risk_factor": "円高進行", "impact": "中", "trigger_event": "日米金利差縮小"}
            ],
            "bearish_counter_arguments": ["為替急変動リスク"],
            "max_drawdown_estimate": "-10%",
            "stop_loss_guideline": "2,900円割れ"
        },
        "verification_result": {
            "status": "OK",
            "completeness_score": 90,
            "consistency_score": 90,
            "transparency_score": 95,
            "fact_grounding_score": 95,
            "numerical_consistency_ok": True,
            "citations_valid": True,
            "time_consistency_ok": True,
            "calculation_basis_present": True,
            "fact_opinion_separated": True,
            "balanced_view_present": True,
            "hidden_missing_detected": False,
            "data_quality_notes": ["欠損隠蔽なし"]
        }
    }

    report = generate_markdown_report(state)

    # 検証: レポートにデータ品質と来歴情報セクションが存在すること
    assert "## 7. データ品質と来歴情報" in report
    assert "6大厳格品質ゲート" in report
    assert "2026-08-20" in report
    assert "yfinance" in report
    assert "ファクト照合: **95/100**" in report
    assert "透明性: **95/100**" in report
    assert "欠損隠蔽なし" in report
