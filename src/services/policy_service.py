"""
Policy Service モジュール
STEP 2: リサーチ方針の策定・安全ガード・人間承認管理・方針に基づく分析実行
"""

import uuid
from typing import Dict, Any, List, Optional, Tuple

from src.contracts.research_policy import (
    ResearchPolicy,
    PolicyDecision,
    PolicyApproval,
    PolicyOutcome,
)
from src.contracts.analysis_plan import DetailedAnalysisPlan
from src.contracts.stock_analysis import StockAnalysisResponse
from src.agents.ceo_agent import propose_research_policy, evaluate_policy_outcome
from src.agents.policy_guard_agent import evaluate_policy_guard
from src.services.planner_adapter import adapt_policy_to_analysis_plan
from src.services.report_adapter import adapt_step0_to_response
from src.graph import create_stock_analysis_graph
from src.repositories.policy_repository import (
    save_research_policy,
    get_research_policy,
    update_policy_status,
    record_policy_decision,
    save_policy_approval,
    save_policy_outcome,
)
from src.services.journal_service import record_policy_journal


def propose_policy(user_request: str) -> ResearchPolicy:
    """
    ユーザー依頼からリサーチ方針を策定し、安全ガード検査を実施して保存する。
    また、意思決定ガバナンスとして意思決定ジャーナルを自動記録する。
    """
    # 1. CEO Agent による方針案策定
    raw_policy = propose_research_policy(user_request)

    # 2. Policy Guard による制約・安全性・コスト検査
    guarded_policy, decisions = evaluate_policy_guard(raw_policy)

    # 3. 永続化
    save_research_policy(guarded_policy)
    for dec in decisions:
        record_policy_decision(dec)

    # 4. [STEP 4] 意思決定ジャーナルの自動記録
    try:
        record_policy_journal(guarded_policy)
    except Exception:
        pass

    # 承認が必要な場合は承認レコードを発行
    if guarded_policy.approval_required:
        approval_id = f"appr_{uuid.uuid4().hex[:12]}"
        save_policy_approval(PolicyApproval(
            approval_id=approval_id,
            strategy_id=guarded_policy.strategy_id,
            requested_action=f"リサーチ方針実行承認: {guarded_policy.objective} ({guarded_policy.approval_reason})",
            status="PENDING",
            created_at=None
        ))

    return guarded_policy


def approve_policy(strategy_id: str, approved_by: str = "human_owner", comment: str = "") -> Optional[ResearchPolicy]:
    """
    承認待ちのリサーチ方針を承認する。
    """
    policy = get_research_policy(strategy_id)
    if not policy:
        return None

    policy.status = "APPROVED"
    policy.approval_required = False
    save_research_policy(policy)

    # 承認レコード更新
    approval_id = f"appr_{uuid.uuid4().hex[:12]}"
    save_policy_approval(PolicyApproval(
        approval_id=approval_id,
        strategy_id=strategy_id,
        requested_action="リサーチ方針承認",
        status="APPROVED",
        approved_by=approved_by,
        comment=comment or "人間所有者による承認完了"
    ))

    # 決定ログ記録
    record_policy_decision(PolicyDecision(
        decision_id=f"dec_appr_{uuid.uuid4().hex[:8]}",
        strategy_id=strategy_id,
        decision_type="MANUALLY_APPROVED",
        rationale=f"所有者 ({approved_by}) により承認されました。コメント: {comment}",
        actor=approved_by
    ))

    return policy


def reject_policy(strategy_id: str, rejected_by: str = "human_owner", comment: str = "") -> Optional[ResearchPolicy]:
    """
    承認待ちのリサーチ方針を却下する。
    """
    policy = get_research_policy(strategy_id)
    if not policy:
        return None

    policy.status = "REJECTED"
    save_research_policy(policy)

    approval_id = f"appr_{uuid.uuid4().hex[:12]}"
    save_policy_approval(PolicyApproval(
        approval_id=approval_id,
        strategy_id=strategy_id,
        requested_action="リサーチ方針却下",
        status="REJECTED",
        approved_by=rejected_by,
        comment=comment or "人間所有者による却下"
    ))

    record_policy_decision(PolicyDecision(
        decision_id=f"dec_rej_{uuid.uuid4().hex[:8]}",
        strategy_id=strategy_id,
        decision_type="MANUALLY_REJECTED",
        rationale=f"所有者 ({rejected_by}) により却下されました。理由: {comment}",
        actor=rejected_by
    ))

    return policy


def execute_policy(policy: ResearchPolicy) -> Tuple[PolicyOutcome, List[StockAnalysisResponse]]:
    """
    承認済みリサーチ方針を STEP 0 株価分析部門へ展開し、実行する。
    """
    update_policy_status(policy.strategy_id, "EXECUTING")

    # 1. 実行計画の構築
    plan: DetailedAnalysisPlan = adapt_policy_to_analysis_plan(policy)

    responses: List[StockAnalysisResponse] = []
    stock_app = create_stock_analysis_graph()

    # 2. 計画された各銘柄の分析実行
    for target in plan.targets:
        step0_state = {
            "ticker": target.ticker,
            "iteration_count": 0,
            "max_iterations": target.max_iterations,
            "logs": [f"[Policy Execution] 方針 {policy.strategy_id} ({target.role}) に基づき分析開始"]
        }
        try:
            final_step0 = stock_app.invoke(step0_state)
            resp = adapt_step0_to_response(final_step0)
            responses.append(resp)
        except Exception as e:
            # 銘柄ごとのエラーハンドリング
            responses.append(StockAnalysisResponse(
                ticker=target.ticker,
                company_name=target.ticker,
                verification_status="NG",
                final_report=f"# エラー\n分析実行中にエラーが発生しました: {str(e)}",
                report_path="",
                logs=[f"[Error] {target.ticker} の分析中に例外発生: {str(e)}"]
            ))

    # 3. 方針達成度の評価と保存
    outcome: PolicyOutcome = evaluate_policy_outcome(policy, responses)
    save_policy_outcome(outcome)

    final_status = "COMPLETED" if outcome.verification_status == "OK" else "COMPLETED_WITH_WARNINGS"
    update_policy_status(policy.strategy_id, final_status)
    policy.status = "COMPLETED"

    return outcome, responses


def run_policy_workflow(user_request: str) -> Dict[str, Any]:
    """
    方針策定から実行（または承認待ち）までを一括制御する総合ワークフロー
    """
    # 1. 方針案策定 & ガード
    policy = propose_policy(user_request)

    # 2. 承認が必要な場合は一旦停止して通知
    if policy.approval_required or policy.status == "WAITING_APPROVAL":
        return {
            "status": "WAITING_APPROVAL",
            "policy": policy,
            "message": f"本リサーチ方針の実行には人間承認が必要です: {policy.approval_reason}",
            "outcome": None,
            "responses": []
        }

    if policy.status == "FAILED":
        return {
            "status": "FAILED",
            "policy": policy,
            "message": "方針の策定または安全ガード検査に失敗しました。",
            "outcome": None,
            "responses": []
        }

    # 3. 自動実行
    outcome, responses = execute_policy(policy)

    return {
        "status": "COMPLETED",
        "policy": policy,
        "message": "リサーチ方針に基づく分析が正常に完了しました。",
        "outcome": outcome,
        "responses": responses
    }
