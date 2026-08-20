# 一人社長型AI株価分析システム 段階的実装仕様設計書（STEP 1〜STEP 5）

## 1. 文書の目的と前提

本書は、既存の株価分析システム（STEP 0）を基盤に、AI CEOを中心とした一人社長型AIシステムへ段階的に発展させるための仕様設計書である。各STEPは**単独で実装、テスト、運用評価、ロールバック**できることを必須とし、後続STEPの実装を前提に既存機能を壊さない。

### 1.1 STEP 0で確立済みの契約

STEP 0は、銘柄を入力として以下を実行し、検証済みのMarkdownレポートを出力する「株価分析部門」である。

```text
Manager → Planner → Market / Financial / News
        → Analysis → Risk → Verification
        →（NG: Plannerへ再調査）/（OK: Report）
```

7203.Tの実行結果では、総合評価、テクニカル、ファンダメンタルズ、ニュース、リスク、シナリオ、期間別アクション、`Verification Status: OK` を含むレポートが生成されている。本書ではこの既存経路を変更せず、上位の意思決定層と周辺部門を追加する。

### 1.2 基本原則

- **部門境界を守る**：CEO Agentは直接、市場・財務・ニュースを分析しない。STEP 0のManager Agentへ委任する。
- **既存入出力を維持する**：`ticker`を受けて既存レポートを返すSTEP 0 API/CLIは後方互換とする。
- **自律性は段階的に増やす**：観測・提案・下書きは自動化できるが、外部公開、通知、費用発生、売買・契約等は人間承認を必須とする。
- **監査可能にする**：依頼、方針、委任、使用データ、生成物、検証、承認、失敗を相関IDで追跡する。
- **投資助言・発注をしない**：本システムの出力はリサーチ情報であり、個別の投資助言、注文執行、顧客資産の運用を行わない。

### 1.3 共通識別子と状態

全STEPで次を共通利用する。

| 項目              | 説明                                        |
| ----------------- | ------------------------------------------- |
| `request_id`      | 外部から受けた依頼を識別                    |
| `run_id`          | 1回のCEO/部門実行を識別                     |
| `analysis_run_id` | STEP 0の分析サイクルを識別                  |
| `strategy_id`     | CEOまたはStrategy Agentが決定した方針を識別 |
| `trace_id`        | ログ、イベント、API呼出しを横断して追跡     |
| `approval_id`     | 人間承認が必要な操作を識別                  |

ステータスは `RECEIVED` → `PLANNED` → `DISPATCHED` → `RUNNING` → `VERIFIED` → `REPORTED` を基本とする。停止・失敗時は `WAITING_APPROVAL`、`RETRYING`、`FAILED`、`CANCELLED` を使用し、既存のVerification結果（`OK` / `NG`）を保持する。

---

## 2. STEP 1：AI CEO追加（分析部門の統括）

### 2.1 目的

既存のSTEP 0を「株価分析部門」としてCEO Agentの配下に置き、ユーザー依頼の理解、部門への委任、結果の受領、経営者向け要約報告を実装する。CEOは分析ロジックを置き換えず、オーケストレーションと説明責任を担う。

### 2.2 追加機能

- 自然言語の依頼を、構造化された分析依頼へ正規化する。
- CEOがManager Agentへ`StockAnalysisRequest`を委任する。
- STEP 0の最終レポートおよびVerification結果を受け、CEOサマリーを生成する。
- 依頼理由、委任内容、結果、エラーを実行履歴として保存する。
- 既存の直接実行経路（`Manager → ... → Report`）を残し、CEO経由を新しい入口として追加する。

### 2.3 エージェント役割

| エージェント                                                         | 役割                                 | STEP 1での制約                       |
| -------------------------------------------------------------------- | ------------------------------------ | ------------------------------------ |
| CEO Agent                                                            | 依頼理解、委任、受領、要約、進捗報告 | 銘柄スコア・投資判断を独自計算しない |
| Manager Agent                                                        | 株価分析部門の受付・実行統括         | STEP 0の役割を維持                   |
| Planner / Market / Financial / News / Analysis / Risk / Verification | STEP 0の分析、反証、再調査、品質検証 | 既存契約を維持                       |
| Human Owner                                                          | 最終意思決定、例外判断               | CEO出力を確認する                    |

### 2.4 ワークフロー

```text
User/API
  → CEO Agent: request_normalize
  → CEO Agent: delegation_record
  → Manager Agent: STEP 0 analysis_run
  → Verification Agent: OK / NG
     ├─ NG → Plannerへ再調査（STEP 0既存ループ）
     └─ OK → Report
  → CEO Agent: executive_summary
  → User/API
```

CEOは`Verification Status != OK`の場合、未検証の内容を断定せず、再調査中または失敗として返す。許容再試行回数を超えた場合は、根拠・欠損・次アクションを含むエラー報告に切り替える。

