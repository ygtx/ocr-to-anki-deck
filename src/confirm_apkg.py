import zipfile, sqlite3, csv, pathlib, sys, json, os

def extract_and_show_apkg(apkg_path):
    """apkgファイルの内容を確認"""
    print(f"📦 パッケージ内容の確認: {apkg_path}")
    
    # 一時ディレクトリを作成
    temp_dir = pathlib.Path("/tmp/anki_inspect")
    temp_dir.mkdir(exist_ok=True)
    
    with zipfile.ZipFile(apkg_path) as z:
        # アーカイブ内のファイル一覧を表示
        print("\n📋 アーカイブ内のファイル:")
        for info in z.infolist():
            print(f"  - {info.filename} ({info.file_size:,} bytes)")
        
        # メディアファイルを抽出
        media_dir = temp_dir / "media"
        media_dir.mkdir(exist_ok=True)
        
        # media.jsonを抽出して解析
        if "media" in z.namelist():
            media_json = json.loads(z.read("media").decode('utf-8'))
            print("\n🎵 メディアファイル一覧:")
            for filename, hash_value in media_json.items():
                print(f"  - {filename} (hash: {hash_value})")
                # メディアファイルを抽出
                try:
                    z.extract(hash_value, media_dir)
                    print(f"    ✅ 抽出成功: {media_dir / hash_value}")
                except KeyError:
                    print(f"    ❌ ファイルが見つかりません: {hash_value}")
        
        # collection.anki2を抽出して解析
        z.extract("collection.anki2", temp_dir)
        conn = sqlite3.connect(temp_dir / "collection.anki2")
        cur = conn.cursor()
        
        # カラム名を取得
        cur.execute("PRAGMA table_info(notes)")
        columns = [col[1] for col in cur.fetchall() if col[1] in ['id', 'flds']]
        
        # データを取得
        cur.execute("SELECT id, flds FROM notes")
        rows = cur.fetchall()
        
        # TSVファイルに出力
        with open("deck_dump.tsv", "w", newline='') as f:
            writer = csv.writer(f, delimiter="\t")
            writer.writerow(columns)
            for _id, flds in rows:
                writer.writerow([_id] + flds.split("\x1f"))
        
        print("\n✅ deck_dump.tsv にエクスポートしました")
        print(f"📂 メディアファイルは {media_dir} に展開されました")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("使い方: python confirm_apkg.py deck.apkg")
        sys.exit(1)
    
    apkg_path = sys.argv[1]
    if not pathlib.Path(apkg_path).exists():
        print(f"❌ ファイルが見つかりません: {apkg_path}")
        sys.exit(1)
    
    extract_and_show_apkg(apkg_path)