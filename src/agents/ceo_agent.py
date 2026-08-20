"""
AI CEO Agent モジュール
ユーザー依頼の解釈・正規化、分析部門への委任、結果受領、経営者向け要約報告（CEOサマリー）の生成を担当します。
※CEO Agentは独自の投資判断計算を行わず、分析部門の検証済み結果に依拠して説明責任を果たします。
"""

import re
import json
from typing import Dict, Any, Optional, List, Tuple
from langchain_core.messages import SystemMessage, HumanMessage

from src.llm import get_fast_model, get_pro_model, extract_text_content, safe_invoke_llm
from src.tools.market_tools import normalize_ticker
from src.contracts.ceo_request import NormalizedRequest, CEOSummary
from src.contracts.stock_analysis import StockAnalysisResponse


NORMALIZATION_SYSTEM_PROMPT = """あなたはAI組織の最高経営責任者（AI CEO）です。
ユーザーから受け取った自然言語の依頼を解析し、社内の「株価分析部門」が実行可能な構造化リクエストに正規化してください。

【出力仕様】
必ず以下のJSONフォーマットのみを出力してください（Markdownコードブロックは不要です）。
{
  "task_type": "stock_analysis", // または "market_inquiry", "unsupported"
  "ticker": "7203.T", // 日本株4桁コードに.Tを付けた形式。不明な場合はnull
  "company_name_hint": "トヨタ自動車", // 企業名がわかる場合は記載
  "horizon": "medium", // "short"(短期1-3ヶ月), "medium"(中期6-12ヶ月), "long"(長期1年以上), "unspecified"
  "focus_areas": ["業績動向", "為替影響"], // 重点調査事項のリスト
  "confidence": 0.95, // 銘柄特定の確信度 (0.0〜1.0)
  "clarification_needed": false, // 銘柄が特定できないなどユーザー確認が必要な場合はtrue
  "clarification_message": null // clarification_neededがtrueの場合の確認文
}

【正規化ルール】
1. 代表的な企業名やティッカー（例: トヨタ→7203.T, ソニー→6758.T, SBG/ソフトバンクG→9984.T, 任天堂→7974.T, レーザーテック→6920.T 等）は正確にティッカーへ変換してください。
2. 4桁の数字（例: 7203）が渡された場合は、日本株ティッカー（例: 7203.T）として解釈してください。
3. 期間の指定があれば "short", "medium", "long" に分類してください（指定がなければ "medium"）。
4. 銘柄が全く推測できない場合や株式リサーチと無関係な依頼の場合は clarification_needed: true としてください。
"""

CEO_SUMMARY_SYSTEM_PROMPT = """あなたはAI組織の最高経営責任者（AI CEO）です。
社内の「株価分析部門」から提出された詳細なリサーチレポートと各部門（市場・財務・ニュース・リスク・検証）の評価結果をもとに、
経営者・投資家が即座に状況を把握できる高次のエグゼクティブ・サマリーを生成してください。

【厳格な遵守事項】
1. **分析結果を歪めない・改変しない**: 分析部門が算出した「総合評価スコア」「投資推奨スタンス」「リスクレベル」などの客観的事実をそのまま尊重し、独自の判断で数字や推奨を変更してはなりません。
2. **検証ステータスの明記**: Verification部門が「OK」を出しているか、あるいは課題・再調査を経ているかを明記してください。
3. **リスクの客観的提示**: 楽観シナリオだけでなく、リスク管理部門が指摘したダウンサイドリスクを必ず併記してください。

【出力仕様】
必ず以下のJSONフォーマットのみを出力してください（Markdownコードブロックは不要です）。
{
  "headline": "1行で核心を突く結論（企業名、現在の総合評価、スタンスを明記）",
  "key_takeaways": [
    "分析部門が導出した重要ポイント1",
    "分析部門が導出した重要ポイント2",
    "分析部門が導出した重要ポイント3"
  ],
  "key_risks": [
    "リスク管理部門が特定した主要リスク1",
    "リスク管理部門が特定した主要リスク2"
  ],
  "limitations": [
    "前提条件や分析における制約事項（データ取得時点など）"
  ],
  "disclaimer": "本出力はリサーチ目的の情報提供であり、投資助言や有価証券の売買を推奨するものではありません。"
}
"""