### 2.5 State / データ設計

既存のSTEP 0 `AnalysisState`は変更せず、外側に`CEOState`を追加する。

```json
{
  "request_id": "req_...",
  "run_id": "ceo_...",
  "user_request": "7203を分析して",
  "task_type": "stock_analysis",
  "ticker": "7203.T",
  "department": "stock_research",
  "delegation": { "target": "manager_agent", "status": "DISPATCHED" },
  "analysis_run_id": "analysis_...",
  "verification_status": "OK",
  "ceo_summary": { "headline": "...", "key_risks": [], "limitations": [] },
  "status": "REPORTED",
  "trace_id": "trace_...",
  "error": null
}
```

`CEOState`にSTEP 0の市場データ全文やプロンプト全文を重複保存しない。参照ID、データスナップショットID、レポートURIのみを保持する。

### 2.6 API・外部ツール

- `POST /v1/ceo/requests`：自然言語または構造化依頼を受け付け、`202 Accepted`と`run_id`を返す。
- `GET /v1/ceo/runs/{run_id}`：進捗、委任先、検証状態を返す。
- `GET /v1/ceo/runs/{run_id}/report`：CEOサマリーとSTEP 0レポートへの参照を返す。
- 既存の株価、財務、ニュース取得ツール（例：yfinance、EDINET、検索Grounding等）はManager配下でのみ使用する。CEOが外部データへ直接アクセスする必要はない。

### 2.7 DB変更

| テーブル            | 主な列                                                                                 | 用途       |
| ------------------- | -------------------------------------------------------------------------------------- | ---------- |
| `ceo_requests`      | `request_id`, `user_request`, `task_type`, `ticker`, `status`, `created_at`            | 依頼受付   |
| `ceo_runs`          | `run_id`, `request_id`, `analysis_run_id`, `verification_status`, `status`, `trace_id` | 実行追跡   |
| `agent_delegations` | `delegation_id`, `run_id`, `from_agent`, `to_agent`, `payload_ref`, `status`           | 委任の監査 |
| `ceo_summaries`     | `run_id`, `summary_json`, `report_ref`, `created_at`                                   | CEO報告    |

既存の分析結果・レポートテーブルへは破壊的変更を加えない。必要なら`analysis_run_id`のインデックスを追加する。

### 2.8 推奨ディレクトリ構成

```text
src/
├── agents/
│   ├── ceo_agent.py                 # 新規
│   ├── manager_agent.py             # STEP 0、原則変更なし
│   └── ...
├── contracts/
│   ├── ceo_request.py               # 新規DTO/schema
│   └── stock_analysis.py            # STEP 0契約
├── orchestration/
│   └── ceo_graph.py                 # 新規
├── repositories/
│   └── ceo_repository.py            # 新規
├── services/
│   └── report_adapter.py            # STEP 0結果をCEOへ適合
└── api/
    └── ceo_routes.py                # 新規
tests/
├── unit/test_ceo_agent.py
└── integration/test_ceo_to_manager.py
```

### 2.9 入出力

入力例：`{"request":"トヨタを中期視点で分析して"}`。

正規化出力例：`{"task_type":"stock_analysis","ticker":"7203.T","horizon":"medium","constraints":{"execution":"research_only"}}`。

最終出力は、(1) CEOの簡潔な完了報告、(2) Verification状態、(3) STEP 0レポート、(4) 重要リスク、(5) 免責・限界を含む。レポート本文の形式はSTEP 0と互換にする。

### 2.10 エラー / 安全設計

- 曖昧なティッカーは候補を提示し、断定的に実行しない。
- 外部データ障害はエージェント別に記録し、欠損を明記する。
- LLMの構造化出力はJSON Schemaで検証し、失敗時は1回だけ修復リトライ後、人間可読な失敗にする。
- プロンプト注入を依頼・ニュース本文から隔離し、ツール実行権限をCEOに与えない。
- 「買い」「売り」等を出す場合も、STEP 0の根拠と免責を添え、売買執行には接続しない。

### 2.11 テスト項目・完了条件・移行条件

| 区分               | 内容                                                                                               |
| ------------------ | -------------------------------------------------------------------------------------------------- |
| テスト             | 7203.T依頼の正規化、CEO→Manager委任、OK/NG分岐、既存直実行の回帰、データ障害、無効JSON、相関ID追跡 |
| 完了条件           | CEO経由でSTEP 0と同等の検証済みレポートが生成され、委任・結果・エラーを`run_id`で追跡できる        |
| STEP 2への移行条件 | CEOの要約が分析結果を改変せず、一定数の正常実行で依頼→委任→報告の監査ログ欠損がない                |

---

## 3. STEP 2：CEOによる分析方針決定

### 3.1 目的

