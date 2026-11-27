"""Vineyard flags from the real BLT row: places where the canopy is thin on BOTH faces of the row.

Reads $BLT_WORK/{geo.npz, tex_*.jpg, alpha_*.png, seen_*.npy} from build_row.py and writes
$BLT_WORK/site/data/flags.json plus $BLT_WORK/site/data/ev/*.jpg (original photos with the flag boxed).

Rule (no training, no ground truth):
  canopy cover = share of the 0.55-1.35 m band, in a 0.5 m slice of the row, where the photos show leaves
  (not a see-through gap and not sky), counted only over spots a photo covered.
  A slice is flagged when its cover is under half of that face's median cover, on both faces, and at least
  half of the band was covered by photos on each face. Adjacent slices join into one flag.
Seeing the same gap from both alleys rules out most single-view effects (a leaf edge, glare, one bad frame).
A flag is a place to walk to, not a diagnosis.
"""
import os, sys, json, glob
import numpy as np, cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pts import qmat, Rbc, tbc, D, cam

W = os.environ.get('BLT_WORK', '/tmp/blt_work/')
OUT = W + 'site/data/'; os.makedirs(OUT + 'ev', exist_ok=True)
T = 0.0025; BIN = 0.5; ZB = (0.55, 1.35); MIN_SEEN = 0.5; FRAC = 0.5
SKIP = set(range(0, 5))  # frames 0-4 show the operator; never used
g = np.load(W + 'geo.npz'); U = g['U']; N = g['N']
K = np.array(cam['K_rgb_scaled']).reshape(3, 3)
metas = {int(f[-9:-5]): json.load(open(f)) for f in sorted(glob.glob(D + 'meta/*.json'))}
SIDES = {'A': range(5, 93), 'B': range(114, 206)}
row_n = float((np.median(g['A_n']) + np.median(g['B_n'])) / 2)

prof = {}
for side in 'AB':
    tex = cv2.imread(W + f'tex_{side}.jpg').astype(float); al = cv2.imread(W + f'alpha_{side}.png', 0)
    seen = np.load(W + f'seen_{side}.npy')
    s0 = float(g[f'{side}_s0']); th, tw = al.shape
    z = 1.55 - (np.arange(th) + 0.5) * T; band = (z > ZB[0]) & (z < ZB[1])
    s = s0 + (np.arange(tw) + 0.5) * T
    rows = {}
    for b0 in np.arange(np.floor(s.min()), s.max(), BIN):
        c = (s >= b0) & (s < b0 + BIN)
        sn = seen[band][:, c]; so = al[band][:, c] > 127
        rows[round(float(b0), 2)] = dict(seen=float(sn.mean()), cover=float(so.sum() / max(sn.sum(), 1)))
    ok = [r['cover'] for r in rows.values() if r['seen'] >= MIN_SEEN]
    prof[side] = dict(rows=rows, median=float(np.median(ok)), n_face=float(np.median(g[f'{side}_n'])))

bins = sorted(set(prof['A']['rows']) & set(prof['B']['rows']))
hit = []
for b in bins:
    a, bb = prof['A']['rows'][b], prof['B']['rows'][b]
    if a['seen'] >= MIN_SEEN and bb['seen'] >= MIN_SEEN and a['cover'] < FRAC * prof['A']['median'] and bb['cover'] < FRAC * prof['B']['median']:
        hit.append(b)
groups = []
for b in hit:
    if groups and abs(b - groups[-1][-1] - BIN) < 1e-6: groups[-1].append(b)
    else: groups.append([b])


def project(i, X):
    p = metas[i]['pose_map']; Rwb = qmat(p['orientation_xyzw']); twb = np.array(p['position'])
    pc = ((X - twb) @ Rwb - tbc) @ Rbc
    return np.c_[K[0, 0] * pc[:, 0] / pc[:, 2] + K[0, 2], K[1, 1] * pc[:, 1] / pc[:, 2] + K[1, 2]], pc[:, 2]


