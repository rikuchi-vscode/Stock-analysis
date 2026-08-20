"""
一人社長型 完全自律マルチエージェント株価分析システム CLI エントリーポイント
STEP 0 (直接実行), STEP 1 (AI CEO 統括), STEP 2 (リサーチ方針), STEP 3 (市場監視), STEP 4 (意思決定ガバナンス & 反省) に対応
"""

import sys
import argparse
import re

# Windows コンソールでの文字化け・UnicodeEncodeError防止
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from src.tools.market_tools import normalize_ticker
from src.graph import create_stock_analysis_graph
from src.db import get_analysis_history, init_db
from src.orchestration.ceo_graph import run_ceo_workflow
from src.repositories.ceo_repository import get_ceo_history
from src.repositories.policy_repository import list_research_policies, get_research_policy
from src.repositories.monitor_repository import (
    list_watch_items,
    list_market_events_with_triage,
    list_notifications,
)
from src.repositories.governance_repository import (
    list_journal_entries,
    list_reflections,
    list_active_guardrail_rules,
    list_human_feedbacks,
)
from src.contracts.ceo_request import CEOState
from src.contracts.research_policy import ResearchPolicy
from src.contracts.watch_item import WatchItem
from src.contracts.decision_journal import JournalEntry, ReflectionReport
from src.services.policy_service import (
    propose_policy,
    approve_policy,
    reject_policy,
    execute_policy,
    run_policy_workflow,
)
from src.services.watch_service import (
    add_to_watchlist,
    remove_from_watchlist,
    get_watchlist,
    run_monitoring_cycle,
)
from src.services.reflection_service import (
    run_reflection_on_journal,
    run_reflection_on_strategy,
    get_reflections_history,
)
from src.services.feedback_service import (
    submit_human_feedback,
    get_active_guardrails,
)
from src.ui.cli_dashboard import display_dashboard

console = Console(force_terminal=True, legacy_windows=False)


def display_banner():
    """CLI タイトルバナー表示"""
    console.print(
        Panel.fit(
            "[bold cyan]一人社長型 完全自律マルチエージェント株価分析システム[/bold cyan]\n"
            "[dim]Powered by Google Gemini API & LangGraph (STEP 4: Governance & Self-Reflection Loop)[/dim]",
            border_style="cyan"
        )
    )


# --- 履歴・表示関数 ---

def show_history():
    """過去の株価分析部門 (STEP 0) 履歴一覧をテーブル表示"""
    init_db()
    records = get_analysis_history(limit=15)
    
    if not records:
        console.print("[yellow]過去の分析履歴はありません。[/yellow]")
        return

    table = Table(title="📊 [STEP 0] 株価分析履歴", show_header=True, header_style="bold magenta")
    table.add_column("ID", style="dim", width=4)
    table.add_column("日時", width=19)
    table.add_column("銘柄コード", width=10)
    table.add_column("銘柄名", width=18)
    table.add_column("スコア", justify="right", width=8)
    table.add_column("投資スタンス", width=16)
    table.add_column("検証結果", width=10)
    table.add_column("レポートパス", style="dim")

    for r in records:
        score_str = f"{r['overall_score']}/100" if r['overall_score'] is not None else "N/A"
        table.add_row(
            str(r["id"]),
            str(r["analysis_date"]),
            str(r["ticker"]),
            str(r["company_name"] or "不明"),
            score_str,
            str(r["investment_stance"] or "N/A"),
            str(r["verification_status"] or "OK"),
            str(r["report_path"] or "")
        )

    console.print(table)


def show_ceo_history():
    """過去の AI CEO 実行履歴一覧をテーブル表示 (STEP 1)"""
    init_db()
    records = get_ceo_history(limit=15)

    if not records:
        console.print("[yellow]過去の CEO 実行履歴はありません。[/yellow]")
        return

    table = Table(title="👔 [STEP 1] AI CEO 実行・監査履歴", show_header=True, header_style="bold cyan")
    table.add_column("Run ID", style="dim", width=16)
    table.add_column("日時", width=19)
    table.add_column("銘柄", width=8)
    table.add_column("依頼内容", width=25)
    table.add_column("検証", width=8)
    table.add_column("ステータス", width=12)
    table.add_column("CEO ヘッドライン", width=35)

    for r in records:
        summary = r.get("summary") or {}
        headline = summary.get("headline", "") if isinstance(summary, dict) else ""
        status = str(r["status"] or "UNKNOWN")
        status_styled = f"[green]{status}[/green]" if status == "REPORTED" else f"[red]{status}[/red]" if status == "FAILED" else status
        display_text = headline if headline else (f"[dim red]{r.get('error') or '進行中・要約なし'}[/dim red]")
        
        table.add_row(
            str(r["run_id"]),
            str(r["created_at"]),
            str(r["ticker"] or "N/A"),
            str(r["user_request"] or "")[:24],
            str(r["verification_status"] or "PENDING"),
            status_styled,
            display_text[:38]
        )

    console.print(table)