CEOが単に「指定銘柄を回す」だけでなく、依頼目的・市場環境・既存結果をもとに、追加調査、比較対象、分析深度、優先順位を**提案・決定**できるようにする。ただし、方針決定と分析実行を分離し、STEP 0のPlannerへ安全に渡す。

### 3.2 追加機能

- `ResearchPolicy`（調査目的、対象、比較銘柄、必要観点、優先度、予算/時間上限）を生成・保存。
- CEOが「単独銘柄」「同業比較」「リスク深掘り」「再調査」の分析モードを選択。
- Planner Agentがポリシーを実行可能な`AnalysisPlan`へ分解。
- 根拠不足、対象拡大、コスト超過を検知し、実行前に人間承認へ回す。
- 実績をポリシー評価へフィードバックするが、自己学習による自動的なルール変更は行わない。

### 3.3 エージェント役割

| エージェント       | 役割                                                                         |
| ------------------ | ---------------------------------------------------------------------------- |
| CEO Agent          | 依頼と既存結果から`ResearchPolicy`を生成、優先順位付け、例外を承認待ちへ送る |
| Planner Agent      | ポリシーをSTEP 0の実行計画へ変換。ツール・対象・再調査回数を明示             |
| Risk Agent         | 方針の見落とし（集中、比較不足、時点不整合）を検査                           |
| Verification Agent | 方針どおりに分析・根拠提示がなされたかを検証                                 |
| Human Owner        | 対象銘柄の大幅追加、外部通知、予算超過を承認                                 |

### 3.4 ワークフロー

```text
依頼 / 既存レポート
  → CEO: ResearchPolicy案
  → Policy Guard（範囲・コスト・安全規則）
     ├─ 承認要 → Human Owner → 承認後にPlanner
     └─ 自動実行可 → Planner: AnalysisPlan
  → STEP 0分析部門
  → Risk / Verification
  → CEO: 方針達成度・次の候補を報告
```

### 3.5 State / データ設計

`CEOState`に`policy_ref`を追加し、ポリシー実体は独立保存する。

```json
{
  "strategy_id": "policy_...",
  "objective": "7203.Tの中期投資仮説を検証",
  "scope": {
    "primary_tickers": ["7203.T"],
    "peer_tickers": [],
    "sector": "automobile"
  },
  "research_questions": ["収益性の持続性", "為替・関税リスク"],
  "analysis_depth": "standard",
  "priority": "high",
  "limits": {
    "max_tickers": 3,
    "max_research_cycles": 2,
    "time_budget_minutes": 15
  },
  "rationale": ["ユーザー依頼", "既存レポートの未確定論点"],
  "approval_required": false,
  "version": 1
}
```

`AnalysisPlan`は既存Plannerの入力にアダプターで変換する。STEP 0が単一ティッカーのみ対応の場合、比較分析は複数の独立STEP 0 runとして実行し、最後に統合比較を行う。

### 3.6 API・外部ツール

- `POST /v1/ceo/policies:propose`：依頼から方針案を作成（実行しない）。
- `POST /v1/ceo/policies/{strategy_id}:approve`：人間承認を記録。
- `POST /v1/ceo/policies/{strategy_id}:execute`：承認済み/自動実行可能な方針を実行。
- `GET /v1/ceo/policies/{strategy_id}`：方針、根拠、実績、変更履歴を返す。

既存の外部データツールを増やす必要はない。比較銘柄・セクター分類が必要になった時だけ、銘柄マスタまたは信頼できる分類データを読み取り専用で追加する。

### 3.7 DB変更

| テーブル            | 主な列                                                                              | 用途         |
| ------------------- | ----------------------------------------------------------------------------------- | ------------ |
| `research_policies` | `strategy_id`, `run_id`, `policy_json`, `status`, `version`                         | 方針の版管理 |
| `policy_decisions`  | `decision_id`, `strategy_id`, `decision_type`, `rationale`, `actor`                 | 決定根拠     |
| `policy_approvals`  | `approval_id`, `strategy_id`, `requested_action`, `status`, `approved_by`           | 人間承認     |
| `policy_outcomes`   | `strategy_id`, `analysis_run_id`, `coverage`, `verification_status`, `outcome_json` | 方針の実績   |

### 3.8 推奨ディレクトリ構成

```text
src/
├── agents/
│   ├── ceo_agent.py
│   ├── policy_guard_agent.py        # 新規：規則ベース中心
│   └── planner_agent.py
├── contracts/
│   ├── research_policy.py           # 新規
│   └── analysis_plan.py             # 新規/既存拡張
├── services/
│   ├── policy_service.py            # 新規
│   └── planner_adapter.py           # 新規
└── repositories/
    └── policy_repository.py         # 新規
tests/
├── unit/test_policy_guard.py
└── integration/test_policy_to_step0.py
```

### 3.9 入出力

