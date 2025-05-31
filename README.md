# Anki OCR

タイ語の語学学習用のAnkiデッキを自動生成するツールです。画像からタイ語の単語とその意味を抽出し、Ankiデッキを作成します。

## 機能

- 画像からタイ語の単語とその意味を自動抽出
- Paiboon式ローマ字の自動生成
- 音声ファイルの自動生成（オプション）
- Ankiデッキの自動生成

## インストール

1. リポジトリをクローン:
```bash
git clone https://github.com/yourusername/anki_ocr.git
cd anki_ocr
```

2. 依存パッケージをインストール:
```bash
pip install -e .
```

3. 環境変数の設定:
```bash
# .envファイルを作成
echo "OPENAI_API_KEY=your-api-key" > .env
```

## 使用方法

### 画像からデッキを生成

1. 画像ファイルを `data/input/images/` ディレクトリに配置します。

2. 以下のコマンドを実行:
```bash
# ディレクトリ内の全画像を処理
anki-ocr --input-dir data/input/images --deck-name "Thai Vocab"

# 単一の画像ファイルを処理
anki-ocr --image data/input/images/example.jpg --deck-name "Thai Vocab"

# 音声ファイルも生成する場合
anki-ocr --input-dir data/input/images --deck-name "Thai Vocab" --generate-media
```

### 出力

- 生成されたAnkiデッキ（`.apkg`ファイル）は `data/output/decks/` ディレクトリに保存されます。
- デッキ名は `--deck-name` オプションで指定した名前になります（デフォルト: "Thai Vocab"）。

### 生成されたデッキの確認

生成されたAnkiデッキの内容を確認するには、以下のコマンドを実行します：

```bash
python src/confirm_apkg.py data/output/decks/Thai_Vocab.apkg
```

このコマンドは以下の情報を表示します：
- アーカイブ内のファイル一覧
- メディアファイルの一覧とハッシュ値
- デッキの内容をTSVファイル（`deck_dump.tsv`）にエクスポート
- メディアファイルを `/tmp/anki_inspect/media` に展開

### 注意事項

- 画像は以下の形式に対応: JPG, JPEG, PNG
- 画像サイズが大きすぎる場合は自動的にリサイズされます
- 音声生成にはインターネット接続が必要です
- OpenAI APIの利用にはAPIキーが必要です（.envファイルに設定）

## 開発

### プロジェクト構造

```
anki_ocr/
├── src/
│   ├── common/           # 共通機能
│   │   ├── audio.py     # 音声生成
│   │   ├── image.py     # 画像処理
│   │   ├── ocr.py       # OCR処理
│   │   └── utils.py     # ユーティリティ
│   ├── deck_builders/   # デッキ生成
│   │   └── image_table.py
│   ├── cli/             # コマンドライン
│   │   └── main.py
│   └── confirm_apkg.py  # デッキ確認ツール
├── data/
│   ├── input/          # 入力ファイル
│   │   └── images/
│   └── output/         # 出力ファイル
│       └── decks/
├── .env               # 環境変数設定ファイル
└── setup.py
```

### 依存パッケージ

- genanki: Ankiデッキ生成
- gTTS: 音声生成
- Pillow: 画像処理
- openai: OCR処理
- numpy: 画像処理
- python-dotenv: 環境変数管理

## ライセンス

MIT License