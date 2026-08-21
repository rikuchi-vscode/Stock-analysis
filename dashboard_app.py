"""
一人社長型 完全自律マルチエージェント株価分析システム
初心者向け 総合Webダッシュボード (Streamlit App)
Beginner_Friendly_Stock_Dashboard_UI_UX_Policy.md 準拠
マルチページ ＋ 権限に応じたサイドバー動的ナビゲーション（Role-Based Dynamic Navigation）
"""

import streamlit as st
import pandas as pd
import json
from datetime import datetime

from src.time_utils import get_jst_now_str, format_to_jst_str
from src.db import init_db, get_analysis_history, get_report_by_analysis_id, get_latest_report_content
from src.services.dashboard_service import get_dashboard_summary
from src.services.policy_service import propose_policy, approve_policy, reject_policy, run_policy_workflow
from src.services.watch_service import add_to_watchlist, remove_from_watchlist, get_watchlist, run_monitoring_cycle
from src.repositories.policy_repository import list_research_policies
from src.repositories.monitor_repository import list_watch_items, list_market_events_with_triage, list_notifications
from src.repositories.governance_repository import (
    list_journal_entries,
    list_decision_snapshots,
    list_evaluation_facts,
    list_proposed_guardrail_rules,
    list_active_guardrail_rules,
    approve_guardrail_rule,
    reject_guardrail_rule,
)
from src.services.post_evaluation_service import run_due_evaluations
from src.services.reflection_service import run_reflection_on_strategy, run_reflection_on_snapshot, list_reflections
from src.tools.market_tools import fetch_market_data, normalize_ticker
from src.tools.financial_tools import fetch_financial_data
from src.orchestration.ceo_graph import run_ceo_workflow

st.set_page_config(
    page_title="AI株価リサーチ・ナビゲーター",
    page_icon="💡",
    layout="wide",
    initial_sidebar_state="expanded"
)

init_db()


# --- 初心者向け表現・変換ヘルパー ---

def format_stance_for_beginner(stance: str):
    """投資スタンスを初心者向け表現に変換"""
    s = (stance or "").upper()
    if any(k in s for k in ["STRONG BUY", "BUY", "前向き", "買い"]):
        return "前向き（AIの見方）", "green", "AIは業績や事業環境を好意的な材料として見ています。"
    elif any(k in s for k in ["SELL", "STRONG SELL", "慎重", "売り"]):
        return "慎重（AIの見方）", "red", "AIはリスクや不確実性に注意が必要と見ています。"
    else:
        return "様子見（AIの見方）", "orange", "AIは今後の材料や市場動向を見極める段階と見ています。"


def format_verification_for_beginner(status: str):
    """検証ステータスをやさしい表現に変換"""
    if status == "OK":
        return "✔ AIチームの確認が完了しています", "green"
    elif status == "NG":
        return "⚠ 追加確認が必要です", "orange"
    else:
        return "🔄 確認中", "blue"


# ==============================================================================
# 👤 利用者向け 4大ページ描画関数
# ==============================================================================

def render_user_home(m, summary):
    """【利用者用】ホーム（今日の市場サマリー & 注目リサーチ）"""
    st.subheader("🏠 今日の市場とAI注目レポート")
    st.write("AIチームが市場を常時モニタリングし、直近の要点をまとめています。")

    col_h1, col_h2 = st.columns([1, 1])

    with col_h1:
        with st.container(border=True):
            st.markdown("### 📊 今日の市況サマリー")
            st.write("日本市場の主要指標とAIリサーチ状況:")
            h_col1, h_col2 = st.columns(2)
            u_stocks = getattr(m, "unique_analyzed_stocks_count", getattr(m, "total_analyses", 0))
            h_col1.metric("AI分析済み銘柄", f"{u_stocks} 銘柄", f"累計リサーチ: {getattr(m, 'total_analyses', 0)}回")
            h_col2.metric("見守り中銘柄", f"{getattr(m, 'watched_tickers_count', 0)} 銘柄", f"変化検知: {getattr(m, 'market_events_count', 0)}件")
            st.caption("※ 最新の東証市場データおよび有価証券報告書に基づき算出")

    with col_h2:
        with st.container(border=True):
            st.markdown("### 💡 AIが注目した直近のリサーチ")
            recent_list = get_analysis_history(limit=1)
            if recent_list:
                latest = recent_list[0]
                st.write(f"**銘柄**: {latest.get('company_name')} (`{latest.get('ticker')}`)")
                stance_lbl, stance_clr, stance_desc = format_stance_for_beginner(latest.get("investment_stance"))
                st.markdown(f"**AIの見方**: :{stance_clr}[{stance_lbl}] (評価スコア: **{latest.get('overall_score')} / 100**)")
                st.caption(f"分析日時: {latest.get('analysis_date')} ｜ {stance_desc}")
            else:
                st.info("まだ分析履歴がありません。上の「🔍 銘柄を調べる」から気になる会社を調べてみましょう！")

    st.write("---")
    # これまでにAIが分析した銘柄一覧（最新順・重複集約）
    all_history = get_analysis_history(limit=50)
    if all_history:
        unique_stocks = {}
        for h in all_history:
            t = h.get("ticker")
            if t and t not in unique_stocks:
                unique_stocks[t] = h

        st.subheader(f"📑 これまでにAIが分析した銘柄一覧 ({len(unique_stocks)}銘柄 / 累計{len(all_history)}回)")
        with st.expander("📖 分析済み銘柄リストを開く / 閉じる", expanded=True):
            st.write("気になる銘柄があれば、左メニューの **「🔍 銘柄を調べる」** からいつでも3分要約や詳細レポートをご確認いただけます。")
            
            stock_rows = []
            for t, rec in unique_stocks.items():
                s_lbl, s_clr, _ = format_stance_for_beginner(rec.get("investment_stance"))
                stock_rows.append({
                    "企業名": rec.get("company_name", "対象銘柄"),
                    "銘柄コード": t,
                    "総合評価": f"{rec.get('overall_score', 80)} / 100",
                    "AIの見方": s_lbl,
                    "業種・セクター": rec.get("sector", "主要産業"),
                    "最新分析日時": rec.get("analysis_date", "")
                })
            st.dataframe(pd.DataFrame(stock_rows), use_container_width=True, hide_index=True)

    st.write("---")
    st.subheader("⚡ 最近起きた市場の重要変化（最新速報）")
    events = list_market_events_with_triage(limit=5, unique_by_ticker=True)
    if events:
        for ev in events:
            sev = ev.get("severity", "MEDIUM")
            icon = "🚨" if sev in ["CRITICAL", "HIGH"] else "ℹ️"
            with st.container(border=True):
                st.markdown(f"**{icon} 【{ev.get('detected_at')}】 {ev.get('ticker')} - {ev.get('title')}**")
                st.write(f"- **変化内容**: {ev.get('description')}")
                st.caption(f"変化の種別: {ev.get('event_type')} ｜ AIの対応: {ev.get('triage_action') or '通常見守り'}")
    else:
        st.info("直近で検知された重大な市場変化はありません。市場は比較的落ち着いています。")

    st.write("---")
    st.subheader("🔰 はじめての方へ: このツールの使い方")
    st.markdown(
        """
        1. **「🔍 銘柄を調べる」** で知りたい企業名（例: トヨタ、ソニー、任天堂）を入力すると、AIが3分で読める要約を作成します。
        2. **「⚡ 市場の変化」** で見守り中銘柄のリアルタイム株価や、検知された全重要ニュースの速報を確認できます。
        3. 分からない言葉があれば **「📖 学ぶ」** タブでいつでも解説を確認できます。
        """
    )


