#!/usr/bin/env python3
import argparse
import pathlib
from ..deck_builders.image_table import process_image_table

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

    if args.image:
        if not args.image.exists():
            print(f"❌ 指定された画像が見つかりません: {args.image}")
            return
        if not args.image.name.startswith("temp_"):
            input_dir = args.image.parent
            process_image_table(input_dir, args.deck_name, args.generate_media)
    else:
        if not args.input_dir.exists():
            print(f"❌ 指定されたディレクトリが見つかりません: {args.input_dir}")
            return
        process_image_table(args.input_dir, args.deck_name, args.generate_media)

if __name__ == "__main__":
    main() 