def evidence(fid, side, sa, sb):
    """Most head-on frame of this face for the slice, with the slice boxed."""
    nf = prof[side]['n_face']; sc = (sa + sb) / 2
    cands = [i for i in SIDES[side] if i not in SKIP]
    i = min(cands, key=lambda k: abs(np.array(metas[k]['pose_map']['position'][:2]) @ U - sc))
    X = np.array([[s * U[0] + nf * N[0], s * U[1] + nf * N[1], z] for s, z in [(sa, ZB[0]), (sb, ZB[0]), (sb, ZB[1]), (sa, ZB[1])]])
    uv, zc = project(i, X)
    img = cv2.imread(D + f'rgb/{i:04d}.jpg')
    cv2.polylines(img, [np.round(uv).astype(np.int32).reshape(-1, 1, 2)], True, (0, 0, 0), 6, cv2.LINE_AA)
    cv2.polylines(img, [np.round(uv).astype(np.int32).reshape(-1, 1, 2)], True, (0, 225, 255), 3, cv2.LINE_AA)
    img = cv2.resize(img, (960, 540), interpolation=cv2.INTER_AREA)
    fn = f'ev/{fid}_{side}.jpg'; cv2.imwrite(OUT + fn, img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    m = metas[i]
    return dict(file=fn, frame=m['frame'], side=side, camera_m=round(float(np.median(zc)), 2),
                box_px=[[round(float(x) * 0.75, 1), round(float(y) * 0.75, 1)] for x, y in uv],
                time_utc=__import__('datetime').datetime.utcfromtimestamp(m['timestamp_unix']).strftime('%H:%M:%S'))


flags = []
for k, gr in enumerate(groups, 1):
    sa, sb = gr[0], gr[-1] + BIN; sc = (sa + sb) / 2
    fid = f'v{k}'
    near = min((i for i in metas if i not in SKIP), key=lambda i: abs(np.array(metas[i]['pose_map']['position'][:2]) @ U - sc) + abs(np.array(metas[i]['pose_map']['position'][:2]) @ N - row_n))
    gps = metas[near]['gps_filtered']
    flags.append(dict(
        id=fid, s0=sa, s1=sb, length_m=round(sb - sa, 2),
        cover_A=round(float(np.mean([prof['A']['rows'][b]['cover'] for b in gr])), 3),
        cover_B=round(float(np.mean([prof['B']['rows'][b]['cover'] for b in gr])), 3),
        lat=round(gps['lat'], 7), lon=round(gps['lon'], 7), gps_note='robot position from the nearest photo, in the alley next to the spot',
        photos=[evidence(fid, 'A', sa, sb), evidence(fid, 'B', sa, sb)]))
    print(fid, sa, sb, flags[-1]['cover_A'], flags[-1]['cover_B'], [p['frame'] for p in flags[-1]['photos']])

seenA = [r for r in prof['A']['rows'].values() if r['seen'] >= MIN_SEEN]; seenB = [r for r in prof['B']['rows'].values() if r['seen'] >= MIN_SEEN]
s_cov = [b for b in bins if prof['A']['rows'][b]['seen'] >= MIN_SEEN and prof['B']['rows'][b]['seen'] >= MIN_SEEN]
out = dict(
    rule=f'Canopy cover (share of the {ZB[0]}-{ZB[1]} m band where the photos show leaves rather than a gap or sky) under '
         f'{int(FRAC * 100)}% of the face median, on both faces of the row, in {BIN} m slices',
    band_m=ZB, bin_m=BIN, median_cover={'A': round(prof['A']['median'], 3), 'B': round(prof['B']['median'], 3)},
    slices_checked=len(s_cov), row_checked_m=round(len(s_cov) * BIN, 1), photos_used=len(SIDES['A']) + len(SIDES['B']),
    profile={side: [[b, round(r['cover'], 3), round(r['seen'], 2)] for b, r in sorted(prof[side]['rows'].items())] for side in 'AB'},
    flags=flags,
    not_assessed='Vine health, yield and disease. No method has been tested against the vineyard\'s own records, so there is no accuracy figure.')
json.dump(out, open(OUT + 'flags.json', 'w'))
print(len(flags), 'flags;', len(s_cov), 'slices checked on both faces; medians', out['median_cover'])
