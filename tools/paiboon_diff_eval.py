import csv
import sys
from pathlib import Path

# 入力: 正解リストと生成リストのファイルパス
# フォーマット: タイ語, Paiboon, 意味（カラム名は何でもOK、1行目はヘッダ）

def load_vocab(path):
    """CSV/TSVから {thai: paiboon} のdictを作成"""
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
    """Paiboon表記の一致率と差分リストを返す"""
    total = 0
    match = 0
    diffs = []
    for thai, gold_paiboon in gold.items():
        pred_paiboon = pred.get(thai)
        if pred_paiboon is None:
            diffs.append((thai, gold_paiboon, None, '未出力'))
        elif gold_paiboon == pred_paiboon:
            match += 1
        else:
            diffs.append((thai, gold_paiboon, pred_paiboon, '不一致'))
        total += 1
    return match, total, diffs

def main():
    if len(sys.argv) != 3:
        print('使い方: python paiboon_diff_eval.py 正解リスト.csv 生成リスト.csv')
        sys.exit(1)
    gold_path, pred_path = sys.argv[1:3]
    gold = load_vocab(gold_path)
    pred = load_vocab(pred_path)
    match, total, diffs = compare_vocab(gold, pred)
    print(f'✅ Paiboon表記一致率: {match}/{total} ({match/total*100:.1f}%)')
    if diffs:
        print('\n❌ 差分一覧:')
        print('タイ語\t正解Paiboon\t生成Paiboon\t種別')
        for thai, gold_p, pred_p, reason in diffs:
            print(f'{thai}\t{gold_p}\t{pred_p or "(なし)"}\t{reason}')
    else:
        print('全て一致！')

if __name__ == '__main__':
    main() 