def show_policy_history():
    """過去のリサーチ方針 (STEP 2) 一覧をテーブル表示"""
    init_db()
    policies = list_research_policies(limit=15)

    if not policies:
        console.print("[yellow]リサーチ方針の履歴はありません。[/yellow]")
        return

    table = Table(title="📋 [STEP 2] リサーチ方針 (Research Policy) 履歴", show_header=True, header_style="bold yellow")
    table.add_column("Strategy ID", style="dim", width=18)
    table.add_column("モード", width=14)
    table.add_column("対象銘柄", width=16)
    table.add_column("深度", width=8)
    table.add_column("ステータス", width=16)
    table.add_column("承認要否", width=10)
    table.add_column("調査目的", width=30)

    for p in policies:
        tickers = ",".join(p.scope.primary_tickers + p.scope.peer_tickers)
        status_styled = (
            f"[green]{p.status}[/green]" if p.status in ["COMPLETED", "APPROVED"]
            else f"[bold yellow]{p.status}[/bold yellow]" if p.status == "WAITING_APPROVAL"
            else f"[red]{p.status}[/red]" if p.status in ["FAILED", "REJECTED"]
            else p.status
        )
        appr_styled = "[bold red]要承認[/bold red]" if p.approval_required else "[dim]自動可[/dim]"

        table.add_row(
            p.strategy_id,
            p.mode,
            tickers[:15],
            p.analysis_depth,
            status_styled,
            appr_styled,
            p.objective[:28]
        )

    console.print(table)


def show_watchlist():
    """監視対象銘柄一覧のテーブル表示 (STEP 3)"""
    init_db()
    items = list_watch_items()

    if not items:
        console.print("[yellow]監視対象の銘柄は登録されていません。(--watch-add <ticker> で登録)[/yellow]")
        return

    table = Table(title="👁 [STEP 3] 監視対象銘柄 (WatchList)", show_header=True, header_style="bold blue")
    table.add_column("Watch ID", style="dim", width=15)
    table.add_column("銘柄コード", width=10)
    table.add_column("企業名", width=18)
    table.add_column("急変閾値", justify="right", width=10)
    table.add_column("間隔", justify="right", width=8)
    table.add_column("状態", width=8)
    table.add_column("最終チェック日時", width=19)

    for item in items:
        state_str = "[green]有効[/green]" if item.active else "[dim]無効[/dim]"
        table.add_row(
            item.watch_id,
            item.ticker,
            item.company_name or "N/A",
            f"±{item.triggers.price_change_pct}%",
            f"{item.interval_minutes}分",
            state_str,
            str(item.last_checked_at or "未実行")
        )

    console.print(table)


def show_events_history():
    """市場イベント・トリアージ履歴のテーブル表示 (STEP 3)"""
    init_db()
    events = list_market_events_with_triage(limit=15)

    if not events:
        console.print("[yellow]検知された市場イベントはありません。[/yellow]")
        return

    table = Table(title="⚡ [STEP 3] 市場イベント & トリアージ履歴", show_header=True, header_style="bold magenta")
    table.add_column("Event ID", style="dim", width=14)
    table.add_column("検知日時", width=19)
    table.add_column("銘柄", width=8)
    table.add_column("種別", width=12)
    table.add_column("重要度", width=10)
    table.add_column("タイトル", width=28)
    table.add_column("トリアージ判定", width=18)

    for e in events:
        sev = e.get("severity", "MEDIUM")
        sev_styled = f"[bold red]{sev}[/bold red]" if sev in ["CRITICAL", "HIGH"] else f"[yellow]{sev}[/yellow]" if sev == "MEDIUM" else sev
        action = e.get("triage_action") or "未判定"
        action_styled = f"[bold green]{action}[/bold green]" if action == "TRIGGER_RESEARCH" else f"[cyan]{action}[/cyan]"

        table.add_row(
            str(e["event_id"]),
            str(e["detected_at"]),
            str(e["ticker"]),
            str(e["event_type"]),
            sev_styled,
            str(e["title"])[:26],
            action_styled
        )

    console.print(table)