# 代表的な日本株銘柄の高速解決マップ (辞書)
COMMON_STOCK_MAP = {
    "トヨタ": ("7203.T", "トヨタ自動車"),
    "トヨタ自動車": ("7203.T", "トヨタ自動車"),
    "ソニー": ("6758.T", "ソニーグループ"),
    "ソニーグループ": ("6758.T", "ソニーグループ"),
    "ソフトバンク": ("9984.T", "ソフトバンクグループ"),
    "ソフトバンクグループ": ("9984.T", "ソフトバンクグループ"),
    "sbg": ("9984.T", "ソフトバンクグループ"),
    "任天堂": ("7974.T", "任天堂"),
    "キーエンス": ("6861.T", "キーエンス"),
    "レーザーテック": ("6920.T", "レーザーテック"),
    "東京エレクトロン": ("8035.T", "東京エレクトロン"),
    "三菱商事": ("8058.T", "三菱商事"),
    "ファーストリテイリング": ("9983.T", "ファーストリテイリング"),
    "ユニクロ": ("9983.T", "ファーストリテイリング"),
    "日立": ("6501.T", "日立製作所"),
    "日立製作所": ("6501.T", "日立製作所"),
    "ntt": ("9432.T", "日本電信電話"),
    "日本電信電話": ("9432.T", "日本電信電話"),
    "ホンダ": ("7267.T", "本田技研工業"),
    "本田技研工業": ("7267.T", "本田技研工業"),
}


def _extract_horizon_rule(user_request: str) -> str:
    """期間キーワードのルールベース抽出"""
    if any(k in user_request for k in ["短期", "ショート", "デイトレ", "数週間", "1ヶ月"]):
        return "short"
    if any(k in user_request for k in ["長期", "ロング", "数年", "配当狙い", "バイアンドホールド"]):
        return "long"
    return "medium"


def normalize_user_request(user_request: str) -> NormalizedRequest:
    """
    ユーザーからの自然言語リクエストを解析し、正規化された構造化オブジェクトを返す。
    辞書検索・正規表現・LLM呼び出しを多層的に併用し、APIレート制限時も確実に機能する高堅牢設計。
    """
    stripped = user_request.strip().lower()
    horizon = _extract_horizon_rule(user_request)

    # 1. 4桁数字の抽出（例: "7203", "7203.T", "7203を中期で" など）
    match_four = re.search(r"(\d{4})(\.T)?", stripped, re.IGNORECASE)
    if match_four:
        code = match_four.group(1)
        return NormalizedRequest(
            task_type="stock_analysis",
            ticker=f"{code}.T",
            company_name_hint=None,
            horizon=horizon,
            focus_areas=[],
            confidence=1.0,
            clarification_needed=False
        )

    # 2. 主要銘柄辞書からの完全/部分一致判定
    dict_ticker = None
    dict_name = None
    for name_key, (code_t, full_name) in COMMON_STOCK_MAP.items():
        if name_key in stripped:
            dict_ticker = code_t
            dict_name = full_name
            return NormalizedRequest(
                task_type="stock_analysis",
                ticker=dict_ticker,
                company_name_hint=dict_name,
                horizon=horizon,
                focus_areas=[],
                confidence=1.0,
                clarification_needed=False
            )

    # 3. LLMによる高度な意図解釈と未知銘柄特定
    try:
        model = get_fast_model(temperature=0.0)
        messages = [
            SystemMessage(content=NORMALIZATION_SYSTEM_PROMPT),
            HumanMessage(content=f"ユーザー依頼: {user_request}")
        ]
        response = safe_invoke_llm(model, messages)
        text = extract_text_content(response)

        clean_json = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"^```\s*", "", clean_json, flags=re.MULTILINE)
        clean_json = clean_json.strip()

        data = json.loads(clean_json)

        # ティッカーの正規化
        raw_ticker = data.get("ticker")
        if raw_ticker:
            data["ticker"] = normalize_ticker(raw_ticker)
        elif dict_ticker:
            data["ticker"] = dict_ticker
            data["company_name_hint"] = dict_name
            data["clarification_needed"] = False

        return NormalizedRequest(**data)

    except Exception:
        # LLM呼び出し失敗（レート制限 429 等）時の高信頼フォールバック
        if dict_ticker:
            return NormalizedRequest(
                task_type="stock_analysis",
                ticker=dict_ticker,
                company_name_hint=dict_name,
                horizon=horizon,
                confidence=0.95,
                clarification_needed=False
            )

        return NormalizedRequest(
            task_type="stock_analysis",
            ticker=None,
            company_name_hint=None,
            horizon=horizon,
            confidence=0.0,
            clarification_needed=True,
            clarification_message=f"分析対象の銘柄コードまたは企業名を特定できませんでした: {user_request}"
        )


