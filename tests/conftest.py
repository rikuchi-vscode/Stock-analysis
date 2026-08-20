"""
Pytest 共通設定・フィクスチャ (conftest.py)
テスト実行時は本番DB (data/stock_analysis.db) を汚染しないよう、
一時テストDB (data/test_stock_analysis.db) に自動で分離します。
"""

import os
import pytest
import tempfile
import sqlite3

import src.db as db_mod
import src.repositories.monitor_repository as mon_repo
import src.repositories.policy_repository as pol_repo
import src.repositories.governance_repository as gov_repo

@pytest.fixture(autouse=True)
def isolate_test_database(tmp_path, monkeypatch):
    """すべてのテスト実行時に独立した一時SQLiteデータベースを使用する"""
    test_db_path = str(tmp_path / "test_stock.db")
    
    # DB_PATH を一時テストDBへ差し替え
    monkeypatch.setattr(db_mod, "DB_PATH", test_db_path)
    monkeypatch.setattr(mon_repo, "DB_PATH", test_db_path)
    monkeypatch.setattr(pol_repo, "DB_PATH", test_db_path)
    monkeypatch.setattr(gov_repo, "DB_PATH", test_db_path)
    
    # 初期化
    db_mod.init_db()
    
    yield
