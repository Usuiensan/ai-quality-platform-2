# AI品質管理プラットフォーム

複数の GitHub リポジトリに対して、共通の品質ゲートを適用するための中央基盤です。

このリポジトリの Phase 1 では、次を最小構成で提供します。

- 中央ロジックの土台
- `.ai-quality.yml` の簡易読み込み
- ルールベースのレビュー判定
- JSON スキーマ検証
- 固定の PR レポート生成
- 仕様・テスト・ドキュメント・最終監査の独立レビュー
- GitHub Actions の reusable workflow
- 標準ライブラリだけで回るテスト

## アーキテクチャ

### 方針

- 人間向けの説明は日本語、機械向けの識別子は英語で固定します。
- 最初の段階では外部 AI API に依存しません。
- レビューは将来の AI 呼び出しに差し替え可能な構造にしています。

### 構成

- `src/ai_quality_platform/`
  - 設定読み込み
  - diff の抽出
  - ルールベースレビュー
  - レポート生成
  - 独立レビュー種別の実行
- `schemas/`
  - review result と config の JSON Schema
- `prompts/`
  - 将来の AI プロンプトの雛形
- `.github/workflows/`
  - reusable workflow の雛形
- `tests/`
  - 失敗系を含む最小検証

## 実行方法

### テスト

```powershell
python -m unittest discover -s tests -p "test_*.py"
```

### レポート生成の考え方

Phase 1 では GitHub Actions 上で、差分から危険な変更を検出し、固定の日本語レポートを作ります。
将来はここに AI レビュアーを差し込んでいきます。

## 既知の制約

- 本版は AI API 連携をまだ持ちません。
- YAML は最小対応の簡易ローダーです。
- PR コメント更新や Ruleset 自動設定は Phase 4 以降です。
- JSON Schema は最小検証です。

## セキュリティ上の注意

- Secrets はまだ扱いません。
- 未信頼コードを高権限で実行する設計は避けています。
- 自動修正は未実装です。

## Phase 2 以降

- Requirements / Test / Documentation レビュアー追加
- Final Auditor の強化
- Ruleset 用 Check 名の固定
- 自動修正ループ