def generate_ceo_summary(
    response: StockAnalysisResponse,
    normalized_request: Optional[NormalizedRequest] = None
) -> CEOSummary:
    """
    株価分析部門からの詳細結果をもとに、歪みのないCEOサマリーを生成する。
    """
    try:
        model = get_pro_model(temperature=0.1)

        # 入力コンテキストの構築
        context = {
            "ticker": response.ticker,
            "company_name": response.company_name,
            "sector": response.sector,
            "overall_score": response.overall_score,
            "investment_stance": response.investment_stance,
            "verification_status": response.verification_status,
            "iteration_count": response.iteration_count,
            "analysis_executive_summary": response.analysis_result.get("executive_summary", ""),
            "core_investment_theses": response.analysis_result.get("core_investment_thesis", []),
            "primary_downside_risks": response.risk_result.get("primary_downside_risks", []),
            "bearish_counter_arguments": response.risk_result.get("bearish_counter_arguments", []),
            "requested_horizon": normalized_request.horizon if normalized_request else "medium"
        }

        messages = [
            SystemMessage(content=CEO_SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=f"分析部門からの提出データ:\n{json.dumps(context, ensure_ascii=False, indent=2)}")
        ]

        llm_output = safe_invoke_llm(model, messages)
        text = extract_text_content(llm_output)

        clean_json = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"^```\s*", "", clean_json, flags=re.MULTILINE)
        clean_json = clean_json.strip()

        data = json.loads(clean_json)
        return CEOSummary(**data)

    except Exception as e:
        # LLM生成失敗時のルールベースフォールバックサマリー
        headline = f"{response.company_name} ({response.ticker}) の分析完了 (総合スコア: {response.overall_score}/100, 推奨: {response.investment_stance})"
        key_takeaways = response.analysis_result.get("core_investment_thesis", [])
        if not key_takeaways and response.analysis_result.get("executive_summary"):
            key_takeaways = [response.analysis_result.get("executive_summary")]

        risks = []
        for r in response.risk_result.get("primary_downside_risks", []):
            if isinstance(r, dict):
                risks.append(f"{r.get('category', 'リスク')}: {r.get('risk_factor', '')}")
            elif isinstance(r, str):
                risks.append(r)

        return CEOSummary(
            headline=headline,
            key_takeaways=key_takeaways or ["分析部門によるレポートが正常に生成されました。"],
            key_risks=risks or ["主要リスクは詳細レポートをご確認ください。"],
            limitations=[f"Verificationステータス: {response.verification_status}", "過去データに基づく試算"],
            disclaimer="本出力はリサーチ目的の情報提供であり、投資助言や有価証券の売買を推奨するものではありません。"
        )


