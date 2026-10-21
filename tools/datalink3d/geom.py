# Small mesh toolkit for the DataLink rover / controller models.
# Units: millimetres. Axes: Y up, Z = rover front, X = rover's left (three.js, right handed).
import numpy as np, trimesh, manifold3d as mf
from manifold3d import Manifold, CrossSection

# tessellation quality: every round thing (cylinders, rounded boxes, tubes, splines, arcs) gets Q times its base segment count
Q = 1.0
def setQ(q):
    global Q
    Q = float(q)
def qs(n, lo=3):
    return max(lo, int(round(n * Q)))

def srgb2lin(c):
    c = np.asarray(c, np.float64)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def lin2srgb(c):
    c = np.clip(np.asarray(c, np.float64), 0, 1)
    return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)

def hexc(h):
    h = h.lstrip('#')
    if len(h) == 3: h = ''.join(ch * 2 for ch in h)
    return srgb2lin(np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]))

def rot(rx=0, ry=0, rz=0):
    """rotation matrix, degrees, applied X then Y then Z (extrinsic)"""
    a, b, c = np.radians([rx, ry, rz])
    X = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    Y = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    Z = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return Z @ Y @ X

class G:
    """vertices, faces, normals, uv (atlas), colour (linear rgb)"""
    def __init__(s, V, F, N=None, UV=None, C=None, AO=None):
        s.AO = None if AO is None else np.asarray(AO, np.float64).ravel()
        s.V = np.asarray(V, np.float64).reshape(-1, 3)
        s.F = np.asarray(F, np.int64).reshape(-1, 3)
        s.N = None if N is None else np.asarray(N, np.float64).reshape(-1, 3)
        s.UV = None if UV is None else np.asarray(UV, np.float64).reshape(-1, 2)
        s.C = None if C is None else np.asarray(C, np.float64).reshape(-1, 3)
        if s.N is None: s.normals()
    def normals(s):
        N = np.zeros_like(s.V)
        if len(s.F):
            t = s.V[s.F]; fn = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
            for k in range(3): np.add.at(N, s.F[:, k], fn)
        l = np.linalg.norm(N, axis=1, keepdims=True); l[l == 0] = 1
        s.N = N / l; return s
    def copy(s):
        return G(s.V.copy(), s.F.copy(), s.N.copy(), None if s.UV is None else s.UV.copy(), None if s.C is None else s.C.copy(), None if s.AO is None else s.AO.copy())
    def M(s, R=None, t=(0, 0, 0)):
        if R is not None:
            s.V = s.V @ np.asarray(R).T; s.N = s.N @ np.asarray(R).T
            if np.linalg.det(R) < 0: s.F = s.F[:, ::-1]
        s.V = s.V + np.asarray(t, np.float64); return s
    def t(s, x=0, y=0, z=0): return s.M(None, (x, y, z))
    def r(s, rx=0, ry=0, rz=0): return s.M(rot(rx, ry, rz))
    def sc(s, x, y=None, z=None):
        y = x if y is None else y; z = x if z is None else z
        S = np.diag([x, y, z]); s.V = s.V @ S
        N = s.N @ np.linalg.inv(S); s.N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        if x * y * z < 0: s.F = s.F[:, ::-1]
        return s
    def col(s, c):
        c = hexc(c) if isinstance(c, str) else np.asarray(c, np.float64)
        s.C = np.tile(c, (len(s.V), 1)); return s
    def bounds(s): return s.V.min(0), s.V.max(0)

def perm(g, order):
    """cyclic axis permutation (a rotation): new axis i takes old axis order[i]"""
    g.V = g.V[:, order]; g.N = g.N[:, order]
    if (order[0], order[1], order[2]) not in [(0, 1, 2), (1, 2, 0), (2, 0, 1)]: g.F = g.F[:, ::-1]
    return g

def side_col(g, col):
    """textured meshes: untextured vertices (sides) get `col`, textured ones stay white"""
    c = hexc(col) if isinstance(col, str) else np.asarray(col, np.float64)
    if g.C is None: g.C = np.ones((len(g.V), 3))
    if g.UV is None: g.C[:] = c; return g
    m = g.UV[:, 0] < 0
    g.C[m] = c; g.C[~m] = 1.0
    return g

