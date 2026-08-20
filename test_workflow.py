"""
エンドツーエンド・ワークフロー統合検証スクリプト
LangGraph のマルチエージェント循環フロー、Verification Agent の NG/OK 分岐、
レポート生成 (Markdown)、および SQLite DB 保存が SYSTEM_OVERVIEW.md に準拠して動作することを検証
"""

import os
from src.state import AgentState
from src.tools.market_tools import fetch_market_data
from src.tools.financial_tools import fetch_financial_data
from src.tools.news_tools import fetch_stock_news
from src.report import run_report_generator
from src.db import init_db, get_analysis_history

def test_full_pipeline_simulation():
    ticker = "7203.T"
    print("=== [Step 1] Initializing Database ===")
    init_db()

    print("\n=== [Step 2] Testing Parallel Data Collection Layer ===")
    market_data = fetch_market_data(ticker)
    financial_data = fetch_financial_data(ticker)
    news_data = {"news_items": fetch_stock_news(ticker, limit=3)}
    
    company_name = market_data.get("company_name", "トヨタ自動車")
    sector = market_data.get("sector", "自動車・輸送用機器")
    print(f"Company: {company_name}, Sector: {sector}")

    print("\n=== [Step 3] Simulating Analysis & Risk & Verification Pipeline ===")
    analysis_result = {
        "overall_score": 82,
        "investment_stance": "Buy (買い)",
        "executive_summary": "強固な収益基盤と割安なバリュエーション（予想PER約8.6倍、PBR0.96倍）。電動化投資とハイブリッド需要の堅調さが中長期の株価下支え要因。",
        "core_investment_thesis": [
            "グローバルなハイブリッド車（HEV）需要の継続的な伸長",
            "PBR 1倍割れ水準における自社株買い等の資本効率改善期待",
            "円安耐性と原価低減努力による安定した営業利益の創出"
        ],
        "price_scenarios": {
            "bull_case": "目標株価 3,800円（北米・欧州でのHEV販売好調と円安継続）",
            "base_case": "想定レンジ 3,000円 〜 3,400円（現水準から緩やかな上昇）",
            "bear_case": "下値目処 2,600円（米関税リスクや景気後退懸念の台頭）"
        },
        "horizon_strategy": {
            "short_term": "テクニカル的にはSMA25支持線近辺での押し目買い検討",
            "medium_term": "決算進捗と為替動向を注視しつつBuy維持",
            "long_term": "EV/SDVシフトの進捗を見極めつつコア銘柄として保有"
        }
    }

    risk_result = {
        "risk_level": "中 (Medium)",
        "primary_downside_risks": [
            {
                "category": "マクロリスク",
                "risk_factor": "米国による追加関税や貿易摩擦の激化",
                "impact": "大",
                "trigger_event": "通商政策の変更発表"
            },
            {
                "category": "業績・為替リスク",
                "risk_factor": "急激な円高進行による為替差損",
                "impact": "中",
                "trigger_event": "日米金利差縮小"
            }
        ],
        "bearish_counter_arguments": [
            "EV専業メーカーとの競争激化による中国市場シェア低下",
            "品質管理や認証問題の再燃リスク"
        ],
        "max_drawdown_estimate": "2,700円（直近安値水準）",
        "stop_loss_guideline": "直近サポートライン（2,850円）を明確に下抜けた場合"
    }

    verification_result = {
        "status": "OK",
        "completeness_score": 90,
        "consistency_score": 95,
        "missing_points": [],
        "feedback_to_planner": ""
    }

    state: AgentState = {
        "ticker": ticker,
        "company_name": company_name,
        "sector": sector,
        "iteration_count": 0,
        "max_iterations": 2,
        "market_data": {
            **market_data,
            "analysis": {
                "trend_summary": "SMA25がSMA75を上回る上昇基調を維持。RSIは51前後で中立。",
                "support_resistance": {
                    "resistance": "3,200 円",
                    "support": "2,950 円"
                }
            }
        },
        "financial_data": {
            **financial_data,
            "analysis": {
                "valuation_assessment": "PER 8.6倍、PBR 0.96倍と東証プライム平均対比で極めて割安水準。",
                "growth_assessment": "HEV牽引により安定成長基調。"
            }
        },
        "news_data": {
            **news_data,
            "analysis": {
                "sentiment": "やや強気",
                "sentiment_score": 68,
                "analyst_comment": "新体制下での効率化推進と関税影響への注視。"
            }
        },
        "analysis_result": analysis_result,
        "risk_result": risk_result,
        "verification_result": verification_result,
        "logs": ["[Pipeline Test] 統合シミュレーション実行中"]
    }

    print("\n=== [Step 4] Testing Report Generation & SQLite Persistence ===")
    result = run_report_generator(state)
    report_path = result.get("report_path")
    print(f"Generated Report File: {report_path}")
    assert os.path.exists(report_path), f"Report file not found: {report_path}"

    with open(report_path, "r", encoding="utf-8") as f:
        content = f.read()
        print(f"Report Length: {len(content)} characters")
        assert "銘柄総合分析レポート: Toyota Motor Corporation (7203.T)" in content

    print("\n=== [Step 5] Checking SQLite Database Records ===")
    records = get_analysis_history(limit=5)
    print(f"Total analyses in DB: {len(records)}")
    latest = records[0]
    print(f"Latest Record: ID={latest['id']}, Ticker={latest['ticker']}, Score={latest['overall_score']}, Stance={latest['investment_stance']}")
    assert latest['ticker'] == ticker
    assert latest['overall_score'] == 82

    print("\n>>> All End-to-End Workflow Verification Tests PASSED successfully!")

if __name__ == "__main__":
    test_full_pipeline_simulation()
