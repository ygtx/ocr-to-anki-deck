import os
import json
import tempfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from openai import OpenAI
from gtts import gTTS
from deep_translator import MyMemoryTranslator
from genanki import Model, Note, Deck, Package
import csv
import re
import time
import random

class BaseDeckBuilder:
    def __init__(self, output_dir: str, deck_name: str, use_paiboon_correction: bool = True):
        self.output_dir = Path(output_dir)
        self.deck_name = deck_name
        self.client = OpenAI()
        self.temp_dir = Path(tempfile.mkdtemp())
        self.use_paiboon_correction = use_paiboon_correction
        
    def build_rules(self) -> str:
        """Paiboon修正プロンプトを動的に生成（例外パターンはTSVから自動挿入）"""
        # 例外パターンのデフォルト
        default_exceptions = [
            ("ขอบคุณ", "khòp khun"),
            ("ขอโทษ", "khǎw thôot"),
            ("ไม่เป็นไร", "mây pen ray"),
            ("ยินดีที่ได้รู้จัก", "yin dii thîi dây rúu càk"),
            ("ชื่ออะไร", "chûʉ aray"),
            ("เป็นยังไงบ้าง", "pen yàŋŋay bâaŋ"),
            ("เรื่อย ๆ", "rʉ̂ay rʉ̂ay"),
        ]
        # TSVから例外パターンを抽出
        tsv_path = Path("data/output/system/paiboon_diff.tsv")
        exceptions = []
        seen = set()
        if tsv_path.exists():
            with open(tsv_path, encoding="utf-8") as f:
                reader = csv.DictReader(f, delimiter="\t")
                for row in reader:
                    if row["type"] == "mismatch" and row["gold_paiboon"]:
                        key = (row["thai"], row["gold_paiboon"])
                        if key not in seen:
                            exceptions.append(key)
                            seen.add(key)
        # 既存例外パターンがtsvに無ければ追記
        new_lines = []
        for thai, paiboon in default_exceptions:
            if (thai, paiboon) not in seen:
                new_lines.append({
                    "thai": thai,
                    "gold_paiboon": paiboon,
                    "generated_paiboon": "",
                    "type": "mismatch"
                })
                exceptions.append((thai, paiboon))
        if new_lines:
            # 追記
            write_header = not tsv_path.exists()
            with open(tsv_path, "a", encoding="utf-8", newline='') as f:
                writer = csv.DictWriter(f, fieldnames=["thai", "gold_paiboon", "generated_paiboon", "type"], delimiter="\t")
                if write_header:
                    writer.writeheader()
                for row in new_lines:
                    writer.writerow(row)
        # 例外パターン文言生成
        if exceptions:
            exception_lines = [f"   - {thai} → {paiboon}" for thai, paiboon in exceptions]
            exception_text = "\n".join(exception_lines)
        else:
            exception_text = "   - 例外パターンなし"
        # ルール本体
        rules = f"""
あなたはタイ文字のPaiboon式ローマ字表記のエキスパートです。以下のルールに従って、Paiboon表記の誤りを修正してください。

【修正手順】
1. まず、例外リストに完全一致する "thai" フィールドがある場合は、"paiboon" を例外リストに書かれている正解に必ず置き換えてください（微妙な一致ではなく、完全一致ベース）。
2. 例外に一致しない場合は、以下のルールに厳密に従って修正を行ってください（自由表現は一切禁止）。

【Paiboon 修正ルール】
- 声調記号は母音の上に1回のみ配置（例：khòòp → khòp）
- 長母音の重複は禁止（例：khòòp → khòp）
- 母音・子音記号はPaiboon標準を用いる（例：ʉ̂ʉ → chûʉ または ue）
- 短母音（ă）と声調母音（ǎ）は明確に区別
- "mây" は常に第3声（yの上に重アクセント）
- 文脈に応じて "dâi"（can）と "dây"（できた）を使い分ける（意味の曖昧な場合は "dây" を優先）
- 最終子音が "b" の場合は "p" に変換（例：khòb khun → khòp khun）
- 音節の再構成は禁止（例：yàŋŋay → yanjay はNG）

【例外リスト（完全一致適用）】
{exception_text}

【入力形式】
{{
  "thai": "タイ語の文字列",
  "paiboon": "OCRで得られたPaiboon式ローマ字",
  "meaning": "日本語の意味"
}}

【出力形式】
{{
  "thai": "（変更なし）",
  "paiboon": "修正後のPaiboon表記（ルールまたは例外に従って修正）",
  "meaning": "（変更なし）"
}}

⚠️ ルールに従っていない修正、創造的な出力、フォーマット逸脱は一切禁止です。
"""
        return rules

    def _save_ocr_data(self, data: List[Dict[str, str]]) -> Path:
        """OCRデータを一時ファイルに保存"""
        temp_file = self.temp_dir / "ocr_data.json"
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return temp_file

    def paiboon_normalize(self, paiboon: str, entry: dict = None) -> str:
        import re
        # 代表的なIPA誤OCR補正
        ipa_map = {
            'nɯ̀ng': 'nʉ̀ng',
            'sʉ̀ʉ': 'sʉʉ',
            # 必要に応じて追加
        }
        for wrong, correct in ipa_map.items():
            paiboon = paiboon.replace(wrong, correct)
        # 最終b→p
        paiboon = re.sub(r'b$', 'p', paiboon)
        # mâyは常に第3声
        paiboon = re.sub(r'mây', 'mây', paiboon)
        # dâi/dâyは意味で分けるが、曖昧ならdây
        paiboon = re.sub(r'dâi', 'dây', paiboon)
        return paiboon

    def _correct_paiboon(self, data: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """タイ語をベースにしたPaiboon式ローマ字の修正（Function Calling+リトライ1回+詳細ログ+content None対応+タイ文字判定）"""
        if not data:
            print("⚠️ 修正対象のデータが空です")
            return []
        corrected_data = []
        rules = self.build_rules()
        function_schema = {
            "name": "fix_paiboon",
            "description": "Paiboon 表記を修正して返す",
            "parameters": {
                "type": "object",
                "properties": {
                    "thai": {"type": "string"},
                    "paiboon": {"type": "string"},
                    "meaning": {"type": "string"}
                },
                "required": ["thai", "paiboon", "meaning"]
            }
        }
        for entry in data:
            print(f"\n---\n[処理開始] 入力データ: {json.dumps(entry, ensure_ascii=False)}")
            # Thaiフィールドにタイ文字が1文字も含まれない場合はスキップ
            if not re.search(r'[\u0E00-\u0E7F]', entry.get("thai", "")):
                print(f"⚠️ Thaiフィールドにタイ文字が含まれていないためスキップ: {json.dumps(entry, ensure_ascii=False)}")
                corrected_data.append(entry)
                continue
            if not entry.get("paiboon"):
                print(f"⚠️ paiboon=None or empty entry: {json.dumps(entry, ensure_ascii=False)}")
                corrected_data.append(entry)
                continue
            print(f"[Paiboon正規化前] {entry['paiboon']}")
            norm_entry = dict(entry)
            norm_entry["paiboon"] = self.paiboon_normalize(norm_entry["paiboon"], norm_entry)
            print(f"[Paiboon正規化後] {norm_entry['paiboon']}")
            single_entry = {
                "thai": norm_entry["thai"],
                "paiboon": norm_entry["paiboon"],
                "meaning": norm_entry["meaning"]
            }
            print(f"[ChatGPT補正前] {json.dumps(single_entry, ensure_ascii=False)}")
            retry = 0
            max_retry = 1
            while retry < max_retry:
                try:
                    response = self.client.chat.completions.create(
                        model="gpt-4o",
                        messages=[
                            {"role": "system", "content": rules},
                            {"role": "user", "content": json.dumps(single_entry, ensure_ascii=False)}
                        ],
                        temperature=0,
                        top_p=1,
                        max_tokens=128,
                        tools=[{"type": "function", "function": function_schema}],
                        tool_choice="auto"
                    )
                    msg = response.choices[0].message
                    if getattr(msg, "tool_calls", None):
                        args = msg.tool_calls[0].function.arguments
                        result = json.loads(args) if isinstance(args, str) else args
                    else:
                        if msg.content is None:
                            raise ValueError("OpenAI応答のcontentがNoneです")
                        json_match = re.search(r'\{[\s\S]*\}', msg.content)
                        if json_match:
                            result = json.loads(json_match.group(0))
                        else:
                            raise ValueError("No JSON found in response content")
                    if isinstance(result, dict) and all(k in result for k in ["thai", "paiboon", "meaning"]):
                        print(f"[ChatGPT補正後] {json.dumps(result, ensure_ascii=False)}")
                        corrected_data.append(result)
                        break
                    else:
                        raise ValueError("Result missing required keys")
                except Exception as e:
                    print(f"⚠️ エラーが発生: {str(e)} (リトライ{retry+1}/{max_retry})")
                    retry += 1
                    if retry == max_retry:
                        print(f"⚠️ 最終エラー詳細: {str(e)} 入力: {json.dumps(single_entry, ensure_ascii=False)}")
                        corrected_data.append(entry)
                        break
        if not all(isinstance(item, dict) and all(k in item for k in ["thai", "paiboon", "meaning"]) for item in corrected_data):
            print("⚠️ 戻り値の型が不正です。元のデータを返します。")
            return data
        return corrected_data

    def _translate_to_english(self, text: str) -> str:
        """日本語から英語に翻訳（レートリミット時は10秒待って1回リトライ）"""
        translator = MyMemoryTranslator(source="ja-JP", target="en-GB")
        try:
            result = translator.translate(text)
            time.sleep(0.5)  # Google翻訳APIのレートリミット回避
            return result
        except Exception as e:
            msg = str(e)
            if "too many requests" in msg.lower() or "you made too many requests" in msg.lower():
                print("⚠️ Google翻訳APIのレートリミットに達しました。10秒待機してリトライします。")
                time.sleep(10)
                try:
                    result = translator.translate(text)
                    time.sleep(0.5)
                    return result
                except Exception as e2:
                    print(f"❌ 再試行でも失敗: {e2}")
                    raise
            else:
                raise

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
                {"name": "Thai"},
                {"name": "Phonetic"},
                {"name": "English"},
                {"name": "Audio"},
            ],
            templates=[
                {
                    "name": "Card1",
                    "qfmt": "<h1>{{Phonetic}}</h1>\n<h2>{{Thai}}</h2>\n<hr>\n<h1>{{Audio}}</h1>",
                    "afmt": "<h1>{{Phonetic}}</h1>\n<h2>{{English}}</h2>\n<h2>{{Thai}}</h2>\n<hr>\n<h1>{{Audio}}</h1>",
                },
                {
                    "name": "Card2",
                    "qfmt": "<h1>{{English}}</h1>",
                    "afmt": "<h1>{{English}}</h1>\n<h2>{{Phonetic}}</h2>\n<h2>{{Thai}}</h2>\n<hr>\n<h1>{{Audio}}</h1>",
                },
            ],
            css="""h1, h2 { text-align: center; }"""
        )
        deck_id = abs(hash(self.deck_name)) % (2**31 - 1)
        deck = Deck(deck_id, self.deck_name)
        for note in notes:
            deck.add_note(Note(model, [
                note["Thai"],
                note["Phonetic"],
                note["English"],
                note["Audio"],
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
        # 空のデータやnull値をフィルタリング
        valid_data = []
        for item in data:
            if (item.get("thai") and item.get("paiboon") and 
                isinstance(item["thai"], str) and isinstance(item["paiboon"], str) and
                item["thai"].strip() and item["paiboon"].strip()):
                valid_data.append(item)
            else:
                print(f"⚠️ 無効なデータをスキップ: {item}")

        if not valid_data:
            print("❌ 有効なデータがありません")
            return None

        print(f"\n📝 デッキ生成対象件数: {len(valid_data)} 件")

        # OCRデータを修正
        if self.use_paiboon_correction:
            corrected_data = self._correct_paiboon(valid_data)
        else:
            corrected_data = valid_data

        # 翻訳とTTS生成
        notes = []
        media_files = []
        total = len(corrected_data)
        for idx, item in enumerate(corrected_data, 1):
            try:
                print(f"[進捗] {idx}/{total} ({(idx/total)*100:.1f}%) - thai: {item['thai']}")
                # 英語に翻訳
                english = self._translate_to_english(item["meaning"])
                # TTS音声を生成
                tts_path = self.temp_dir / f"{item['thai']}.mp3"
                self._generate_tts(item["thai"], tts_path)
                media_files.append(tts_path)
                # ノートを作成
                notes.append({
                    "Thai": item["thai"],
                    "Phonetic": item["paiboon"],
                    "English": english,
                    "Audio": f"[sound:{tts_path.name}]"
                })
            except Exception as e:
                print(f"⚠️ ノート生成中にエラーが発生: {str(e)}")
                continue

        if not notes:
            print("❌ 有効なノートが生成できませんでした")
            return None

        # Ankiパッケージを作成
        return self._create_anki_package(notes, media_files)

    def cleanup(self):
        """一時ファイルを削除"""
        import shutil
        shutil.rmtree(self.temp_dir) 