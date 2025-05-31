import os
import uuid
import pathlib
from gtts import gTTS
from .utils import sanitize_filename

def gen_audio(word: str, thai: str, out_dir: pathlib.Path) -> str:
    """タイ語の音声ファイルを生成する"""
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