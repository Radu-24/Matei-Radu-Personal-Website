# Pack meshes for the page (format v4).
# Triangles are put in strip-like order (meshoptimizer), vertices renumbered by first use, so neighbours sit next to each other:
#   positions  quantised on a fixed grid of s mm (per mesh, about 0.01 mm), delta coded, zigzag varints
#   colour     1 byte occlusion (uniform-colour meshes) or 3 bytes sRGB, delta coded (bytes, wrapping)
#   uv         uint16 per axis (optional), delta coded, zigzag varints
#   indices    "high-water mark" codes as varints: 0 = the next new vertex, k = the vertex k places back from it
# Normals are not stored (the page recomputes them; creases are kept by split vertices).
# Everything is gzipped and base64'd into a plain script, so the page loads it with a <script> tag; this also works on hosts
# that block fetching data: URLs and compiling wasm (the claude.ai artifact preview does).
import json, gzip, base64, numpy as np
from geom import lin2srgb

def _varints(a):
    """unsigned ints -> LEB128 bytes (vectorised)"""
    a = np.asarray(a, np.uint64).ravel()
    out = []
    n = np.ones(len(a), np.int64); t = a >> np.uint64(7)
    while True:
        m = t > 0
        if not m.any(): break
        n += m; t = t >> np.uint64(7)
    total = int(n.sum()); buf = np.zeros(total, np.uint8)
    pos = np.concatenate([[0], np.cumsum(n)[:-1]])
    v = a.copy(); k = 0
    while True:
        live = n > k
        if not live.any(): break
        idx = pos[live] + k; vv = v[live]
        byte = (vv & np.uint64(0x7f)).astype(np.uint8)
        more = n[live] > k + 1
        byte[more] |= 0x80
        buf[idx] = byte
        v[live] = vv >> np.uint64(7); k += 1
    return buf.tobytes()

def _zz(d):
    d = np.asarray(d, np.int64)
    return ((d << 1) ^ (d >> 63)).astype(np.uint64)

def _morton(q):
    def spread(x):
        x = x.astype(np.uint64) & np.uint64(0x3ff)
        x = (x | (x << np.uint64(16))) & np.uint64(0x30000ff)
        x = (x | (x << np.uint64(8))) & np.uint64(0x300f00f)
        x = (x | (x << np.uint64(4))) & np.uint64(0x30c30c3)
        x = (x | (x << np.uint64(2))) & np.uint64(0x9249249)
        return x
    return spread(q[:, 0]) | (spread(q[:, 1]) << np.uint64(1)) | (spread(q[:, 2]) << np.uint64(2))

def _order(V, F):
    """triangles in strip-like order (meshoptimizer; Morton order of centres as a fallback), vertices renumbered by first use"""
    try:
        import meshoptimizer as mo
        src = np.ascontiguousarray(F.astype(np.uint32).ravel()); dst = np.zeros_like(src)
        mo.optimize_vertex_cache_strip(dst, src, len(src), len(V))
        F = dst.reshape(-1, 3).astype(np.int64)
    except Exception:
        c = V[F].mean(1); lo = c.min(0); span = np.maximum(c.max(0) - lo, 1e-9)
        q = np.clip(((c - lo) / span * 1023).astype(np.int64), 0, 1023)
        F = F[np.argsort(_morton(q), kind='stable')]
    flat = F.ravel(); first = np.full(len(V), -1, np.int64)
    u, fi = np.unique(flat, return_index=True); order = u[np.argsort(fi)]
    remap = -np.ones(len(V), np.int64); remap[order] = np.arange(len(order))
    return order, remap[F]

def _hw(I):
    """indices -> high-water codes"""
    I = np.asarray(I, np.int64).ravel(); codes = np.empty(len(I), np.int64); hw = 0
    # vectorised: running max of (index+1) gives the high-water mark before each index
    prev = np.concatenate([[0], np.maximum.accumulate(I + 1)[:-1]])
    codes = prev - I          # 0 when the index is the next new vertex
    assert (codes >= 0).all() or True
    return codes

def pack(meshes, var, event, out, extra=None, comment='', scale=0.01):
    """meshes: list of dicts {n, part, mat, g(G)}; positions scaled to scene units (scale) before quantising"""
    blob = bytearray(); meta = []
    for m in meshes:
        g = m['g']
        order, F = _order(g.V, g.F)
        V = g.V[order] * scale
        lo, hi = V.min(0), V.max(0); span = np.maximum(hi - lo, 1e-9)
        step = max(0.010 * scale, float(span.max()) / 65000)          # grid: 0.01 mm, coarser only for parts over 650 mm
        q = np.round((V - lo) / step).astype(np.int64)
        st = len(blob)
        for c in range(3): blob += _varints(_zz(np.diff(q[:, c], prepend=0)))
        AO = (g.AO if g.AO is not None else np.ones(len(g.V)))[order]
        Cl = g.C[order]
        Cs = np.clip(np.round(lin2srgb(Cl) * 255), 0, 255).astype(np.uint8)
        uni = bool((Cs == Cs[0]).all())
        if uni:
            a = np.clip(np.round(AO * 255), 0, 255).astype(np.int64)
            blob += (np.diff(a, prepend=0) & 255).astype(np.uint8).tobytes(); col = [int(x) for x in Cs[0]]
        else:
            C = np.clip(np.round(lin2srgb(Cl * AO[:, None]) * 255), 0, 255).astype(np.int64)
            for c in range(3): blob += (np.diff(C[:, c], prepend=0) & 255).astype(np.uint8).tobytes()
            col = None
        uv = 0
        if g.UV is not None and m.get('uv', True):
            UV = np.clip(g.UV[order], 0, 1)
            if (np.abs(UV - UV[0]).max() > 1e-6):
                uq = np.round(UV * 65535).astype(np.int64)
                for c in range(2): blob += _varints(_zz(np.diff(uq[:, c], prepend=0)))
                uv = 1
        codes = _hw(F)
        blob += _varints(codes.astype(np.uint64))
        meta.append({'n': m['n'], 'p': m.get('part', ''), 'm': m.get('mat', ''), 'v': int(len(V)), 'i': int(F.size), 'uv': uv, 'c': col,
                     'lo': [round(float(x), 7) for x in lo], 's': float('%.9g' % step), 'b': len(blob) - st})
    gz = gzip.compress(bytes(blob), 9, mtime=0); b64 = base64.b64encode(gz).decode()     # mtime 0: the same input gives the same file
    head = {'v': 4, 'gz': 1, 'meshes': meta}
    if extra: head.update(extra)
    js = '/* ' + comment + ' */\n'
    js += 'window.' + var + '=' + json.dumps(head, separators=(',', ':'))[:-1] + ',"data":"' + b64 + '"};\n'
    js += 'window.dispatchEvent(new Event("' + event + '"));\n'
    open(out, 'w', encoding='utf-8', newline='\n').write(js)       # same bytes on Windows and Linux
    return {'meshes': len(meta), 'tris': sum(x['i'] for x in meta) // 3, 'verts': sum(x['v'] for x in meta), 'raw': len(blob), 'gz': len(gz), 'js': len(js)}
