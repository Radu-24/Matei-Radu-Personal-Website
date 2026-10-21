# bake occlusion into the rover (both detail levels) and its atlas regions, then pack it for the page
# usage: pack_rover.py TOOLS_DIR [fast]   -> build/rover.js (lo), build/rover-hi.js (hi), work/atlas_rv.pkl (atlas + baked texel AO)
import sys, os, pickle, time, math, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from geom import *
from bake import Occ, shade_ao
import pack as PK
S = sys.argv[1]
FAST = len(sys.argv) > 2 and sys.argv[2] == 'fast'
t0 = time.time()
D = pickle.load(open(f'{S}/work/rover.pkl', 'rb'))
A = D['atlas']
LEVEL = None
def level(lev):
    global parts, wheels, meta, AY, RP, AZ, TX, PITCH, NL, LEVEL
    LEVEL = lev
    parts, wheels, meta = D[lev]
    AY, RP, AZ, TX, PITCH, NL = meta['AY'], meta['RP'], meta['AZ'], meta['TX'], meta['PITCH'], meta['NL']
level('hi')

def path_pt(s):
    """pin line of the track loop (y,z) and outward normal, s along the loop"""
    P = NL * PITCH; s = s % P; L = 2 * AZ; arc = math.pi * RP
    if s < L: return np.array([AY - RP, -AZ + s]), np.array([-1.0, 0])
    s -= L
    if s < arc:
        ph = -math.pi / 2 + s / RP; return np.array([AY + RP * math.sin(ph), AZ + RP * math.cos(ph)]), np.array([math.sin(ph), math.cos(ph)])
    s -= arc
    if s < L: return np.array([AY + RP, AZ - s]), np.array([1.0, 0])
    s -= L
    ph = math.pi / 2 + s / RP; return np.array([AY + RP * math.sin(ph), -AZ + RP * math.cos(ph)]), np.array([math.sin(ph), math.cos(ph)])

def link_frames(offset=0.0):
    out = []
    for k in range(NL):
        a, _ = path_pt(offset + k * PITCH); b, _ = path_pt(offset + (k + 1) * PITCH)
        c = (a + b) / 2; t = b - a; t /= np.linalg.norm(t)
        n = np.array([t[1], -t[0]])          # rotate tangent (y,z) by -90 deg -> outward for a loop run this way
        _, nm = path_pt(offset + (k + 0.5) * PITCH)
        if np.dot(n, nm) < 0: n = -n
        out.append((c, t, n))
    return out

def link_matrix(x, c, t, n):
    z = np.array([0, t[0], t[1]]); y = np.array([0, n[0], n[1]]); xx = np.cross(y, z)
    R = np.stack([xx, y, z], 1)
    return R, np.array([x, c[0], c[1]])

