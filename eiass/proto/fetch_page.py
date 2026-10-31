import sys, cv2
sys.path.insert(0, '.')
from core import site
cd, seq, page = sys.argv[1], sys.argv[2], int(sys.argv[3])
E = site.Eiass()
d = E.detail(cd, seq)
ov = next(f for f in d['files'] if __import__('re').search(r'사업\s*의?\s*개요', f['name']))
sid = E.streamdocs_id(ov['seq'], ov['name'])
img = E.render(sid, page)
cv2.imwrite(f'proto/{cd}_p{page}.png', img[:, :, ::-1]); print(img.shape)