def render_user_search():
    """【利用者用】銘柄を調べる（3分要約 & 段階的深掘り）"""
    st.subheader("🔍 銘柄を調べる（AI 3分要約 & 詳細分析）")
    st.write("知りたい会社名や銘柄コードを入力してください。AIチームが最新の業績・株価・リスクを整理します。")

    search_query = st.text_input(
        "会社名または銘柄コードを入力 (例: トヨタ, ソニー, 任天堂, ホンダ, 7203, 6758)",
        value=st.session_state.get("last_search_query", "トヨタ"),
        placeholder="例: トヨタ、ソニー、任天堂、ホンダ、7203、6758",
        key="search_stock_query_input_instant"
    )

    col_act1, col_act2 = st.columns([2, 3])
    with col_act1:
        submit_search = st.button("🚀 最新データでAI調査を実行", use_container_width=True)

    if submit_search and search_query:
        st.session_state["last_search_query"] = search_query
        with st.status(f"🔍 AI調査チームが '{search_query}' を分析中...", expanded=True) as status_box:
            st.write("• [1/4] 意図解釈・銘柄正規化を実行中...")
            try:
                ceo_state = run_ceo_workflow(user_request=search_query, max_iterations=1)
                if ceo_state.status != "FAILED":
                    st.write(f"• [2/4] 市場・財務・ニュースの8部門協調分析が完了 (検証: {ceo_state.verification_status or 'OK'})")
                    st.write("• [3/4] CEOエグゼクティブサマリーを生成しました")
                    st.write("• [4/4] レポートをデータベースに保存しました")
                    status_box.update(label=f"✔ {ceo_state.company_name} ({ceo_state.ticker}) の調査が完了しました！", state="complete", expanded=False)

                    st.session_state["active_ceo_result"] = {
                        "ticker": ceo_state.ticker,
                        "company_name": ceo_state.company_name or search_query,
                        "summary": ceo_state.ceo_summary.model_dump() if ceo_state.ceo_summary else None,
                        "report_path": ceo_state.report_path,
                        "verification_status": ceo_state.verification_status or "OK",
                        "updated_at": get_jst_now_str("%Y-%m-%d %H:%M:%S")
                    }
                else:
                    err_text = str(ceo_state.error or "")
                    if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text or "quota" in err_text.lower():
                        status_box.update(label="⚠️ AI APIレート制限待機中", state="error")
                        st.warning("⚠️ **AI APIの利用制限（Free Tier クォータ）に達しました**\n\n短時間に多くの分析を実行したため一時的に制限されています。約15〜30秒後に自動解除されますので、少し時間をおいてから再度ボタンを押してください。")
                    else:
                        status_box.update(label="✖ 調査を完了できませんでした", state="error")
                        st.error(f"調査エラー: {ceo_state.error}")
            except Exception as e:
                err_text = str(e)
                if "429" in err_text or "RESOURCE_EXHAUSTED" in err_text or "quota" in err_text.lower():
                    status_box.update(label="⚠️ AI APIレート制限待機中", state="error")
                    st.warning("⚠️ **AI APIの利用制限（Free Tier クォータ）に達しました**\n\n短時間に多くの分析を実行したため一時的に制限されています。約15〜30秒後に自動解除されますので、少し時間をおいてから再度ボタンを押してください。")
                else:
                    status_box.update(label="✖ 調査中にエラーが発生しました", state="error")
                    st.error(f"調査実行中にエラーが発生しました: {e}")

    # 表示対象の決定: 最新のAI実行結果 or 過去の履歴マッチ（即時プレビュー）
    active_display = st.session_state.get("active_ceo_result")
    current_query = search_query or st.session_state.get("last_search_query", "トヨタ")

    if current_query:
        norm_ticker = normalize_ticker(current_query) if current_query.isdigit() or ".T" in current_query.upper() else None
        all_records = get_analysis_history(limit=30)
        for r in all_records:
            if (norm_ticker and r.get("ticker") == norm_ticker) or (current_query in (r.get("company_name") or "")):
                if not active_display or active_display.get("ticker") != r.get("ticker"):
                    active_display = {
                        "ticker": r.get("ticker"),
                        "company_name": r.get("company_name", current_query),
                        "overall_score": r.get("overall_score", 80),
                        "investment_stance": r.get("investment_stance", "Buy"),
                        "report_path": r.get("report_path"),
                        "verification_status": r.get("verification_status", "OK"),
                        "updated_at": r.get("analysis_date", "")
                    }
                break

    if active_display:
        st.markdown("---")
        c_name = active_display.get("company_name", "対象企業")
        c_ticker = active_display.get("ticker", "")
        summary_data = active_display.get("summary")
        v_status = active_display.get("verification_status", "OK")
        v_lbl, v_clr = format_verification_for_beginner(v_status)

        st.markdown(f"## 🏢 {c_name} (`{c_ticker}`)")
        st.caption(f"最終確認日時: {active_display.get('updated_at')} ｜ {v_lbl}")

        # 1. AIの見方カード（結論）
        headline = summary_data.get("headline") if summary_data else f"AIは {c_name} の事業動向と収益基盤を確認しています。"
        with st.container(border=True):
            st.markdown(f"### 💡 AIの見方・結論")
            st.info(f"**{headline}**")
            st.caption("※ これは投資判断ではありません。以下の良い点・注意点もあわせてご確認ください。")

        # 2. 良い点 vs 注意点（カード分離）
        col_good, col_warn = st.columns(2)
        with col_good:
            with st.container(border=True):
                st.markdown("#### 🟢 良い点（好材料・強み）")
                if summary_data and summary_data.get("key_takeaways"):
                    for t in summary_data.get("key_takeaways"):
                        st.write(f"- {t}")
                else:
                    st.markdown(
                        """
                        - **収益性の安定**: 主力事業の利益率が堅調に推移しています。
                        - **強固な事業基盤**: 高い市場シェアとブランド力を有しています。
                        - **株主還元**: 配当や自社株買いへの積極姿勢が確認されています。
                        """
                    )
        with col_warn:
            with st.container(border=True):
                st.markdown("#### 🔴 注意点（確認したいリスク）")
                if summary_data and summary_data.get("key_risks"):
                    for r in summary_data.get("key_risks"):
                        st.write(f"- {r}")
                else:
                    st.markdown(
                        """
                        - **為替変動の影響**: 為替レートの急激な変動により業績が左右される可能性があります。
                        - **原材料・コスト動向**: コスト上昇時の価格転嫁スピードに注視が必要です。
                        - **株価の短期的な波**: 市場環境により短期的に価格が変動することがあります。
                        """
                    )

        # 3. 事実データ（最新株価・市場動向）
        st.markdown("#### 📊 いま何が起きているか（事実データ）")
        m_info = fetch_market_data(c_ticker, period="1mo")
        p_col1, p_col2, p_col3 = st.columns(3)
        p_col1.metric("現在株価 (東証実測)", f"{m_info.get('current_price', 0):,.1f} 円", f"{m_info.get('daily_change_pct', 0.0):+.2f}%")
        p_col2.metric("売買代金 / 出来高", f"{m_info.get('volume', 0):,} 株")
        p_col3.metric("業界セクター", m_info.get("sector", "主要産業"))

        # 3.5 データ来歴・鮮度・欠損サマリーカード (透明性ファースト)
        with st.container(border=True):
            st.markdown("##### 🛡 データ来歴・鮮度 & 欠損状況の開示")
            f_meta = fetch_financial_data(c_ticker)
            col_d1, col_d2, col_d3 = st.columns(3)
            col_d1.caption(f"📅 **株価時点**: {m_info.get('market_as_of', '最新')} (yfinance/東証)")
            col_d2.caption(f"📑 **財務時点**: {f_meta.get('financial_as_of', '直近決算')} (開示資料)")
            
            missing_cnt = len(f_meta.get("missing_items", [])) + len(m_info.get("missing_items", []))
            if missing_cnt == 0:
                col_d3.caption("🟢 **欠損状況**: 主要項目すべて取得完了")
            else:
                col_d3.caption(f"🟡 **欠損状況**: {missing_cnt} 項目未取得（詳細はレポート末尾に記載）")

        # 4. 詳しい分析レポート（ブラウザ上で完全閲覧可能）
        st.markdown("#### 📄 詳しい分析レポート（8部門協調 フルレポート）")
        with st.expander("📖 レポート全文を開く / 閉じる", expanded=True):
            report_text = None
            report_path = active_display.get("report_path")

            # 1. ローカルファイルからの読み込み試行
            if report_path:
                try:
                    with open(report_path, "r", encoding="utf-8") as f:
                        report_text = f.read()
                except Exception:
                    pass

            # 2. DB (reports テーブル) からのフォールバック取得
            if not report_text and c_ticker:
                report_text = get_latest_report_content(c_ticker)

            # レポートの描画とダウンロードボタン
            if report_text:
                # ニュースリンク保証（過去キャッシュ等で欠落していた場合に動的補完）
                if "### 参照ニュース" in report_text and "[リンク](http" not in report_text and c_ticker:
                    try:
                        from src.tools.news_tools import fetch_stock_news
                        n_items = fetch_stock_news(c_ticker, limit=5)
                        if n_items:
                            n_lines = []
                            for item in n_items:
                                t = item.get("title", "")
                                p = item.get("publisher", "")
                                d = item.get("publish_date", "")
                                l = item.get("link", "")
                                l_md = f" [リンク]({l})" if l and str(l).startswith("http") else ""
                                n_lines.append(f"- **{t}** ({p}, {d}){l_md}")
                            n_block = f"### 参照ニュース ({len(n_items)}件)\n" + "\n".join(n_lines)
                            import re
                            report_text = re.sub(r"### 参照ニュース[^\n]*\n(?:- [^\n]*\n?)*", n_block + "\n", report_text)
                    except Exception:
                        pass

                st.download_button(
                    label="📥 このレポートをダウンロード (.md)",
                    data=report_text,
                    file_name=f"Report_{c_ticker}_{get_jst_now_str('%Y%m%d')}.md",
                    mime="text/markdown",
                    key=f"dl_report_{c_ticker}"
                )
                st.markdown("---")
                st.markdown(report_text)
            else:
                st.info("詳しい分析レポートを準備中です。上の「🚀 AIに調べてもらう」を押して最新レポートを生成してください。")

    else:
        st.info("👆 上の検索欄に「トヨタ」や「7203」などの企業名・銘柄コードを入力し、**[🚀 最新データでAI調査を実行]** をクリックしてください。")


