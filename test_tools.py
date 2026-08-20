"""
データ収集ツール単体テストスクリプト
東証銘柄（トヨタ自動車: 7203）の株価、財務、ニュースデータが正常に取得・計算できるかを検証
"""

from src.tools.market_tools import fetch_market_data
from src.tools.financial_tools import fetch_financial_data
from src.tools.news_tools import fetch_stock_news

def test_data_fetch():
    ticker = "7203"
    print(f"--- 1. Market Data Test ({ticker}) ---")
    market = fetch_market_data(ticker)
    print("Market Data Keys:", list(market.keys()))
    print(f"Company: {market.get('company_name')}, Price: {market.get('current_price')} JPY, Trend: {market.get('sma_trend')}, RSI: {market.get('rsi_14')}")
    assert "error" not in market, f"Market fetch error: {market.get('error')}"

    print(f"\n--- 2. Financial Data Test ({ticker}) ---")
    fin = fetch_financial_data(ticker)
    print("Financial Data Keys:", list(fin.keys()))
    print(f"Market Cap: {fin.get('market_cap_formatted')}, Trailing PE: {fin.get('valuation', {}).get('pe_trailing')}x, PBR: {fin.get('valuation', {}).get('pb_ratio')}x")
    assert "error" not in fin, f"Financial fetch error: {fin.get('error')}"

    print(f"\n--- 3. News Data Test ({ticker}) ---")
    news = fetch_stock_news(ticker, limit=3)
    print(f"News count: {len(news)}")
    for item in news:
        print(f" - [{item.get('publish_date')}] {item.get('title')} ({item.get('publisher')})")
    
    print("\n>>> All data fetch tool tests PASSED successfully!")

if __name__ == "__main__":
    test_data_fetch()