def merge(gs):
    gs = [g for g in gs if g is not None and len(g.F)]
    if not gs: return None
    V, F, N, UV, C, AO, o = [], [], [], [], [], [], 0
    anyuv = any(g.UV is not None for g in gs); anyao = any(g.AO is not None for g in gs)
    for g in gs:
        V.append(g.V); F.append(g.F + o); N.append(g.N); o += len(g.V)
        UV.append(g.UV if g.UV is not None else np.full((len(g.V), 2), -1.0))
        C.append(g.C if g.C is not None else np.ones((len(g.V), 3)))
        AO.append(g.AO if g.AO is not None else np.ones(len(g.V)))
    return G(np.concatenate(V), np.concatenate(F), np.concatenate(N), np.concatenate(UV) if anyuv else None, np.concatenate(C), np.concatenate(AO) if anyao else None)

def smooth(V, F, crease=35):
    """split vertices at edges sharper than `crease` degrees, smooth normals elsewhere"""
    m = trimesh.Trimesh(V, F, process=True)
    if crease >= 179:
        m2 = m; m2.fix_normals() if False else None
        return G(m2.vertices, m2.faces, np.asarray(m2.vertex_normals))
    if crease <= 0:
        m2 = m.copy(); m2.unmerge_vertices()
        fn = np.repeat(np.asarray(m.face_normals), 3, axis=0)
        return G(m2.vertices, m2.faces, fn.reshape(-1, 3))
    m2 = trimesh.graph.smooth_shade(m, angle=np.radians(crease), facet_minarea=None)
    return G(m2.vertices, m2.faces, np.asarray(m2.vertex_normals))

def from_manifold(M_, crease=35):
    m = M_.to_mesh()
    V = np.asarray(m.vert_properties)[:, :3]; F = np.asarray(m.tri_verts)
    return smooth(V, F, crease)

# ---------- primitives ----------
def box(sx, sy, sz, center=(0, 0, 0)):
    """flat shaded box, 24 vertices"""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    V, F, N = [], [], []
    for ax in range(3):
        for sg in (-1, 1):
            n = np.zeros(3); n[ax] = sg
            u = np.zeros(3); v = np.zeros(3)
            u[(ax + 1) % 3] = 1; v[(ax + 2) % 3] = 1
            if sg < 0: u, v = v, u
            h = np.array([hx, hy, hz])
            c = n * h
            pts = [c - u * h - v * h, c + u * h - v * h, c + u * h + v * h, c - u * h + v * h]
            b = len(V)
            V += pts; N += [n] * 4; F += [[b, b + 1, b + 2], [b, b + 2, b + 3]]
    return G(np.array(V) + center, F, np.array(N))

def rbox(sx, sy, sz, r, seg=3, center=(0, 0, 0)):
    """rounded box (all edges rounded with radius r), smooth normals"""
    seg = qs(seg, 1)
    r = min(r, sx / 2 - 1e-4, sy / 2 - 1e-4, sz / 2 - 1e-4)
    if r <= 1e-4: return box(sx, sy, sz, center)
    h = np.array([sx, sy, sz]) / 2; inner = h - r
    # face grids: each axis uses points [-1, ..rounding.., -k, k, ..rounding.., 1]
    ts = np.concatenate([-1 + (1 - np.cos(np.linspace(0, np.pi / 2, seg + 1))) * 0, []])
    def axis_pts(hh, ii):
        a = np.linspace(0, np.pi / 2, seg + 1)
        side = ii + r * np.sin(a)  # from inner to h
        pts = np.concatenate([-side[::-1], side])
        return np.unique(np.round(pts, 9))
    P = [axis_pts(h[i], inner[i]) for i in range(3)]
    V, F = [], []
    for ax in range(3):
        a1, a2 = (ax + 1) % 3, (ax + 2) % 3
        for sg in (-1, 1):
            U, W = P[a1], P[a2]
            b = len(V)
            for j, w in enumerate(W):
                for i, u in enumerate(U):
                    p = np.zeros(3); p[ax] = sg * h[ax]; p[a1] = u; p[a2] = w
                    V.append(p)
            nu = len(U)
            for j in range(len(W) - 1):
                for i in range(nu - 1):
                    q0 = b + j * nu + i; q1 = q0 + 1; q2 = q0 + nu + 1; q3 = q0 + nu
                    if sg > 0: F += [[q0, q1, q2], [q0, q2, q3]]
                    else: F += [[q0, q2, q1], [q0, q3, q2]]
    V = np.array(V)
    c = np.clip(V, -inner, inner); d = V - c; l = np.linalg.norm(d, axis=1, keepdims=True); l[l == 0] = 1
    n = d / l
    V2 = c + n * r
    # faces with zero-length offsets (flat face interiors): normal = face axis
    flat = (np.linalg.norm(V - c, axis=1) < 1e-9)
    m = trimesh.Trimesh(V2, F, process=True)
    g = G(m.vertices, m.faces)
    g.normals()
    return g.t(*center)