POLICY_FORMULATION_SYSTEM_PROMPT = """あなたはAI組織の最高経営責任者（AI CEO）です。
ユーザーからのリサーチ依頼と市場背景をもとに、社内の株価分析部門に対する戦略的な「リサーチ方針 (ResearchPolicy)」を策定してください。

【リサーチモード判定】
- "single_stock": 単一銘柄の通常調査
- "peer_comparison": 複数銘柄の比較・競合調査（例: トヨタとホンダの比較など）
- "deep_dive_risk": 特定リスクやダウンサイドシナリオの深掘り調査
- "re_investigation": 既存レポートに対する再調査・追加論点の検証

【出力仕様】
必ず以下のJSONフォーマットのみを出力してください（Markdownコードブロックは不要です）。
{
  "objective": "調査目的の簡潔な説明",
  "mode": "single_stock", // "single_stock" | "peer_comparison" | "deep_dive_risk" | "re_investigation"
  "primary_tickers": ["7203.T"], // 主要対象銘柄
  "peer_tickers": [], // 比較対象銘柄
  "sector": "自動車・輸送用機器",
  "research_questions": [
    "検証すべき重要論点1",
    "検証すべき重要論点2"
  ],
  "analysis_depth": "standard", // "standard" | "deep" | "quick"
  "priority": "high", // "low" | "medium" | "high" | "urgent"
  "max_tickers": 3,
  "max_research_cycles": 2,
  "time_budget_minutes": 15,
  "rationale": [
    "方針策定の根拠1",
    "方針策定の根拠2"
  ]
}
"""


def propose_research_policy(
    user_request: str,
    normalized: Optional[NormalizedRequest] = None
) -> "ResearchPolicy":
    """
    ユーザー依頼からリサーチ方針 (ResearchPolicy) を策定する。
    LLM (Gemini Pro) による高度な論点分解とルールベース辞書を融合。
    """
    import uuid
    from src.contracts.research_policy import ResearchPolicy, PolicyScope, PolicyLimits

    strategy_id = f"policy_{uuid.uuid4().hex[:12]}"
    
    # 正規化オブジェクトがない場合は生成
    if normalized is None:
        normalized = normalize_user_request(user_request)

    # 1. ルールベースによる初期値構築
    primary_ticker = normalized.ticker or "7203.T"
    peer_tickers = []
    mode = "single_stock"
    depth = "standard"

    lower_req = user_request.lower()

    # 比較キーワードの検出
    if any(k in lower_req for k in ["比較", "対比", "競合", "どっち", "vs", "versus", "と"]):
        # 4桁コードをすべて抽出
        found_codes = re.findall(r"\b(\d{4})\b", user_request)
        if len(found_codes) >= 2:
            primary_ticker = f"{found_codes[0]}.T"
            peer_tickers = [f"{c}.T" for c in found_codes[1:]]
            mode = "peer_comparison"
        else:
            # 辞書から複数銘柄を探す
            matched = []
            for k, (t, _) in COMMON_STOCK_MAP.items():
                if k in lower_req and t not in matched:
                    matched.append(t)
            if len(matched) >= 2:
                primary_ticker = matched[0]
                peer_tickers = matched[1:]
                mode = "peer_comparison"

    # 深掘りキーワードの検出
    if any(k in lower_req for k in ["徹底", "深掘り", "リスク分析", "ダウンサイド", "詳細に", "詳しく"]):
        depth = "deep"
        if mode == "single_stock":
            mode = "deep_dive_risk"

    # 2. LLMによる高度な方針策定試行
    try:
        model = get_pro_model(temperature=0.1)
        messages = [
            SystemMessage(content=POLICY_FORMULATION_SYSTEM_PROMPT),
            HumanMessage(content=f"ユーザー依頼: {user_request}\n正規化ティッカー: {primary_ticker}\n推定モード: {mode}")
        ]
        response = safe_invoke_llm(model, messages)
        text = extract_text_content(response)

        clean_json = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        clean_json = re.sub(r"^```\s*", "", clean_json, flags=re.MULTILINE)
        data = json.loads(clean_json.strip())

        primaries = [normalize_ticker(t) for t in data.get("primary_tickers", [primary_ticker])]
        peers = [normalize_ticker(t) for t in data.get("peer_tickers", peer_tickers)]

        return ResearchPolicy(
            strategy_id=strategy_id,
            objective=data.get("objective", f"{primary_ticker} の投資リサーチ方針"),
            mode=data.get("mode", mode),
            scope=PolicyScope(
                primary_tickers=primaries,
                peer_tickers=peers,
                sector=data.get("sector")
            ),
            research_questions=data.get("research_questions", ["業績動向の持続性", "下落リスク要因"]),
            analysis_depth=data.get("analysis_depth", depth),
            priority=data.get("priority", "high"),
            limits=PolicyLimits(
                max_tickers=data.get("max_tickers", len(primaries) + len(peers)),
                max_research_cycles=data.get("max_research_cycles", 2),
                time_budget_minutes=data.get("time_budget_minutes", 15)
            ),
            rationale=data.get("rationale", ["ユーザー依頼に基づく分析計画策定"]),
            approval_required=False,
            status="PROPOSED",
            version=1
        )

    except Exception:
        # LLM呼び出し失敗時の高信頼ルールベースフォールバック
        return ResearchPolicy(
            strategy_id=strategy_id,
            objective=f"{primary_ticker} の{mode}リサーチ方針",
            mode=mode,
            scope=PolicyScope(
                primary_tickers=[primary_ticker],
                peer_tickers=peer_tickers,
                sector=normalized.company_name_hint
            ),
            research_questions=["収益性の持続性と市場シェア", "為替・マクロ要因によるダウンサイドリスク"],
            analysis_depth=depth,
            priority="high",
            limits=PolicyLimits(
                max_tickers=max(3, len(peer_tickers) + 1),
                max_research_cycles=2,
                time_budget_minutes=15
            ),
            rationale=[f"ユーザー依頼 '{user_request}' に基づく自動方針生成"],
            approval_required=False,
            status="PROPOSED",
            version=1
        )


