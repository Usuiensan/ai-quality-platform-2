# 🚀 AI品質管理プラットフォーム (AI Quality Platform)

複数の GitHub リポジトリに対して、共通の「AIコードレビュー」と「バグ自動修正（Autofix）」を適用するための中央品質管理基盤です。

「プログラムの詳しい仕組みはわからないけれど、とりあえず手元で動かしてみたい！」というバイブコーディング（プロンプト主導・AI対話型開発）の方に向けて、**PowerShellをコピペするだけで5分で動かせる**手順を用意しました。

---

## 🛠️ 5分で動かす超速クイックスタート

Windows の **PowerShell** を開いて、以下のコマンドを順番にコピペして実行してください。

### ステップ 1: プログラムをダウンロードしてフォルダーに移動する
PowerShellで、プログラムをダウンロードして、そのフォルダーに移動します。

```powershell
# ドキュメントフォルダーに移動
cd "$home\Documents"

# ダウンロードを実行（URLは環境に合わせて変更してください）
git clone https://github.com/Usuiensan/ai-quality-platform-2.git

# ダウンロードしたフォルダーに移動
cd ai-quality-platform-2
```
> [!NOTE]
> もし `git` コマンドが動かない、または GitHub CLI (`gh`) などが未設定の場合は、GitHub ページから **「Download ZIP」** でZIPファイルをダウンロードし、解凍したフォルダーをPowerShellで開いて `cd`（移動）してください。

### ステップ 2: 必要なライブラリをインストールする（初回のみ）
Pythonがインストールされている環境で、以下のコマンドを実行します。
```powershell
pip install pyyaml tiktoken num2words
```

### ステップ 3: Gemini / OpenAI のAPIキーを設定する
AIモデルを呼び出すためのAPIキーを設定します。一時的な環境変数としてPowerShellに登録します。
```powershell
# Gemini APIを使う場合 (推奨・最新世代の高速ルーティングに対応)
$env:AI_API_KEY="AI_STUDIOで取得したAPIキー"

# OpenAI APIを使う場合
$env:AI_API_KEY="OpenAIで取得したAPIキー"
```

### ステップ 4: 実際にチェックを実行してみる！
付属のダミー差分ファイル（`diff.txt`）を使って、最新のAI（Gemini 2.5など）をフル活用する「お急ぎモード」で実行します。
```powershell
python -m ai_quality_platform.cli --diff diff.txt --urgent --autofix-root .
```

---

## 💡 動かした時の画面の流れ (これだけ知っておけばOK!)

### 1. 初回の見積もりの承認
実行すると、AIが「もしエラーなしで一発成功した場合にいくらかかるか（ハッピーパス）」を計算し、1.2倍の安全マージンと切り上げ処理（1001円→1010円など）を行った最大想定コストを日本円で提示します。

- **1円未満の場合**: `コストが1円未満のため自動承認されました` と表示され、そのまま進行します。
- **100円以下の数字が出た場合**:
  ```text
  初回見積もりコストを承認しますか？ 見積もりコスト: 10.00 JPY。進行するには 'ok' と入力してください:
  ```
  → キーボードで `ok` と打ってEnterを押すと進みます。
- **100円を超える高額な数字が出た場合（安全ロック）**:
  誤課金を防ぐために、スペルアウトされた英語入力を求められます。
  ```text
  【高額警告】見積もりコストは JPY 130.00 です。
  承認するには、正確に 'One hundred thirty yen' と入力してください:
  ```
  → **`One hundred thirty yen`** と正確にタイピング（コピペも可）してEnterを押すと進みます。
  
  ⚠️ **もし `expensive`（高い）や `nope`（嫌だ）などの拒否ワードを打つと、即座に実行をキャンセルします。**
  ✍️ タイポした場合は `本当に拒否しますか？それとも再入力しますか？ [retry/abort]` と聞かれるので、`retry`（または `r`）と打てばやり直せます。

### 2. 反復修正やエラー時の「追加見積もり」
AIが自動修正（Autofix）を試みて失敗した場合や、フォーマットエラーでより強力なモデル（`gemini-2.5-pro` など）へ切り替える必要が出た場合、**その場で追加のコストを計算して再承認を求めます**。
```text
[追加見積もり] Fallback Model Retry
追加コスト: +JPY 120.00 (合計: JPY 130.00)
【高額警告】見積もりコストは JPY 120.00 です。
承認するには、正確に 'One hundred twenty yen' と入力してください:
```
バックグラウンドで知らない間に高額な請求が発生する心配はありません！

---

## ⚙️ AIエディタ（Cursor/Windsurfなど）で簡単にカスタマイズする

バイブコーディングの際、AIエディタに以下を指示して編集させると便利です。

- **AIの価格設定を変更したいとき**:
  [models_pricing.json](src/ai_quality_platform/models_pricing.json) を開き、各モデルの `input`（入力100万トークンあたり）と `output`（出力100万トークンあたり）の価格（ドル）を書き換えます。
- **拒否ワードを追加・変更したいとき**:
  [rejection_words.json](src/ai_quality_platform/rejection_words.json) に拒否させたい単語を追加します。半角英語なら単語完全一致、日本語などの全角文字なら部分一致で自動検知されます。
- **自動修正用の指示（プロンプト）を書き換えたいとき**:
  [prompts/autofix.md](prompts/autofix.md) を直接書き換えて、AIに指示したい修正のトーンや注意点を調整します。

---

## 🧪 テストの実行方法

プログラムが正しく動いているかを検証する自動テストを実行します。
```powershell
python -m unittest discover -s tests -p "test_*.py"
```