入力はSTEP 1の構造化依頼、既存レポート、所有者が設定した運用制約。出力は、実行計画そのものではなく、根拠・対象範囲・上限・承認要否を含む`ResearchPolicy`と、実行後の「方針達成度」である。

### 3.10 エラー / 安全設計

- CEO生成の比較銘柄・投資テーマは事実として扱わず、銘柄マスタで検証する。
- 対象数、実行時間、再調査回数に上限を設け、無限再調査を防ぐ。
- ポリシー変更は追記型のバージョン管理とし、実行済み方針を上書きしない。
- 同一依頼の自動重複実行は冪等キーで抑止する。
- 重要なイベントを理由とする追加分析は、イベントの出典・時刻・信頼度を必須とする。

### 3.11 テスト項目・完了条件・移行条件

| 区分               | 内容                                                                                                      |
| ------------------ | --------------------------------------------------------------------------------------------------------- |
| テスト             | 方針のスキーマ検証、単一銘柄方針のSTEP 0互換、比較対象上限、承認分岐、方針版管理、Verification NGの再計画 |
| 完了条件           | CEOが根拠付き方針を作り、Plannerが上限内の実行計画へ変換し、方針と成果を追跡できる                        |
| STEP 3への移行条件 | 手動依頼の方針実行が安定し、不要な対象拡張・無限再試行が発生せず、承認規則が機能している                  |

---

## 4. STEP 3：自律市場監視

### 4.1 目的

定期的な市場データ・ニュース・開示の観測から重要イベントを検出し、CEOに「分析すべき候補」を提示する。最初は自動分析ではなく、**検知→評価→承認/限定実行**の順に導入する。

### 4.2 追加機能

- 監視ジョブ（取引時間、開示時刻、日次バッチ）を実装。
- 価格変動、出来高、決算・適時開示、ニュースをイベントとして正規化。
- 重複除去、信頼度評価、対象銘柄との関連付け、重要度スコアリング。
- CEOが監視キューから`ResearchPolicy`案を起票。
- 通知と自動実行はポリシー別の閾値とクールダウンに従う。

### 4.3 エージェント役割

| エージェント/サービス     | 役割                                                   |
| ------------------------- | ------------------------------------------------------ |
| Market Monitor            | 価格・出来高・指数・為替等を定期取得しイベント化       |
| Disclosure / News Monitor | 開示・ニュースを取得、出典と時刻を保存                 |
| Event Triage Agent        | 重要度、重複、関連銘柄、信頼度を判定。売買判断はしない |
| CEO Agent                 | 監視候補を方針に変換、優先度を決定                     |
| Planner / STEP 0          | 承認済みの深掘り分析を実行                             |
| Human Owner               | 通知先、監視対象、完全自動分析の範囲を設定・承認       |

### 4.4 ワークフロー

```text
Scheduler
  → Monitor（価格 / 開示 / ニュース）
  → Event Store
  → Event Triage（重複除去・信頼度・重要度）
  → CEO Watch Queue
     ├─ 低重要度：記録のみ
     ├─ 中重要度：方針案・ダイジェスト
     └─ 高重要度：承認待ち、または許可済みの限定自動分析
  → STEP 2 Policy → STEP 0 analysis → 検証済み報告
```

### 4.5 State / データ設計

イベントは不変イベントログとして保持する。

```json
{
  "event_id": "evt_...",
  "event_type": "price_move|filing|news|macro",
  "occurred_at": "2026-08-19T...Z",
  "observed_at": "2026-08-19T...Z",
  "source": { "name": "...", "url": "...", "license": "..." },
  "ticker": "7203.T",
  "facts": { "price_change_pct": 5.2 },
  "confidence": 0.92,
  "importance": 0.74,
  "dedupe_key": "...",
  "triage_status": "QUEUED",
  "trace_id": "trace_..."
}
```

重要度は規則とモデル評価を組み合わせ、モデル単独で発火させない。例：価格急変、出来高倍率、公式開示の有無、監視方針との適合、同一情報源の重複を評価する。

### 4.6 API・外部ツール

- `POST /v1/monitoring/rules`：対象、時刻、閾値、通知、承認要否を設定。
- `GET /v1/monitoring/events`：監視イベントを検索。
- `POST /v1/monitoring/events/{event_id}:triage`：再評価または手動判定。
- `POST /v1/monitoring/events/{event_id}:create-policy`：STEP 2方針案を起票。
- 外部ツールはレート制限、キャッシュ、利用規約、出典URLの保存を必須とする。監視は読み取り専用である。

### 4.7 DB変更

