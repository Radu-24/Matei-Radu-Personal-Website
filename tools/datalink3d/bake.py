# ambient occlusion baking (embree): per vertex for geometry, per texel for atlas regions
import numpy as np, trimesh, math, time

def hemi_dirs(K, seed=1):
    """K cosine-weighted directions around +Z (stratified)"""
    rng = np.random.default_rng(seed)
    n = int(math.ceil(math.sqrt(K)))
    out = []
    for i in range(n):
        for j in range(n):
            u1 = (i + rng.random()) / n; u2 = (j + rng.random()) / n
            r = math.sqrt(u1); th = 2 * math.pi * u2
            out.append([r * math.cos(th), r * math.sin(th), math.sqrt(max(0, 1 - u1))])
    out = np.array(out[:K]); return out

def frames(N):
    """tangent frames for normals N (M,3)"""
    a = np.where(np.abs(N[:, [0]]) < 0.9, np.array([[1, 0, 0]]), np.array([[0, 1, 0]]))
    T = np.cross(N, a); T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)
    B = np.cross(N, T)
    return T, B

class Occ:
    def __init__(s, V, F):
        s.mesh = trimesh.Trimesh(V, F, process=False)
        s.ri = trimesh.ray.ray_pyembree.RayMeshIntersector(s.mesh)
    def ao(s, P, N, K=40, maxd=25.0, eps=0.06, power=1.0, chunk=200000, seed=3):
        P = np.asarray(P, np.float64); N = np.asarray(N, np.float64)
        N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
        N[np.linalg.norm(N, axis=1) < 0.5] = [0, 1, 0]
        D0 = hemi_dirs(K, seed)
        T, B = frames(N)
        M = len(P); res = np.zeros(M)
        rng = np.random.default_rng(seed)
        per = max(1, chunk // K)
        for a in range(0, M, per):
            b = min(M, a + per); m = b - a
            ang = rng.random(m) * 2 * math.pi            # random spin per point (decorrelates the pattern)
            ca, sa = np.cos(ang)[:, None], np.sin(ang)[:, None]
            Tt = T[a:b] * ca + B[a:b] * sa; Bt = np.cross(N[a:b], Tt)
            dirs = (D0[None, :, 0:1] * Tt[:, None, :] + D0[None, :, 1:2] * Bt[:, None, :] + D0[None, :, 2:3] * N[a:b][:, None, :]).reshape(-1, 3)
            orig = np.repeat(P[a:b] + N[a:b] * eps, K, axis=0)
            loc, ir, it = s.ri.intersects_location(orig, dirs, multiple_hits=False)
            occ = np.zeros(m * K)
            if len(ir):
                d = np.linalg.norm(loc - orig[ir], axis=1)
                w = np.clip(1 - d / maxd, 0, 1) ** power
                occ[ir] = w
            res[a:b] = 1 - occ.reshape(m, K).mean(1)
        return res

def shade_ao(ao, floor=0.18, gamma=1.15):
    return floor + (1 - floor) * np.clip(ao, 0, 1) ** gamma
