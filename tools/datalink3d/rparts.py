# Controller parts that the CAD file does not have (or only as a placeholder), built to datasheet sizes.
# Units mm. Every builder works in its own frame and returns a Comp (see rover.py); the caller places it.
import math, numpy as np
from geom import *
from atlas import *
from rover import Comp, smd, ecap, header_male, wtex, GOLD, TIN, BRASS, COPPER, BLUE_POT, STEEL, CAP_SLV, CAP_TOP

CHROME = '#d6dade'; NICKEL = '#bfc4ca'; GREEN_SW = '#1f9d55'; RED_CAP = '#c42a2a'; TERM_GREEN = '#2f9f52'
WIRE_RED = '#d23a26'; WIRE_BLK = '#141414'; WIRE_ORG = '#e8862a'; WIRE_YEL = '#e3c12b'; WIRE_WHT = '#e8e8e2'; WIRE_BLU = '#2f5fd0'
WIRE_PUR = '#7a4cc0'; WIRE_GRN = '#2f9e4a'


def revolve(profile, seg=48):
    """solid of revolution about +Y from a (radius, y) outline (counter-clockwise, radius >= 0)"""
    cs = CrossSection([np.asarray(profile, np.float64)], mf.FillRule.Positive)
    M_ = Manifold.revolve(cs, qs(seg, 12))          # profile y -> z
    return M_.rotate([-90, 0, 0])                    # z -> y


def threaded_rod(r_maj, r_min, pitch, y0, y1, seg=64, per_pitch=8):
    """outside surface of a threaded rod along +Y (open at both ends): trapezoid thread on a helix, chamfered ends"""
    seg = qs(seg, 24); ny = int(math.ceil((y1 - y0) / pitch * per_pitch)) + 1
    ys = np.linspace(y0, y1, ny); a = np.linspace(0, 2 * np.pi, seg, endpoint=False)
    A_, Y_ = np.meshgrid(a, ys)
    ph = ((Y_ - y0) / pitch - A_ / (2 * np.pi)) % 1.0
    d = np.abs(ph - 0.5)
    prof = np.clip((7 / 16 - d) / (6 / 16), 0, 1)
    R_ = r_min + (r_maj - r_min) * prof
    end = np.minimum(Y_ - y0, y1 - Y_)
    R_ = np.minimum(R_, r_min - 0.15 + end * 1.4)
    V = np.stack([R_ * np.cos(A_), Y_, R_ * np.sin(A_)], -1).reshape(-1, 3)
    F = []
    for j in range(ny - 1):
        for i in range(seg):
            i2 = (i + 1) % seg
            q0, q1, q2, q3 = j * seg + i, j * seg + i2, (j + 1) * seg + i2, (j + 1) * seg + i
            F += [[q0, q2, q1], [q0, q3, q2]]
    g = G(V, np.array(F))
    # outward normals
    t = g.V[g.F]; fn = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]); c = t.mean(1)
    out = (fn[:, 0] * c[:, 0] + fn[:, 2] * c[:, 2]) < 0
    g.F[out] = g.F[out][:, ::-1]; g.normals()
    return g


def hex_nut(af, t, bore, seg=48):
    """hex nut, across-flats af, thickness t, chamfered on both faces; along +Y from 0 to t"""
    R = af / math.sqrt(3); ch = min(0.42, t * 0.3)
    hexa = CrossSection([np.array([[R * math.cos(math.radians(30 + 60 * k)), R * math.sin(math.radians(30 + 60 * k))] for k in range(6)])])
    prism = Manifold.extrude(hexa, t).rotate([-90, 0, 0])            # extrusion z 0..t -> y 0..t
    cham = revolve([(0, 0), (af / 2 * 0.93, 0), (R * 1.05, ch), (R * 1.05, t - ch), (af / 2 * 0.93, t), (0, t)], seg)
    nut = (prism ^ cham) - man_cyl(bore, t * 3, 'y', (0, t / 2, 0), seg)
    return from_manifold(nut, 30)


def washer(ro, ri, t, seg=48):
    w = man_cyl(ro, t, 'y', (0, t / 2, 0), seg) - man_cyl(ri, t * 3, 'y', (0, t / 2, 0), seg)
    return from_manifold(w, 30)