| テーブル           | 主な列                                                                        | 用途         |
| ------------------ | ----------------------------------------------------------------------------- | ------------ |
| `monitoring_rules` | `rule_id`, `scope`, `schedule`, `thresholds`, `auto_action`                   | 監視設定     |
| `market_events`    | `event_id`, `event_type`, `source`, `occurred_at`, `facts_json`, `dedupe_key` | 原本イベント |
| `event_triage`     | `event_id`, `importance`, `confidence`, `reasoning_ref`, `status`             | 評価結果     |
| `watch_queue`      | `queue_id`, `event_id`, `strategy_id`, `priority`, `status`, `cooldown_until` | CEO処理待ち  |
| `notifications`    | `notification_id`, `event_id`, `channel`, `status`, `approval_id`             | 通知監査     |

### 4.8 推奨ディレクトリ構成

```text
src/
├── monitoring/
│   ├── scheduler.py
│   ├── market_monitor.py
│   ├── disclosure_monitor.py
│   ├── news_monitor.py
│   ├── event_normalizer.py
│   └── deduplicator.py
├── agents/
│   └── event_triage_agent.py
├── services/
│   ├── watch_queue_service.py
│   └── notification_service.py
└── api/
    └── monitoring_routes.py
tests/
├── unit/test_event_normalizer.py
├── unit/test_deduplicator.py
└── integration/test_monitor_to_policy.py
```

### 4.9 入出力

入力は監視ルールと外部データの観測値。出力は、出典・時刻・事実値・信頼度・重要度・推奨アクションを含むイベントである。ユーザー通知は「事実」「AIの仮説」「未確認事項」を分離して記載する。

### 4.10 エラー / 安全設計

- データ遅延・市場休場・取得失敗をイベントとして誤発火しない。
- 1銘柄・1イベント種別あたりの通知頻度を制限し、クールダウンを設ける。
- ニュースは公開時刻と取得時刻を分け、未来情報混入を防ぐ。
- 高重要度でも外部公開や売買はしない。まず所有者通知または承認待ちとする。
- スケジューラの重複起動、リトライ、部分失敗に対して冪等な`dedupe_key`を用いる。

### 4.11 テスト項目・完了条件・移行条件

| 区分               | 内容                                                                                                       |
| ------------------ | ---------------------------------------------------------------------------------------------------------- |
| テスト             | 休場日、遅延データ、重複ニュース、急変イベント、同時ジョブ、レート制限、通知抑制、承認付き自動分析         |
| 完了条件           | 指定ルールでイベントを安定して収集・重複除去・記録し、CEOが監査可能な方針案として扱える                    |
| STEP 4への移行条件 | 誤検知率・重複通知率・未処理キュー滞留を運用指標で管理でき、監視から分析への自動起票が上限内で安定している |

---

## 5. STEP 4：投資リサーチ戦略AI

### 5.1 目的

市場全体、セクター、投資テーマ、既存リサーチのカバレッジを横断し、CEOを補佐するStrategy Agentを追加する。注目テーマ、調査配分、スクリーニング条件、検証優先度を決めるが、投資推奨や自動取引は行わない。

### 5.2 追加機能

- リサーチユニバース（対象市場・セクター・銘柄）の管理。
- テーマ仮説と調査質問を生成し、根拠・反証条件・有効期限を付与。
- スクリーニングとランキング候補の作成。
- カバレッジ、鮮度、イベント重要度、方針優先度をもとに調査ポートフォリオを配分。
- 実施済み分析の結果を集約し、次の方針案をCEOへ提出。

### 5.3 エージェント役割

| エージェント        | 役割                                                       |
| ------------------- | ---------------------------------------------------------- |
| Strategy Agent      | 調査テーマ、仮説、スクリーニング、カバレッジ優先順位を提案 |
| CEO Agent           | 事業・ユーザー目的と整合する戦略を採択し、上限を設定       |
| Screener Service    | 数値条件により候補を絞る。決定論的な処理を優先             |
| Planner Agent       | 採択されたテーマを銘柄単位のSTEP 0実行計画に変換           |
| Risk / Verification | テーマの一面的解釈、データ鮮度、比較可能性、根拠を検証     |
| Human Owner         | 新市場追加、公開テーマ、評価基準の変更を承認               |

### 5.4 ワークフロー

```text
STEP 3イベント + 市場スナップショット + 過去の検証済みレポート
  → Strategy Agent: Theme / Coverage / Screening proposal
  → Strategy Guard（ユニバース・鮮度・上限・承認）
  → CEO: 採択または修正
  → Screener Service
  → Planner: 銘柄別ResearchPolicy
  → STEP 0分析部門
  → Risk / Verification
  → Research Portfolio Report → CEO / Human Owner
```

### 5.5 State / データ設計

```json
{
  "strategy_id": "rs_...",
  "as_of": "2026-08-19",
  "universe_id": "jp_equities_core",
  "theme": {
    "name": "...",
    "hypothesis": "...",
    "counter_hypothesis": "...",
    "expiry": "2026-09-30"
  },
  "screen": {
    "rules": [{ "field": "dividend_yield", "op": ">=", "value": 0.04 }]
  },
  "coverage_plan": [
    { "ticker": "7203.T", "reason": "event+coverage_gap", "priority": 90 }
  ],
  "limits": {
    "max_candidates": 50,
    "max_deep_dives": 5,
    "daily_run_budget": 10
  },
  "evidence_refs": ["event:...", "report:..."],
  "status": "PROPOSED"
}
```

