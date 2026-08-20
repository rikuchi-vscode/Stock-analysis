"""
AI CEO Agent 単体テスト
"""

import pytest
from src.agents.ceo_agent import normalize_user_request, generate_ceo_summary
from src.contracts.ceo_request import NormalizedRequest
from src.contracts.stock_analysis import StockAnalysisResponse


def test_normalize_user_request_direct_ticker():
    """4桁数字および .T付きコードが即座に正規化されること"""
    res1 = normalize_user_request("7203")
    assert res1.ticker == "7203.T"
    assert res1.confidence == 1.0
    assert not res1.clarification_needed

    res2 = normalize_user_request("9984.T")
    assert res2.ticker == "9984.T"
    assert res2.confidence == 1.0


def test_normalize_user_request_natural_language():
    """自然言語からティッカーと投資期間が抽出できること"""
    res = normalize_user_request("トヨタ自動車を長期視点で分析してください")
    assert res.ticker == "7203.T"
    assert res.horizon in ["long", "medium"]
    assert not res.clarification_needed


def test_generate_ceo_summary():
    """STEP 0 レスポンスから CEO サマリーが正しく生成されること"""
    mock_response = StockAnalysisResponse(
        analysis_id=1,
        ticker="7203.T",
        company_name="トヨタ自動車",
        sector="自動車・輸送機",
        overall_score=85,
        investment_stance="中立・押し目買い",
        verification_status="OK",
        iteration_count=1,
        final_report="# テストレポート",
        report_path="output/test.md",
        analysis_result={
            "overall_score": 85,
            "investment_stance": "中立・押し目買い",
            "executive_summary": "強固な財務体質とハイブリッド需要が業績を牽引。",
            "core_investment_thesis": [
                "HEVの販売好調による高収益性維持",
                "円安恩恵と強固なネットキャッシュ"
            ]
        },
        risk_result={
            "risk_level": "中",
            "primary_downside_risks": [
                {"category": "為替リスク", "risk_factor": "急速な円高進行による収益圧迫"}
            ],
            "bearish_counter_arguments": ["EVシフトの遅れ懸念"]
        },
        logs=["テストログ"]
    )

    summary = generate_ceo_summary(mock_response)
    assert summary is not None
    assert summary.headline != ""
    assert len(summary.key_takeaways) > 0
    assert len(summary.key_risks) > 0
    assert "投資助言" in summary.disclaimer
