import os
import time
import pathlib
import tempfile
from typing import List, Tuple
from genanki import Model, Note, Deck, Package
from ..common.audio import gen_audio
from ..common.ocr import ocr_and_process

def build_deck(rows: List[Tuple[str, str, str, str, str]], deck_name: str, media_dir: pathlib.Path) -> None:
    """Ankiデッキを生成する"""
    if not rows:
        print("❌ 処理対象のデータがありません")
        return

    print(f"\n📦 デッキ生成開始: {deck_name}")
    print(f"📂 メディアディレクトリ: {media_dir}")
    
    # メディアファイルの存在確認
    media_files = list(media_dir.iterdir())
    print(f"📋 メディアファイル一覧:")
    for f in media_files:
        print(f"  - {f.name} ({f.stat().st_size:,} bytes)")

    model = Model(
        1607392319,
        "Thai IPA Model",
        fields=[{"name": f} for f in
                ("Thai", "Phonetic", "English", "Extra", "Audio", "Picture")],
        templates=[{
            "name": "Card1",
            "qfmt": "{{Phonetic}}",
            "afmt": "{{FrontSide}}<hr>{{Thai}}<br>{{English}}<br>{{Extra}}<br>{{Audio}}<br>{{Picture}}",
        }],
    )

    # デッキIDを32ビット整数に収まるように生成
    deck_id = abs(hash(deck_name)) % (2**31 - 1)
    deck = Deck(deck_id, deck_name)

    for eng, thai, phonetic, audio, pic in rows:
        try:
            if not phonetic:
                print(f"⚠️ 声調付きローマ字変換に失敗しました: {thai}")
            note = Note(model, [
                thai,           # Thai
                phonetic,       # Phonetic (声調付きローマ字)
                eng,            # English
                "",             # Extra (空文字)
                f"[sound:{audio}]" if audio else "",
                f"<img src=\"{pic}\">" if pic else "",
            ])
            deck.add_note(note)
        except Exception as e:
            print(f"❌ ノートの作成に失敗しました: {thai}")
            print(f"エラー: {str(e)}")
            continue

    try:
        print("\n📦 パッケージ生成開始")
        # メディアファイルのパスを絶対パスに変換
        media_files = [str(p.absolute()) for p in media_dir.iterdir()]
        print(f"📋 パッケージに含めるメディアファイル:")
        for f in media_files:
            print(f"  - {f}")
            if not pathlib.Path(f).exists():
                print(f"  ❌ ファイルが存在しません: {f}")
            else:
                print(f"  ✅ ファイルサイズ: {pathlib.Path(f).stat().st_size:,} bytes")

        # 出力ディレクトリの作成
        output_dir = pathlib.Path("data/output/decks")
        output_dir.mkdir(parents=True, exist_ok=True)
        fname = f"{deck_name.replace(' ', '_')}.apkg"
        output_path = output_dir / fname

        if media_files:
            pkg = Package(deck, media_files=media_files)
            pkg.write_to_file(str(output_path))
            print(f"✅ 生成完了: {output_path}")
        else:
            print("⚠️ メディアファイルが見つかりません")
            pkg = Package(deck)
            pkg.write_to_file(str(output_path))
            print(f"✅ 生成完了（メディアなし）: {output_path}")
    except Exception as e:
        print("❌ デッキの生成に失敗しました")
        print(f"エラー: {str(e)}")
        import traceback
        traceback.print_exc()

def process_image_table(input_dir: pathlib.Path, deck_name: str, generate_media: bool = False) -> None:
    """画像表を処理してAnkiデッキを生成する"""
    image_files = []
    pats = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
    image_files = sorted([
        p for p in input_dir.iterdir()
        if p.suffix.lower() in pats and not p.name.startswith("temp_")
    ])

    if not image_files:
        print("❌ 処理対象の画像が見つかりません")
        return

    media_dir = pathlib.Path(tempfile.mkdtemp())
    print(f"\n📂 メディアディレクトリ作成: {media_dir}")
    all_rows = []

    for img in image_files:
        print(f"\n📝 処理中: {img.name}")
        rows = ocr_and_process(img, media_dir)
        all_rows.extend(rows)
        time.sleep(2.5)  # OpenAI Vision API対策

    # Paiboonで重複排除
    unique_rows = []
    seen_paiboon = set()
    for eng, thai, paiboon in all_rows:
        if not paiboon or paiboon in seen_paiboon:
            continue
        seen_paiboon.add(paiboon)
        unique_rows.append((eng, thai, paiboon))

    # 音声ファイル生成（重複排除後のみ）
    final_rows = []
    for eng, thai, paiboon in unique_rows:
        audio_file = ""
        if generate_media:
            try:
                audio_file = gen_audio(eng, thai, media_dir)
                time.sleep(0.7)  # gTTS対策
            except Exception as e:
                print(f"⚠️ 音声生成に失敗しました: {eng}")
                print(f"エラー: {str(e)}")
        pic_file = ""  # 画像は使わない
        final_rows.append((eng, thai, paiboon, audio_file, pic_file))

    build_deck(final_rows, deck_name, media_dir) 