テーマ仮説には必ず反証仮説、観測指標、失効日を持たせる。ランキングは分析候補の優先順位であり、投資成績の予測値として扱わない。

### 5.6 API・外部ツール

- `POST /v1/research-strategies:propose`：テーマ・カバレッジ案を作成。
- `POST /v1/research-strategies/{strategy_id}:approve`：CEO/所有者の採択を記録。
- `POST /v1/screeners:run`：明示した条件で候補一覧を返す。
- `GET /v1/research-portfolio`：テーマ、対象、鮮度、検証状態を返す。
- 銘柄分類・財務指標・価格履歴等のデータソースは、取得日、ライセンス、スナップショットIDを保存する。

### 5.7 DB変更

| テーブル                     | 主な列                                                             | 用途                 |
| ---------------------------- | ------------------------------------------------------------------ | -------------------- |
| `research_universes`         | `universe_id`, `definition_json`, `version`                        | 分析対象母集団       |
| `research_themes`            | `theme_id`, `hypothesis`, `counter_hypothesis`, `expiry`, `status` | テーマの版管理       |
| `screen_runs`                | `screen_run_id`, `rules_json`, `snapshot_id`, `result_ref`         | スクリーニング再現性 |
| `coverage_plan_items`        | `strategy_id`, `ticker`, `priority`, `reason`, `status`            | 調査配分             |
| `research_portfolio_metrics` | `as_of`, `coverage_freshness`, `verification_rate`, `queue_depth`  | 運用評価             |

### 5.8 推奨ディレクトリ構成

```text
src/
├── agents/
│   ├── strategy_agent.py
│   └── strategy_guard_agent.py
├── research/
│   ├── universe_service.py
│   ├── screener_service.py
│   ├── coverage_planner.py
│   └── theme_repository.py
├── contracts/
│   └── research_strategy.py
└── api/
    └── research_routes.py
tests/
├── unit/test_screener_service.py
├── unit/test_strategy_guard.py
└── integration/test_strategy_to_analysis.py
```

### 5.9 入出力

入力は市場イベント、データスナップショット、検証済みレポート、運用制約。出力はテーマ仮説、反証条件、候補銘柄、優先順位、根拠参照、実行上限である。最終ユーザー向けには、候補が「リサーチ優先候補」であることを明示する。

### 5.10 エラー / 安全設計

- 生存者バイアス、先読みバイアスを避けるため、ユニバースとデータ時点を固定して保存する。
- スクリーニング条件・重み・データ欠損処理は宣言的に記録し、ブラックボックス順位だけを残さない。
- テーマに関するニュースのセンチメントは根拠URLと引用範囲を保持し、事実と推論を分離する。
- パフォーマンス評価を行う場合は、仮想ポートフォリオ、手数料、リバランス、時点制約を明示し、誤認を防ぐ。
- 監視対象の急拡大や高コストデータ取得は所有者承認と日次上限を必要とする。

### 5.11 テスト項目・完了条件・移行条件

| 区分               | 内容                                                                                                         |
| ------------------ | ------------------------------------------------------------------------------------------------------------ |
| テスト             | 時点固定スクリーニング、欠損値、テーマ反証条件、上限超過、Strategy→Planner変換、カバレッジ優先順、STEP 0回帰 |
| 完了条件           | Strategy Agentが再現可能な候補・根拠・上限を出し、採択した戦略から個別分析まで追跡できる                     |
| STEP 5への移行条件 | リサーチの鮮度、検証率、候補から詳細分析への変換率を可視化でき、公開前のレビュー運用が定着している           |

---

## 6. STEP 5：AI企業化（分析・顧客・マーケ部門）

### 6.1 目的

CEO配下に「分析部門」「顧客部門」「マーケティング部門」を明確に分け、リサーチ成果を安全に顧客価値・事業運営へつなぐ。部門間のデータ、権限、公開承認を分離し、STEP 0〜4の研究機能を壊さない。

### 6.2 組織構成

```text
Human Owner（最終意思決定・公開/支出/契約承認）
  └─ CEO Agent（優先順位・部門横断の統括・監査）
      ├─ 分析部門：Manager / Planner / Market / Financial / News / Analysis / Risk / Verification / Strategy
      ├─ 顧客部門：Customer Agent / Support Knowledge Service
      └─ マーケ部門：Marketing Agent / Content Review Service
```

### 6.3 追加機能

