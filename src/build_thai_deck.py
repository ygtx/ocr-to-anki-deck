#!/usr/bin/env python3
"""
Usage examples
--------------

# ① フォルダを丸ごと処理（音声生成）
python build_thai_deck.py --input-dir ./photos --deck-name "Name" --generate-media

# ② 単一画像だけ（音声なし）
python build_thai_deck.py --image IMG_4637.jpeg --deck-name "Name"
"""
import os, re, csv, uuid, argparse, tempfile, pathlib, requests, shutil, time
from typing import List, Tuple, Optional
from PIL import Image, UnidentifiedImageError, ImageOps
from pythainlp.transliterate import romanize
from genanki import Model, Note, Deck, Package
from gtts import gTTS
import eng_to_ipa as ipa
import base64
import openai
from dotenv import load_dotenv

# .envファイルを読み込む
load_dotenv()

# ---------- OCR & PARSE -------------------------------------------------

def load_and_convert_image(img_path: pathlib.Path) -> Optional[Image.Image]:
    """画像を読み込んで適切な形式に変換する"""
    try:
        # 画像を開く
        with Image.open(img_path) as img:
            # 画像の形式を確認
            if img.format not in ['JPEG', 'PNG']:
                print(f"⚠️ 非推奨の画像形式です: {img.format} ({img_path})")
                print("JPEGまたはPNG形式に変換します")
                # 一時ファイルに変換して保存
                temp_path = img_path.parent / f"temp_{img_path.stem}.jpg"
                img = img.convert('RGB')
                img.save(temp_path, 'JPEG', quality=95)
                img_path = temp_path
                print(f"✅ 変換完了: {temp_path}")
            
            # 画像をRGBモードに変換
            if img.mode != 'RGB':
                img = img.convert('RGB')
            
            # 画像の向きを自動修正
            img = ImageOps.exif_transpose(img)
            
            # 画像のサイズを確認
            if img.size[0] > 4000 or img.size[1] > 4000:
                print(f"⚠️ 画像サイズが大きすぎます: {img.size} ({img_path})")
                print("リサイズします")
                img.thumbnail((4000, 4000), Image.Resampling.LANCZOS)
            
            return img
    except UnidentifiedImageError:
        print(f"❌ 画像形式が認識できません: {img_path}")
        print("画像が破損しているか、サポートされていない形式です")
        return None
    except Exception as e:
        print(f"❌ 画像の読み込みに失敗しました: {img_path}")
        print(f"エラー: {str(e)}")
        return None

def extract_thai_words(text: str) -> list:
    """タイ語の単語を抽出（3文字以上の連続したタイ文字）"""
    return re.findall(r'[\u0E00-\u0E7F]{2,}', text)

def get_phonetic_with_tone(thai: str) -> str:
    """Google Translateの発音記号（ラテン文字）を優先し、なければpythainlpのromanizeでフォールバック"""
    try:
        translator = Translator()
        result = translator.translate(thai, src='th', dest='en')
        # Google Translateのpronunciation（ラテン文字表記）を優先
        pron = result.extra_data.get('pronunciation') if hasattr(result, 'extra_data') else None
        if pron and pron.strip():
            return pron.strip()
    except Exception as e:
        print(f"⚠️ Google翻訳での発音記号取得に失敗: {thai}")
        print(f"エラー: {str(e)}")
    # フォールバック: pythainlpのromanize
    try:
        roman = romanize(thai, engine="thai2rom")
        if roman and roman.strip():
            return roman.strip()
    except Exception as e:
        print(f"⚠️ pythainlp romanizeでも変換に失敗: {thai}")
        print(f"エラー: {str(e)}")
    return ""

def preprocess_image_for_ocr(img: Image.Image) -> Image.Image:
    """OCR用に画像を前処理（グレースケール化・二値化・リサイズ）"""
    # グレースケール化
    img = img.convert('L')
    # リサイズ（幅が2000pxを超える場合は2000pxに縮小）
    max_width = 2000
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    # 二値化（大津の方法）
    try:
        import numpy as np
        arr = np.array(img)
        threshold = arr.mean()  # シンプルな平均値で二値化
        binarized = (arr > threshold) * 255
        img = Image.fromarray(binarized.astype('uint8'))
    except Exception:
        # numpyがなければImageOpsで簡易二値化
        img = ImageOps.autocontrast(img)
    return img

def extract_meaning_column(text: str) -> list:
    """OCRテキストからMeaning列の値のみを抽出"""
    # Meaning列の値を抽出（例: 'Meaning: word' または 'Meaning\tword' など）
    lines = text.splitlines()
    meanings = []
    for line in lines:
        # 'Meaning'で始まる列を抽出
        m = re.search(r'Meaning[:\t ]+([A-Za-z\- ]+)', line)
        if m:
            value = m.group(1).strip()
            if value:
                meanings.append(value)
    return meanings

def get_phonetic(english: str) -> str:
    """Google Translateのpronunciation（英語）を優先し、なければeng_to_ipaでIPAを生成"""
    try:
        translator = Translator()
        result = translator.translate(english, src='en', dest='th')
        pron = result.extra_data.get('pronunciation') if hasattr(result, 'extra_data') else None
        if pron and pron.strip():
            return pron.strip()
    except Exception as e:
        print(f"⚠️ Google翻訳での発音記号取得に失敗: {english}")
        print(f"エラー: {str(e)}")
    # フォールバック: eng_to_ipa
    try:
        ipa_str = ipa.convert(english)
        if ipa_str and ipa_str.strip():
            return ipa_str.strip()
    except Exception as e:
        print(f"⚠️ eng_to_ipaでも変換に失敗: {english}")
        print(f"エラー: {str(e)}")
    return ""