# ------------------------------------------------------------------ MTS-102 mini toggle switch
def mts102(body=GREEN_SW, cap=RED_CAP, tilt=-15.0, wall=(3.6, 6.1)):
    """SPDT mini toggle switch (MTS-102 class): 13 x 7.9 mm body, M6 x 0.75 bushing, three solder lugs.
    Frame: +Y is the bushing axis, y = 0 where the bushing leaves the metal frame; the body is below, the lever above.
    wall = (inner face, outer face) of the panel it goes through, along +Y (nuts and washers sit against it)."""
    c = Comp()
    # plastic housing (the coloured part) and the narrower base the lugs come out of
    c.add('plastic', rbox(12.5, 7.7, 7.84, 0.55, 2, (0, -0.8 - 7.7 / 2, 0)), body)
    c.add('plastic', rbox(11.4, 0.6, 6.9, 0.25, 1, (0, -8.5 - 0.3 + 0.05, 0)), body)
    # moulded ribs on the wide faces
    for sz in (-1, 1):
        for k in (-1, 1):
            c.add('plastic', rbox(0.5, 5.6, 0.3, 0.12, 1, (k * 3.9, -4.8, sz * (3.92 + 0.1))), body)
    # chrome frame: top plate + two clinched tabs down the short sides
    c.add('metal', rbox(13.0, 0.8, 7.84, 0.2, 1, (0, -0.4, 0)), CHROME)
    for sx in (-1, 1):
        c.add('metal', rbox(0.55, 5.4, 4.0, 0.15, 1, (sx * 6.52, -0.8 - 2.7, 0)), CHROME)
        c.add('metal', cyl(0.75, 0.25, 16, axis='x', center=(sx * 6.84, -3.4, 0)), CHROME)
    # three solder lugs (tinned) with holes
    for x in (-4.7, 0.0, 4.7):
        L = Manifold.cube([2.0, 4.6, 0.5], True).translate([x, -8.8 - 2.3, 0]) - Manifold.cylinder(2.0, 0.6, 0.6, qs(20, 8), True).translate([x, -12.0, 0])
        L = L - Manifold.cube([0.7, 1.0, 1.0], True).translate([x - 1.0, -13.3, 0]) - Manifold.cube([0.7, 1.0, 1.0], True).translate([x + 1.0, -13.3, 0])
        c.add('metal', from_manifold(L, 30), TIN)
    # bushing: M6 x 0.75, 8.7 long, bored
    rod = threaded_rod(3.0, 2.6, 0.75, 0.0, 8.7, 48); c.add('metal', rod, NICKEL)
    c.add('metal', from_manifold(man_cyl(2.62, 0.3, 'y', (0, 8.55, 0), 48) - man_cyl(1.75, 1.0, 'y', (0, 8.55, 0), 40), 30), NICKEL)
    c.add('plastic', cyl(1.76, 1.2, 32, center=(0, 8.05, 0), caps=False), '#3a3c40')
    # nuts and washers on both sides of the panel
    wi, wo = wall
    if wi > 2.6:
        lw = washer(4.6, 3.05, 0.5); lw.t(0, wi - 0.5, 0); c.add('metal', lw, NICKEL)
        n1 = hex_nut(8.0, 1.8, 3.0); n1.t(0, wi - 0.5 - 1.8, 0); c.add('metal', n1, CHROME)
    w2 = washer(4.75, 3.05, 0.5); w2.t(0, wo, 0); c.add('metal', w2, NICKEL)
    n2 = hex_nut(8.0, 1.8, 3.0); n2.t(0, wo + 0.5, 0); c.add('metal', n2, CHROME)
    # lever: pivot ball in the bushing mouth, tapered chrome shaft, red cap
    lev = Comp()
    lev.add('metal', sphere(1.62, 28, (0, 8.45, 0)), CHROME)
    lev.add('metal', cyl(1.3, 9.0, 32, r2=1.15, center=(0, 8.6 + 4.5, 0), caps=False), CHROME)
    capm = revolve([(0, 0), (1.95, 0), (2.05, 0.35), (2.0, 1.0), (1.86, 6.6), (1.7, 7.4), (1.25, 7.95), (0.6, 8.2), (0, 8.25)], 40)
    capg = from_manifold(capm, 25); capg.t(0, 18.7 - 8.25, 0); lev.add('rubber', capg, cap)
    R_t = rot(tilt, 0, 0)
    for _, g in lev.p: g.t(0, -8.45, 0).M(R_t).t(0, 8.45, 0)
    c.extend(lev)
    return c


