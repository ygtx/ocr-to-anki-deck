import os
import re
import json
import base64
import openai
from typing import List, Tuple
import pathlib
from dotenv import load_dotenv
from .image import load_and_convert_image, preprocess_image_for_ocr
import shutil
import datetime

# .envファイルを読み込む
load_dotenv()

def extract_thai_words(text: str) -> list:
    """タイ語の単語を抽出（3文字以上の連続したタイ文字）"""
    return re.findall(r'[\u0E00-\u0E7F]{2,}', text)

def extract_english_words(text: str) -> list:
    """OCRテキストから英語の単語（3文字以上）だけを抽出"""
    # Meaning列の値があれば優先して抽出
    meanings = extract_meaning_column(text)
    if meanings:
        return meanings
    # それ以外は英単語のみ抽出
    return re.findall(r'\b[a-zA-Z]{3,}\b', text)

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

def save_invalid_frame(img_path, reason):
    debug_dir = pathlib.Path("data/debug/invalid_frames")
    debug_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out_path = debug_dir / f"{img_path.stem}__{reason}__{ts}{img_path.suffix}"
    shutil.copy(img_path, out_path)
    print(f"⚠️ 無効画像を保存: {out_path}")

def ocr_and_process(img_path: pathlib.Path, media_dir: pathlib.Path) -> List[Tuple[str, str, str]]:
    """OpenAI o3モデルで画像からThai, Paiboon, Englishを抽出"""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEYが設定されていません")
        print("⚠️ .envファイルにOPENAI_API_KEYを設定してください")
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
                # Thaiに日本語（ひらがな・カタカナ・漢字・全角カッコ・日本語記号）が含まれる場合はスキップ
                if re.search(r'[\u3040-\u30FF\u4E00-\u9FFF（）「」『』【】［］｛｝〈〉《》〔〕・ー]', thai):
                    print(f"⚠️ Thaiに日本語や日本語記号が含まれるためスキップ: {thai}")
                    continue
                if re.search(r'-training\.com', thai):
                    print(f"⚠️ Thaiに'-training.com'が含まれるためスキップ: {thai}")
                    continue
                if not paiboon:
                    print(f"⚠️ paiboon=None or empty: {img_path}, row={row}")
                    save_invalid_frame(img_path, "no_paiboon")
                    continue  # Paiboon重複排除
                if paiboon in seen_paiboon:
                    continue
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

def ocr_and_process_youtube_frame(img_path: pathlib.Path, media_dir: pathlib.Path) -> List[Tuple[str, str, str]]:
    """YouTubeフレーム用のプロンプトでOCR処理"""
    from dotenv import load_dotenv
    load_dotenv()
    import os
    import base64
    import openai
    import re
    import json
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEYが設定されていません")
        print("⚠️ .envファイルにOPENAI_API_KEYを設定してください")
        return []
    client = openai.OpenAI(api_key=api_key)
    with open(img_path, "rb") as image_file:
        b64_image = base64.b64encode(image_file.read()).decode("utf-8")
    prompt = (
        "この画像は語学学習表の画像です。画面に表示されている「タイ語」「Paiboon式ローマ字」「意味」を抽出し、"
        "JSON形式で出力してください。その3要素が揃っていない画像は無視してださい。例: [{\"thai\": \"...\", \"paiboon\": \"...\", \"meaning\": \"...\"}, ...]"
    )
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
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
        content = response.choices[0].message.content
        print(content)  # デバッグ用
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
                meaning = row.get("meaning", "")
                thai = row.get("thai", "")
                paiboon = row.get("paiboon", "")
                # Thaiに日本語（ひらがな・カタカナ・漢字・全角カッコ・日本語記号）が含まれる場合はスキップ
                if re.search(r'[\u3040-\u30FF\u4E00-\u9FFF（）「」『』【】［］｛｝〈〉《》〔〕・ー]', thai):
                    print(f"⚠️ Thaiに日本語や日本語記号が含まれるためスキップ: {thai}")
                    continue
                if re.search(r'-training\.com', thai):
                    print(f"⚠️ Thaiに'-training.com'が含まれるためスキップ: {thai}")
                    continue
                if not paiboon:
                    print(f"⚠️ paiboon=None or empty: {img_path}, row={row}")
                    save_invalid_frame(img_path, "no_paiboon")
                    continue
                if paiboon in seen_paiboon:
                    continue
                seen_paiboon.add(paiboon)
                results.append((meaning, thai, paiboon))
                print(f"✅ 処理成功: {meaning} | {thai} | {paiboon}")
            return results
        except json.JSONDecodeError as e:
            print(f"❌ JSONの解析に失敗しました: {str(e)}")
            return []
    except Exception as e:
        print(f"❌ OpenAI APIでの処理に失敗しました: {img_path}")
        print(f"エラー: {str(e)}")
        return [] 