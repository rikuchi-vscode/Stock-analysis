"""
主要銘柄（ソニー・任天堂・ホンダ・日立）の初期分析データをDBに登録するシードスクリプト
"""

from src.db import init_db, save_analysis
from datetime import datetime

def seed_sample_analyses():
    init_db()
    
    samples = [
        {
            "ticker": "6758.T",
            "company_name": "Sony Group Corporation (ソニーグループ)",
            "sector": "電気機器・エンターテインメント",
            "overall_score": 86,
            "investment_stance": "Buy (買い)",
            "verification_status": "OK",
            "iteration_count": 0,
            "report_path": "output/Report_6758_T_sample.md",
            "report_content": "# ソニーグループ (6758.T) 企業分析レポート\n\n## 総合スコア: 86 / 100\n- ゲーム、音楽、半導体（CMOSセンサー）が強力に成長を牽引しています。\n- 多角化による安定したキャッシュフローが強みです。",
            "market_data": {"current_price": 3456.0, "daily_change_pct": 1.45, "volume": 8245600, "sector": "電気機器"},
            "financial_data": {"score": 78.0, "summary": "営業利益率が高水準を維持"},
            "news_data": {"count": 5, "headlines": ["ソニー、次世代センサー技術を発表", "音楽事業が過去最高益"]},
            "logs": ["[PlannerAgent] 計画策定完了", "[AnalysisAgent] 総合スコア86判定", "[VerificationAgent] OK"]
        },
        {
            "ticker": "7974.T",
            "company_name": "Nintendo Co., Ltd. (任天堂)",
            "sector": "その他製品・ゲーム",
            "overall_score": 84,
            "investment_stance": "Buy (買い)",
            "verification_status": "OK",
            "iteration_count": 0,
            "report_path": "output/Report_7974_T_sample.md",
            "report_content": "# 任天堂 (7974.T) 企業分析レポート\n\n## 総合スコア: 84 / 100\n- 世界屈指のキャラクターIPと無借金経営による強固な財務体質を有しています。\n- 次世代機への期待とIP展開が注目材料です。",
            "market_data": {"current_price": 8120.0, "daily_change_pct": -0.85, "volume": 3450000, "sector": "その他製品"},
            "financial_data": {"score": 85.0, "summary": "自己資本比率80%超の実質無借金経営"},
            "news_data": {"count": 5, "headlines": ["任天堂IPテーマパークが好調", "次世代ゲーム機に関する公式言及"]},
            "logs": ["[PlannerAgent] 計画策定完了", "[AnalysisAgent] 総合スコア84判定", "[VerificationAgent] OK"]
        },
        {
            "ticker": "7267.T",
            "company_name": "Honda Motor Co., Ltd. (本田技研工業)",
            "sector": "輸送用機器",
            "overall_score": 82,
            "investment_stance": "Buy (買い)",
            "verification_status": "OK",
            "iteration_count": 0,
            "report_path": "output/Report_7267_T_sample.md",
            "report_content": "# 本田技研工業 (7267.T) 企業分析レポート\n\n## 総合スコア: 82 / 100\n- 二輪事業の世界シェア首位と高い利益率が収益基盤を支えています。\n- 北米ハイブリッド四輪車も堅調です。",
            "market_data": {"current_price": 1580.0, "daily_change_pct": 0.64, "volume": 15230000, "sector": "輸送用機器"},
            "financial_data": {"score": 75.0, "summary": "二輪高収益・積極的な自社株買い"},
            "news_data": {"count": 5, "headlines": ["ホンダ、二輪新モデル好調", "EV戦略の共同開発発表"]},
            "logs": ["[PlannerAgent] 計画策定完了", "[AnalysisAgent] 総合スコア82判定", "[VerificationAgent] OK"]
        }
    ]

    for s in samples:
        save_analysis(
            ticker=s["ticker"],
            company_name=s["company_name"],
            sector=s["sector"],
            overall_score=s["overall_score"],
            investment_stance=s["investment_stance"],
            verification_status=s["verification_status"],
            iteration_count=s["iteration_count"],
            report_content=s["report_content"],
            report_path=s["report_path"],
            market_data=s["market_data"],
            financial_data=s["financial_data"],
            news_data=s["news_data"],
            logs=s["logs"]
        )
    print("[OK] ソニーグループ・任天堂・本田技研工業の分析データをDBに登録完了しました。")

if __name__ == "__main__":
    seed_sample_analyses()