def run(out_js, texel, var, event):
    # ---- occluder scene: everything static + wheels + all links
    geo = []
    for k, c in parts.items():
        for m, g in c.p: geo.append(g)
    wheel_inst = []
    for w in meta['wheels']:
        R = rot(0, 0 if w['side'] > 0 else 180, 0)
        for m, g in wheels[w['w']].p:
            gg = g.copy().M(R, (w['x'], AY, w['z'])); geo.append(gg)
    links = link_frames(0.0)
    for side in (1, -1):
        for (c, t, n) in links:
            R, T = link_matrix(side * TX, c, t, n)
            for m, g in wheels['link'].p:
                geo.append(g.copy().M(R, T))
    allg = merge(geo)
    occ = Occ(allg.V, allg.F)
    # parts that are mostly seen taken apart get their occlusion from a smaller scene: the box and the cells from themselves
    # alone (the cells slide out of the box), the T101 and its motors without the printed chassis standing on the deck
    wgeo = geo[sum(len(c.p) for c in parts.values()):]
    LOW = ('chassis', 'motors')
    lowg = merge([g for k in LOW if k in parts for m, g in parts[k].p] + wgeo)
    occs = {'_low': Occ(lowg.V, lowg.F)}
    for k in ('battery', 'cells'):
        if k in parts:
            gg = merge([g for m, g in parts[k].p]); occs[k] = Occ(gg.V, gg.F)
    def occ_for(k): return occs.get(k) or (occs['_low'] if k in LOW else occ)
    print('occluder tris', len(allg.F), round(time.time() - t0, 1), 's')

    K = 24 if FAST else 56
    # ---- per-vertex AO for static parts
    stats = {}
    for k, c in parts.items():
        for m, g in c.p:
            ao = occ_for(k).ao(g.V, g.N, K=K, maxd=14.0, power=1.6)
            fl = 0.42 if m in ('metal', 'gold', 'satin') else 0.26
            g.AO = shade_ao(ao, floor=fl)
            fix = getattr(g, 'AOFIX', None)
            if fix is not None:
                mk = ~np.isnan(fix); g.AO[mk] = fix[mk]
            stats.setdefault(k + ':' + m, []).append(ao)
    if os.environ.get('AOSTAT'):
        for k, v in stats.items(): print('  ao', k, round(float(np.concatenate(v).mean()), 3))
    print('static AO', round(time.time() - t0, 1), 's')
    # ---- wheels / link in context
    def ao_local(name, R, T):
        for m, g in wheels[name].p:
            gw = g.copy().M(R, T)
            ao = occ.ao(gw.V, gw.N, K=K, maxd=12.0, power=1.6)
            g.AO = shade_ao(ao, floor=0.3)
    ao_local('sprocket', rot(0, 0, 0), (TX, AY, -AZ))
    ao_local('idler', rot(0, 0, 0), (TX, AY, AZ))
    c_, t_, n_ = links[NL // 6]
    R, T = link_matrix(TX, c_, t_, n_); ao_local('link', R, T)
    print('wheel AO', round(time.time() - t0, 1), 's')

    # ---- texel AO for the atlas regions
    step = 3 if FAST else 2
    for k, c in (parts.items() if texel else ()):
        for rec in c.bk:
            region, o, u, v, n = rec[:5]; hf = rec[5] if len(rec) > 5 else None
            x0, y0, x1, y1 = A.regions[region]
            w, h = x1 - x0, y1 - y0
            gw, gh = max(2, w // step), max(2, h // step)
            ii, jj = np.meshgrid((np.arange(gw) + 0.5) / gw, (np.arange(gh) + 0.5) / gh)
            P = o[None, :] + ii.ravel()[:, None] * u[None, :] + jj.ravel()[:, None] * v[None, :]
            if hf is not None: P[:, 1] += hf(P[:, 0], P[:, 2])          # the plate's facets
            N = np.tile(n / np.linalg.norm(n), (len(P), 1))
            ao = occ_for(k).ao(P, N, K=K, maxd=26.0 if region == 'plate' else 14.0, eps=0.08, power=1.8).reshape(gh, gw)
            from PIL import Image
            im = Image.fromarray((np.clip(ao, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
            A.ao[y0:y1, x0:x1] = shade_ao(np.asarray(im).astype(np.float32) / 255, floor=0.22)
    print('texel AO', round(time.time() - t0, 1), 's')

    # ---- pack: one mesh per (part, material); wheels and link on their own
    meshes = []
    for k, c in parts.items():
        by = {}
        for m, g in c.p: by.setdefault(m, []).append(g)
        for m, gs in by.items():
            meshes.append({'n': f'{k}:{m}', 'part': k, 'mat': m, 'g': merge(gs)})
    for k, c in wheels.items():
        by = {}
        for m, g in c.p: by.setdefault(m, []).append(g)
        for m, gs in by.items():
            meshes.append({'n': f'w_{k}:{m}', 'part': 'w_' + k, 'mat': m, 'g': merge(gs)})
    extra = {'track': {k: (round(v, 4) if isinstance(v, float) else v) for k, v in meta.items() if k != 'wheels'}, 'wheels': meta['wheels'], 'unit': 0.01}
    st = PK.pack(meshes, var, event, out_js, extra,
                 'DataLink Rover: the rover, part by part (T101 chassis, the printed plate and battery box from its CAD, Pi 5, Nano, sensors, cameras, fibre converter). '
                 'Per mesh, in triangle order: delta-coded positions, colours with baked occlusion, atlas uv, indices; gzipped, base64. datalink-3d.js unpacks it.')
    print(st, round(time.time() - t0, 1), 's')


level('hi'); run(f'{S}/build/rover-hi.js', True, 'DL_ROVER_HI', 'dl-rover-hi')
level('lo'); run(f'{S}/build/rover.js', False, 'DL_ROVER', 'dl-rover')
pickle.dump(A, open(f'{S}/work/atlas_rv.pkl', 'wb'))
print('atlas saved', round(time.time() - t0, 1), 's')
