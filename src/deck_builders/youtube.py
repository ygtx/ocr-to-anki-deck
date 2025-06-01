import os
import time
import pathlib
import tempfile
from typing import List, Tuple, Set, Dict, Any
import yt_dlp
from moviepy.editor import VideoFileClip
from PIL import Image
import numpy as np
import cv2
from ..common.ocr import ocr_and_process, ocr_and_process_youtube_frame
from ..common.audio import gen_audio
from .image_table import build_deck
import openai
from skimage.metrics import structural_similarity as ssim
from deep_translator import MyMemoryTranslator
from pathlib import Path
from .base import BaseDeckBuilder
import csv
import base64
import json
import re

def download_video(url: str, output_dir: pathlib.Path) -> pathlib.Path:
    """YouTube動画をダウンロードする"""
    print(f"\n📥 動画のダウンロード開始: {url}")
    
    # 出力ディレクトリをdata/input/youtube/に変更
    youtube_dir = pathlib.Path("data/input/youtube")
    youtube_dir.mkdir(parents=True, exist_ok=True)
    
    ydl_opts = {
        'format': 'best[height<=720]',  # 720p以下に制限
        'outtmpl': str(youtube_dir / '%(id)s.%(ext)s'),
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_path = youtube_dir / f"{info['id']}.{info['ext']}"
        print(f"✅ ダウンロード完了: {video_path}")
        return video_path

def extract_frames(video_path: pathlib.Path, output_dir: pathlib.Path, interval: int = 5) -> List[pathlib.Path]:
    """動画から一定間隔でフレームを抽出する"""
    print(f"\n🎞️ フレーム抽出開始: {interval}秒間隔")
    
    clip = VideoFileClip(str(video_path))
    frame_paths = []
    
    for t in range(0, int(clip.duration), interval):
        frame = clip.get_frame(t)
        frame_path = output_dir / f"frame_{t:04d}.jpg"
        Image.fromarray(frame).save(frame_path)
        frame_paths.append(frame_path)
        print(f"  - {frame_path.name}")
    
    clip.close()
    print(f"✅ フレーム抽出完了: {len(frame_paths)}枚")
    return frame_paths

def translate_to_english(japanese_text: str) -> str:
    """日本語テキストを英語に翻訳する"""
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a translator. Translate the given Japanese text to English. Only output the English translation, nothing else."},
                {"role": "user", "content": japanese_text}
            ],
            temperature=0.3,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ 翻訳に失敗しました: {japanese_text}")
        print(f"エラー: {str(e)}")
        return ""

