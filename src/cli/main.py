#!/usr/bin/env python3
import argparse
import pathlib
from ..deck_builders.image_table import process_image_table
from ..deck_builders.youtube import process_youtube_video, YouTubeDeckBuilder, download_video
import click
from pathlib import Path

@click.group()
def cli():
    """Anki OCR - YouTube動画や画像からAnkiデッキを生成"""
    pass

@cli.command()
@click.argument("url")
@click.option("--output-dir", "-o", default="data/output/decks", help="出力ディレクトリ")
@click.option("--deck-name", "-n", help="デッキ名（デフォルト: 動画タイトル）")
@click.option("--frame-interval", "-i", default=1, help="フレーム抽出間隔（秒）")
@click.option("--ssim-threshold", "-s", default=0.95, help="SSIMしきい値（0-1）")
@click.option("--no-paiboon-correction", is_flag=True, help="Paiboon最終修正（ChatGPT一括投げ）を行わない")
def youtube(url: str, output_dir: str, deck_name: str, frame_interval: int, ssim_threshold: float, no_paiboon_correction: bool):
    """YouTube動画からAnkiデッキを生成"""
    try:
        # 出力ディレクトリを作成
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # 動画をダウンロード
        video_path = download_video(url, output_path)
        
        # デッキ名が指定されていない場合は動画タイトルを使用
        if not deck_name:
            deck_name = video_path.stem
        
        # デッキビルダーを作成
        builder = YouTubeDeckBuilder(
            output_dir=str(output_path),
            deck_name=deck_name,
            ssim_threshold=ssim_threshold,
            use_paiboon_correction=not no_paiboon_correction
        )
        
        # デッキをビルド
        apkg_path = builder.build(video_path, frame_interval)
        
        print(f"\n✅ 生成完了: {apkg_path}")
        
    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        raise click.Abort()
    finally:
        # 一時ファイルを削除
        builder.cleanup()

def main():
    parser = argparse.ArgumentParser(description="Anki OCR - タイ語の語学学習用Ankiデッキ生成ツール")
    
    # 入力ソースのグループ
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument("--input-dir", type=pathlib.Path, help="入力画像ディレクトリ")
    input_group.add_argument("--image", type=pathlib.Path, help="入力画像ファイル")
    input_group.add_argument("--youtube", type=str, help="YouTube動画のURL")
    
    # 共通オプション
    parser.add_argument("--deck-name", type=str, default="Thai Vocab", help="デッキ名")
    parser.add_argument("--generate-media", action="store_true", help="音声ファイルを生成")
    
    # YouTube専用オプション
    parser.add_argument("--frame-interval", type=int, default=5, help="フレーム抽出間隔（秒）")
    parser.add_argument("--ssim-threshold", type=float, default=0.99, help="SSIMによる重複排除のしきい値（0.90〜0.99推奨、デフォルト0.99）")
    parser.add_argument("--no-paiboon-correction", action="store_true", help="Paiboon最終修正（ChatGPT一括投げ）を行わない")
    
    args = parser.parse_args()
    
    # 入力ディレクトリの作成
    if args.input_dir:
        args.input_dir.mkdir(parents=True, exist_ok=True)
    
    # 出力ディレクトリの作成
    output_dir = pathlib.Path("data/output/decks")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 処理の実行
    if args.youtube:
        # 明示的にYouTubeDeckBuilderを使う
        builder = YouTubeDeckBuilder(
            output_dir=str(output_dir),
            deck_name=args.deck_name,
            ssim_threshold=args.ssim_threshold,
            use_paiboon_correction=not args.no_paiboon_correction
        )
        video_path = download_video(args.youtube, output_dir)
        apkg_path = builder.build(video_path, args.frame_interval)
        print(f"\n✅ 生成完了: {apkg_path}")
        builder.cleanup()
    else:
        process_image_table(
            args.input_dir or args.image.parent,
            args.deck_name,
            args.generate_media
        )

if __name__ == "__main__":
    cli() 