def cyl(r, h, seg=32, r2=None, caps=True, axis='y', center=(0, 0, 0), bevel=0.0, smooth_side=True):
    """cylinder / frustum along axis, centred; optional small bevel on both rims"""
    seg = qs(seg, 6)
    r2 = r if r2 is None else r2
    a = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    ca, sa = np.cos(a), np.sin(a)
    V, F, N = [], [], []
    rings = []
    if bevel > 0:
        rings = [(-h / 2, r - bevel, -1), (-h / 2 + bevel, r, 0), (h / 2 - bevel, r2, 0), (h / 2, r2 - bevel, 1)]
    else:
        rings = [(-h / 2, r, 0), (h / 2, r2, 0)]
    # side
    slope = (r - r2) / h
    for k in range(len(rings) - 1):
        (y0, ra, _), (y1, rb, _) = rings[k], rings[k + 1]
        b = len(V)
        for i in range(seg):
            dy = (rb - ra); nr = np.array([ca[i], 0, sa[i]]) * (y1 - y0) - np.array([0, 1, 0]) * dy
            nr = nr / np.linalg.norm(nr)
            V += [[ra * ca[i], y0, ra * sa[i]], [rb * ca[i], y1, rb * sa[i]]]
            N += [nr, nr]
        for i in range(seg):
            j = (i + 1) % seg
            F += [[b + 2 * i, b + 2 * i + 1, b + 2 * j + 1], [b + 2 * i, b + 2 * j + 1, b + 2 * j]]
    if caps:
        for (y, rr, sg) in [(rings[0][0], rings[0][1], -1), (rings[-1][0], rings[-1][1], 1)]:
            b = len(V); V.append([0, y, 0]); N.append([0, sg, 0])
            for i in range(seg): V.append([rr * ca[i], y, rr * sa[i]]); N.append([0, sg, 0])
            for i in range(seg):
                j = (i + 1) % seg
                F += [[b, b + 1 + j, b + 1 + i]] if sg > 0 else [[b, b + 1 + i, b + 1 + j]]
    g = G(V, F, N)
    if not smooth_side:
        g = smooth(g.V, g.F, 0)
    # orient: default axis y. F winding: check outward
    g = fix_winding(g)
    if axis == 'x': g.r(0, 0, -90)
    elif axis == 'z': g.r(90, 0, 0)
    return g.t(*center)

def fix_winding(g):
    """make faces agree with the stored normals"""
    t = g.V[g.F]; fn = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    vn = g.N[g.F].sum(1)
    flip = (fn * vn).sum(1) < 0
    g.F[flip] = g.F[flip][:, ::-1]
    return g

def torus(R, r, seg=48, seg2=16, center=(0, 0, 0)):
    seg = qs(seg, 8); seg2 = qs(seg2, 6)
    a = np.linspace(0, 2 * np.pi, seg, endpoint=False); b = np.linspace(0, 2 * np.pi, seg2, endpoint=False)
    V, N, F = [], [], []
    for i in range(seg):
        for j in range(seg2):
            c = np.array([np.cos(a[i]), 0, np.sin(a[i])])
            n = c * np.cos(b[j]) + np.array([0, 1, 0]) * np.sin(b[j])
            V.append(c * R + n * r); N.append(n)
    for i in range(seg):
        for j in range(seg2):
            i2, j2 = (i + 1) % seg, (j + 1) % seg2
            q0, q1, q2, q3 = i * seg2 + j, i2 * seg2 + j, i2 * seg2 + j2, i * seg2 + j2
            F += [[q0, q2, q1], [q0, q3, q2]]
    return fix_winding(G(V, F, N)).t(*center)