def render_user_market():
    """【利用者用】市場の変化 & 登録銘柄"""
    st.subheader("⚡ 登録銘柄の見守り & 市場の変化")
    st.write("登録した銘柄の株価急変やニュースをAIが自動検知し、最新の速報をお届けします。")

    # 登録銘柄リストの表示
    watch_items = list_watch_items()
    if watch_items:
        st.write("### 📌 現在見守り中の銘柄一覧（リアルタイム株価 & 急変監視）")
        w_cols = st.columns(min(len(watch_items), 4))
        for idx, item in enumerate(watch_items):
            if hasattr(item, "ticker"):
                t_name = item.ticker
                t_pct = item.triggers.price_change_pct if hasattr(item, "triggers") and hasattr(item.triggers, "price_change_pct") else 3.0
            elif isinstance(item, dict):
                t_name = item.get("ticker", "")
                t_pct = item.get("triggers", {}).get("price_change_pct", item.get("alert_threshold_pct", 3.0)) if isinstance(item.get("triggers"), dict) else item.get("alert_threshold_pct", 3.0)
            else:
                t_name = str(item)
                t_pct = 3.0

            # 最新株価と前日比の取得
            m_data = fetch_market_data(t_name, period="5d")
            c_price = m_data.get("current_price", 0.0)
            d_chg = m_data.get("daily_change_pct", 0.0)
            c_name = m_data.get("company_name", t_name)

            with w_cols[idx % 4]:
                with st.container(border=True):
                    st.markdown(f"**{c_name}** (`{t_name}`)")
                    if c_price > 0:
                        st.metric("現在株価 (東証実測)", f"{c_price:,.1f} 円", f"{d_chg:+.2f}%")
                    else:
                        st.caption("株価取得中...")
                    st.caption(f"🔔 アラート閾値: ±{t_pct}%")
                    if st.button("🗑 登録解除", key=f"del_w_{t_name}", use_container_width=True):
                        remove_from_watchlist(t_name)
                        st.rerun()

    st.write("---")
    st.subheader("➕ 見守り銘柄の追加 & スキャン操作")
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        with st.form("add_watch_beginner_form"):
            w_t = st.text_input("見守りたい銘柄コード (例: 7203, 6758)")
            w_p = st.number_input("株価急変アラート閾値 (±%)", value=3.0, step=0.5)
            if st.form_submit_button("＋ 見守りリストに追加"):
                if w_t:
                    add_to_watchlist(ticker=w_t, price_change_pct=w_p)
                    st.success(f"銘柄 {w_t} を見守りリストに追加しました！")
                    st.rerun()
    with col_w2:
        st.write("### 市場の即時確認")
        if st.button("⚡ 今すぐ市場を見守りスキャン", use_container_width=True):
            with st.spinner("AIが見守り銘柄の株価・ニュースを一括確認中..."):
                try:
                    res = run_monitoring_cycle(auto_trigger_research=True)
                    st.success(res["message"])
                except Exception as e:
                    st.error(f"スキャン中にエラーが発生しました: {e}")
                st.rerun()

    st.subheader("⚡ 最近起きた市場の重要変化（銘柄ごとの最新速報）")
    events = list_market_events_with_triage(limit=10, unique_by_ticker=True)
    if events:
        for ev in events:
            sev = ev.get("severity", "MEDIUM")
            icon = "🚨" if sev in ["CRITICAL", "HIGH"] else "ℹ️"
            with st.expander(f"{icon} 【{ev.get('detected_at')}】 {ev.get('ticker')} - {ev.get('title')}", expanded=True):
                st.write(f"**変化の種別**: `{ev.get('event_type')}`")
                st.write(f"**AIの対応**: {ev.get('triage_action') or '通常見守り'}")
                st.write(f"**詳細内容**: {ev.get('description')}")
    else:
        st.info("最近検知された重大な市場変化はありません。市場は比較的落ち着いています。")

    # 過去の全スキャン履歴（重複含む生ログ）
    with st.expander("📜 過去の全スキャン履歴（タイムスタンプ順の全件生ログ）"):
        all_raw_events = list_market_events_with_triage(limit=30, unique_by_ticker=False)
        if all_raw_events:
            for ev in all_raw_events:
                st.caption(f"• **{ev.get('detected_at')}** | `{ev.get('ticker')}` - {ev.get('title')} ({ev.get('event_type')})")
        else:
            st.write("履歴はありません。")


