"""
Policy Guard Agent モジュール
STEP 2: リサーチ方針の安全性、リソース上限、コスト、人間承認要否をルールベースで厳格に検証・ガード
"""

import uuid
from typing import Tuple, List
from src.contracts.research_policy import ResearchPolicy, PolicyDecision


# ガードの定数閾値
MAX_AUTO_TICKERS = 3              # 人間承認なしで自動実行可能な最大銘柄数
MAX_AUTO_RESEARCH_CYCLES = 2     # 自動実行可能な最大再調査サイクル数
MAX_AUTO_TIME_BUDGET = 30        # 自動実行可能な最大時間(分)


def evaluate_policy_guard(policy: ResearchPolicy) -> Tuple[ResearchPolicy, List[PolicyDecision]]:
    """
    リサーチ方針を検査し、承認要否と決定根拠を付与した方針を返す。
    """
    decisions: List[PolicyDecision] = []
    reasons_for_approval: List[str] = []

    total_tickers = len(policy.scope.primary_tickers) + len(policy.scope.peer_tickers)

    # 1. 銘柄数チェック
    if total_tickers == 0:
        policy.status = "FAILED"
        policy.approval_required = False
        decisions.append(PolicyDecision(
            decision_id=f"dec_guard_{uuid.uuid4().hex[:10]}",
            strategy_id=policy.strategy_id,
            decision_type="GUARD_REJECTED",
            rationale="分析対象銘柄が1つも指定されていません。",
            actor="Policy Guard"
        ))
        return policy, decisions

    if total_tickers > MAX_AUTO_TICKERS:
        reasons_for_approval.append(f"対象銘柄数 ({total_tickers}銘柄) が自動実行上限 ({MAX_AUTO_TICKERS}銘柄) を超過")

    # 2. 分析深度チェック
    if policy.analysis_depth == "deep":
        reasons_for_approval.append("深掘り分析 (deep analysis) が指定されたため、計算・APIコスト承認が必要")

    # 3. 再調査サイクル上限チェック
    if policy.limits.max_research_cycles > MAX_AUTO_RESEARCH_CYCLES:
        reasons_for_approval.append(
            f"再調査反復上限 ({policy.limits.max_research_cycles}回) が安全基準 ({MAX_AUTO_RESEARCH_CYCLES}回) を超過"
        )

    # 4. 時間予算チェック
    if policy.limits.time_budget_minutes > MAX_AUTO_TIME_BUDGET:
        reasons_for_approval.append(
            f"想定実行時間 ({policy.limits.time_budget_minutes}分) が安全基準 ({MAX_AUTO_TIME_BUDGET}分) を超過"
        )

    # 5. 判定の確定
    if reasons_for_approval:
        policy.approval_required = True
        policy.approval_reason = "、".join(reasons_for_approval)
        policy.status = "WAITING_APPROVAL"
        decisions.append(PolicyDecision(
            decision_id=f"dec_guard_{uuid.uuid4().hex[:10]}",
            strategy_id=policy.strategy_id,
            decision_type="APPROVAL_REQUIRED",
            rationale=f"安全ガード発動: {policy.approval_reason}",
            actor="Policy Guard"
        ))
    else:
        policy.approval_required = False
        policy.approval_reason = None
        policy.status = "APPROVED" if policy.status == "PROPOSED" else policy.status
        decisions.append(PolicyDecision(
            decision_id=f"dec_guard_{uuid.uuid4().hex[:10]}",
            strategy_id=policy.strategy_id,
            decision_type="AUTO_APPROVED",
            rationale="全ガード検査を通過。自動実行可能と判定されました。",
            actor="Policy Guard"
        ))

    return policy, decisions
