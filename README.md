# Anki OCR

タイ語の語学学習用のAnkiデッキを自動生成するツールです。画像からタイ語の単語とその意味を抽出し、Ankiデッキを作成します。

## 機能

- 画像からタイ語の単語とその意味を自動抽出
- Paiboon式ローマ字の自動生成
- 音声ファイルの自動生成（オプション）
- Ankiデッキの自動生成
- YouTube動画からのフレーズ抽出（重複フレームはSSIMで自動排除）

## インストール

1. リポジトリをクローン:
```bash
git clone https://github.com/yourusername/anki_ocr.git
cd anki_ocr
```

2. 依存パッケージをインストール:
```bash
pip install -e .
# YouTube重複排除に必要な追加パッケージ
pip install scikit-image
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

### YouTube動画からデッキを生成

```bash
anki-ocr --youtube "https://www.youtube.com/watch?v=..." --deck-name "Thai Vocab"

# フレーム抽出間隔や重複排除のしきい値を調整したい場合
anki-ocr --youtube "https://www.youtube.com/watch?v=..." --deck-name "Thai Vocab" --frame-interval 3 --ssim-threshold 0.92
```

- `--frame-interval` : フレーム抽出間隔（秒、デフォルト5）
- `--ssim-threshold` : SSIMによる重複排除のしきい値（0.90〜0.99推奨、デフォルト0.95）
  - 値を下げると「より違いのある画像だけ残す」
  - 値を上げると「より厳密に重複を排除」

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
- YouTube動画の重複排除には `scikit-image` パッケージが必要です

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
│   │   └── youtube.py   # YouTube対応
│   └── cli/             # コマンドライン
│       └── main.py
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
- yt-dlp: YouTube動画ダウンロード
- moviepy: 動画処理
- opencv-python: 画像処理
- scikit-image: SSIMによる重複排除

## ライセンス

MIT License

## Paiboon表記の自動フィードバックループ

本プロジェクトでは、Paiboon式ローマ字表記の精度を継続的に高めるため、**差分検出からプロンプト改善までの自動フィードバックループ**を実装しています。

### 仕組みの概要

1. **apkgファイルの比較と差分検出**
    - 正解データ（例: 人手修正済みapkg）とシステム生成データ（自動生成apkg）を用意します。
    - `python scripts/apkg_paiboon_diff.py correct.apkg generated.apkg` を実行すると、
        - それぞれのapkgからCSVを一時生成
        - タイ語ごとにPaiboon表記を比較し、差分（不一致や未出力）を `data/output/system/paiboon_diff.tsv` に出力します。

2. **差分TSVの内容**
    - `paiboon_diff.tsv` には以下のカラムが含まれます：
        - `thai`（タイ語）
        - `gold_paiboon`（正解Paiboon）
        - `generated_paiboon`（システム出力）
        - `type`（mismatch など）
    - ここで `gold_paiboon` が「正解」として今後のプロンプトに反映されます。

3. **プロンプト（rules）の自動改善**
    - `src/deck_builders/base.py` の `BaseDeckBuilder` では、
        - `build_rules()` メソッドが `paiboon_diff.tsv` を参照し、差分（例外パターン）をプロンプトに自動で組み込みます。
        - 例外パターンがTSVに無い場合は自動で追記されます。
        - TSVが存在しない場合は従来の例外パターンが使われます。
    - これにより、**過去の差分が次回以降のPaiboon修正プロンプトに自動反映**され、システムの精度が継続的に向上します。

### 運用フロー

1. 正解apkgと生成apkgを用意。例えば、本システムをデフォルトの状態で実行して生成したものを「生成apkg」、それをAnkiに取り込んで手動生成を加えたものを「正解apkg」とするなど。
2. `python scripts/apkg_paiboon_diff.py correct.apkg generated.apkg` を実行
3. 差分が `data/output/system/paiboon_diff.tsv` に出力される
4. 次回以降のデッキ生成時、差分がプロンプトに自動反映される

### メリット
- 人手で例外パターンを管理する必要がなく、**差分検出→プロンプト改善→精度向上**が自動で回る
- 新たな誤りが出ても、差分TSVに追加するだけで次回以降に反映
- 継続的なPaiboon表記の品質向上が可能

---

この仕組みにより、Paiboon式ローマ字の自動変換精度を高いレベルで維持・改善できます。


## Anki Card Template example

### Front
```html
<h1>{{Phonetic}}</h1>
<h2>{{Thai}}</h2>
<hr>
<h1>{{Audio}}</h1>
```

### Back
```html
<h1>{{Phonetic}}</h1>
<h2>{{English}}</h2>
<h2>{{Thai}}</h2>
<hr>
<h1>{{Audio}}</h1>
```

### Styling
```csv
h1, h2 { text-align: center }
```