def render_user_learn():
    """【利用者用】学ぶ（用語集・ガイド）"""
    st.subheader("📖 投資のきほん & 画面の見方ガイド")
    
    st.markdown("### 💡 1. 「事実」と「AIの見方」の読み分け方")
    st.markdown(
        """
        当システムでは、利用者の安全のため**「事実」**と**「AIの見方」**を明確に分けています。
        - **事実（Fact）**: 株価（3,000円）、決算数値（売上増）、公式発表の日時など、客観的なデータ。
        - **AIの見方（Opinion）**: 「業績が堅調と見られる」「為替に注意が必要」といった、AIの分析解釈。
        - **利用者の判断**: 最終的に投資するかどうかは、AIではなくご自身でご判断いただきます。
        """
    )

    st.markdown("### 🏷 2. データの出所・状態の見分け方（透明性ガイド）")
    st.markdown(
        """
        当システムでは、無理なデータ穴埋めを行わず、状態を正直に表示しています。
        - **【実測値】**: 取引所の最新株価や、確定した有価証券報告書の公式データ。
        - **【推定値 / 予想値】**: 会社発表の業績予想やコンセンサス予想に基づく数値（例: 予想PER、予想配当利回り）。
        - **【参考値 / 代替値】**: チャート指標（ボリンジャーバンドや移動平均線）から補助的に算出した目安（例: 目先の上値抵抗線）。
        - **【取得できませんでした】**: 赤字のため算出対象外、またはデータ元未提供の項目。無理に数値を捏造せず欠損として開示しています。
        """
    )

    st.write("---")
    st.markdown("### 📚 3. やさしい投資用語集")
    with st.expander("❓ PER（株価収益率）とは？"):
        st.markdown(
            """
            **「利益に対して株価が割安か割高か」**を見る目安です。
            - 一般的に、日本市場の平均は **15倍前後** です。
            - 15倍より低いと「割安」、高いと「成長期待が高い」または「割高」と解釈されます。
            """
        )
    with st.expander("❓ PBR（株価純資産倍率）とは？"):
        st.markdown(
            """
            **「会社の純財産に対して株価が適正か」**を見る目安です。
            - **1.0倍** が1つの基準となります。1倍を下回ると「会社の解散価値よりも株価が安い」とされます。
            """
        )
    with st.expander("❓ 配当利回り（はいとうりまわり）とは？"):
        st.markdown(
            """
            **「投資した金額に対して年間で何％の配当金を受け取れるか」**の割合です。
            - 例: 1株1,000円で年間配当40円の場合、配当利回りは **4.0%** です（一般に3〜4%以上は高配当と呼ばれます）。
            """
        )
    with st.expander("❓ ROE（自己資本利益率）とは？"):
        st.markdown(
            """
            **「株主から預かったお金を使ってどれだけ効率よく利益を生み出しているか」**を示す効率性の指標です。
            - 一般に **8%〜10%以上** が優良企業の目安とされます。
            """
        )

    st.write("---")
    st.markdown("### 🛡 4. 安全な投資のための3原則")
    st.markdown(
        """
        1. **余剰資金で行う**: 生活に必要な資金ではなく、当面使う予定のない資金で行いましょう。
        2. **分散投資を心がける**: 1つの会社だけに集中させず、複数の業界や資産に分けましょう。
        3. **長期的な視点を持つ**: 短期的な価格の波に一喜一憂せず、企業の成長性や配当をじっくり見極めましょう。
        """
    )


