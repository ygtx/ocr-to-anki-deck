import zipfile
import sqlite3
import csv
import sys
from pathlib import Path
import shutil

def extract_apkg_to_csv(apkg_path, out_csv):
    apkg_path = Path(apkg_path)
    temp_dir = out_csv.parent / ('apkg_extract_' + apkg_path.stem)
    temp_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(apkg_path, 'r') as z:
        z.extract('collection.anki2', temp_dir)
    conn = sqlite3.connect(temp_dir / 'collection.anki2')
    cur = conn.cursor()
    cur.execute('PRAGMA table_info(notes)')
    columns = [col[1] for col in cur.fetchall()]
    cur.execute('SELECT flds FROM notes')
    rows = cur.fetchall()
    field_count = len(rows[0][0].split('\x1f')) if rows else 0
    field_names = ['thai', 'paiboon', 'meaning'] + [f'field{i+4}' for i in range(field_count-3)]
    with open(out_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(field_names[:field_count])
        for (flds,) in rows:
            fields = flds.split('\x1f')
            writer.writerow(fields[:field_count])
    print(f'✅ Extracted: {apkg_path} → {out_csv}')

def load_vocab(path):
    ext = Path(path).suffix.lower()
    delimiter = '\t' if ext == '.tsv' else ','
    vocab = {}
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            thai = row.get('thai') or row.get('タイ語')
            paiboon = row.get('paiboon') or row.get('Paiboon')
            if thai and paiboon:
                vocab[thai.strip()] = paiboon.strip()
    return vocab

def compare_vocab(gold, pred):
    total = 0
    match = 0
    diffs = []
    for thai, gold_paiboon in gold.items():
        pred_paiboon = pred.get(thai)
        if pred_paiboon is None:
            diffs.append((thai, gold_paiboon, None, 'not_generated'))
        elif gold_paiboon == pred_paiboon:
            match += 1
        else:
            diffs.append((thai, gold_paiboon, pred_paiboon, 'mismatch'))
        total += 1
    return match, total, diffs

def merge_and_write_diffs_tsv(new_diffs, out_path):
    # 既存データを読み込み（積み上げ式）
    existing = []
    if out_path.exists():
        with open(out_path, encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            for row in reader:
                existing.append(row)
    # 新しいデータを追加（積み上げ）
    for row in new_diffs:
        existing.append({
            'thai': row[0],
            'gold_paiboon': row[1],
            'generated_paiboon': row[2] if row[2] is not None else '',
            'type': row[3]
        })
    # generated_paiboonが重複する例外定義を削除（新しいものを優先）
    seen = {}
    for row in reversed(existing):
        key = row['generated_paiboon']
        if key and key not in seen:
            seen[key] = row
    # generated_paiboonが空のものも残す
    for row in reversed(existing):
        key = row['generated_paiboon']
        if not key:
            seen[(row['thai'], row['gold_paiboon'])] = row
    # 出力
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['thai', 'gold_paiboon', 'generated_paiboon', 'type'], delimiter='\t')
        writer.writeheader()
        for row in reversed(list(seen.values())):
            writer.writerow(row)

def main():
    if len(sys.argv) != 3:
        print('Usage: python apkg_paiboon_diff.py correct.apkg generated.apkg')
        sys.exit(1)
    apkg_gold, apkg_pred = sys.argv[1:3]
    # 一時ディレクトリ
    tmp_dir = Path('tmp/paiboon_diff_eval')
    tmp_dir.mkdir(parents=True, exist_ok=True)
    csv_gold = tmp_dir / 'correct.csv'
    csv_pred = tmp_dir / 'generated.csv'
    extract_apkg_to_csv(apkg_gold, csv_gold)
    extract_apkg_to_csv(apkg_pred, csv_pred)
    gold = load_vocab(csv_gold)
    pred = load_vocab(csv_pred)
    match, total, diffs = compare_vocab(gold, pred)
    if total == 0:
        print('❌ No data found in the correct (gold) file. Please check the file contents.')
        shutil.rmtree(tmp_dir)
        sys.exit(1)
    out_path = Path('data/output/system/paiboon_diff.tsv')
    merge_and_write_diffs_tsv(diffs, out_path)
    print(f'✅ Paiboon match rate: {match}/{total} ({match/total*100:.1f}%)')
    print(f'❗ Diff results written to: {out_path.resolve()}')
    if diffs:
        print(f'❌ {len(diffs)} differences found (see TSV file above)')
    else:
        print('All matched!')
    shutil.rmtree(tmp_dir)

if __name__ == '__main__':
    main() 