# ------------------------------------------------------------------ 30 mm fan (3010), blue LEDs
def _blades(n=7, rh=7.35, rt=14.05, y0=1.6, y1=7.6, thick=0.42, span_t=37.0, span_r=43.0, sweep=16.0, camber=0.55, nr=18, nc=14):
    nr = qs(nr, 6); nc = qs(nc, 6)
    gs = []
    for k in range(n):
        th0 = 2 * math.pi * k / n
        rs = np.linspace(rh - 0.25, rt, nr); us = np.linspace(-0.5, 0.5, nc)
        P = np.zeros((nr, nc, 3))
        for i, r in enumerate(rs):
            f = (r - rh) / (rt - rh)
            span = math.radians(span_r + (span_t - span_r) * f)
            thc = th0 + math.radians(sweep) * max(f, 0.0) ** 1.4
            ym = (y0 + y1) / 2; h = (y1 - y0) * (0.98 - 0.12 * f)
            for j, u in enumerate(us):
                th = thc + u * span
                y = ym - u * h + camber * (1 - (2 * u) ** 2) * (0.6 + 0.4 * f)
                P[i, j] = [r * math.cos(th), y, r * math.sin(th)]
        # normals of the mid surface
        du = np.gradient(P, axis=1); dr = np.gradient(P, axis=0)
        Nn = np.cross(du, dr); Nn /= np.maximum(np.linalg.norm(Nn, axis=2, keepdims=True), 1e-9)
        # thickness thins toward the edges and the tip
        tt = thick * (0.55 + 0.45 * (1 - np.abs(np.linspace(-1, 1, nc)) ** 2))[None, :, None] * np.linspace(1.15, 0.8, nr)[:, None, None]
        A = P + Nn * tt / 2; B = P - Nn * tt / 2
        V = np.concatenate([A.reshape(-1, 3), B.reshape(-1, 3)]); off = nr * nc; F = []
        for i in range(nr - 1):
            for j in range(nc - 1):
                q0 = i * nc + j; q1 = q0 + 1; q2 = q0 + nc + 1; q3 = q0 + nc
                F += [[q0, q1, q2], [q0, q2, q3], [off + q0, off + q2, off + q1], [off + q0, off + q3, off + q2]]
        # rims: leading / trailing edges (j = 0, nc-1) and tip / root (i = 0, nr-1)
        for i in range(nr - 1):
            for j in (0, nc - 1):
                a0, a1 = i * nc + j, (i + 1) * nc + j
                if j == 0: F += [[a0, off + a0, off + a1], [a0, off + a1, a1]]
                else: F += [[a0, a1, off + a1], [a0, off + a1, off + a0]]
        for j in range(nc - 1):
            for i in (0, nr - 1):
                a0, a1 = i * nc + j, i * nc + j + 1
                if i == 0: F += [[a0, a1, off + a1], [a0, off + a1, off + a0]]
                else: F += [[a0, off + a0, off + a1], [a0, off + a1, a1]]
        g = G(V, np.array(F)); g = smooth(g.V, g.F, 60)
        gs.append(g)
    b = merge(gs)
    # consistent outward winding per face against the face's own normal is fine for a thin closed shell
    return b