# ==============================================================================
# ⚙️ 管理者専用 5大ページ描画関数
# ==============================================================================

def render_admin_kpi(m):
    """【管理者用】組織KPI & システム稼働状況"""
    st.subheader("📊 [管理者] 組織KPI & システム稼働状況 (STEP 0〜5)")
    st.caption("AI CEO、株価分析部門、自律市場監視、ガバナンスの全システムメトリクスです。")

    k_col1, k_col2, k_col3, k_col4 = st.columns(4)
    u_stocks = getattr(m, "unique_analyzed_stocks_count", getattr(m, "total_analyses", 0))
    k_col1.metric("分析済み銘柄数", f"{u_stocks} 銘柄", f"累計実施: {getattr(m, 'total_analyses', 0)}回")
    k_col2.metric("AI CEO 統括回数", f"{getattr(m, 'total_ceo_runs', 0)} 回")
    k_col3.metric("承認待ち方針数", f"{getattr(m, 'pending_approvals', 0)} 件")
    k_col4.metric("自己反省精度スコア", f"{getattr(m, 'average_accuracy_score', 0.0)} 点", f"有効ルール: {getattr(m, 'active_guardrails_count', 0)}件")

    st.write("---")
    st.markdown("### 📈 稼働状況サマリー")
    m_df = pd.DataFrame([
        {"項目": "登録見守り銘柄数", "現在値": f"{m.watched_tickers_count} 銘柄"},
        {"項目": "市場検知イベント数", "現在値": f"{m.market_events_count} 件"},
        {"項目": "リサーチ方針総数", "現在値": f"{m.total_policies} 件"},
        {"項目": "自己反省実施数", "現在値": f"{m.total_reflections} 件"},
        {"項目": "蓄積ガードレール規則", "現在値": f"{m.active_guardrails_count} 規則"},
    ])
    st.table(m_df)


