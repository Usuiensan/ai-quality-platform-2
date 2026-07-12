# AI Quality Platform 展開・運用ガイド (Deployment Guide)

このドキュメントは、組織内の他のプロジェクト・リポジトリへ「AI Quality Platform（自律型AIコードレビュー＆自動修正システム）」を**横展開（ロールアウト）**するためのシステム運用ガイドです。

---

## 1. プラットフォームの概要と特徴

本プラットフォームは、GitHubのプルリクエスト（PR）に対して、AIが自動でコードレビューを行い、発見された脆弱性やバグを**自律的に自動修正（Autofix）**し、最終的な監査レポートをPRへ投稿するシステムです。

### 動作モード
本システムは用途に合わせて2つの実行モードをシームレスに切り替えて運用できます。

1. **通常モード (Local LLM)**
   - **用途**: 通常の開発フロー、非公開プロジェクト、コストゼロでの無限ループテスト
   - **構成**: Ollamaを用いた完全ローカルLLM環境（`qwen3:8b` で高速推論、失敗時は `qwen3:14b` へフォールバック、レポート生成は `gemma3:12b`）。
   - **コスト**: 無料

2. **お急ぎ・高性能モード (Cloud API)**
   - **用途**: 本番リリース前の厳密な監査、数千行を超える巨大なDiffの処理、ローカルリソース不足時
   - **構成**: `--urgent` フラグを付与することで起動。対象Diffのトークン量を自動計算し、Gemini 1.5 Flash/Pro（または OpenAI）へ動的にルーティングします。
   - **コスト**: 事前にAPI単価（`models_pricing.json`）と為替レート（APIによる動的取得）から日本円で見積もりを算出し、3段階の安全ロック（1円未満自動、100円未満OK、100円超スペルアウト承認）を経て課金されます。

---

## 2. 展開方法 (Horizontal Deployment)

新規リポジトリへAI Quality Platformを導入する手順です。専用のPowerShellモジュール（`AiQuality.psd1`）を利用することで、数秒で初期化が完了します。

### ステップ 1: プラットフォームモジュールのインポート
プラットフォームのルートディレクトリにて、PowerShellからモジュールをロードします。

```powershell
Import-Module ./powershell/AiQuality/AiQuality.psd1 -Force
```

### ステップ 2: 新規リポジトリの初期化
導入対象のリポジトリディレクトリに移動し、`New-AiManagedRepo` コマンドレットを実行します。

```powershell
cd path/to/target-repository
New-AiManagedRepo -TemplatePath "path/to/ai-quality-platform/templates/repository-template" -Force
```

このコマンドにより以下の処理が自動化されます：
1. プラットフォーム設定ファイル (`.ai-quality.yml`) の配置
2. GitHub Actions ワークフローの配置 (`.github/workflows/ai-quality.yml`)
3. `pull_request_template.md` などの標準化

### ステップ 3: 環境変数の設定 (CI/CD)
クラウドAPIモード（`--urgent`）を使用する場合、およびPRへの自動コメント投稿を行うために、対象リポジトリの GitHub Secrets に以下の変数を登録してください。

- `AI_API_KEY`: Gemini API または OpenAI API のキー
- `GITHUB_TOKEN`: PRコメント投稿・コミットプッシュ用のトークン（通常はActions内蔵のものを利用）

---

## 3. アーキテクチャとパイプライン

プラットフォームは以下の4つの自律エージェントプロセスで構成されています。

1. **Unified Review (統合レビュー)**
   - `diff` をパースし、コード、セキュリティ、テスト、ドキュメントの4観点から問題を抽出します。（言語：英語）
2. **Autofix (自動修正)**
   - 指摘された問題を元にパッチ（search & replace ブロック）を生成しソースコードに適用します。（言語：英語）
   - パースエラーや推論タイムアウトが発生した場合は、自動でより強力なモデルにフォールバック（昇格）します。
3. **Final Audit (最終監査)**
   - 全てのレビュー結果と修正履歴を監査し、マージの可否（PASS / WARN / BLOCK）を判定します。（言語：英語）
4. **Report Generation (レポート生成)**
   - 上記のJSONデータを人間が読みやすい日本語のMarkdownへ整形します。（言語：日本語）

### カスタマイズ
対象リポジトリの `.ai-quality.yml` を編集することで、プロジェクト固有のルールや予算上限 (`auto_approve_threshold`) を設定できます。最新のモデル価格はプラットフォーム側の `models_pricing.json` を更新するだけで全リポジトリに反映されます。
