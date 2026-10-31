import sys, json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
from core import site
import cv2, numpy as np
sys.path.insert(0, 'proto')
import ocr_labels as O
E = site.Eiass()
sid = 'ZV3Y7nqn1py3KtV6_fmHNuXMoNOfvlW8zLpR0gE0dig'
img = E.render(sid, 11)
print(img.shape)
cv2.imwrite('proto/p11.png', img[:, :, ::-1])
toks = O.ocr_tiles(img)
print(len(toks), 'tokens')
jb = O.jibun_tokens(toks)
print(len(jb), 'jibun-like')
for j in jb: print(j['txt'], int(j['x']), int(j['y']), j['conf'])
json.dump({'img': list(img.shape), 'jibun': jb, 'all': toks}, open('proto/ocr_p11.json', 'w', encoding='utf-8'), ensure_ascii=False)