def show_notifications_history():
    """通知履歴のテーブル表示 (STEP 3)"""
    init_db()
    notifs = list_notifications(limit=15)

    if not notifs:
        console.print("[yellow]通知履歴はありません。[/yellow]")
        return

    table = Table(title="📢 [STEP 3] システム通知履歴", show_header=True, header_style="bold cyan")
    table.add_column("ID", style="dim", width=14)
    table.add_column("日時", width=19)
    table.add_column("重要度", width=10)
    table.add_column("件名", width=30)
    table.add_column("本文", width=40)

    for n in notifs:
        sev = n.get("severity", "INFO")
        sev_styled = f"[red]{sev}[/red]" if sev in ["CRITICAL", "ALERT"] else f"[yellow]{sev}[/yellow]" if sev == "WARNING" else sev
        table.add_row(
            str(n["notification_id"]),
            str(n["created_at"]),
            sev_styled,
            str(n["title"])[:28],
            str(n["body"])[:38]
        )

    console.print(table)


def show_journal_history():
    """意思決定ジャーナル一覧のテーブル表示 (STEP 4)"""
    init_db()
    journals = list_journal_entries(limit=15)

    if not journals:
        console.print("[yellow]意思決定ジャーナルはまだ記録されていません。[/yellow]")
        return

    table = Table(title="📔 [STEP 4] 意思決定ジャーナル (Decision Journal)", show_header=True, header_style="bold blue")
    table.add_column("Journal ID", style="dim", width=16)
    table.add_column("日時", width=19)
    table.add_column("種別", width=16)
    table.add_column("銘柄", width=8)
    table.add_column("決定者", width=10)
    table.add_column("初期仮説・期待成果", width=38)

    for j in journals:
        table.add_row(
            j.journal_id,
            str(j.created_at or ""),
            j.decision_type,
            j.ticker or "N/A",
            j.actor,
            j.hypothesis[:36]
        )

    console.print(table)


def show_reflections_history():
    """自己反省レポート一覧のテーブル表示 (STEP 4)"""
    init_db()
    reflections = list_reflections(limit=15)

    if not reflections:
        console.print("[yellow]自己反省レポートはまだ生成されていません。(--reflect <id> で実行)[/yellow]")
        return

    table = Table(title="🪞 [STEP 4] 自己反省 (Self Reflection) レポート履歴", show_header=True, header_style="bold magenta")
    table.add_column("Reflection ID", style="dim", width=14)
    table.add_column("日時", width=19)
    table.add_column("精度スコア", justify="right", width=10)
    table.add_column("成功要因", width=25)
    table.add_column("改善教訓 (Lessons Learned)", width=32)

    for r in reflections:
        score_styled = f"[bold green]{r.accuracy_score}/100[/bold green]" if r.accuracy_score >= 80 else f"[yellow]{r.accuracy_score}/100[/yellow]"
        success_str = ", ".join(r.success_factors)[:23]
        lessons_str = ", ".join(r.lessons_learned)[:30]

        table.add_row(
            r.reflection_id,
            str(r.created_at or ""),
            score_styled,
            success_str,
            lessons_str
        )

    console.print(table)


def show_guardrails():
    """アクティブなガードレール規則一覧のテーブル表示 (STEP 4)"""
    init_db()
    rules = list_active_guardrail_rules()

    if not rules:
        console.print("[yellow]現在有効なガードレールルールはありません。[/yellow]")
        return

    table = Table(title="🛡 [STEP 4] アクティブ・ガードレール規則 (Guardrails)", show_header=True, header_style="bold green")
    table.add_column("Rule ID", style="dim", width=14)
    table.add_column("カテゴリ", width=12)
    table.add_column("出所", width=16)
    table.add_column("ルール指示・制約テキスト", width=45)

    for r in rules:
        table.add_row(
            r.rule_id,
            r.category,
            r.source,
            r.rule_text[:42]
        )

    console.print(table)


