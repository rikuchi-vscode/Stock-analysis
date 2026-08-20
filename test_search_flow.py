"""
Webダッシュボードの「最新データでAI再調査を実行」ボタンの内部フロー実機動作検証
"""

import time
import json
from src.db import init_db, get_latest_report_content, get_analysis_history
from src.orchestration.ceo_graph import run_ceo_workflow

def verify_ai_reanalysis():
    print("==================================================")
    print("[Web UI Button Simulation] AI Re-analysis Start...")
    print("==================================================")
    
    init_db()
    start_time = time.time()
    query = "ソニーグループ"

    print(f"Input Query: '{query}'")
    ceo_state = run_ceo_workflow(user_request=query, max_iterations=1)
    elapsed = time.time() - start_time

    print(f"\nElapsed Time: {elapsed:.2f} s")
    print(f"Status: {ceo_state.status}")
    print(f"Ticker: {ceo_state.ticker}")
    print(f"Company: {ceo_state.company_name}")
    print(f"Verification: {ceo_state.verification_status}")
    print(f"Report Path: {ceo_state.report_path}")

    assert ceo_state.status != "FAILED", f"Analysis failed: {ceo_state.error}"
    assert ceo_state.ticker == "6758.T", f"Ticker mismatch: {ceo_state.ticker}"
    assert ceo_state.ceo_summary is not None, "CEO summary is None"

    print("\n--- CEO Summary ---")
    print(f"Headline: {ceo_state.ceo_summary.headline}")
    print("Key Takeaways:")
    for t in ceo_state.ceo_summary.key_takeaways:
        print(f"  * {t}")
    print("Key Risks:")
    for r in ceo_state.ceo_summary.key_risks:
        print(f"  * {r}")

    # DB永続化の確認
    print("\n--- DB Persistence Check ---")
    latest_report = get_latest_report_content(ceo_state.ticker)
    assert latest_report is not None, "Could not fetch report from DB"
    print(f"[OK] Fetched report from DB successfully (Length: {len(latest_report)} chars)")
    print(f"Report Preview:\n{latest_report[:200]}...")

    print("\n==================================================")
    print("[SUCCESS] AI Re-analysis is completely working!")
    print("==================================================")

if __name__ == "__main__":
    verify_ai_reanalysis()