def sphere(r, seg=24, center=(0, 0, 0)):
    seg = qs(seg, 6)
    m = trimesh.creation.uv_sphere(r, count=[seg, seg * 2 // 2 + 1])
    return G(m.vertices, m.faces, m.vertex_normals).t(*center)

# ---------- 2D -> 3D ----------
def cs_rect(w, d, r=0.0, cx=0.0, cz=0.0):
    c = CrossSection.square([w, d], center=True)
    if r > 0:
        c = CrossSection.square([max(w - 2 * r, 1e-3), max(d - 2 * r, 1e-3)], center=True).offset(r, mf.JoinType.Round, 2.0, qs(24, 8))
    return c.translate([cx, cz])

def cs_circle(r, cx=0.0, cz=0.0, seg=32):
    return CrossSection.circle(r, qs(seg, 8)).translate([cx, cz])

def cs_poly(pts):
    return CrossSection([np.asarray(pts, np.float64)], mf.FillRule.Positive)

def extrude_cs(cs, h, y0=0.0, crease=35):
    """extrude a cross section (x,z plane) upward along +Y from y0"""
    M_ = Manifold.extrude(cs, h)  # along +Z of manifold coordinates; (x,y)->(x,z)
    m = M_.to_mesh(); V = np.asarray(m.vert_properties)[:, :3]
    V = np.stack([V[:, 0], V[:, 2] + y0, V[:, 1]], 1)
    F = np.asarray(m.tri_verts)[:, ::-1]   # mirror (y<->z swap) flips handedness
    return smooth(V, F, crease)

def man_extrude(cs, h, y0=0.0):
    """manifold extruded along +Y (x,z cross section)"""
    M_ = Manifold.extrude(cs, h)
    # rotate manifold: its z -> our y, its y -> our z  (x stays). This is a mirror; use rotation about x by -90 then flip
    M_ = M_.rotate([-90, 0, 0])   # (x,y,z) -> (x, z, -y)
    M_ = M_.mirror([0, 0, 1])     # z -> -z  => (x, z, y)
    return M_.translate([0, y0, 0])

def man_box(sx, sy, sz, c=(0, 0, 0)):
    return Manifold.cube([sx, sy, sz], True).translate(list(c))

def man_cyl(r, h, axis='y', c=(0, 0, 0), seg=32, r2=None):
    M_ = Manifold.cylinder(h, r, r if r2 is None else r2, qs(seg, 6), True)  # along z
    if axis == 'y': M_ = M_.rotate([-90, 0, 0])
    elif axis == 'x': M_ = M_.rotate([0, 90, 0])
    return M_.translate(list(c))

def tube(pts, r, seg=10, cap=True, absolute=False):
    """round cable along a polyline (smoothed by caller); absolute=True keeps seg as given (no quality scaling)"""
    seg = seg if absolute else qs(seg, 5)
    P = np.asarray(pts, np.float64)
    n = len(P)
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    # parallel transport frames
    up = np.array([0, 1, 0.0]) if abs(T[0][1]) < 0.9 else np.array([1, 0, 0.0])
    Nn = np.cross(T[0], up); Nn /= np.linalg.norm(Nn)
    frames = []
    for i in range(n):
        if i > 0:
            v = np.cross(T[i - 1], T[i]); sv = np.linalg.norm(v)
            if sv > 1e-9:
                v /= sv; ang = np.arccos(np.clip(np.dot(T[i - 1], T[i]), -1, 1))
                Nn = Nn * np.cos(ang) + np.cross(v, Nn) * np.sin(ang) + v * np.dot(v, Nn) * (1 - np.cos(ang))
        B = np.cross(T[i], Nn); frames.append((Nn.copy(), B))
    a = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    V, N, F = [], [], []
    for i in range(n):
        Nn_, B = frames[i]
        for k in range(seg):
            d = Nn_ * np.cos(a[k]) + B * np.sin(a[k]); V.append(P[i] + d * r); N.append(d)
    for i in range(n - 1):
        for k in range(seg):
            k2 = (k + 1) % seg
            q0, q1, q2, q3 = i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k
            F += [[q0, q2, q1], [q0, q3, q2]]
    g = fix_winding(G(V, F, N))
    if cap:
        for i, sg in ((0, -1), (n - 1, 1)):
            b = len(g.V); cV = [P[i]] + [g.V[i * seg + k] for k in range(seg)]; cN = [T[i] * sg] * (seg + 1)
            cF = [[b, b + 1 + k, b + 1 + (k + 1) % seg] for k in range(seg)]
            cg = fix_winding(G(cV, np.array(cF) - b, cN)); cg.F += 0
            g = merge([g, cg])
    return g

def ribbon(pts, w, t, up_hint=(0, 1, 0)):
    """flat cable (FPC) following a path, width w, thickness t; its flat side faces up_hint where possible"""
    P = np.asarray(pts, np.float64); n = len(P)
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True)
    up = np.asarray(up_hint, np.float64)
    gs = []
    V, N, F = [], [], []
    for i in range(n):
        side = np.cross(T[i], up);
        if np.linalg.norm(side) < 1e-6: side = np.cross(T[i], [1, 0, 0])
        side /= np.linalg.norm(side); nn = np.cross(side, T[i])
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            V.append(P[i] + side * sx * w / 2 + nn * sy * t / 2)
            N.append(nn * sy * 0.9 + side * sx * 0.1)
    for i in range(n - 1):
        for k in range(4):
            k2 = (k + 1) % 4
            q0, q1, q2, q3 = i * 4 + k, i * 4 + k2, (i + 1) * 4 + k2, (i + 1) * 4 + k
            F += [[q0, q2, q1], [q0, q3, q2]]
    g = G(V, F, N); g.N /= np.linalg.norm(g.N, axis=1, keepdims=True)
    return fix_winding(smooth(g.V, g.F, 40))

def spline(pts, n=40, absolute=False):
    """Catmull-Rom through control points"""
    n = n if absolute else qs(n, 4)
    P = np.asarray(pts, np.float64)
    if len(P) < 3: return np.linspace(P[0], P[-1], n)
    P = np.vstack([P[0] * 2 - P[1], P, P[-1] * 2 - P[-2]])
    out = []
    segs = len(P) - 3
    for s in range(segs):
        p0, p1, p2, p3 = P[s:s + 4]
        for t in np.linspace(0, 1, max(2, n // segs), endpoint=(s == segs - 1)):
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    return np.array(out)

# ---------- uv helpers ----------
def uv_top(g, rect, x0, x1, z0, z1, ny=1, flipu=False, flipv=False, thr=0.9):
    """vertices whose normal points along +Y (or -Y) get atlas UVs from their (x,z); rect = (u0,v0,u1,v1) in 0..1 atlas space"""
    if g.UV is None: g.UV = np.full((len(g.V), 2), -1.0)
    sel = (g.N[:, 1] * ny) > thr
    s = (g.V[sel, 0] - x0) / (x1 - x0); t = (g.V[sel, 2] - z0) / (z1 - z0)
    if flipu: s = 1 - s
    if flipv: t = 1 - t
    u0, v0, u1, v1 = rect
    g.UV[sel, 0] = u0 + s * (u1 - u0); g.UV[sel, 1] = v0 + t * (v1 - v0)
    return g

def uv_face(g, rect, axis_n, o, uax, vax, thr=0.9):
    """generic planar mapping for vertices whose normal ~ axis_n: uv from dot with uax/vax (vectors spanning the face)"""
    if g.UV is None: g.UV = np.full((len(g.V), 2), -1.0)
    sel = (g.N @ np.asarray(axis_n, np.float64)) > thr
    d = g.V[sel] - np.asarray(o)
    uax = np.asarray(uax, np.float64); vax = np.asarray(vax, np.float64)
    s = d @ uax / (uax @ uax); t = d @ vax / (vax @ vax)
    u0, v0, u1, v1 = rect
    g.UV[sel, 0] = u0 + s * (u1 - u0); g.UV[sel, 1] = v0 + t * (v1 - v0)
    return g
