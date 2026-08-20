"""
厳格品質ゲート (Strict Verification Gate) のユニットテスト
6大検証基準（数値一致、出典URL、時点整合、計算根拠、事実解釈分離、両論併記）の動作を検証
"""

import pytest
from src.agents.verification_agent import verify_deterministic_rules
from src.state import AgentState


def test_deterministic_rules_all_pass():
    # 正常なState
    state: AgentState = {
        "ticker": "7203.T",
        "company_name": "トヨタ自動車",
        "sector": "自動車・輸送用機器",
        "iteration_count": 0,
        "market_data": {
            "current_price": 3150.0,
            "price_change_pct": 1.2,
            "market_as_of": "2026-08-20",
            "missing_items": [],
            "fallback_items": []
        },
        "financial_data": {
            "financial_as_of": "2026-03-31",
            "valuation": {"pe_trailing": 10.5, "pb_ratio": 1.1},
            "missing_items": []
        },
        "news_data": {
            "news_items": [
                {
                    "title": "トヨタ、新技術開発",
                    "publisher": "日経新聞",
                    "link": "https://example.com/news/123",
                    "publish_date": "2026-08-20 10:00"
                }
            ]
        },
        "analysis_result": {
            "overall_score": 80,
            "score_calculation_basis": "財務健全性(40点) + テクニカル(40点)",
            "investment_stance": "Buy (買い)",
            "executive_summary": "強固な事業基盤（現在株価: 3150.0円）を評価する一方、為替変動および景気後退のリスクに注意が必要です。",
            "price_scenarios": {
                "bull_case": "3,500円（前提: 予想EPS 250円 × PER 14倍）",
                "base_case": "3,150円（前提: 現行PER水準維持）",
                "bear_case": "2,800円（前提: 75日線サポート割れ）"
            }
        },
        "risk_result": {
            "primary_downside_risks": [
                {"category": "マクロ", "risk_factor": "為替円高", "impact": "中", "trigger_event": "金利差縮小"}
            ]
        }
    }

    flags, failed_checks, score = verify_deterministic_rules(state)
    assert flags["citations_valid"] is True
    assert flags["time_consistency_ok"] is True
    assert flags["calculation_basis_present"] is True
    assert flags["balanced_view_present"] is True
    assert len(failed_checks) == 0
    assert score == 100


def test_deterministic_rules_detect_invalid_citation():
    # ニュースのURLがないState
    state: AgentState = {
        "ticker": "7203.T",
        "market_data": {"market_as_of": "2026-08-20"},
        "financial_data": {"financial_as_of": "2026-03-31"},
        "news_data": {
            "news_items": [
                {
                    "title": "未確認情報",
                    "publisher": "匿名の噂",
                    "link": "",  # URLなし
                    "publish_date": "不明"  # 日時不明
                }
            ]
        },
        "analysis_result": {
            "executive_summary": "収益性は安定ですが、為替リスクに注意。",
            "price_scenarios": {"bull_case": "3,500円（前提: 業績拡大）"}
        },
        "risk_result": {"primary_downside_risks": [{"risk_factor": "為替"}]}
    }

    flags, failed_checks, score = verify_deterministic_rules(state)
    assert flags["citations_valid"] is False
    assert any("出典URL" in c for c in failed_checks)
    assert any("公開日時" in c for c in failed_checks)
    assert score < 100


def test_deterministic_rules_detect_unjustified_calculation():
    # 目標株価に根拠のないState
    state: AgentState = {
        "ticker": "7203.T",
        "market_data": {"market_as_of": "2026-08-20"},
        "financial_data": {"financial_as_of": "2026-03-31"},
        "news_data": {"news_items": []},
        "analysis_result": {
            "executive_summary": "事業基盤は強固ですが、市場リスクに留意。",
            "price_scenarios": {
                "bull_case": "なんとなく上がる",
                "base_case": "そのまま",
                "bear_case": "下がる"
            }
        },
        "risk_result": {"primary_downside_risks": [{"risk_factor": "リスク"}]}
    }

    flags, failed_checks, score = verify_deterministic_rules(state)
    assert flags["calculation_basis_present"] is False
    assert any("計算前提" in c for c in failed_checks)


def test_deterministic_rules_detect_bias_without_risks():
    # 良い点のみでリスクに一切触れていない買い煽りState
    state: AgentState = {
        "ticker": "7203.T",
        "market_data": {"market_as_of": "2026-08-20"},
        "financial_data": {"financial_as_of": "2026-03-31"},
        "news_data": {"news_items": []},
        "analysis_result": {
            "executive_summary": "この企業は最高です。利益も急拡大しており将来性抜群です。",
            "price_scenarios": {"bull_case": "5,000円（前提: EPS成長）"}
        },
        "risk_result": {
            "primary_downside_risks": [{"risk_factor": "原材料高騰", "impact": "高"}]
        }
    }

    flags, failed_checks, score = verify_deterministic_rules(state)
    assert flags["balanced_view_present"] is False
    assert any("リスク" in c or "併記" in c for c in failed_checks)