def evaluate_policy_outcome(
    policy: "ResearchPolicy",
    responses: List[StockAnalysisResponse]
) -> "PolicyOutcome":
    """
    方針実行完了後に、各銘柄の分析結果から方針達成度を評価する。
    """
    from src.contracts.research_policy import PolicyOutcome

    all_verified = all(r.verification_status == "OK" for r in responses)
    avg_score = None
    scores = [r.overall_score for r in responses if r.overall_score is not None]
    if scores:
        avg_score = sum(scores) / len(scores)

    tickers_covered = [r.ticker for r in responses]
    coverage_rate = len(tickers_covered) / max(1, len(policy.scope.primary_tickers) + len(policy.scope.peer_tickers))

    summary_parts = [
        f"リサーチ方針 '{policy.objective}' の実行が完了しました。",
        f"対象銘柄カバレッジ: {len(tickers_covered)}/{len(policy.scope.primary_tickers) + len(policy.scope.peer_tickers)} ({coverage_rate*100:.0f}%)",
        f"品質検証ステータス: {'全銘柄OK' if all_verified else '要確認あり'}",
    ]
    if avg_score is not None:
        summary_parts.append(f"平均総合評価スコア: {avg_score:.1f}/100")

    recommendations = []
    if policy.mode == "peer_comparison" and len(responses) >= 2:
        # スコア比較
        sorted_resp = sorted(responses, key=lambda x: x.overall_score or 0, reverse=True)
        top = sorted_resp[0]
        recommendations.append(f"同業比較において {top.company_name} ({top.ticker}) が最高スコア ({top.overall_score}点) を獲得")
    recommendations.append("必要に応じて追加の深掘り調査 (deep_dive_risk) の実施を検討")

    return PolicyOutcome(
        strategy_id=policy.strategy_id,
        analysis_run_ids=[str(r.analysis_id) for r in responses if r.analysis_id is not None],
        coverage={
            "tickers_covered": tickers_covered,
            "coverage_rate": coverage_rate,
            "all_verified": all_verified
        },
        verification_status="OK" if all_verified else "PARTIAL",
        outcome_summary="\n".join(summary_parts),
        next_recommendations=recommendations
    )
