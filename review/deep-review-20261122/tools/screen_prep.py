# -*- coding: utf-8 -*-
"""검출기 A·B·C 후보 판정용 꾸러미: 한자음 옮김 쌍 전부(빈도 무관)와 가타카나 음차 쌍 전부.
각 쌍마다 예문 하나(성적 구간 칸은 예문에서 뺌)."""
import os, sys, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import *
rows = {r['id']: r for r in load_corpus()}
ad = set(json.load(open(os.path.join(DATA, 'adult.json'), encoding='utf-8'))['ids'])
def snip(t, key, w=14):
    t = flat(t); i = t.find(key)
    if i < 0: return t[:40]
    return t[max(0, i - w): i + len(key) + w]
def pick(ids, kk, jk):
    for i in ids:
        if i not in ad: return i, snip(rows[i]['ko'], kk), snip(rows[i]['ja'], jk)
    return ids[0] + '*', '(성적 구간)', ''
carry = json.load(open(os.path.join(DATA, 'carry_pairs.json'), encoding='utf-8'))
with open(os.path.join(DATA, 'screen_carry.tsv'), 'w', encoding='utf-8') as fo:
    fo.write('no\tw(일본어)\tr(한국어로 옮긴 한자음)\t구어빈도\t칸수\t예칸\t한국어 예문\t일본어 예문\n')
    for n, p in enumerate(carry, 1):
        i, k, j = pick(p['ids'], p['r'], p['w'])
        fo.write('%d\t%s\t%s\t%d\t%d\t%s\t%s\t%s\n' % (n, p['w'], p['r'], p['freq'], p['n'], i, k, j))
kata = [p for p in json.load(open(os.path.join(DATA, 'kata_pairs.json'), encoding='utf-8')) if p['ko'] != '∅']
with open(os.path.join(DATA, 'screen_kata.tsv'), 'w', encoding='utf-8') as fo:
    fo.write('no\t가나\t한국어 음차\t구어빈도\t칸수\t예칸\t한국어 예문\t일본어 예문\n')
    for n, p in enumerate(kata, 1):
        i, k, j = pick(p['ids'], p['ko'], p['kana'])
        fo.write('%d\t%s\t%s\t%d\t%d\t%s\t%s\t%s\n' % (n, p['kana'], p['ko'], p['freq'], p['n'], i, k, j))
print(len(carry), len(kata))
