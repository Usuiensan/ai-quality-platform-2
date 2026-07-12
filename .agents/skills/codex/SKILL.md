---
name: codex
description: AI Quality Platform を使用したコードレビューと品質ゲートの実行、およびバグ自動修正のガイド
---

# AI Quality Platform コードレビュー＆自動修正スキル

このスキルは、本リポジトリ（AI Quality Platform）におけるコード品質チェック、コードレビュー、および自動修正（Autofix）の実行手順を定めたガイドです。ユーザーからコードのレビューや品質チェックを求められた場合、このスキルに沿って実行します。

## 1. 実行モードとコマンド

本プラットフォームのCLIツールを利用して、以下のコマンドを実行します。

### 通常のコードレビュー（差分の検証）
手元のGit差分または差分ファイルを指定して、AI（またはローカルヒューリスティックルール）による品質チェックレポートを出力します。

```powershell
# 差分ファイル（diff.txt）を指定してレビューを実行する
python -m ai_quality_platform.cli --diff diff.txt

# GitHub PRコメント用にフォーマットして出力する
python -m ai_quality_platform.cli --diff diff.txt --github-pr
```

### ローカルでのバグ自動修正（Autofix）の適用
差分に対してAI（またはローカルモック）を適用し、コードを自動修正します。

```powershell
python -m ai_quality_platform.cli --diff diff.txt --autofix-root .
```
* ※ 自動修正が適用された後は、自動コミット・プッシュは行われません。手元の差分を確認し、手動でコミット・プッシュしてください。

### 自動テストの実行
修正後やプラットフォームの機能追加後は、必ず以下のコマンドで自動テスト（Discover）を実行し、問題がないかを確認します。

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

## 2. APIキーとLLMプロバイダの設定

自動レビューには、ローカルLLM（Ollama等）またはクラウドAPI（Gemini/OpenAI）を設定可能です。

- **ローカルLLMの場合**:
  `.ai-quality.yml` の `ai` セクションで `provider: ollama` または `provider: openai-compatible` に設定し、`base_url` をローカルエンドポイントに指定します。この場合、APIキーの設定は不要（空のままでOK）です。
- **クラウドAPIの場合**:
  環境変数 `AI_API_KEY`（または `GEMINI_API_KEY` / `OPENAI_API_KEY`）を設定して実行します。

## 3. レポートの総合判定
レポートは最終監査エージェントによって、以下の3段階の判定結果を出力します。
- **PASS**: 品質ゲートを通過。マージ可能です。
- **WARN**: 軽微な警告あり。確認した上でマージ可能です。
- **BLOCK**: 重大な不備・セキュリティリスクあり。修正が必須です。