def fan3010(frame_col='#111214', blade_col='#16213f', led='#3d7bff', hole=12.0):
    """30 x 30 x 10 mm fan. Frame: axis +Y, intake face at y = 0, outlet (struts, motor) at y = 10; centred on x = z = 0."""
    c = Comp()
    sq = lambda s, h, y0: Manifold.extrude(CrossSection.square([s - 3.0, s - 3.0], True).offset(1.5, mf.JoinType.Round, 2.0, qs(16, 6)), h).rotate([-90, 0, 0]).translate([0, y0 + h, 0])
    def place(M_):
        lo = M_.bounding_box(); return M_
    fr = Manifold.extrude(CrossSection.square([27.0, 27.0], True).offset(1.5, mf.JoinType.Round, 2.0, qs(16, 6)), 10.0)   # z 0..10
    fr = fr - Manifold.cylinder(14.0, 14.35, 14.35, qs(96, 32), True).translate([0, 0, 5.0])
    hollow = Manifold.extrude(CrossSection.square([28.0, 28.0], True).offset(1.6, mf.JoinType.Round, 2.0, qs(16, 6)), 6.6).translate([0, 0, 1.7])
    hollow = hollow - Manifold.cylinder(8.0, 15.05, 15.05, qs(96, 32), True).translate([0, 0, 5.0])
    fr = fr - hollow
    for sx in (-1, 1):
        for sz in (-1, 1):
            fr = fr - Manifold.cylinder(14.0, 1.65, 1.65, qs(24, 10), True).translate([sx * hole, sz * hole, 5.0])
    # outlet struts and the motor plate
    st = Manifold.cylinder(1.6, 7.7, 7.7, qs(64, 24), True).translate([0, 0, 10.0 - 0.8])
    for k in range(4):
        a = math.radians(45 + 90 * k + 8)
        arm = Manifold.cube([8.2, 1.7, 1.6], True).translate([7.2 + 4.0, 0, 0]).rotate([0, 0, math.degrees(a)]).translate([0, 0, 10.0 - 0.8])
        st = st + arm
    fr = fr + (st - Manifold.cylinder(30, 0.9, 0.9, qs(16, 8), True))
    fg = from_manifold(fr.rotate([-90, 0, 0]).mirror([0, 0, 1]).rotate([0, 0, 0]), 35)
    # extrusion was along manifold z (0..10); rotate(-90 about x) maps z->y? rotate([-90,0,0]): (x,y,z)->(x, z, -y); mirror z -> (x, z, y)
    c.add('plastic', fg, frame_col)
    # rotor: hub cup (closed on the intake side) + blades
    hub = cyl(7.35, 6.9, 64, center=(0, 1.15 + 3.45, 0), bevel=0.35)
    c.add('plastic', hub, '#0d0e10')
    c.add('plastic', cyl(4.2, 0.1, 48, center=(0, 1.13, 0)), '#18191c')
    bl = _blades(); c.add('blade', bl, blade_col)
    # four blue LEDs in the outlet struts, looking back through the blades
    for k in range(4):
        a = math.radians(45 + 90 * k + 8)
        x, z = 10.6 * math.cos(a), 10.6 * math.sin(a)
        c.add('plastic', cyl(1.25, 0.5, 20, center=(x, 8.2, z)), '#9fb4ff')
        c.add('emit', sphere(0.95, 20, (x, 8.75, z)), led)
    return c


# ------------------------------------------------------------------ toroid inductor with real windings
def toroid(R=6.4, r=3.0, turns=20, cover=300.0, wire=0.42, core='#c9b75a', cu=COPPER, lead_drop=2.2):
    """lying flat on y = 0 (bottom of the core at y = 0); axis +Y; leads go down through the board"""
    c = Comp()
    cy = r
    c.add('plastic', torus(R, r, 72, 28, (0, cy, 0)), core)
    n = turns * qs(16, 10)
    t = np.linspace(0, 1, n)
    ph = math.radians(-cover / 2) + t * math.radians(cover); th = 2 * math.pi * turns * t
    rr = r + wire * 1.02
    pts = np.stack([(R + rr * np.cos(th)) * np.cos(ph), cy + rr * np.sin(th), (R + rr * np.cos(th)) * np.sin(ph)], 1)
    c.add('metal', tube(pts, wire, 6, cap=True), cu)
    for e in (0, -1):
        p = pts[e]; d = np.array([p[0], 0, p[2]]); d /= np.linalg.norm(d)
        q = np.array([p[0], cy, p[2]]) + d * (rr + 0.4)
        lead = spline([p, q + np.array([0, 0.2, 0]), np.array([q[0], -lead_drop + 0.6, q[2]]), np.array([q[0], -lead_drop, q[2]])], 14)
        c.add('metal', tube(lead, wire, 8, cap=True), cu)
    return c


# ------------------------------------------------------------------ shared small parts
def trimpot3296(c, x, z, y, rotz=0.0):
    """3296W multi-turn trimmer: 9.5 x 4.8 x 10 body, brass screw on top at one end"""
    b = rbox(9.5, 10.0, 4.8, 0.45, 1, (0, 5.0, 0)).col(BLUE_POT)
    s = cyl(1.15, 1.3, 24, center=(-3.1, 10.6, 0), bevel=0.2).col(BRASS)
    slot = box(2.0, 0.3, 0.45, (-3.1, 11.27, 0)).col('#5a4520')
    for g, m in ((b, 'plastic'), (s, 'metal'), (slot, 'metal')):
        g.r(0, rotz, 0).t(x, y, z); c.add(m, g)