def detect_text_regions(frame: np.ndarray) -> List[np.ndarray]:
    """フレームからテキスト領域を検出する"""
    # グレースケール変換
    gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
    
    # 二値化
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # ノイズ除去
    kernel = np.ones((3,3), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
    
    # 輪郭検出
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    # テキスト領域の抽出
    text_regions = []
    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        if w > 50 and h > 20:  # 小さすぎる領域を除外
            text_regions.append(frame[y:y+h, x:x+w])
    
    return text_regions

def is_similar_image(img1: np.ndarray, img2: np.ndarray, threshold: float = 0.95) -> bool:
    img1 = cv2.cvtColor(cv2.resize(img1, (200, 200)), cv2.COLOR_RGB2GRAY)
    img2 = cv2.cvtColor(cv2.resize(img2, (200, 200)), cv2.COLOR_RGB2GRAY)
    score, _ = ssim(img1, img2, full=True)
    return score > threshold

def filter_unique_images(image_paths, threshold=0.95):
    unique = []
    unique_paths = []
    for path in image_paths:
        img = np.array(Image.open(path))
        if not any(is_similar_image(img, uimg, threshold) for uimg in unique):
            unique.append(img)
            unique_paths.append(path)
    return unique_paths

def process_youtube_video(url: str, deck_name: str, generate_media: bool = False, frame_interval: int = 5, ssim_threshold: float = 0.95) -> None:
    """YouTube動画を処理してAnkiデッキを生成する"""
    # 一時ディレクトリの作成
    temp_dir = pathlib.Path(tempfile.mkdtemp())
    video_dir = temp_dir / "video"
    frame_dir = temp_dir / "frames"
    media_dir = temp_dir / "media"
    translator = MyMemoryTranslator(source='ja-JP', target='en-GB')
    
    for d in [video_dir, frame_dir, media_dir]:
        d.mkdir(exist_ok=True)
    
    try:
        # 動画のダウンロード
        video_path = download_video(url, video_dir)
        
        # フレームの抽出
        print("\n🎞️ フレーム抽出開始")
        frame_paths = extract_frames(video_path, frame_dir, frame_interval)
        print(f"✅ フレーム抽出完了: {len(frame_paths)}枚")

        # SSIMによる重複排除
        print("\n🔍 SSIMによる重複排除")
        unique_paths = filter_unique_images(frame_paths, threshold=ssim_threshold)
        print(f"✅ 重複排除後: {len(unique_paths)}枚")

        # テキスト領域の検出・OCR処理はユニーク画像のみ対象
        processed_frames = unique_paths

        # 各フレームをOCR処理
        all_rows = []
        for frame in processed_frames:
            print(f"\n📝 処理中: {frame.name}")
            rows = ocr_and_process_youtube_frame(frame, media_dir)
            translated_rows = []
            for meaning, thai, paiboon in rows:
                # 意味（日本語）を英訳（deep-translatorを利用）
                eng = meaning
                if meaning.strip():
                    try:
                        eng_trans = translator.translate(meaning)
                        if eng_trans:
                            print(f"  🔄 意味翻訳: {meaning} → {eng_trans}")
                            eng = eng_trans
                        else:
                            print(f"  ⚠️ 意味翻訳失敗: {meaning}")
                    except Exception as e:
                        print(f"⚠️ MyMemory翻訳に失敗しました: {meaning}")
                        print(f"エラー: {str(e)}")
                # タイ語音声ファイル生成（gTTSは無料なのでそのまま）
                audio_file = ""
                try:
                    audio_file = gen_audio(eng, thai, media_dir)
                    time.sleep(0.7)  # gTTS対策
                except Exception as e:
                    print(f"⚠️ 音声生成に失敗しました: {thai}")
                    print(f"エラー: {str(e)}")
                pic_file = ""  # 画像は使わない
                translated_rows.append((eng, thai, paiboon, audio_file, pic_file))
            all_rows.extend(translated_rows)
            time.sleep(2.5)  # OpenAI Vision API対策
        
        # Paiboonで重複排除
        unique_rows = []
        seen_paiboon = set()
        for eng, thai, paiboon, audio_file, pic_file in all_rows:
            if not paiboon or paiboon in seen_paiboon:
                continue
            seen_paiboon.add(paiboon)
            unique_rows.append((eng, thai, paiboon, audio_file, pic_file))
        
        # デッキの生成
        build_deck(unique_rows, deck_name, media_dir)
        
    finally:
        # 一時ファイルの削除
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 一時ファイルを削除しました: {temp_dir}")

class YouTubeDeckBuilder(BaseDeckBuilder):
    def __init__(self, output_dir: str, deck_name: str, ssim_threshold: float = 0.95, use_paiboon_correction: bool = True):
        super().__init__(output_dir, deck_name, use_paiboon_correction=use_paiboon_correction)
        self.ssim_threshold = ssim_threshold

    def _extract_frames(self, video_path: Path, interval: int = 1) -> List[Path]:
        """動画から一定間隔でフレームを抽出"""
        frames = []
        cap = cv2.VideoCapture(str(video_path))
        frame_count = 0
        
        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_count % interval == 0:
                frame_path = self.temp_dir / f"frame_{frame_count:04d}.jpg"
                cv2.imwrite(str(frame_path), frame)
                frames.append(frame_path)
            
            frame_count += 1
        
        cap.release()
        return frames

    def _remove_duplicates(self, frames: List[Path]) -> List[Path]:
        """SSIMを使って重複フレームを除去"""
        unique_frames = [frames[0]]
        
        for i in range(1, len(frames)):
            current = cv2.imread(str(frames[i]))
            prev = cv2.imread(str(unique_frames[-1]))
            
            # グレースケールに変換
            current_gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
            prev_gray = cv2.cvtColor(prev, cv2.COLOR_BGR2GRAY)
            
            # SSIMを計算
            score = ssim(current_gray, prev_gray)
            
            if score < self.ssim_threshold:
                unique_frames.append(frames[i])
        
        return unique_frames

    def _ocr_frame(self, frame_path: Path) -> Dict[str, str]:
        """フレーム画像からOCRでテキストを抽出"""
        # 画像を読み込み
        with open(frame_path, "rb") as f:
            image_data = f.read()
        b64_image = base64.b64encode(image_data).decode("utf-8")
        # OCRプロンプトを動的生成
        prompt = build_ocr_prompt()
        # OpenAI Vision APIでOCR
        response = self.client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )
        # レスポンスをパース
        result = response.choices[0].message.content
        # コードブロックを除去し、JSONとしてパース
        json_match = re.search(r'```json\n(.*?)\n```', result, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\[[\s\S]*\]', result)
            if not json_match:
                print("❌ OpenAI応答にJSONが見つかりませんでした")
                return {}
            json_str = json_match.group(0)
        try:
            data = json.loads(json_str)
            # バリデーション
            if not isinstance(data, list):
                print("❌ JSONが配列ではありません")
                return {}
            if not data:
                print("❌ 空の配列が返されました")
                return {}
            # 最初の要素を返す（複数ある場合は最初の1つだけ）
            item = data[0]
            if not all(k in item for k in ["meaning", "thai", "paiboon"]):
                print("❌ 必要なキーが不足しています")
                return {}
            return item
        except Exception as e:
            print(f"❌ JSONの解析に失敗しました: {str(e)}")
            return {}

    def build(self, video_path: Path, frame_interval: int = 1) -> Path:
        """動画からデッキをビルド"""
        # フレームを抽出
        frames = self._extract_frames(video_path, frame_interval)
        
        # 重複フレームを除去
        unique_frames = self._remove_duplicates(frames)
        
        # OCRでテキストを抽出
        ocr_data = []
        for frame in unique_frames:
            result = self._ocr_frame(frame)
            if result:  # 有効な結果の場合のみ追加
                ocr_data.append(result)
        
        # 親クラスのbuildメソッドを呼び出し（修正機能を含む）
        return super().build(ocr_data)

    def cleanup(self):
        """一時ファイルを削除"""
        super().cleanup()

def build_ocr_prompt():
    diff_path = "data/output/system/paiboon_diff.tsv"
    mis_list = []
    if Path(diff_path).exists():
        with open(diff_path, encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter="\t")
            for row in reader:
                if row["type"] == "mismatch":
                    mis_list.append(f"- タイ語: {row['thai']}, 正しいPaiboon: {row['gold_paiboon']}, 誤判定: {row['generated_paiboon']}")
    mis_text = "\n".join(mis_list)
    prompt = (
        "この画像からタイ語、Paiboon式ローマ字、日本語の意味を抽出してください。\n"
        "必ず以下の形式のJSON配列で返してください（説明文は不要）:\n"
        "[\n"
        "  {\n"
        '    "meaning": "日本語の意味",\n'
        '    "thai": "タイ語",\n'
        '    "paiboon": "Paiboon式ローマ字"\n'
        "  }\n"
        "]\n"
        "\n【重要な注意事項】\n"
        "1. 必ず上記の形式のJSON配列のみを返してください。説明文は不要です。\n"
        "2. 過去のOCR処理では、Paiboon式ローマ字の抽出において下記のような誤判定が繰り返し発生しています。"
        "これらの誤りを繰り返さないよう、タイ語の発音・綴りに忠実なPaiboon式ローマ字を正確に抽出してください。"
        "特に、Paiboon式ローマ字以外の記号や曖昧な推測による文字を割り当てることは避けてください。"
        "\n---\n誤判定例:\n" + mis_text + "\n---\n"
        "上記の誤りを参考に、同じ間違いを繰り返さず、正しいPaiboon式ローマ字を出力してください。"
    )
    return prompt 