- 分析部門から、公開可能な「検証済みリサーチ成果」を`ResearchAsset`として発行する。
- Customer Agentが問い合わせを分類し、認可・顧客コンテキスト・FAQを用いて回答下書きを作成する。
- Marketing Agentが承認済み`ResearchAsset`のみを用い、記事、メール、SNS文案等を作る。
- CEOが部門KPI（分析の検証率、問い合わせ解決率、公開承認待ち、コンテンツ品質）を集約する。
- CRM/配信/SNS等への書込みは承認キューを経由し、最初は下書き生成までに限定する。

### 6.4 エージェント役割

| 部門・エージェント | 役割                                                       | 禁止/承認事項                              |
| ------------------ | ---------------------------------------------------------- | ------------------------------------------ |
| 分析部門           | STEP 0〜4の収集、分析、検証、リサーチ資産化                | 未検証結果の公開禁止                       |
| Customer Agent     | 問い合わせ分類、既存資料検索、回答下書き、エスカレーション | 個別投資助言、口座情報要求、契約変更は禁止 |
| Marketing Agent    | 承認済み資産からコンテンツ下書きを生成                     | 公開・投稿・広告出稿は人間承認             |
| CEO Agent          | 部門間優先順位、KPI、障害時停止                            | 公開承認者を兼務しない設計を推奨           |
| Human Owner        | 公開、支出、契約、重要顧客対応、制度対応                   | 最終責任を負う                             |

### 6.5 ワークフロー

#### A. 分析成果の公開可能化

```text
STEP 0〜4の分析 → Verification OK
  → ResearchAsset Builder（根拠・時点・免責を付与）
  → Content Review Queue
  → Human Owner承認
  → 顧客部門の回答根拠 / マーケ部門の素材として利用
```

#### B. 顧客対応

```text
Customer inquiry → Customer Agent（分類・認可・安全判定）
  ├─ FAQ / 公開済みResearchAsset → 回答下書き → 必要に応じ承認 → 返信
  ├─ 新規リサーチ要望 → CEO → STEP 1/2の依頼として起票
  └─ 投資助言 / 苦情 / 個人情報 / 契約 → Human Ownerへエスカレーション
```

#### C. マーケティング

```text
公開済みResearchAsset + ブランドガイド
  → Marketing Agent：文案下書き
  → Compliance / Brand Review
  → Human Owner承認
  → 外部チャネルへ投稿（将来段階。初期は下書き保存のみ）
```

### 6.6 State / データ設計

部門をまたぐ成果物は、必ず公開状態を持つ`ResearchAsset`として扱う。

```json
{
  "asset_id": "asset_...",
  "source_analysis_run_ids": ["analysis_..."],
  "title": "...",
  "as_of": "2026-08-19T...Z",
  "verification_status": "OK",
  "evidence_refs": ["report:...", "event:..."],
  "audience": "internal|customer|public",
  "publication_status": "DRAFT|APPROVED|PUBLISHED|REVOKED",
  "disclaimer_version": "v1",
  "owner": "research_department"
}
```

顧客コンテキストは最小限とし、分析データとは論理・物理の両面で分離する。顧客識別子をプロンプトに渡す際は目的に必要な属性だけをマスキングして渡す。

### 6.7 API・外部ツール

- `POST /v1/research-assets`、`POST /v1/research-assets/{id}:approve`：成果物と公開承認。
- `POST /v1/customer/inquiries`、`GET /v1/customer/inquiries/{id}`：問い合わせ受付・追跡。
- `POST /v1/marketing/drafts`：承認済み素材から下書き作成。
- `POST /v1/approvals/{id}:approve|reject`：公開・送信・投稿などの共通承認。
- CRM、メール、SNS、Web CMS等の外部ツール連携は、初期は**読み取りまたは下書き作成のみ**。送信・投稿・顧客データ更新には細粒度のOAuth権限、操作ログ、人間承認を必要とする。

### 6.8 DB変更

| テーブル                   | 主な列                                                                             | 用途               |
| -------------------------- | ---------------------------------------------------------------------------------- | ------------------ |
| `research_assets`          | `asset_id`, `source_refs`, `audience`, `publication_status`, `disclaimer_version`  | 公開可能な分析成果 |
| `customer_inquiries`       | `inquiry_id`, `customer_ref`, `category`, `risk_level`, `status`                   | 問い合わせ管理     |
| `customer_response_drafts` | `draft_id`, `inquiry_id`, `asset_refs`, `approval_status`, `content_ref`           | 回答下書き         |
| `marketing_drafts`         | `draft_id`, `asset_refs`, `channel`, `review_status`, `content_ref`                | マーケ文案         |
| `approval_requests`        | `approval_id`, `action_type`, `resource_ref`, `requested_by`, `status`, `reviewer` | 共通承認           |
| `department_metrics`       | `as_of`, `department`, `metric_name`, `metric_value`                               | CEO用KPI           |