def to263(c, x, z, y, rotz=0.0, col='#141517'):
    """TO-263-5 regulator (body + exposed tab + gull-wing leads)"""
    parts = [(rbox(10.1, 4.4, 8.6, 0.35, 1, (0, 2.2, 0)), 'plastic', col),
             (box(10.3, 0.4, 2.2, (0, 0.2, -4.3 - 1.0)), 'metal', TIN)]
    for k in range(5):
        xx = -3.4 + k * 1.7
        parts.append((box(0.8, 0.3, 2.6, (xx, 0.3, 4.3 + 1.2)), 'metal', TIN))
        parts.append((box(0.8, 1.6, 0.3, (xx, 1.0, 4.3 + 0.1)), 'metal', TIN))
    for g, m, cc in parts:
        g.col(cc).r(0, rotz, 0).t(x, y, z); c.add(m, g)


def screw_terminal2(c, x, z, y, rotz=0.0, col=TERM_GREEN):
    """2-way PCB screw terminal, 5.0 pitch: 10 x 7.6 x 10 box; screws on top, wire openings on the -z face"""
    body = Manifold.cube([10.0, 10.0, 7.6], True).translate([0, 5.0, 0])
    for k in (-2.5, 2.5):
        body = body - Manifold.cylinder(6.0, 1.85, 1.85, qs(24, 10), True).rotate([-90, 0, 0]).translate([k, 10.0, -0.4])
        body = body - Manifold.cube([3.4, 3.4, 4.0], True).translate([k, 3.6, -3.8 - 0.8])
    g = from_manifold(body, 30).col(col)
    parts = [(g, 'plastic')]
    for k in (-2.5, 2.5):
        sc = cyl(1.55, 1.1, 24, center=(k, 8.2, -0.4)).col(NICKEL)
        sl = box(3.0, 0.35, 0.5, (k, 8.8, -0.4)).col('#55595e')
        cl = box(3.1, 2.6, 0.4, (k, 3.6, -3.25)).col(NICKEL)
        parts += [(sc, 'metal'), (sl, 'metal'), (cl, 'metal')]
    for g2, m in parts:
        g2.r(0, rotz, 0).t(x, y, z); c.add(m, g2)


# ------------------------------------------------------------------ boards (frame: x 0..L, z 0..W, PCB y 0..1.6, parts on +Y)
def board(c, A, region, L, W, side, T=1.6, r=0.5):
    g = rbox(L, T, W, r, 1, (L / 2, T / 2, W / 2)); uv_top(g, A.uv(region), 0, L, 0, W); c.add('pcb', side_col(g, side))
    c.bake(region, 0, L, 0, W, T + 0.02)
    return T


XL1 = dict(region='xl4015k', L=54.0, W=23.0, cap_r=4.0, cap_h=10.6, tor=(20.5, 8.0, 5.0, 2.4, 0.38, 18), cin=(49.5, 4.5), cout=(39.0, 16.8),
           ic=(40.5, 4.8, 0.0), diode=(45.0, 21.0), pot=(48.6, 13.0, 90.0), led=(34.5, 12.0),
           smd=[(27.0, 21.0), (31.5, 20.5), (14.0, 20.0), (32.0, 13.5)],
           pads=[(0.8, 3.0, 4.8, 7.0, 'IN-'), (0.8, 8.0, 4.8, 12.0, 'IN+'), (49.6, 18.6, 53.4, 20.4, 'OUT+'), (49.6, 20.9, 53.4, 22.7, 'OUT-')], text=(12.5, 19.6))
XL2 = dict(region='xl4015k2', L=36.0, W=20.0, cap_r=3.15, cap_h=7.7, tor=(14.0, 10.0, 4.4, 2.1, 0.34, 15), cin=(4.6, 4.4), cout=(31.0, 15.9),
           ic=(26.5, 5.4, -90.0), diode=(23.6, 16.9), pot=(33.2, 6.0, 90.0), led=(19.0, 1.4),
           smd=[(22.0, 12.5), (7.5, 18.2), (11.0, 1.4)],
           pads=[(0.6, 9.0, 3.4, 12.0, 'IN-'), (0.6, 13.2, 3.4, 16.2, 'IN+'), (25.2, 18.9, 28.2, 19.9, 'OUT+'), (33.0, 11.6, 35.6, 13.0, 'OUT-')], text=(11.0, 18.4))


