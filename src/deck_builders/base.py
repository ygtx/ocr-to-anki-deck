import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from gtts import gTTS
from deep_translator import MyMemoryTranslator
from genanki import Model, Note, Deck, Package

class BaseDeckBuilder:
    def __init__(self, output_dir: str, deck_name: str):
        self.output_dir = Path(output_dir)
        self.deck_name = deck_name
        self.client = OpenAI()
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def _save_ocr_data(self, data: List[Dict[str, str]]) -> Path:
        """OCRデータを一時ファイルに保存"""
        temp_file = self.temp_dir / "ocr_data.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return temp_file

    def _correct_paiboon(self, data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """タイ語をベースにしたPaiboon式ローマ字の修正"""
        # 修正ルールの説明
        rules = """
        あなたはタイ語の専門家です。以下のルールに従ってPaiboon式ローマ字を修正してください：

        1. 基本ルール
           - 声調記号は母音の上に1回のみ配置（例：khòòp → khòp）
           - 長母音は1回のみ表記（例：khòòp → khòp）
           - 子音の連結は音節境界で行う（例：yàŋŋay → yàŋŋay）
           - 母音記号はPaiboon標準に従う（例：ʉ̂ʉ よりも chûʉ, ûʉ, ue 系を優先）

        2. 実用Paiboon標準への補正ルール
           - 語末の "b" は "p" に補正（例：khòb khun → khòp khun）
           - "ă"（短母音）と "ǎ"（上昇声調）は厳密に区別する
           - 否定副詞 "mây" は第3声（yの上に重アクセント）で表記（mây）
           - "dâi"（can）と "dây"（できて）は文脈で正しく使い分ける
           - "ʉ̂ʉ" は "ûʉ" または "ue" 系に正規化（例：chûʉ aray）

        3. 例外パターン
           - ขอบคุณ → khòp khun
           - ขอโทษ → khǎw thôot
           - ไม่เป็นไร → mây pen ray
           - ยินดีที่ได้รู้จัก → yin dii thîi dây rúu càk
           - ชื่ออะไร → chûʉ aray
           - เป็นยังไงบ้าง → pen yàŋŋay bâaŋ
           - เรื่อย ๆ → rʉ̂ay rʉ̂ay

        4. 音節解析ルール
           - 子音連結（例：ŋŋ）は音節境界で行う
           - 母音の長さは音節構造に基づいて決定
           - 声調記号は音節の主要母音に配置
           - 音節構造は元の語の構造を維持（例：yàŋŋay を yanjay に変更しない）

        5. 修正の優先順位
           1. 例外パターンの適用
           2. 実用Paiboon標準への補正
           3. 音節解析に基づく修正
           4. 基本ルールの適用

        6. 禁止事項
           - 声調記号の重複（例：khòòp）
           - 非標準的な母音記号（例：ᵾ）
           - 音節構造の過度な簡略化（例：yàŋŋay → yanjay）
           - 語末の "b"（例：khòb khun）
           - "ă" と "ǎ" の混同
           - "ʉ̂ʉ" のまま残す（chûʉ, ûʉ, ue 系に正規化）

        入力データは以下の形式です：
        {
            "thai": "タイ語の文字列",
            "paiboon": "OCRで得られたPaiboon式ローマ字",
            "meaning": "日本語の意味"
        }

        出力は以下の形式で返してください：
        {
            "thai": "タイ語の文字列（変更なし）",
            "paiboon": "修正後のPaiboon式ローマ字",
            "meaning": "日本語の意味（変更なし）",
            "correction_reason": "修正の理由（例外パターン適用の場合はその旨を明記）"
        }
        """
        
        # データをJSON形式で整形
        data_json = json.dumps(data, ensure_ascii=False, indent=2)
        
        # ChatGPTに修正を依頼
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": rules},
                {"role": "user", "content": f"以下のデータのPaiboon式ローマ字を修正してください：\n{data_json}"}
            ],
            temperature=0.15  # より一貫性のある出力のために温度をさらに下げる
        )
        
        # 修正されたデータを取得
        corrected_data = json.loads(response.choices[0].message.content)
        
        # 修正理由を表示
        for item in corrected_data:
            if "correction_reason" in item:
                print(f"\n🔍 修正理由: {item['correction_reason']}")
                del item["correction_reason"]  # 修正理由は表示後削除
        
        return corrected_data

    def _translate_to_english(self, text: str) -> str:
        """日本語から英語に翻訳"""
        translator = MyMemoryTranslator(source="ja-JP", target="en-GB")
        return translator.translate(text)

    def _generate_tts(self, text: str, output_path: Path) -> None:
        """タイ語のTTS音声を生成"""
        tts = gTTS(text=text, lang="th")
        tts.save(str(output_path))

    def _create_anki_package(self, notes: List[Dict[str, str]], media_files: List[Path]) -> Path:
        """Ankiパッケージを作成し、音声ファイルを含める"""
        # モデル定義
        model = Model(
            1607392319,
            "Thai Vocab Model",
            fields=[
                {"name": "thai"},
                {"name": "paiboon"},
                {"name": "meaning"},
                {"name": "audio"},
            ],
            templates=[{
                "name": "Card1",
                "qfmt": "{{thai}}<br>{{paiboon}}",
                "afmt": "{{FrontSide}}<hr>{{meaning}}<br>{{audio}}",
            }],
        )
        deck_id = abs(hash(self.deck_name)) % (2**31 - 1)
        deck = Deck(deck_id, self.deck_name)
        for note in notes:
            deck.add_note(Note(model, [
                note["thai"],
                note["paiboon"],
                note["meaning"],
                note["audio"],
            ]))
        # メディアファイルの絶対パスリスト
        media_paths = [str(p) for p in media_files if Path(p).exists()]
        output_path = self.output_dir / f"{self.deck_name.replace(' ', '_')}.apkg"
        pkg = Package(deck, media_files=media_paths)
        pkg.write_to_file(str(output_path))
        print(f"✅ Ankiパッケージ生成完了: {output_path} (メディアファイル数: {len(media_paths)})")
        return output_path

    def build(self, data: List[Dict[str, str]]) -> Path:
        """デッキをビルド"""
        # OCRデータを修正
        corrected_data = self._correct_paiboon(data)
        
        # 翻訳とTTS生成
        notes = []
        media_files = []
        
        for item in corrected_data:
            # 英語に翻訳
            english = self._translate_to_english(item["meaning"])
            
            # TTS音声を生成
            tts_path = self.temp_dir / f"{item['thai']}.mp3"
            self._generate_tts(item["thai"], tts_path)
            media_files.append(tts_path)
            
            # ノートを作成
            notes.append({
                "thai": item["thai"],
                "paiboon": item["paiboon"],
                "meaning": english,
                "audio": f"[sound:{tts_path.name}]"
            })
        
        # Ankiパッケージを作成
        return self._create_anki_package(notes, media_files)

    def cleanup(self):
        """一時ファイルを削除"""
        import shutil
        shutil.rmtree(self.temp_dir) 