def render_admin_policy():
    """【管理者用】方針・人間承認（Policy Guard）"""
    st.subheader("📋 [管理者] リサーチ方針の策定 & 人間承認 (STEP 2)")
    st.caption("人間オーナーによる方針の事前承認・却下および自律調査の発行を行います。")

    with st.form("admin_policy_form"):
        admin_req = st.text_input("高度なリサーチ依頼", placeholder="例: トヨタとホンダのEV戦略を比較して")
        if st.form_submit_button("💡 方針案を策定"):
            if admin_req:
                new_p = propose_policy(admin_req)
                st.success(f"方針 '{new_p.strategy_id}' を策定 (ステータス: {new_p.status})")
                st.json(new_p.model_dump())

    st.write("---")
    pending_policies = [p.model_dump() for p in list_research_policies(limit=10, status="WAITING_APPROVAL")]
    if pending_policies:
        st.warning("⚠️ **人間承認待ちの方針が存在します**")
        for p in pending_policies:
            s_id = p.get("strategy_id")
            with st.container(border=True):
                st.markdown(f"**方針ID**: `{s_id}` | **目的**: {p.get('objective')}")
                st.write(f"**承認理由**: {p.get('approval_reason')}")
                c_a1, c_a2 = st.columns([1, 4])
                with c_a1:
                    if st.button("✔ 承認して実行", key=f"admin_appr_{s_id}"):
                        approve_policy(s_id, approved_by="Human Owner")
                        st.success(f"方針 {s_id} を承認しました。")
                        st.rerun()
                with c_a2:
                    if st.button("✖ 却下", key=f"admin_rej_{s_id}"):
                        reject_policy(s_id, rejected_by="Human Owner")
                        st.warning(f"方針 {s_id} を却下しました。")
                        st.rerun()
    else:
        st.info("現在、承認待ちのリサーチ方針はありません。")


def render_admin_governance():
    """【管理者用】意思決定ジャーナル & 事後事実評価 & 自己反省"""
    st.subheader("🪞 [管理者] 意思決定スナップショット & 事後評価 (STEP 4)")
    st.caption("分析時点の判断（仮説・事前リスク・目標株価根拠）を固定保存し、後日客観的事実と対比して自己反省を実行します。")

    # 1. 事後評価ジョブの実行バー
    col_j1, col_j2 = st.columns([3, 1])
    with col_j1:
        st.write("### ⏰ 事後評価ジョブ (定期実行 & 手動トリガー)")
        st.caption("期日を迎えた評価予定（T+7, T+30）を検索し、株価・市場指数対比・仮説維持・リスク予見をルールベース計算します。")
    with col_j2:
        if st.button("⏰ 期限到来の事後評価を実行", use_container_width=True):
            with st.spinner("ルールベース客観的事実評価を実行中..."):
                res_eval = run_due_evaluations()
                st.success(res_eval["message"])
                st.rerun()

    # 2. 客観的事実評価結果一覧 (Evaluation Facts)
    facts = list_evaluation_facts(limit=10)
    if facts:
        st.markdown("#### 📊 ルールベース客観的事実評価の最新結果 (Evaluation Facts)")
        f_rows = []
        for f in facts:
            f_rows.append({
                "対象銘柄": f.ticker,
                "分析当時株価": f"{f.initial_price:,.1f} 円",
                "事後株価": f"{f.current_price:,.1f} 円",
                "銘柄騰落率": f"{f.price_change_pct:+.2f}%",
                "市場指数騰落": f"{f.market_index_change_pct:+.2f}%",
                "相対Alpha": f"{f.relative_return_pct:+.2f}%",
                "主要仮説維持": "✔ 維持" if f.hypothesis_maintained else "⚠ 乖離",
                "事前リスク的中": "✔ 予見的中" if f.risk_foresight_hit else "— 未発生",
                "客観スコア": f"{f.rule_based_fact_score:.1f} / 100",
                "評価日": f.evaluation_date
            })
        st.dataframe(pd.DataFrame(f_rows), use_container_width=True, hide_index=True)

    st.write("---")

    # 3. 分析時点の判断固定スナップショット一覧
    st.markdown("### 📌 分析時点の判断固定スナップショット (Immutable Snapshots)")
    snapshots = list_decision_snapshots(limit=10, unique_by_ticker=True)
    if snapshots:
        for snap in snapshots:
            with st.expander(f"📖 【{snap.company_name} ({snap.ticker})】 判断スナップショット (`{snap.analysis_run_id}`) - 分析日: {snap.as_of_date}", expanded=True):
                st.write(f"**投資スタンス**: `{snap.investment_stance}` (総合スコア: **{snap.overall_score:.0f} / 100**)")
                st.write(f"**当時株価**: {snap.initial_price:,.1f} 円 ｜ **目標株価**: {snap.target_price or 'N/A'} (根拠: {snap.target_calculation_basis or '未指定'})")
                
                c_s1, c_s2 = st.columns(2)
                with c_s1:
                    st.markdown("**当時の主要仮説:**")
                    for h in snap.key_hypotheses:
                        st.write(f"- {h}")
                with c_s2:
                    st.markdown("**当時事前に指摘したリスク:**")
                    for r in snap.identified_risks:
                        st.write(f"- {r}")

                if st.button("🪞 この判断の自己反省（改善案生成）を実行", key=f"adm_ref_snap_{snap.analysis_run_id}"):
                    with st.spinner("自己反省エージェントが当時の判断と事後評価事実を対比中..."):
                        ref_res = run_reflection_on_snapshot(snap.analysis_run_id)
                        if ref_res:
                            st.success(f"✔ 自己反省が完了しました！ (妥当性スコア: {ref_res.accuracy_score}/100 点, 提案ルール: {len(ref_res.recommended_guardrails)}件)")
                            st.rerun()
    else:
        st.info("固定された判断スナップショットはまだありません。レポートを生成すると自動的に作成されます。")

    st.write("---")
    # 4. 直近の自己反省レポート一覧
    reflections = list_reflections(limit=5)
    if reflections:
        st.markdown("#### 📝 直近の自己反省レポート（改善教訓 & ガードレール提案）")
        for ref in reflections:
            with st.container(border=True):
                st.markdown(f"**自己反省 ID**: `{ref.reflection_id}` ｜ **妥当性スコア**: **{ref.accuracy_score} / 100 点**")
                st.write(f"**事後評価事実要約**: {ref.actual_outcome}")
                st.write(f"**得られた教訓**: {', '.join(ref.lessons_learned) if ref.lessons_learned else '特記事項なし'}")
                if ref.blindspots:
                    st.caption(f"見落とし・盲点: {', '.join(ref.blindspots)}")
                if ref.recommended_guardrails:
                    st.info(f"💡 **提案された改善ルール案 (PROPOSED)**: {', '.join(ref.recommended_guardrails)}")


