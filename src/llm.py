"""
Gemini API クライアント初期化およびレスポンス抽出モジュール
"""

import os
import time
from typing import Optional, Any
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from src.logger import get_logger

logger = get_logger("llm")
load_dotenv()


def get_api_key() -> str:
    """GEMINI_API_KEY を環境変数または Streamlit Secrets から取得・検証"""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        try:
            import streamlit as st
            if hasattr(st, "secrets") and "GEMINI_API_KEY" in st.secrets:
                api_key = st.secrets["GEMINI_API_KEY"]
                os.environ["GEMINI_API_KEY"] = api_key
        except Exception:
            pass

    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY が設定されていません。.env ファイルまたは Streamlit Secrets に GEMINI_API_KEY を設定してください。"
        )
    return api_key


def extract_text_content(response: Any) -> str:
    """
    LLMレスポンスからテキスト文字列を確実に抽出（文字列型およびマルチパートリスト型の両方に対応）
    """
    if hasattr(response, "content"):
        content = response.content
    else:
        content = response

    if isinstance(content, str):
        return content.strip()
    elif isinstance(content, list):
        text_parts = []
        for item in content:
            if isinstance(item, str):
                text_parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                text_parts.append(item["text"])
            elif hasattr(item, "text"):
                text_parts.append(getattr(item, "text", ""))
        return "".join(text_parts).strip()
    return str(content).strip()


import time
import re

def get_fast_model(temperature: float = 0.2, model_name: Optional[str] = None) -> ChatGoogleGenerativeAI:
    """
    データ収集・要約用モデル
    """
    api_key = get_api_key()
    selected_model = model_name or os.getenv("DEFAULT_FAST_MODEL", "gemini-3.6-flash")
    return ChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=api_key,
        temperature=temperature,
        max_retries=2,
        request_timeout=30.0,
    )


def get_pro_model(temperature: float = 0.2, model_name: Optional[str] = None) -> ChatGoogleGenerativeAI:
    """
    計画策定・統合分析・リスク評価・検証用モデル
    """
    api_key = get_api_key()
    selected_model = model_name or os.getenv("DEFAULT_PRO_MODEL", "gemini-3.6-flash")
    return ChatGoogleGenerativeAI(
        model=selected_model,
        google_api_key=api_key,
        temperature=temperature,
        max_retries=2,
        request_timeout=30.0,
    )


def safe_invoke_llm(llm: ChatGoogleGenerativeAI, messages: Any, max_attempts: int = 2, base_delay: float = 3.0) -> Any:
    """
    429 RESOURCE_EXHAUSTED (レート制限) を自動検知し、短時間待機してリトライする安全な呼び出しラッパー。
    長時間のフリーズを防ぐため、待機時間は最大5秒とし、上限到達時は速やかに例外を送出してフォールバックへ委譲する。
    """
    attempt = 0
    delay = base_delay
    while attempt < max_attempts:
        attempt += 1
        try:
            return llm.invoke(messages)
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                wait_sec = min(delay, 5.0)
                logger.warning(f"Gemini API レート制限 (429) を検知 (試行: {attempt}/{max_attempts}) - {wait_sec:.1f}秒待機してリトライします")
                if attempt >= max_attempts:
                    logger.error(f"Gemini API レート制限の最大試行回数に到達: {e}")
                    raise e
                time.sleep(wait_sec)
                delay *= 1.5
            else:
                logger.error(f"Gemini API 呼び出しエラー: {e}")
                raise e