顧客の個人情報、認証情報、問い合わせ本文は暗号化・アクセス制御の対象とし、分析用DBのロールから直接参照させない。

### 6.9 推奨ディレクトリ構成

```text
src/
├── departments/
│   ├── research/
│   │   └── research_asset_service.py
│   ├── customer/
│   │   ├── customer_agent.py
│   │   ├── inquiry_router.py
│   │   └── knowledge_service.py
│   └── marketing/
│       ├── marketing_agent.py
│       ├── content_service.py
│       └── brand_guard.py
├── governance/
│   ├── approval_service.py
│   ├── access_policy.py
│   └── audit_log.py
├── contracts/
│   ├── research_asset.py
│   ├── customer_inquiry.py
│   └── marketing_draft.py
└── api/
    ├── customer_routes.py
    ├── marketing_routes.py
    └── approval_routes.py
tests/
├── integration/test_research_asset_to_customer.py
├── integration/test_asset_to_marketing_draft.py
└── security/test_authorization_boundaries.py
```

### 6.10 入出力

| 入力                  | 出力                          | 必須の制約                                 |
| --------------------- | ----------------------------- | ------------------------------------------ |
| 検証済み分析結果      | `ResearchAsset`               | 根拠、時点、免責、公開状態を含む           |
| 顧客問い合わせ        | 回答下書き / エスカレーション | 個別投資助言を避け、認可済み資料のみを利用 |
| 承認済みResearchAsset | マーケ文案                    | 事実・意見・将来見通しを分離、投稿は未実行 |
| 部門ログ/KPI          | CEO運営ダッシュボード         | 個人情報・秘匿情報を集計から除外           |

### 6.11 エラー / 安全設計

- 承認されていない分析、検証NG、失効した資産は顧客・マーケ部門へ公開しない。
- 顧客問い合わせに含まれる個人情報、口座情報、取引指示は検出して保存範囲を最小化し、人間へ即時エスカレーションする。
- Marketing Agentは出典のない数値、収益保証、過度な断定、誤認を招く表現を生成・公開しない。Guardで検査する。
- 外部送信は冪等キー、送信先確認、承認者、監査ログ、取り消し可能な下書きを必須とする。
- プロンプト、モデル、ツールのアクセス権を部門ごとに分離し、顧客データが分析用のモデル入力へ不要に流れないようにする。
- 法令・登録・利用規約・データライセンスの確認が必要な事業行為は、実装前に専門家と人間所有者の承認を要する。

### 6.12 テスト項目・完了条件

| 区分         | 内容                                                                                                                                                         |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| テスト       | 未承認資産の遮断、顧客問い合わせの分類・エスカレーション、PIIマスキング、下書き→承認→送信の権限、コンテンツ根拠追跡、部門間データ越境、外部API失敗・重複送信 |
| 完了条件     | 分析・顧客・マーケの各部門が、承認済み成果物と最小権限で連携し、公開/送信を人間承認下で安全に運用できる                                                      |
| 運用移行条件 | KPI、監査ログ、承認待ち、エスカレーションが可視化され、障害時に部門単位で停止しても分析部門のSTEP 0〜4が継続または安全停止できる                             |

---

## 7. 共通の実装・検証順序

各STEPは以下の順で進める。

1. 契約（State、API、DBマイグレーション、権限）を先に固定する。
2. 新規機能をFeature Flagで無効のまま導入し、STEP 0の回帰テストを通す。
3. テスト用データ・スタブで単体/結合テストを行う。
4. 本番と分離した環境で読み取り専用または下書きモードの試験運用を行う。
5. ログ、コスト、失敗、検証NG、承認待ちを評価する。
6. 完了条件を満たした場合のみ次STEPを有効化する。満たさない場合は当該STEPのみ無効化し、STEP 0の直接実行を維持する。

### 7.1 共通の受入基準

- STEP 0の`Manager → ... → Verification → Report`が各STEP後も同じ入力で実行できる。
- すべての新規実行で`request_id`、`run_id`、`trace_id`が検索できる。
- LLM生成物はスキーマ検証され、外部への書込み・送信・公開は承認経路なしに行われない。
- データソース、取得時点、検証状態、免責をレポート・資産・下書きへ伝播できる。
- 障害時に部分結果を成功扱いせず、欠損と再実行可否を明示する。

## 8. 最終到達像

STEP 5完了時、システムは「株価を1銘柄ずつ分析するAI」から、CEOが分析方針と優先順位を統括し、分析部門が検証済みリサーチを作成し、顧客部門とマーケ部門が承認済みの範囲でそれを活用するAI組織へ発展する。

ただし、人間所有者は常に、方向性、公開、支出、契約、法令対応、重要な顧客対応、最終的な投資判断を担う。各STEPの独立性とSTEP 0互換性を維持することが、この成長を安全かつ検証可能にする前提である。