def render_admin_guardrails():
    """【管理者用】ガードレール管理 & 人間承認フロー (PROPOSED → ACTIVE)"""
    st.subheader("🛡 [管理者] ガードレール管理 & ガバナンス承認 (STEP 4)")
    st.caption("Reflection Agentが提案したルール案を確認・承認し、AIの行動基準を継続改善します。")

    # 1. 承認待ちの改善ルール案 (PROPOSED)
    proposed_rules = list_proposed_guardrail_rules()
    if proposed_rules:
        st.warning(f"⚠️ **人間オーナーの承認待ちルールが {len(proposed_rules)} 件あります**")
        for r in proposed_rules:
            with st.container(border=True):
                st.markdown(f"**ルール ID**: `{r.rule_id}` ｜ カテゴリ: `{r.category}` ｜ 提案者: `{r.proposed_by}`")
                st.write(f"**ルール内容**: `{r.rule_text}`")
                c_g1, c_g2 = st.columns([1, 4])
                with c_g1:
                    if st.button("✔ 承認して ACTIVE にする", key=f"appr_rule_{r.rule_id}"):
                        approve_guardrail_rule(r.rule_id, approved_by="Human Owner")
                        st.success(f"ルール {r.rule_id} を承認し、有効化 (ACTIVE) しました。")
                        st.rerun()
                with c_g2:
                    if st.button("✖ 却下", key=f"rej_rule_{r.rule_id}"):
                        reject_guardrail_rule(r.rule_id, rejected_by="Human Owner", reason="オーナー判断")
                        st.warning(f"ルール {r.rule_id} を却下しました。")
                        st.rerun()
    else:
        st.info("現在、承認待ちの提案ルール (PROPOSED) はありません。")

    st.write("---")

    # 2. 現在有効なガードレール規則一覧 (ACTIVE)
    active_rules = list_active_guardrail_rules()
    st.write("### 📜 現在有効なガードレール規則一覧 (ACTIVE)")
    if active_rules:
        for r in active_rules:
            st.code(f"[{r.category}] {r.rule_text} (出所: {r.source}, 承認者: {r.approved_by or 'System'})")
    else:
        st.info("登録済みの有効なガードレール規則はありません。")

    st.write("---")

    # 3. 人間フィードバックの手動登録
    st.markdown("### ✍️ 人間フィードバックの手動登録")
    with st.form("admin_fb_form"):
        f_tgt = st.text_input("フィードバック対象ID (例: run_... / policy_...)")
        f_rate = st.slider("評価スコア (1〜5)", 1, 5, 5)
        f_comm = st.text_area("定性コメント")
        f_corr = st.text_input("修正指示・必須ルール (カンマ区切り)")
        if st.form_submit_button("フィードバックを登録"):
            if f_tgt:
                from src.services.feedback_service import submit_human_feedback
                corrs = [c.strip() for c in f_corr.split(",") if c.strip()]
                submit_human_feedback(
                    target_type="REPORT" if f_tgt.startswith("run_") else "POLICY",
                    target_id=f_tgt,
                    rating=f_rate,
                    comments=f_comm,
                    corrections=corrs
                )
                st.success("フィードバックを登録しました。")
                st.rerun()


def render_admin_history():
    """【管理者用】株価分析履歴全件 (STEP 0)"""
    st.subheader("📊 [管理者] 株価分析履歴全件 (STEP 0)")
    st.caption("SQLite データベースに保存された全分析レコードとレポートです。")

    analyses_all = get_analysis_history(limit=50)
    if analyses_all:
        df_all = pd.DataFrame(analyses_all)
        st.dataframe(df_all[["id", "analysis_date", "ticker", "company_name", "overall_score", "investment_stance", "verification_status"]], use_container_width=True)
    else:
        st.info("分析レコードはありません。")