def xl4015k(A, lay=XL1):
    """black XL4015 buck module: 220 uF / 35 V caps, wound toroid, TO-263 regulator, SS54 diode, 3296 trimmer"""
    L, W = lay['L'], lay['W']
    c = Comp(); y = board(c, A, lay['region'], L, W, '#0f1012')
    for (x, z) in (lay['cin'], lay['cout']): ecap(c, x, z, lay['cap_r'], lay['cap_h'], y)
    tx, tz, R, r, wr, n = lay['tor']
    tr = toroid(R, r, n, 300.0, wr); tr.M(None, (tx, y + 0.12, tz)); c.extend(tr)
    x, z, a = lay['ic']; to263(c, x, z, y, a)
    x, z = lay['diode']; smd(c, x, z, 5.4, 3.6, 2.2, '#16171a', y, 'plastic', 0.15)
    c.add('label', box(0.7, 0.05, 3.3, (x - 2.0, y + 2.22, z)), '#d9d9d4')
    x, z, a = lay['pot']; trimpot3296(c, x, z, y, a)
    for (x, z) in lay['smd']:
        smd(c, x, z, 1.6, 0.8, 0.5, '#2a2a2c', y, 'plastic', 0.05)
        c.add('metal', box(0.3, 0.52, 0.82, (x - 0.65, y + 0.26, z)), TIN); c.add('metal', box(0.3, 0.52, 0.82, (x + 0.65, y + 0.26, z)), TIN)
    x, z = lay['led']; c.add('emit', box(1.4, 0.5, 0.8, (x, y + 0.25, z)), '#ff3a2a')
    for (x0, z0, x1, z1, lab) in lay['pads']:
        c.add('metal', sphere(1.0, 16).sc((x1 - x0) * 0.42, 0.42, (z1 - z0) * 0.4).t((x0 + x1) / 2, y + 0.12, (z0 + z1) / 2), TIN)
    return c


def pad_xyz(lay, k, y=1.6):
    x0, z0, x1, z1, _ = lay['pads'][k]
    return np.array([(x0 + x1) / 2, y + 0.3, (z0 + z1) / 2])


INA_TERM = (3.7, 5.2)            # the screw terminal on the INA219 (its wire openings face +x)
BMS_PADS = [(3.2, 2.88), (3.2, 8.0), (3.2, 13.12), (37.8, 4.32), (37.8, 11.68)]
USB_PADS = [(33.5, 1.9, 3.0), (33.5, 1.9, 9.0)]


def ina219(A, region='ina219'):
    L, W = 25.5, 22.3
    c = Comp(); y = board(c, A, region, L, W, '#16255c')
    # 2512 shunt: black body, tinned ends, its top shows the painted R100 (same footprint as the board region underneath)
    sh = rbox(5.7, 0.62, 3.3, 0.08, 1, (12.75, y + 0.31, 5.8)); uv_top(sh, A.uv(region), 0, L, 0, W); c.add('label', side_col(sh, '#121214'))
    for x in (9.3, 16.2): c.add('metal', box(1.3, 0.66, 3.4, (x, y + 0.33, 5.8)), TIN)
    smd(c, 12.9, 12.6, 3.0, 3.0, 1.0, '#141416', y, 'plastic', 0.08)            # INA219 (SOT-23-8 class)
    for k in range(4):
        for sz in (-1, 1):
            c.add('metal', box(0.3, 0.2, 0.7, (12.0 + k * 0.65 - 0.97 + 0.97 * 0, y + 0.1, 12.6 + sz * 1.8)), TIN)
    for (x, z) in [(7.2, 13.6), (9.0, 14.6), (17.8, 15.2), (5.6, 6.6)]:
        smd(c, x, z, 1.6, 0.8, 0.5, '#b38d5a' if x < 8 else '#232325', y, 'plastic', 0.05)
    screw_terminal2(c, INA_TERM[0], INA_TERM[1], y, -90.0)
    return c


def ads1015(A, region='ads1015'):
    L, W = 28.0, 17.8
    c = Comp(); y = board(c, A, region, L, W, '#3c1b63')
    smd(c, 14.0, 11.0, 3.0, 3.0, 1.0, '#151517', y, 'plastic', 0.08)              # ADS1015 (MSOP-10)
    for k in range(5):
        for sz in (-1, 1):
            c.add('metal', box(0.25, 0.2, 0.7, (12.8 + k * 0.5 - 0.2, y + 0.1, 11.0 + sz * 1.85)), TIN)
    for (x, z) in [(6.0, 9.0), (8.0, 12.5), (20.5, 9.5), (22.5, 12.6), (18.4, 13.6)]:
        smd(c, x, z, 1.6, 0.8, 0.5, '#232325' if x != 8.0 else '#b38d5a', y, 'plastic', 0.05)
    h = header_male(10, 1, up=6.0).M(None, (2.57, y, 1.6)); c.extend(h)
    return c


