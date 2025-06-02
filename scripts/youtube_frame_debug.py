import pathlib
from src.deck_builders.youtube import download_video, extract_frames
from PIL import Image
import numpy as np
import cv2
import shutil
from skimage.metrics import structural_similarity as ssim

def is_similar_image(img1: np.ndarray, img2: np.ndarray, threshold: float = 0.95) -> bool:
    img1 = cv2.cvtColor(cv2.resize(img1, (200, 200)), cv2.COLOR_RGB2GRAY)
    img2 = cv2.cvtColor(cv2.resize(img2, (200, 200)), cv2.COLOR_RGB2GRAY)
    score, _ = ssim(img1, img2, full=True)
    return score > threshold

def filter_unique_images(image_paths, threshold):
    unique = []
    unique_paths = []
    for path in image_paths:
        img = np.array(Image.open(path))
        if not any(is_similar_image(img, uimg, threshold) for uimg in unique):
            unique.append(img)
            unique_paths.append(path)
    return unique_paths

def main():
    url = input("YouTubeのURLを入力してください: ").strip()
    threshold = input("重複判定のしきい値を入力してください（例: 0.92、デフォルト0.95）: ").strip()
    threshold = float(threshold) if threshold else 0.99

    output_dir = pathlib.Path("data/output/frames_test")
    frames_dir = output_dir / "frames"
    unique_dir = output_dir / "unique"
    frames_dir.mkdir(parents=True, exist_ok=True)
    unique_dir.mkdir(parents=True, exist_ok=True)

    # 動画ダウンロード
    video_path = download_video(url, output_dir)
    # フレーム抽出
    frame_paths = extract_frames(video_path, frames_dir, interval=5)

    print(f"\n--- 全フレーム画像 ({len(frame_paths)}枚) ---")
    for p in frame_paths:
        print(p.resolve())

    # 重複排除
    unique_paths = filter_unique_images(frame_paths, threshold)
    for i, upath in enumerate(unique_paths):
        dst = unique_dir / f"unique_{i:04d}.jpg"
        shutil.copy(upath, dst)
        print(f"✔️ {dst.resolve()}")

    print(f"\n--- 重複排除後のユニーク画像 {len(unique_paths)}枚 ---")
    for p in unique_dir.glob("*.jpg"):
        print(p.resolve())

if __name__ == "__main__":
    main()