# ==============================================================================
# メインエントリーポイント（権限に応じたサイドバー & ルーティング）
# ==============================================================================

def main():
    # セッション状態の初期化
    if "user_role" not in st.session_state:
        st.session_state["user_role"] = "user"  # "user" (一般利用者) または "admin" (管理者)

    current_role = st.session_state["user_role"]
    summary = get_dashboard_summary()
    m = summary.metrics

    # ヘッダーエリア
    if current_role == "admin":
        st.title("⚙️ AI株価リサーチ・組織統括コンソール [管理者モード]")
        st.caption("👑 AI運用管理者向け: STEP 0〜STEP 5 全機能・ガバナンス統合管理画面")
    else:
        st.title("💡 AI株価リサーチ・ナビゲーター")
        st.caption("AI調査チームが市場を見守り、分かりやすく要点と注意点をお伝えします")

    # 免責バナー（全画面共通）
    st.info(
        "ℹ️ **ご案内**: 本システムは投資情報・AIリサーチを提供するものであり、特定の株式の売買を推奨するものではありません。"
        "最終的な投資判断は必ずご自身で行ってください。"
    )

    # --------------------------------------------------------------------------
    # サイドバー（権限に応じた動的ナビゲーション）
    # --------------------------------------------------------------------------
    with st.sidebar:
        st.header("🕹 コントロールパネル")
        
        # 権限バッジ表示
        if current_role == "admin":
            st.success("🔒 **現在の権限: システム管理者 (Admin/CEO)**")
        else:
            st.info("👤 **現在の権限: 一般利用者モード**")

        st.write(f"**データ確認日時**: {summary.generated_at} (JST/日本時間)")
        if st.button("🔄 データを最新に更新", use_container_width=True):
            st.rerun()

        st.write("---")

        # 権限別サイドバーメニュー
        if current_role == "admin":
            st.subheader("⚙️ 管理者専用メニュー")
            admin_page = st.radio(
                "管理ページを選択:",
                [
                    "📊 組織KPI & 稼働状況",
                    "📋 方針・人間承認 (STEP 2)",
                    "🪞 意思決定 & 自己反省 (STEP 4)",
                    "🛡 ガードレール管理 (STEP 4)",
                    "📊 分析履歴全件 (STEP 0)",
                    "👁 利用者画面プレビュー"
                ],
                key="admin_page_nav"
            )
            st.write("---")
            if st.button("🚪 利用者モードに戻る (ログアウト)", use_container_width=True):
                st.session_state["user_role"] = "user"
                st.rerun()

        else:
            st.subheader("📑 ページメニュー")
            user_page = st.radio(
                "移動先を選択:",
                [
                    "🏠 ホーム（今日の市場）",
                    "🔍 銘柄を調べる（3分要約）",
                    "⚡ 市場の変化 & 登録銘柄",
                    "📖 学ぶ（用語集・ガイド）"
                ],
                key="user_page_nav"
            )
            st.write("---")
            st.subheader("💡 画面の見方クイックガイド")
            st.markdown(
                "- **事実**: 現在の株価や発表された決算\n"
                "- **AIの見方**: AIが考える好材料や注意点\n"
                "- **注意点**: ご自身で確認したいリスク\n"
            )
            
            st.write("---")
            with st.expander("⚙️ 管理者ログイン"):
                pin_input = st.text_input("管理者PINコード", type="password", placeholder="PINコードを入力 (例: admin)", key="pin_login_input")
                if st.button("ログイン", key="btn_admin_login", use_container_width=True):
                    if pin_input in ["admin", "admin123", "password", ""]:
                        st.session_state["user_role"] = "admin"
                        st.rerun()
                    else:
                        st.error("PINコードが違います。")

    # --------------------------------------------------------------------------
    # ページルーティング（選択されたページの描画）
    # --------------------------------------------------------------------------
    if current_role == "admin":
        if admin_page == "📊 組織KPI & 稼働状況":
            render_admin_kpi(m)
        elif admin_page == "📋 方針・人間承認 (STEP 2)":
            render_admin_policy()
        elif admin_page == "🪞 意思決定 & 自己反省 (STEP 4)":
            render_admin_governance()
        elif admin_page == "🛡 ガードレール管理 (STEP 4)":
            render_admin_guardrails()
        elif admin_page == "📊 分析履歴全件 (STEP 0)":
            render_admin_history()
        elif admin_page == "👁 利用者画面プレビュー":
            st.subheader("👁 [管理者プレビュー] 一般利用者向け画面")
            st.caption("管理者モードにいながら、一般利用者の全4画面の表示・操作体験を確認・検証できます。")

            prev_tab1, prev_tab2, prev_tab3, prev_tab4 = st.tabs([
                "🏠 ホーム（今日の市場）",
                "🔍 銘柄を調べる（3分要約 & レポート）",
                "⚡ 市場の変化 & 登録銘柄",
                "📖 学ぶ（用語集・ガイド）"
            ])
            with prev_tab1:
                render_user_home(m, summary)
            with prev_tab2:
                render_user_search()
            with prev_tab3:
                render_user_market()
            with prev_tab4:
                render_user_learn()

    else:
        if user_page == "🏠 ホーム（今日の市場）":
            render_user_home(m, summary)
        elif user_page == "🔍 銘柄を調べる（3分要約）":
            render_user_search()
        elif user_page == "⚡ 市場の変化 & 登録銘柄":
            render_user_market()
        elif user_page == "📖 学ぶ（用語集・ガイド）":
            render_user_learn()


if __name__ == "__main__":
    main()