def display_reflection_panel(reflection: ReflectionReport):
    """自己反省レポートの詳細パネル表示"""
    success_text = "\n".join([f"  • {s}" for s in reflection.success_factors])
    blindspots_text = "\n".join([f"  • {b}" for b in reflection.blindspots])
    lessons_text = "\n".join([f"  • {l}" for l in reflection.lessons_learned])
    guardrails_text = "\n".join([f"  • {g}" for g in reflection.recommended_guardrails])

    content = (
        f"[bold]反省ID:[/bold] [magenta]{reflection.reflection_id}[/magenta] | [bold]対象ジャーナル:[/bold] {reflection.journal_id}\n"
        f"[bold]仮説妥当性スコア:[/bold] [bold green]{reflection.accuracy_score} / 100[/bold green]\n"
        f"[bold]実績サマリー:[/bold] {reflection.actual_outcome}\n\n"
        f"[bold green]■ うまくいった要因 (Success Factors):[/bold green]\n{success_text}\n\n"
        f"[bold yellow]■ 盲点・見落とし (Blindspots & Gaps):[/bold yellow]\n{blindspots_text}\n\n"
        f"[bold cyan]■ 次回への改善教訓 (Lessons Learned):[/bold cyan]\n{lessons_text}\n\n"
        f"[bold red]■ 推奨ガードレール更新案:[/bold red]\n{guardrails_text}\n"
    )

    console.print(Panel(content, title="🪞 自己反省レポート (Self-Reflection Report)", border_style="magenta"))


# --- STEP 4 ハンドラー ---

def handle_reflect(target_id: str):
    """特定のジャーナルまたは方針に対する自己反省を実行"""
    console.print(f"\n[bold magenta]🪞 対象 '{target_id}' に対する自己反省 (Self-Reflection) を実行中...[/bold magenta]")
    
    if target_id.startswith("jrnl_"):
        reflection = run_reflection_on_journal(target_id)
    else:
        reflection = run_reflection_on_strategy(target_id)

    if not reflection:
        console.print(f"[bold red]✖ 対象 '{target_id}' の記録が見つかりませんでした。[/bold red]")
        return

    display_reflection_panel(reflection)
    console.print("[bold green]✔ 反省レポートを保存し、推奨ガードレールルールを自動更新しました。[/bold green]\n")


def handle_feedback(target_id: str, rating: int, comments: str = "", corrections_str: str = ""):
    """人間フィードバックの登録"""
    corrections = [c.strip() for c in corrections_str.split(",") if c.strip()] if corrections_str else []
    target_type = "POLICY" if target_id.startswith("policy_") else "REPORT"

    fb = submit_human_feedback(
        target_type=target_type,
        target_id=target_id,
        rating=rating,
        comments=comments,
        corrections=corrections
    )

    console.print(f"\n[bold green]✔ 人間フィードバックを登録しました！ (ID: {fb.feedback_id})[/bold green]")
    console.print(f"  • 対象: {fb.target_id} ({fb.target_type})")
    console.print(f"  • 評価: {'★' * fb.rating}{'☆' * (5 - fb.rating)} ({fb.rating}/5)")
    if fb.comments:
        console.print(f"  • コメント: {fb.comments}")
    if fb.corrections:
        console.print(f"  • 改善指示: {', '.join(fb.corrections)}")
        console.print("[bold cyan]🛡 指摘事項に基づきガードレールルールを新規有効化しました。[/bold cyan]\n")


# --- 既存ハンドラー ---

def handle_watch_add(ticker: str, price_pct: float = 3.0):
    item = add_to_watchlist(ticker=ticker, price_change_pct=price_pct)
    console.print(f"[bold green]✔ 銘柄 {item.ticker} を監視リストに追加しました！[/bold green] (急変閾値: ±{item.triggers.price_change_pct}%)")


def handle_watch_remove(ticker: str):
    deleted = remove_from_watchlist(ticker)
    if deleted:
        console.print(f"[bold yellow]✔ 銘柄 {ticker} を監視リストから削除しました。[/bold yellow]")
    else:
        console.print(f"[bold red]✖ 銘柄 {ticker} は監視リストに存在しませんでした。[/bold red]")


def handle_monitor_once(auto_trigger: bool = True):
    console.print("\n[bold cyan]👁 監視対象銘柄の市場・開示・ニュースを一括スキャン中...[/bold cyan]")
    result = run_monitoring_cycle(auto_trigger_research=auto_trigger)
    console.print(f"\n[bold green]✔ {result['message']}[/bold green]\n")


