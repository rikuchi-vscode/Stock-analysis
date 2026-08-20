"""
システムログファイル (Central System Logger) ユニットテスト
"""

import os
import time
from src.logger import get_logger, LOG_FILE_PATH


def test_logger_writes_to_file():
    """ログファイルへの追記とフォーマットの検証"""
    logger = get_logger("test_module")
    
    unique_msg = f"TEST_LOG_MESSAGE_{int(time.time() * 1000)}"
    logger.info(unique_msg)

    # ログファイルが存在することを確認
    assert os.path.exists(LOG_FILE_PATH), f"ログファイルが見つかりません: {LOG_FILE_PATH}"

    # ファイルの中身を読み取ってメッセージが含まれているか確認
    with open(LOG_FILE_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    assert unique_msg in content, "出力したテストメッセージがログファイルに見つかりません"
    assert "[INFO]" in content, "ログレベル [INFO] がフォーマットに含まれていません"
    assert "[StockAnalysis.test_module]" in content, "モジュール名がフォーマットに含まれていません"
