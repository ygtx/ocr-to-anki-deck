# Anki OCR

## 開発環境のセットアップ

1. Python 3.8以上をインストールしてください。

2. 仮想環境を作成して有効化します：
```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
```

3. 依存関係をインストールします：
```bash
pip install -r requirements.txt
```

## プロジェクト構造

```
.
├── src/          # ソースコード
├── tests/        # テストコード
├── requirements.txt
└── README.md
```

## 開発ガイドライン

- コードフォーマット: Black
- リント: Flake8
- テスト: pytest 


### How to use

# ① フォルダを丸ごと処理（音声生成）
python build_thai_deck.py --input-dir ./photos --deck-name "Name" --generate-media

# ② 単一画像だけ（音声なし）
python build_thai_deck.py --image IMG_4637.jpeg --deck-name "Name"