def display_policy_panel(policy: ResearchPolicy, title: str = "📋 策定されたリサーチ方針 (Research Policy)"):
    primaries = ", ".join(policy.scope.primary_tickers) or "なし"
    peers = ", ".join(policy.scope.peer_tickers) or "なし"
    questions = "\n".join([f"  • {q}" for q in policy.research_questions])
    rationale = "\n".join([f"  • {r}" for r in policy.rationale])

    status_color = "yellow" if policy.status == "WAITING_APPROVAL" else "green" if policy.status == "APPROVED" else "cyan"

    content = (
        f"[bold]方針ID:[/bold] [yellow]{policy.strategy_id}[/yellow] (v{policy.version})\n"
        f"[bold]調査目的:[/bold] {policy.objective}\n"
        f"[bold]分析モード:[/bold] [bold magenta]{policy.mode}[/bold magenta] | [bold]分析深度:[/bold] {policy.analysis_depth} | [bold]優先度:[/bold] {policy.priority}\n"
        f"[bold]主要銘柄:[/bold] [cyan]{primaries}[/cyan] | [bold]比較銘柄:[/bold] [cyan]{peers}[/cyan]\n"
        f"[bold]リソース上限:[/bold] 最大銘柄数={policy.limits.max_tickers}, 再調査サイクル={policy.limits.max_research_cycles}回, 時間={policy.limits.time_budget_minutes}分\n"
        f"[bold]ステータス:[/bold] [{status_color}]{policy.status}[/{status_color}]\n\n"
        f"[bold cyan]■ 重要リサーチ論点 (Research Questions):[/bold cyan]\n{questions}\n\n"
        f"[bold]■ 策定根拠 (Rationale):[/bold]\n{rationale}\n"
    )

    if policy.approval_required:
        content += f"\n[bold red]⚠ 人間承認が必要です:[/bold red] {policy.approval_reason}\n"
        content += f"[dim]承認コマンド: python main.py --approve {policy.strategy_id}[/dim]\n"

    console.print(Panel(content, title=title, border_style=status_color))


def handle_propose_policy(user_request: str):
    console.print(f"\n[bold yellow]💡 リサーチ方針案を策定中...:[/bold yellow] [italic]\"{user_request}\"[/italic]")
    policy = propose_policy(user_request)
    display_policy_panel(policy, title="💡 策定されたリサーチ方針案 (実行未着手)")


def handle_policy_run(user_request: str):
    console.print(f"\n[bold cyan]👔 AI CEO がリサーチ方針を策定・評価中...:[/bold cyan] [italic]\"{user_request}\"[/italic]")
    result = run_policy_workflow(user_request)
    policy: ResearchPolicy = result["policy"]

    display_policy_panel(policy)

    if result["status"] == "WAITING_APPROVAL":
        console.print(f"\n[bold yellow]⏸ 安全ガード発動:[/bold yellow] 人間承認待ちとして保存しました。")
        console.print(f"[bold cyan]承認して実行する場合:[/bold cyan] python main.py --approve {policy.strategy_id}\n")
        return

    if result["status"] == "FAILED":
        console.print(f"\n[bold red]✖ 方針実行に失敗しました:[/bold red] {result['message']}\n")
        return

    outcome = result.get("outcome")
    responses = result.get("responses", [])

    console.print("\n" + "=" * 65)
    console.print(f"[bold green]✔ リサーチ方針に基づく分析がすべて完了しました！[/bold green]")
    console.print("=" * 65)

    if outcome:
        rec_text = "\n".join([f"  • {r}" for r in outcome.next_recommendations])
        outcome_md = (
            f"[bold yellow]{outcome.outcome_summary}[/bold yellow]\n\n"
            f"[bold cyan]■ 次の推奨アクション・比較評価:[/bold cyan]\n{rec_text}"
        )
        console.print(Panel(outcome_md, title="🎯 方針達成度 & リサーチ成果サマリー", border_style="green"))

    console.print("\n[bold]📄 生成された個別レポート一覧:[/bold]")
    for r in responses:
        status_tag = f"[{'green' if r.verification_status=='OK' else 'red'}]{r.verification_status}[/]"
        console.print(f"  • [bold cyan]{r.company_name} ({r.ticker})[/bold cyan] (Score: {r.overall_score}/100, Stance: {r.investment_stance}) [Verify: {status_tag}] -> {r.report_path}")
    console.print()


def handle_approve_policy(strategy_id: str):
    console.print(f"\n[bold green]✔ 方針 {strategy_id} を承認します...[/bold green]")
    policy = approve_policy(strategy_id, approved_by="Human Owner")
    if not policy:
        console.print(f"[bold red]✖ 方針 {strategy_id} が見つかりませんでした。[/bold red]")
        return

    console.print(f"[bold cyan]方針に基づく株価分析部門の実行を開始します...[/bold cyan]")
    outcome, responses = execute_policy(policy)

    console.print("\n" + "=" * 65)
    console.print(f"[bold green]✔ 承認済み方針の分析が完了しました！[/bold green]")
    console.print("=" * 65)

    if outcome:
        rec_text = "\n".join([f"  • {r}" for r in outcome.next_recommendations])
        console.print(Panel(f"{outcome.outcome_summary}\n\n[bold cyan]■ 次の推奨アクション:[/bold cyan]\n{rec_text}", title="🎯 リサーチ成果サマリー", border_style="green"))

    for r in responses:
        console.print(f"  • {r.company_name} ({r.ticker}) -> {r.report_path}")
    console.print()


