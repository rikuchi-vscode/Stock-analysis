"""
Decision Journal Service モジュール
STEP 4: 方針策定・イベントトリアージ・重要判断における仮説と期待成果の自動記録
"""

import uuid
from typing import Dict, Any, Optional, List

from src.contracts.decision_journal import JournalEntry
from src.contracts.research_policy import ResearchPolicy
from src.contracts.watch_item import MarketEvent, TriageResult
from src.repositories.governance_repository import save_journal_entry, list_journal_entries, get_journal_entry


def record_policy_journal(policy: ResearchPolicy, run_id: Optional[str] = None) -> JournalEntry:
    """
    リサーチ方針策定時の意思決定ジャーナルを記録する。
    """
    journal_id = f"jrnl_pol_{uuid.uuid4().hex[:10]}"
    primary_ticker = policy.scope.primary_tickers[0] if policy.scope.primary_tickers else None

    # 仮説・前提・期待成果の構造化
    hypothesis = f"【調査目的】{policy.objective}。{policy.mode}モードおよび深度 {policy.analysis_depth} による調査が妥当である。"
    assumptions = [
        f"分析モード: {policy.mode}",
        f"対象銘柄: 主要={','.join(policy.scope.primary_tickers)}, 比較={','.join(policy.scope.peer_tickers)}",
        f"リサーチ論点: {'; '.join(policy.research_questions)}"
    ]
    expected_outcome = f"{primary_ticker or '対象銘柄'} に関する検証済み投資スタンス、リスク要因の明確化、および総合サマリーの獲得。"
    risk_assessment = policy.rationale or ["市場データの急変", "開示情報の解釈齟齬"]

    entry = JournalEntry(
        journal_id=journal_id,
        run_id=run_id or policy.run_id,
        strategy_id=policy.strategy_id,
        decision_type="POLICY_CREATION",
        ticker=primary_ticker,
        hypothesis=hypothesis,
        assumptions=assumptions,
        expected_outcome=expected_outcome,
        risk_assessment=risk_assessment,
        actor="AI CEO"
    )

    save_journal_entry(entry)
    return entry


def record_event_triage_journal(event: MarketEvent, triage: TriageResult) -> JournalEntry:
    """
    市場イベントトリアージ時の意思決定ジャーナルを記録する。
    """
    journal_id = f"jrnl_trg_{uuid.uuid4().hex[:10]}"
    hypothesis = f"市場イベント '{event.title}' (重要度: {event.severity}) に対し、アクション '{triage.action}' を選択することが最善である。"
    assumptions = [
        f"イベント種別: {event.event_type}",
        f"対象銘柄: {event.ticker} ({event.company_name})",
        f"検知詳細: {event.description}"
    ]
    expected_outcome = f"トリアージ理由: {triage.reason} に基づく迅速なアクション（{triage.action}）の完遂。"

    entry = JournalEntry(
        journal_id=journal_id,
        decision_type="EVENT_TRIAGE",
        ticker=event.ticker,
        hypothesis=hypothesis,
        assumptions=assumptions,
        expected_outcome=expected_outcome,
        risk_assessment=[f"ノイズ誤認リスクまたは初動遅延リスク"],
        actor="Event Triage Agent"
    )

    save_journal_entry(entry)
    return entry
