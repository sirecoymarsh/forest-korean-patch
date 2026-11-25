import os
SRC = r'Y:\AI\forest-4k\src'
ex = set(l.split('\t')[0].strip() for l in open(r'Y:\AI\forest-4k\exclude.txt', encoding='utf-8') if l.strip() and not l.startswith('#'))
keys = [a + '/' + n[:-4] for a in ['grpe', 'grpo_bg', 'grpo_bu', 'grpo_f', 'grpo_ci'] for n in sorted(os.listdir(os.path.join(SRC, a))) if n.endswith('.png')]
keys = [k for k in keys if k not in ex]
open(r'Y:\AI\forest-4k\batch_list.txt', 'w').write('\n'.join(keys))
done = [k for k in keys if os.path.exists(os.path.join(r'Y:\AI\forest-4k\ai', *k.split('/')) + '.png')]
print('targets', len(keys), 'excluded', sorted(ex), 'already', len(done))