def extract_english_words(text: str) -> list:
    """OCRテキストから英語の単語（3文字以上）だけを抽出"""
    # Meaning列の値があれば優先して抽出
    meanings = extract_meaning_column(text)
    if meanings:
        return meanings
    # それ以外は英単語のみ抽出
    return re.findall(r'\b[a-zA-Z]{3,}\b', text)

def sanitize_filename(name: str) -> str:
    # スラッシュが含まれる場合はスラッシュより前だけを使う
    if '/' in name:
        name = name.split('/')[0]
    # それ以外のファイル名に使えない文字をアンダースコアに置換
    return re.sub(r'[\\:*?"<>|]', '_', name)

def gen_audio(word: str, thai: str, out_dir: pathlib.Path) -> str:
    safe_word = sanitize_filename(word)
    fname = f"{safe_word}_{uuid.uuid4().hex[:6]}.mp3"
    out_path = out_dir / fname
    try:
        print(f"🎵 音声生成開始: {word} -> {out_path}")
        gTTS(thai, lang="th").save(out_path)
        print(f"✅ 音声生成成功: {out_path}")
    except Exception as e:
        print(f"❌ 音声生成に失敗しました: {word}")
        print(f"エラー: {str(e)}")
        return ""
    return fname  # ファイル名のみ返す

def fetch_image(keyword: str, out_dir: pathlib.Path) -> str:
    # 画像取得は行わない
    return ""

def ocr_and_process(img_path: pathlib.Path, media_dir: pathlib.Path) -> List[Tuple[str, str, str]]:
    """OpenAI o3モデルで画像からThai, Paiboon, Englishを抽出（Paiboon重複排除・画像取得なし・音声生成なし）"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEYが設定されていません")
        return []
    client = openai.OpenAI(api_key=api_key)
    with open(img_path, "rb") as image_file:
        b64_image = base64.b64encode(image_file.read()).decode("utf-8")
    prompt = (
        "この画像は語学学習用の表です。各行から「タイ語」「Paiboon式ローマ字」「英語の意味」を抽出し、"
        "JSON形式で出力してください。特にPaiboon式ローマ字の抽出は画像に忠実になるよう注意してください。例: [{\"thai\": \"...\", \"paiboon\": \"...\", \"english\": \"...\"}, ...]"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",  # o3モデルを使用
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_image}"}}
                    ]
                }
            ],
            max_completion_tokens=2048
        )
        import json, re
        content = response.choices[0].message.content
        print(content)  # デバッグ用に出力を保持
        json_match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\[[\s\S]*\]', content)
            if not json_match:
                print("❌ OpenAI応答にJSONが見つかりませんでした")
                return []
            json_str = json_match.group(0)
        try:
            table = json.loads(json_str)
            results = []
            seen_paiboon = set()
            for row in table:
                english = row.get("english", "")
                thai = row.get("thai", "")
                paiboon = row.get("paiboon", "")
                if not paiboon or paiboon in seen_paiboon:
                    continue  # Paiboon重複排除
                seen_paiboon.add(paiboon)
                results.append((english, thai, paiboon))
                print(f"✅ 処理成功: {english} | {thai} | {paiboon}")
            return results
        except json.JSONDecodeError as e:
            print(f"❌ JSONの解析に失敗しました: {str(e)}")
            return []
    except Exception as e:
        print(f"❌ OpenAI APIでの処理に失敗しました: {img_path}")
        print(f"エラー: {str(e)}")
        return []

# ---------- DECK BUILD --------------------------------------------------

def build_deck(rows, deck_name, media_dir):
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
        if media_files:
            pkg = Package(deck, media_files=media_files)
            fname = f"{deck_name.replace(' ', '_')}.apkg"
            pkg.write_to_file(fname)
            print(f"✅ 生成完了: {fname}")
        else:
            print("⚠️ メディアファイルが見つかりません")
            pkg = Package(deck)
            fname = f"{deck_name.replace(' ', '_')}.apkg"
            pkg.write_to_file(fname)
            print(f"✅ 生成完了（メディアなし）: {fname}")
    except Exception as e:
        print("❌ デッキの生成に失敗しました")
        print(f"エラー: {str(e)}")
        import traceback
        traceback.print_exc()

# ---------- MAIN --------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", type=pathlib.Path,
                     help="単一画像ファイルを指定")
    src.add_argument("--input-dir", type=pathlib.Path,
                     help="画像を置いたフォルダを指定（*.jpg, *.png, *.jpeg を再帰なしで検索）")
    ap.add_argument("--deck-name", default="Thai Vocab")
    ap.add_argument("--generate-media", action="store_true",
                    help="音声(TTS)と画像(Unsplash)を自動取得")
    args = ap.parse_args()

    image_files = []
    if args.image:
        if not args.image.exists():
            print(f"❌ 指定された画像が見つかりません: {args.image}")
            return
        if not args.image.name.startswith("temp_"):
            image_files = [args.image]
    else:
        if not args.input_dir.exists():
            print(f"❌ 指定されたディレクトリが見つかりません: {args.input_dir}")
            return
        pats = (".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")
        image_files = sorted([
            p for p in args.input_dir.iterdir()
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
        try:
            audio_file = gen_audio(eng, thai, media_dir)
            time.sleep(0.7)  # gTTS対策
        except Exception as e:
            print(f"⚠️ 音声生成に失敗しました: {eng}")
            print(f"エラー: {str(e)}")
        pic_file = ""  # 画像は使わない
        final_rows.append((eng, thai, paiboon, audio_file, pic_file))

    build_deck(final_rows, args.deck_name, media_dir)

if __name__ == "__main__":
    main()