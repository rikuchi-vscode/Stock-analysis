"""
CLI 総合社長ダッシュボード (Executive Dashboard)
STEP 5: Rich を用いた組織全体のKPI・稼働状態・アクションアイテムの可視化
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.columns import Columns
from rich.text import Text

from src.contracts.dashboard_metrics import DashboardSummary
from src.services.dashboard_service import get_dashboard_summary

console = Console(force_terminal=True, legacy_windows=False)


def render_cli_dashboard(summary: DashboardSummary) -> None:
    """
    一人社長向け CLI 総合ダッシュボードを描画する。
    """
    m = summary.metrics

    # 1. ヘッダーバナー
    console.print(
        Panel.fit(
            f"[bold cyan]👑 一人社長 AI 自律リサーチ組織 統合ダッシュボード[/bold cyan]\n"
            f"[dim]システム稼働日時: {summary.generated_at} | 状態: 全エージェント稼働中 (STEP 0〜STEP 5)[/dim]",
            border_style="cyan"
        )
    )

    # 2. 主要 KPI メトリクスパネル群
    appr_color = "red" if m.pending_approvals > 0 else "green"
    kpi_panels = [
        Panel(f"[bold yellow]{m.total_analyses}[/bold yellow] 件\n[dim]平均: {m.average_overall_score}点[/dim]", title="📊 [STEP 0] 部門分析数", border_style="magenta"),
        Panel(f"[bold yellow]{m.total_ceo_runs}[/bold yellow] 回\n[dim]統括サマリー[/dim]", title="👔 [STEP 1] CEO実行", border_style="cyan"),
        Panel(f"[bold {appr_color}]{m.pending_approvals}[/bold {appr_color}] 件\n[dim]総方針: {m.total_policies}件[/dim]", title="📋 [STEP 2] 承認待ち", border_style="yellow"),
        Panel(f"[bold yellow]{m.watched_tickers_count}[/bold yellow] 銘柄\n[dim]検知: {m.market_events_count}件[/dim]", title="👁 [STEP 3] 自律市場監視", border_style="blue"),
        Panel(f"[bold green]{m.average_accuracy_score}[/bold green] / 100\n[dim]反省: {m.total_reflections}件[/dim]", title="🪞 [STEP 4] 反省精度", border_style="green"),
        Panel(f"[bold green]{m.active_guardrails_count}[/bold green] 規則\n[dim]教訓蓄積[/dim]", title="🛡 ガードレール", border_style="bright_blue"),
    ]
    console.print(Columns(kpi_panels, equal=True))
    console.print()

    # 3. 承認待ち方針 (Action Required)
    if summary.pending_approval_policies:
        table_appr = Table(title="⚠️ [要アクション] 人間承認待ちのリサーチ方針 (Waiting Approval)", show_header=True, header_style="bold red", border_style="red")
        table_appr.add_column("Strategy ID", style="dim", width=18)
        table_appr.add_column("モード", width=14)
        table_appr.add_column("対象銘柄", width=14)
        table_appr.add_column("調査目的 / 承認理由", width=36)
        table_appr.add_column("承認コマンド", style="bold yellow", width=30)

        for p in summary.pending_approval_policies:
            scope = p.get("scope", {})
            tickers = ",".join(scope.get("primary_tickers", []) + scope.get("peer_tickers", []))
            table_appr.add_row(
                p.get("strategy_id", ""),
                p.get("mode", ""),
                tickers[:13],
                (p.get("approval_reason") or p.get("objective", ""))[:34],
                f"python main.py --approve {p.get('strategy_id')}"
            )
        console.print(table_appr)
        console.print()

    # 4. 直近の市場イベント & トリアージ
    if summary.recent_market_events:
        table_evt = Table(title="⚡ 直近の検知市場イベント & トリアージ結果", show_header=True, header_style="bold magenta")
        table_evt.add_column("検知日時", width=19)
        table_evt.add_column("銘柄", width=8)
        table_evt.add_column("種別", width=12)
        table_evt.add_column("重要度", width=10)
        table_evt.add_column("イベントタイトル", width=28)
        table_evt.add_column("トリアージ結果", width=18)

        for e in summary.recent_market_events:
            sev = e.get("severity", "MEDIUM")
            sev_styled = f"[bold red]{sev}[/bold red]" if sev in ["CRITICAL", "HIGH"] else f"[yellow]{sev}[/yellow]" if sev == "MEDIUM" else sev
            action = e.get("triage_action") or "NOTIFY_ONLY"
            action_styled = f"[bold green]{action}[/bold green]" if action == "TRIGGER_RESEARCH" else f"[cyan]{action}[/cyan]"
            table_evt.add_row(
                str(e.get("detected_at", "")),
                str(e.get("ticker", "")),
                str(e.get("event_type", "")),
                sev_styled,
                str(e.get("title", ""))[:26],
                action_styled
            )
        console.print(table_evt)
        console.print()

    # 5. 直近の自己反省と教訓
    if summary.recent_reflections:
        table_ref = Table(title="🪞 直近の自己反省レポート & 改善教訓", show_header=True, header_style="bold green")
        table_ref.add_column("反省ID", style="dim", width=14)
        table_ref.add_column("日時", width=19)
        table_ref.add_column("精度スコア", justify="right", width=10)
        table_ref.add_column("導出された教訓 (Lessons Learned)", width=42)

        for r in summary.recent_reflections:
            score = r.get("accuracy_score", 0)
            score_styled = f"[bold green]{score}/100[/bold green]" if score >= 80 else f"[yellow]{score}/100[/yellow]"
            lessons = ", ".join(r.get("lessons_learned", []))[:40]
            table_ref.add_row(
                r.get("reflection_id", ""),
                str(r.get("created_at", "")),
                score_styled,
                lessons
            )
        console.print(table_ref)

    console.print("\n[dim]💡 コマンド一覧: --help, --web (Web UI起動), -p (方針策定), --monitor-once (市場スキャン), --journal (意思決定履歴)[/dim]\n")


def display_dashboard() -> None:
    """ダッシュボードを取得して描画"""
    summary = get_dashboard_summary()
    render_cli_dashboard(summary)