def bms2s(A, region='bms2s', L=41.0, W=16.0):
    """2S 20 A BMS with balancing, 41 x 16 x 4 mm (the module named in the thesis)"""
    c = Comp(); y = board(c, A, region, L, W, '#153f27')
    for k in range(3):                                                            # MOSFETs (SOP-8)
        x = 12.5 + k * 7.0
        for z in (4.2, W - 4.2):
            smd(c, x, z, 4.9, 3.9, 1.5, '#121214', y, 'plastic', 0.1)
            for j in range(4):
                for sx in (-1, 1):
                    c.add('metal', box(0.4, 0.25, 1.0, (x - 1.9 + j * 1.27, y + 0.12, z + sx * 2.45)), TIN)
    smd(c, 33.5, W / 2, 2.9, 1.6, 1.0, '#141416', y, 'plastic', 0.06)              # protection IC
    for (x, z) in [(9.2, W / 2), (30.5, W / 2 - 3.0), (30.5, W / 2 + 3.0)]:
        smd(c, x, z, 2.0, 1.25, 0.5, '#202022', y, 'plastic', 0.05)
    for (x, z) in BMS_PADS:
        c.add('metal', sphere(1.2, 16).sc(1.4, 0.4, 0.8).t(x, y + 0.1, z), TIN)
    return c


def usbc_board(A, region='usbc', L=36.0, W=12.0):
    c = Comp(); y = board(c, A, region, L, W, '#0d0e10')
    # USB-C receptacle (8.94 x 3.26), mouth facing -x, overhanging the edge a little
    sh = Manifold.extrude(CrossSection.square([7.6, 1.9], True).offset(0.67, mf.JoinType.Round, 2.0, qs(16, 6)), 7.35)
    sh = sh - Manifold.extrude(CrossSection.square([7.0, 1.4], True).offset(0.5, mf.JoinType.Round, 2.0, qs(16, 6)), 6.6).translate([0, 0, -0.1])
    g = from_manifold(sh.rotate([0, 90, 0]), 40)           # extrusion along +x from 0 to 7.35
    g.t(-0.8, y + 1.63, W / 2); c.add('metal', g, '#c4c8cd')
    c.add('plastic', box(4.6, 0.7, 6.4, (2.7, y + 1.63, W / 2)), '#18191b')
    smd(c, 16.0, 6.0, 4.9, 3.9, 1.5, '#131315', y, 'plastic', 0.1)                 # charger IC (ESOP-8)
    smd(c, 23.5, 6.0, 4.0, 4.0, 2.0, '#2c2e33', y, 'plastic', 0.4)                 # inductor
    for (x, z) in [(11.0, 3.0), (11.0, 9.0), (28.0, 3.0), (28.0, 9.0)]:
        smd(c, x, z, 2.0, 1.25, 0.9, '#b38d5a', y, 'plastic', 0.08)
    c.add('emit', box(1.4, 0.5, 0.8, (30.5, y + 0.25, 6.0)), '#ff3030'); c.add('emit', box(1.4, 0.5, 0.8, (32.4, y + 0.25, 6.0)), '#3d7bff')
    return c


def pan_screw(c, x, y, z, r=2.1, h=1.3, col=BRASS, down=False):
    """cross-head pan screw head sitting on y (pointing +y, or -y with down=True)"""
    hd = revolve([(0, 0), (r, 0), (r, h * 0.42), (r * 0.82, h * 0.86), (r * 0.45, h), (0, h)], 32)
    for (sx, sz) in ((r * 1.25, 0.5), (0.5, r * 1.25)):
        hd = hd - Manifold.cube([sx, 1.4, sz], True).translate([0, h, 0])
    g = from_manifold(hd, 28).col(col)
    if down: g.r(180, 0, 0)
    g.t(x, y, z); c.add('metal', g)


# ------------------------------------------------------------------ wires
def wire(points, r=0.6, col=WIRE_RED, n=60, mat='rubber'):
    pts = spline(points, n)
    return (mat, tube(pts, r, 10, cap=True).col(col))
