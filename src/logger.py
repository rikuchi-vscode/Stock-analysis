"""
集中システムロギングモジュール (Central System Logger)
ブラウザ画面には表示せず、logs/stock_analysis.log ファイルに詳細な実行・監査ログを安全に出力・永続化する。
RotatingFileHandler による容量制限 (最大10MB × 5世代) 対応。
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
LOG_FILE_PATH = os.path.join(LOG_DIR, "stock_analysis.log")

# ログディレクトリの自動作成
os.makedirs(LOG_DIR, exist_ok=True)

# ログフォーマット定義
LOG_FORMAT = "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s] %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_initialized = False


def setup_system_logging(level: int = logging.INFO) -> logging.Logger:
    """システムロガーの初期化 (シングルトン構成)"""
    global _initialized
    root_logger = logging.getLogger("StockAnalysis")
    root_logger.setLevel(level)

    if not _initialized:
        # 1. ファイルハンドラー (RotatingFileHandler: 10MB × 5世代, UTF-8)
        file_handler = RotatingFileHandler(
            LOG_FILE_PATH,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

        # 2. コンソールハンドラー (標準出力用)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.WARNING)  # コンソールは WARNING 以上のみ
        console_formatter = logging.Formatter(fmt="[%(levelname)s] [%(name)s] %(message)s")
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

        _initialized = True

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    モジュール名に応じたロガーインスタンスを返す。
    使用例:
        from src.logger import get_logger
        logger = get_logger(__name__)
        logger.info("リサーチを開始しました")
    """
    setup_system_logging()
    return logging.getLogger(f"StockAnalysis.{name}")


# 初期化
setup_system_logging()
