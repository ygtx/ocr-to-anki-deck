import pathlib
from typing import Optional
from PIL import Image, UnidentifiedImageError, ImageOps

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