def handle_reject_policy(strategy_id: str):
    policy = reject_policy(strategy_id, rejected_by="Human Owner")
    if not policy:
        console.print(f"[bold red]✖ 方針 {strategy_id} が見つかりませんでした。[/bold red]")
        return
    console.print(f"[bold yellow]🚫 方針 {strategy_id} を却下しました。[/bold yellow]")


def run_ceo_analysis(user_request: str, max_iterations: int = 2):
    console.print(f"\n[bold cyan]👔 AI CEO がリクエストを受領しました:[/bold cyan] [italic]\"{user_request}\"[/italic]")
    try:
        with console.status("[bold cyan]AI CEO が意図解釈・部門委任・検証統括を実行中...[/bold cyan]", spinner="dots"):
            ceo_state: CEOState = run_ceo_workflow(user_request=user_request, max_iterations=max_iterations)

        if ceo_state.status == "FAILED":
            console.print(f"\n[bold red]✖ CEO ワークフローが失敗しました:[/bold red] {ceo_state.error}")
            return

        summary = ceo_state.ceo_summary
        console.print("\n" + "=" * 65)
        console.print(f"[bold green]✔ AI CEO 統括分析が完了しました！[/bold green] [bold cyan]{ceo_state.company_name} ({ceo_state.ticker})[/bold cyan]")
        console.print(f"[dim]Request ID: {ceo_state.request_id} | Run ID: {ceo_state.run_id} | Trace ID: {ceo_state.trace_id}[/dim]")
        console.print("=" * 65)

        if summary:
            takeaways_text = "\n".join([f"• {t}" for t in summary.key_takeaways])
            risks_text = "\n".join([f"• {r}" for r in summary.key_risks])
            limitations_text = "\n".join([f"• {l}" for l in summary.limitations])

            summary_md = (
                f"[bold yellow]{summary.headline}[/bold yellow]\n\n"
                f"[bold cyan]■ 主要要点 (Key Takeaways):[/bold cyan]\n{takeaways_text}\n\n"
                f"[bold red]■ 重要リスク (Key Risks):[/bold red]\n{risks_text}\n\n"
                f"[bold]■ 前提・制約 (Limitations):[/bold] [dim]\n{limitations_text}[/dim]\n\n"
                f"[dim italic]※ {summary.disclaimer}[/dim italic]"
            )
            console.print(Panel(summary_md, title="👔 AI CEO エグゼクティブ・サマリー", border_style="cyan"))

        console.print("\n[bold]📋 CEO & 部門 協調ログ:[/bold]")
        for log in ceo_state.logs:
            console.print(f"  [dim]• {log}[/dim]")

        console.print(f"\n[bold cyan]📄 分析部門 最終レポート:[/bold cyan] {ceo_state.report_path}")
        console.print(f"[bold cyan]💾 監査ログ & サマリーDB永続化:[/bold cyan] 完了 (data/stock_analysis.db)\n")

    except Exception as e:
        console.print(f"\n[bold red]✖ エラーが発生しました:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())


def run_analysis(ticker: str, max_iterations: int = 2):
    normalized_ticker = normalize_ticker(ticker)
    console.print(f"\n[bold green]▶ 株価分析部門 (STEP 0) を直接実行します:[/bold green] [bold yellow]{normalized_ticker}[/bold yellow] (最大再調査回数: {max_iterations})")
    
    app = create_stock_analysis_graph()
    initial_state = {
        "ticker": normalized_ticker,
        "iteration_count": 0,
        "max_iterations": max_iterations,
        "logs": []
    }

    try:
        with console.status("[bold green]エージェントチームが協調分析を実行中...[/bold green]", spinner="dots"):
            final_state = app.invoke(initial_state)

        analysis_result = final_state.get("analysis_result", {})
        market_data = final_state.get("market_data", {})
        risk_result = final_state.get("risk_result", {})
        company_name = final_state.get("company_name", normalized_ticker)
        report_path = final_state.get("report_path", "")

        console.print("\n" + "=" * 60)
        console.print(f"[bold green]✔ 分析が完了しました！[/bold green] [bold cyan]{company_name} ({normalized_ticker})[/bold cyan]")
        console.print("=" * 60)

        score = analysis_result.get("overall_score", "N/A")
        stance = analysis_result.get("investment_stance", "N/A")
        risk = risk_result.get("risk_level", "N/A")
        price = market_data.get("current_price", "N/A")

        summary_text = (
            f"[bold]総合評価スコア:[/bold] [bold yellow]{score} / 100[/bold yellow]\n"
            f"[bold]推奨投資スタンス:[/bold] [bold magenta]{stance}[/bold magenta]\n"
            f"[bold]リスクレベル:[/bold] {risk}\n"
            f"[bold]現在株価:[/bold] {price} 円\n\n"
            f"[dim]{analysis_result.get('executive_summary', '')}[/dim]"
        )
        console.print(Panel(summary_text, title="🎯 総合投資判断サマリー", border_style="green"))

        console.print("\n[bold]📋 エージェント協調ログ:[/bold]")
        for log in final_state.get("logs", []):
            console.print(f"  [dim]• {log}[/dim]")

        console.print(f"\n[bold cyan]📄 最終レポート保存先:[/bold cyan] {report_path}")
        console.print(f"[bold cyan]💾 データベース永続化:[/bold cyan] 完了 (data/stock_analysis.db)\n")

    except Exception as e:
        console.print(f"\n[bold red]✖ エラーが発生しました:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())


def main():
    parser = argparse.ArgumentParser(description="一人社長型 完全自律マルチエージェント株価分析システム (STEP 1〜STEP 5)")

    # STEP 5 総合ダッシュボード
    parser.add_argument("-d", "--dashboard", action="store_true", help="[STEP 5] CLI 総合社長ダッシュボードを表示")
    parser.add_argument("--web", action="store_true", help="[STEP 5] Streamlit Web UI ダッシュボードを起動")

    # STEP 4 ガバナンス・反省コマンド
    parser.add_argument("--journal", action="store_true", help="[STEP 4] 意思決定ジャーナル一覧を表示")
    parser.add_argument("--reflect", type=str, help="[STEP 4] 特定の方針またはジャーナルに対する自己反省を実行 (ID)")
    parser.add_argument("--reflections", action="store_true", help="[STEP 4] 自己反省レポート一覧を表示")
    parser.add_argument("--feedback", type=str, help="[STEP 4] 人間フィードバックを登録する対象ID (例: policy_...)")
    parser.add_argument("--rating", type=int, choices=[1, 2, 3, 4, 5], default=5, help="[STEP 4] フィードバックスコア (1〜5)")
    parser.add_argument("--comment", type=str, default="", help="[STEP 4] フィードバックコメント")
    parser.add_argument("--corrections", type=str, default="", help="[STEP 4] 修正指示 (カンマ区切り)")
    parser.add_argument("--guardrails", action="store_true", help="[STEP 4] アクティブなガードレール規則一覧を表示")

    # STEP 3 監視コマンド
    parser.add_argument("--watch-add", type=str, help="[STEP 3] 監視対象銘柄の追加 (例: --watch-add 7203)")
    parser.add_argument("--watch-remove", type=str, help="[STEP 3] 監視対象銘柄の削除 (例: --watch-remove 7203)")
    parser.add_argument("--watch-list", action="store_true", help="[STEP 3] 監視対象銘柄一覧の表示")
    parser.add_argument("--price-pct", type=float, default=3.0, help="[STEP 3] 監視株価急変閾値(%%) (デフォルト: 3.0)")
    parser.add_argument("--monitor-once", action="store_true", help="[STEP 3] 監視対象を一括スキャンして急変検知・自律トリガー実行")
    parser.add_argument("--events", action="store_true", help="[STEP 3] 市場イベント・トリアージ履歴一覧を表示")
    parser.add_argument("--notifications", action="store_true", help="[STEP 3] システム通知履歴一覧を表示")

    # STEP 2 リサーチ方針コマンド
    parser.add_argument("-p", "--policy", type=str, help="[STEP 2] リサーチ方針を策定・評価して実行 (例: 'トヨタとホンダを比較して')")
    parser.add_argument("--propose", type=str, help="[STEP 2] リサーチ方針案のみを策定・提示 (実行はしない)")
    parser.add_argument("--approve", type=str, help="[STEP 2] 承認待ちのリサーチ方針を承認して実行 (Strategy ID)")
    parser.add_argument("--reject", type=str, help="[STEP 2] 承認待ちのリサーチ方針を却下 (Strategy ID)")
    parser.add_argument("--policies", "--policy-history", action="store_true", help="[STEP 2] リサーチ方針の一覧と承認状態を表示")

    # STEP 1 & STEP 0 コマンド
    parser.add_argument("-c", "--ceo", type=str, help="[STEP 1] AI CEO への単一銘柄自然言語依頼")
    parser.add_argument("-t", "--ticker", type=str, help="[STEP 0 直接実行] 分析対象の銘柄コード (例: 7203, 7203.T)")
    parser.add_argument("--history", action="store_true", help="STEP 0 の分析履歴一覧を表示")
    parser.add_argument("--ceo-history", action="store_true", help="AI CEO の実行・監査履歴一覧を表示")
    parser.add_argument("--max-iterations", type=int, default=2, help="Verification Agent による最大再調査反復回数 (デフォルト: 2)")

    args = parser.parse_args()

    # STEP 5 Web UI 起動
    if args.web:
        import subprocess
        console.print("[bold cyan]🚀 Streamlit Web ダッシュボードを起動中...[/bold cyan]")
        subprocess.run([sys.executable, "-m", "streamlit", "run", "dashboard_app.py"])
        return

    display_banner()

    # STEP 5 総合ダッシュボード
    if args.dashboard:
        display_dashboard()

    # STEP 4 コマンド処理
    elif args.journal:
        show_journal_history()
    elif args.reflections:
        show_reflections_history()
    elif args.guardrails:
        show_guardrails()
    elif args.reflect:
        handle_reflect(args.reflect)
    elif args.feedback:
        handle_feedback(args.feedback, rating=args.rating, comments=args.comment, corrections_str=args.corrections)

    # STEP 3 コマンド処理
    elif args.watch_add:
        handle_watch_add(args.watch_add, price_pct=args.price_pct)
    elif args.watch_remove:
        handle_watch_remove(args.watch_remove)
    elif args.watch_list:
        show_watchlist()
    elif args.monitor_once:
        handle_monitor_once(auto_trigger=True)
    elif args.events:
        show_events_history()
    elif args.notifications:
        show_notifications_history()

    # STEP 2 コマンド処理
    elif args.policies:
        show_policy_history()
    elif args.propose:
        handle_propose_policy(args.propose)
    elif args.approve:
        handle_approve_policy(args.approve)
    elif args.reject:
        handle_reject_policy(args.reject)
    elif args.policy:
        handle_policy_run(args.policy)

    # STEP 1 & STEP 0 コマンド処理
    elif args.ceo_history:
        show_ceo_history()
    elif args.history:
        show_history()
    elif args.ceo:
        run_ceo_analysis(args.ceo, max_iterations=args.max_iterations)
    elif args.ticker:
        run_analysis(args.ticker, max_iterations=args.max_iterations)
    else:
        console.print("[bold]分析の依頼内容を入力してください[/bold] (例: 'トヨタとホンダを比較して', 'トヨタ', '7203')")
        console.print("[dim]※ コマンド: ダッシュボード='d', 監視='w', イベント='ev', 通知='n', 方針='p', 反省='rf', CEO='ch', STEP0='h'[/dim]")
        user_input = input("依頼 > ").strip()
        if user_input.lower() == 'd':
            display_dashboard()
        elif user_input.lower() == 'j':
            show_journal_history()
        elif user_input.lower() == 'rf':
            show_reflections_history()
        elif user_input.lower() == 'g':
            show_guardrails()
        elif user_input.lower() == 'w':
            show_watchlist()
        elif user_input.lower() == 'ev':
            show_events_history()
        elif user_input.lower() == 'n':
            show_notifications_history()
        elif user_input.lower() == 'p':
            show_policy_history()
        elif user_input.lower() == 'ch':
            show_ceo_history()
        elif user_input.lower() == 'h':
            show_history()
        elif user_input:
            if any(k in user_input for k in ["比較", "対比", "競合", "徹底", "深掘り"]):
                handle_policy_run(user_input)
            elif re.match(r"^\d{4}(\.T)?$", user_input, re.IGNORECASE):
                run_analysis(user_input, max_iterations=args.max_iterations)
            else:
                run_ceo_analysis(user_input, max_iterations=args.max_iterations)
        else:
            console.print("[yellow]入力がなかったため終了します。[/yellow]")


if __name__ == "__main__":
    main()
