# Anki OCR

タイ語の語学学習用Ankiデッキを画像やYouTube動画から自動生成するPython CLIツールです。OCR・Paiboon式ローマ字・意味（日本語）を抽出し、ChatGPTによる自動修正・例外パターン管理・自動フィードバックループを備えています。

## 主な機能

- 画像・YouTube動画からタイ語フレーズ・Paiboon式ローマ字・意味（日本語）を自動抽出
- Paiboon式ローマ字の自動修正（ChatGPT API利用、例外パターンはTSVで自動管理）
- 音声ファイル（TTS）の自動生成
- Ankiデッキ（.apkg）の自動生成
- 差分TSVによる例外パターンの自動反映・フィードバックループ
- CLI一発で全自動処理

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

## 使い方

### 画像からデッキを生成

1. 画像ファイルを `data/input/images/` に配置
2. コマンド実行:
```bash
anki-ocr --input-dir data/input/images --deck-name "Thai Vocab"
anki-ocr --image data/input/images/example.jpg --deck-name "Thai Vocab"
# 音声ファイルも生成する場合
anki-ocr --input-dir data/input/images --deck-name "Thai Vocab" --generate-media
```

### YouTube動画からデッキを生成

```bash
anki-ocr --youtube "https://www.youtube.com/watch?v=..." --deck-name "Thai Vocab"
# フレーム抽出間隔や重複排除のしきい値を調整
anki-ocr --youtube "https://www.youtube.com/watch?v=..." --deck-name "Thai Vocab" --frame-interval 3 --ssim-threshold 0.92
```
- **YouTube動画は `data/input/youtube/` に自動保存されます。**

### 主なCLIオプション

| オプション | 説明 |
|---|---|
| `--deck-name` | 出力デッキ名（必須） |
| `--input-dir` | 画像ディレクトリを指定（画像用） |
| `--image` | 単一画像ファイルを指定（画像用） |
| `--youtube` | YouTube動画URLを指定（動画用） |
| `--frame-interval` | フレーム抽出間隔（秒、デフォルト5、動画用） |
| `--ssim-threshold` | SSIMによる重複排除のしきい値（0.90〜0.99、デフォルト0.95、動画用） |
| `--no-paiboon-correction` | ChatGPTによるPaiboon最終修正をスキップ（デフォルトは修正あり） |
| `--generate-media` | 音声ファイルも生成（画像用のみ） |

### 出力

- 生成されたAnkiデッキ（`.apkg`ファイル）は `data/output/decks/` に保存されます。
- YouTube動画は `data/input/youtube/` に保存されます。

### 生成デッキの確認

```bash
python src/confirm_apkg.py data/output/decks/Thai_Vocab.apkg
```
- アーカイブ内のファイル一覧、メディアファイルの一覧とハッシュ値、デッキ内容のTSVエクスポートなどが可能です。

### 注意事項

- 画像は JPG, JPEG, PNG に対応
- 画像サイズが大きすぎる場合は自動リサイズ
- 音声生成・OCR・Paiboon修正にはインターネット接続とOpenAI APIキーが必要
- YouTube動画の重複排除には `scikit-image` が必要
- 無効なデータ（空文字列やnull値）は自動でスキップされます

## プロジェクト構成

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
│   ├── input/
│   │   ├── images/
│   │   └── youtube/
│   └── output/
│       ├── decks/
│       └── system/
├── .env
└── setup.py
```

## 依存パッケージ

- genanki: Ankiデッキ生成
- gTTS: 音声生成
- Pillow: 画像処理
- openai: OCR・Paiboon修正
- numpy: 画像処理
- python-dotenv: 環境変数管理
- yt-dlp: YouTube動画ダウンロード
- moviepy: 動画処理
- opencv-python: 画像処理
- scikit-image: SSIMによる重複排除

## Paiboon表記の自動フィードバックループ

本プロジェクトは、Paiboon式ローマ字表記の精度を継続的に高めるため、**差分検出からプロンプト改善までの自動フィードバックループ**を実装しています。

### 仕組みの概要

1. **apkgファイルの比較と差分検出**
    - 正解データ（例: 人手修正済みapkg）とシステム生成データ（自動生成apkg）を用意
    - `python scripts/apkg_paiboon_diff.py correct.apkg generated.apkg` を実行すると、
        - それぞれのapkgからCSVを一時生成
        - タイ語ごとにPaiboon表記を比較し、差分（不一致や未出力）を `data/output/system/paiboon_diff.tsv` に出力

2. **差分TSVの内容**
    - `paiboon_diff.tsv` には以下のカラムが含まれます：
        - `thai`（タイ語）
        - `gold_paiboon`（正解Paiboon）
        - `generated_paiboon`（システム出力）
        - `type`（mismatch など）
    - `gold_paiboon` が「正解」として今後のプロンプトに反映されます

3. **プロンプト（rules）の自動改善**
    - `src/deck_builders/base.py` の `BaseDeckBuilder` では、
        - `build_rules()` メソッドが `paiboon_diff.tsv` を参照し、差分（例外パターン）をプロンプトに自動で組み込みます
        - 例外パターンがTSVに無い場合は自動で追記されます
        - TSVが存在しない場合は従来の例外パターンが使われます
    - これにより、**過去の差分が次回以降のPaiboon修正プロンプトに自動反映**され、システムの精度が継続的に向上します

### 運用フロー

1. 正解apkgと生成apkgを用意（例：本システムで生成→Ankiで手動修正→正解apkg）
2. `python scripts/apkg_paiboon_diff.py correct.apkg generated.apkg` を実行
3. 差分が `data/output/system/paiboon_diff.tsv` に出力
4. 次回以降のデッキ生成時、差分がプロンプトに自動反映

### メリット
- 人手で例外パターンを管理する必要がなく、**差分検出→プロンプト改善→精度向上**が自動で回る
- 新たな誤りが出ても、差分TSVに追加するだけで次回以降に反映
- 継続的なPaiboon表記の品質向上が可能

---

この仕組みにより、Paiboon式ローマ字の自動変換精度を高いレベルで維持・改善できます。

## エラー処理・データバリデーション

- OCRや修正後のデータで、**空文字列やnull値のエントリは自動でスキップ**されます。
- 無効なデータはAnkiデッキに含まれません。
- エラー発生時は詳細なメッセージが出力されます。

## Ankiカードテンプレート例

### Front
```html
<h1>{{paiboon}}</h1>
<h2>{{thai}}</h2>
<hr>
<h1>{{audio}}</h1>
```

### Back
```html
<h1>{{paiboon}}</h1>
<h2>{{meaning}}</h2>
<h2>{{thai}}</h2>
<hr>
<h1>{{audio}}</h1>
```

### Styling
```css
h1, h2 { text-align: center }
```

## ライセンス

MIT License
