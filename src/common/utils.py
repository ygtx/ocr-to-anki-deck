import re

def sanitize_filename(name: str) -> str:
    """ファイル名を安全な形式に変換する"""
    # スラッシュが含まれる場合はスラッシュより前だけを使う
    if '/' in name:
        name = name.split('/')[0]
    # それ以外のファイル名に使えない文字をアンダースコアに置換
    return re.sub(r'[\\:*?"<>|]', '_', name) 