"""
ニュース・適時開示・定性情報収集ツール
"""

import yfinance as yf
from typing import List, Dict, Any
from datetime import datetime
from src.tools.market_tools import normalize_ticker


def fetch_stock_news(ticker: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    銘柄に関する直近のニュース記事一覧を取得
    """
    normalized_ticker = normalize_ticker(ticker)
    stock = yf.Ticker(normalized_ticker)
    news_items = stock.news or []

    results = []
    for item in news_items[:limit]:
        content = item.get("content", {}) if isinstance(item.get("content"), dict) else item
        title = content.get("title") or item.get("title", "")
        
        # publisher 抽出
        provider = content.get("provider") or item.get("publisher", "")
        publisher = provider.get("displayName") if isinstance(provider, dict) else str(provider)
        
        # link 抽出
        canonical_url = content.get("canonicalUrl", {})
        link = canonical_url.get("url") if isinstance(canonical_url, dict) else (content.get("link") or item.get("link", ""))
        
        # 日時抽出
        pub_date_str = content.get("pubDate") or item.get("providerPublishTime")
        publish_date = "不明"
        if isinstance(pub_date_str, int):
            publish_date = datetime.fromtimestamp(pub_date_str).strftime("%Y-%m-%d %H:%M")
        elif isinstance(pub_date_str, str):
            publish_date = pub_date_str[:16].replace("T", " ")

        if title:
            results.append({
                "title": title,
                "publisher": publisher,
                "link": link,
                "publish_date": publish_date
            })

    return results
