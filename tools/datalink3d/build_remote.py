# The controller: its CAD file plus the parts the CAD leaves out (or only reserves space for), at two detail levels.
# usage: build_remote.py TOOLS_DIR [fast] [check]
#   reads  work/atlas_rv.pkl (painted atlas + the rover's baked texel occlusion), cad/remote_cad.npz, cad/remote_cad_names.json,
#          cad/remote_designed_hi.npz (hi), cad/remote_designed_lo.npz (lo)
#   writes build/remote.js (lo), build/remote-hi.js (hi), build/atlas.webp (the finished shared atlas)
# Coordinates: parts are placed in the CAD frame (mm, z toward the screen), then mapped to the page frame (y up).
import sys, os, json, time, math, pickle, numpy as np, trimesh, fast_simplification as fs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from geom import *
from bake import Occ, shade_ao
import pack as PK
import rover as RV
import rparts as RP

S = sys.argv[1]; FAST = 'fast' in sys.argv[2:]; CHECK = 'check' in sys.argv[2:]
ONLY = [a[5:] for a in sys.argv[2:] if a.startswith('only=')]
t0 = time.time()
A = pickle.load(open(f'{S}/work/atlas_rv.pkl', 'rb'))
RV.ATL = A
raw = np.load(f'{S}/cad/remote_cad.npz'); names = json.load(open(f'{S}/cad/remote_cad_names.json', encoding='utf-8'))
inv = {n: i for i, n in names.items()}
allv = np.concatenate([raw['v' + i] for i in names]); lo_, hi_ = allv.min(0), allv.max(0); ctr = (lo_ + hi_) / 2; ctr[2] = lo_[2]
RT = np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], np.float64)          # CAD (x, y, z) -> page (x, z, -y)
R_DOWN = RT.copy()                                                     # board frames: local y (parts side) -> CAD -z, local z -> CAD +y
R_DOWN180 = np.array([[-1, 0, 0], [0, 0, -1], [0, -1, 0]], np.float64) # same, turned half way round
R_FAN = np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], np.float64)       # fan axis (local y) -> CAD +z
def tfV(V): return (np.asarray(V, np.float64) - ctr) @ RT.T
def to_page(c): return c.M(RT, -RT @ ctr)
def cad_of_page(p): return ctr + RT.T @ np.asarray(p, np.float64)

DESIGNED = {'_____suport buck mare': 0, '_____suport buck mic': 1, '_____capac inferior': 2, '_____capac median': 3, 'Body739': 4}
GROUP = {'Joystick stanga': 'sticks', 'Joystick dreapta': 'sticks', 'adaptor HDMI': 'screen', 'Ecran': 'screen',
         '_____suport buck mare': 'power', '_____suport buck mic': 'power', '_____capac inferior': 'bottom', '_____capac median': 'mid', 'Body739': 'shell',
         '21700 2S Battery Holder (1)': 'batt', '21700 2S Battery Holder': 'batt'}
LO_TARGET = {'Body739': 70000, '_____capac median': 18000, '_____capac inferior': 10000, '_____suport buck mare': 9000, '_____suport buck mic': 500,
             'Joystick stanga': 6000, 'Joystick dreapta': 6000, 'Ecran': 4000, '21700 2S Battery Holder (1)': 3000, '21700 2S Battery Holder': 3000}
PLA = '#151517'
# where the new parts go (CAD mm); see the notes at the end of this file
SW_AT = (551.17, 579.4, -24.94)          # the CAD toggle's axis; its bushing leaves the body at y 579.4
FAN_AT = (509.49, 529.02, -46.0)         # centre of the three screw holes in the support's bosses (23.5 mm pitch); intake face flush with the back cover
XL1_AT = (490.0, 516.0, -28.4)           # resting on the bosses' tops (z -30), parts facing the fan
INA_AT = (584.3, 581.0, -26.0)           # right wing, by the switch (as in the photos)
ADS_AT = (556.6, 545.5, -20.0)           # right wing, under the INA219
# left wing (photo of the inside: a long green board stands along the wing's wall). The wing's wall has two slot clips 41 mm apart at
# z -20, the BMS's length: the BMS stands in them. The USB-C board and the second buck stand beside it like books.
R_BMS = np.diag([1.0, -1.0, -1.0])                  # board frame: x along the wing, parts toward -y, width downward (-z)
R_STAND = np.eye(3)                                  # board frame: x along the wing, parts toward +y, width upward (+z)
BMS_AT = (437.0, 578.8, -18.0)           # in the slot clips at x 437 / 478, y 577-579
XL2_AT = (448.0, 566.0, -41.6)           # standing between the USB-C board and the BMS, on the wing floor
USB_AT = (434.8, 560.8, -28.5)           # standing against the wing's bottom wall, its USB-C mouth at the outer wall's opening


def cad_parts(level):
    """[(group, mat, G)] for the CAD solids at this level, plus the screen rectangle"""
    src = np.load(f'{S}/cad/remote_designed_hi.npz' if level == 'hi' else f'{S}/cad/remote_designed_lo.npz')
    out = []; screen_rect = None
    for i, n in names.items():
        if n not in GROUP: continue                                        # the Pi, its bits, the toggle and Body719 are rebuilt below
        if n in DESIGNED:
            k = DESIGNED[n]; V, F = src['v%d' % k], src['f%d' % k]
        else:
            V, F = raw['v' + i], raw['f' + i]
        m = trimesh.Trimesh(tfV(V), F, process=True)
        if level == 'lo':
            if len(m.faces) > 2000 and n not in DESIGNED:
                bs = m.split(only_watertight=False); keep = [b for b in bs if np.linalg.norm(b.bounds[1] - b.bounds[0]) > 3.0]
                if keep and len(keep) < len(bs): m = trimesh.util.concatenate(keep)
            tgt = LO_TARGET.get(n, len(m.faces))
            if len(m.faces) > tgt * 1.1:
                v2, f2 = fs.simplify(np.asarray(m.vertices, np.float32), np.asarray(m.faces, np.int32), target_reduction=max(0., 1 - tgt / len(m.faces)), agg=7)
                m = trimesh.Trimesh(v2, f2, process=True)
        grp = GROUP[n]
        g = smooth(m.vertices, m.faces, 42 if n in DESIGNED else 34)
        fc = g.V[g.F].mean(1); fn = np.cross(g.V[g.F][:, 1] - g.V[g.F][:, 0], g.V[g.F][:, 2] - g.V[g.F][:, 0]); fn /= np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-9)
        def sub(mask):
            idx = np.where(mask)[0]
            if not len(idx): return None
            used = np.unique(g.F[idx]); remap = -np.ones(len(g.V), int); remap[used] = np.arange(len(used))
            return G(g.V[used], remap[g.F[idx]], g.N[used])
        def addm(mat, gg, col):
            if gg is not None: out.append((grp, mat, gg.col(col)))
        if grp in ('shell', 'mid', 'bottom', 'power'):
            addm('pla', g, PLA)
        elif n == 'Ecran':
            ymax = g.V[:, 1].max()
            front = (fn[:, 1] > 0.8) & (fc[:, 1] > ymax - 0.8); back = fn[:, 1] < -0.6
            addm('glass', sub(front), '#06070a'); addm('pcb', sub(back), '#1e4f9c'); addm('plastic', sub(~front & ~back), '#0d0e11')
            fv = g.V[np.unique(g.F[front])]
            screen_rect = [float(fv[:, 0].min()), float(fv[:, 0].max()), float(fv[:, 2].min()), float(fv[:, 2].max()), float(ymax)]
        elif n == 'adaptor HDMI':
            addm('pcb', g, '#1f6e3c')
        elif n.startswith('Joystick'):
            y = fc[:, 1]
            addm('rubber', sub(y > 55.0), '#131315'); addm('plastic', sub((y > 43.0) & (y <= 55.0)), '#24252a'); addm('pcb', sub(y <= 43.0), '#18191c')
        elif n.startswith('21700'):
            addm('plastic', g, '#121214')
        else:
            addm('plastic', g, '#2a2b30')
    return out, screen_rect


def cells(pieces):
    """the four Samsung INR21700-50S cells in the two holders"""
    holders = [g for (grp, mat, g) in pieces if grp == 'batt']
    for hg in holders:
        tm = trimesh.Trimesh(hg.V, hg.F, process=False)
        obb = tm.bounding_box_oriented; T4 = obb.primitive.transform; ext = obb.primitive.extents
        order = np.argsort(-ext); ax = T4[:3, :3][:, order]; e = ext[order]; c = T4[:3, 3]
        if ax[1, 2] < 0: ax[:, 2] = -ax[:, 2]
        if np.linalg.det(ax) < 0: ax[:, 1] = -ax[:, 1]
        for sgn in (-1, 1):
            body = cyl(10.85, 68.6, 48, axis='x', caps=False)
            ang = np.arctan2(body.V[:, 1], body.V[:, 2]); s_ = (ang + math.pi) / (2 * math.pi); t_ = (body.V[:, 0] + 34.3) / 68.6
            u0, v0, u1, v1 = A.uv('cell'); body.UV = np.stack([u0 + s_ * (u1 - u0), v0 + t_ * (v1 - v0)], 1); body.col('#ffffff')
            caps = []
            for sx in (-1, 1):
                caps.append(cyl(10.85, 0.8, 48, axis='x', center=(sx * 34.7, 0, 0), bevel=0.35).col('#2f9e74'))
                caps.append(cyl(9.6, 0.5, 40, axis='x', center=(sx * 35.3, 0, 0)).col('#c8ccd1'))
            R = np.stack([ax[:, 0], ax[:, 1], ax[:, 2]], 1)
            off = c + ax[:, 1] * sgn * 11.2 + ax[:, 2] * (e[2] / 2 - 10.85 - 1.2)
            body.M(R, off); pieces.append(('batt', 'label', body))
            for cp in caps: cp.M(R, off); pieces.append(('batt', 'metal' if cp.C[0, 0] > 0.3 else 'label', cp))


def wire(group, pts, r, col, pieces):
    P = np.asarray(pts, np.float64); L = np.linalg.norm(np.diff(P, axis=0), axis=1).sum()
    hi = geom.Q > 1.5
    n = max(8, int(L / (1.4 if hi else 3.0)))
    g = tube(spline(P, n, absolute=True), r, 10 if hi else 6, cap=True, absolute=True).col(col)
    g.M(RT, -RT @ ctr); pieces.append((group, 'plastic', g))


def cad_pt(R, at, local):
    return np.asarray(at, np.float64) + R @ np.asarray(local, np.float64)


def new_parts(level, pieces):
    """switch, fan, both bucks, INA219, ADS1015, BMS, the USB-C board, wires; returns the fan centre (page mm)"""
    def put(grp, comp):
        to_page(comp)
        for (m, g) in comp.p: pieces.append((grp, m, g))
        return comp
    bakes = []
    # ---- the switch, through the top wall (5 mm thick at the boss): outer washer and nut only
    sw = RP.mts102(wall=(1.2, 6.1)); sw.M(None, SW_AT); put('switch', sw)
    # ---- the fan on the support's three bosses; pan-head screws on the intake side (the fourth corner has no boss but keeps its screw)
    fan = RP.fan3010(hole=11.75)
    for sx in (-1, 1):
        for sz in (-1, 1): RP.pan_screw(fan, sx * 11.75, 0.0, sz * 11.75, down=True)
    fan.M(R_FAN, FAN_AT); put('power', fan)
    # ---- XL4015 #1 (5.1 V for the Pi), on the bosses' tops, parts toward the fan
    xl1 = RP.xl4015k(A, RP.XL1); xl1.M(R_DOWN, XL1_AT); bakes += xl1.bk; put('power', xl1)
    # ---- right wing: INA219 and ADS1015 (as in the photos)
    ina = RP.ina219(A); ina.M(R_DOWN180, INA_AT); bakes += ina.bk; put('elec', ina)
    ads = RP.ads1015(A); ads.M(R_DOWN, ADS_AT); bakes += ads.bk; put('elec', ads)
    # ---- left wing: the 2S BMS standing in the wing's slot clips, XL4015 #2 (3.3 V) and the USB-C board standing beside it
    bms = RP.bms2s(A); bms.M(R_BMS, BMS_AT); bakes += bms.bk; put('elec', bms)
    xl2 = RP.xl4015k(A, RP.XL2); xl2.M(R_STAND, XL2_AT); bakes += xl2.bk; put('elec', xl2)
    usb = RP.usbc_board(A); usb.M(R_STAND, USB_AT); bakes += usb.bk; put('elec', usb)

    # ---- wires (CAD mm). Silicone wire: power 0.75 mm radius, signals 0.38
    RD, BK, OR, YE, WH, BL, PU, GN = RP.WIRE_RED, RP.WIRE_BLK, RP.WIRE_ORG, RP.WIRE_YEL, RP.WIRE_WHT, RP.WIRE_BLU, RP.WIRE_PUR, RP.WIRE_GRN
    P = lambda R, at, l: cad_pt(R, at, l)
    # switch lugs: common (middle) and one side lug, soldered, running down toward the INA219
    for dx, col, end in ((0.0, RD, (560.0, 563.0, -31.5)), (4.7, RD, (566.0, 566.5, -33.0))):
        a = np.array([SW_AT[0] + dx, SW_AT[1] - 12.4, SW_AT[2]])
        wire('switch', [a + [0, 0.8, 0], a + [0, -2.5, 0], a + [0.8, -6.0, -2.0], [ (a[0] + end[0]) / 2, (a[1] + end[1]) / 2 - 1.5, -29.0], end], 0.72, col, pieces)
    # INA219 screw terminal (Vin+, Vin-): two red leads toward the switch and the bucks
    ti = RP.INA_TERM
    for k, end in ((-1, (563.5, 571.0, -32.5)), (1, (562.0, 580.5, -34.5))):
        o = P(R_DOWN180, INA_AT, (ti[0] + 4.6, 1.6 + 3.6, ti[1] + k * 2.5))
        wire('elec', [o + [0.5, 0, 0], o + [-3.0, 0, -0.6], o + [-8.0, k * 0.8, -2.5], end], 0.72, RD, pieces)
    # ADS1015: I2C to the Pi (four thin wires) and the stick bundle down the wing
    for k, col in enumerate((RD, BK, YE, GN)):
        o = P(R_DOWN, ADS_AT, (2.57 + k * 2.54, 1.6 + 6.2, 1.6))
        wire('elec', [o + [0, 0, 0.6], o + [0, -1.0, -1.4], o + [-2.0 - k * 0.6, 2.0, -6.0], [552.0 - k * 0.9, 552.0 + k * 0.6, -26.0], [545.0 - k * 0.9, 554.0 + k * 0.7, -22.0]], 0.38, col, pieces)
    for k, col in enumerate((PU, WH, OR, BL)):
        o = P(R_DOWN, ADS_AT, (2.57 + (6 + k) * 2.54, 1.6 + 6.2, 1.6))
        wire('elec', [o + [0, 0, 0.6], o + [0, -1.2, -1.2], o + [k * 0.5, -3.0, -5.0], [574.0 + k * 0.9, 546.5, -31.0], [586.0 + k * 0.4, 545.0, -33.5]], 0.38, col, pieces)
    # INA219 header: VCC, GND, SCL, SDA hop over to the ADS1015 (shared I2C)
    for k, col in enumerate((RD, BK, YE, GN)):
        o = P(R_DOWN180, INA_AT, (6.4 + k * 2.54, 1.6 + 0.4, 20.4))
        q = P(R_DOWN, ADS_AT, (2.57 + k * 2.54, 1.6 + 6.0, 1.6))
        mid_ = (o + q) / 2 + [0, 0, -7.0 - k * 0.5]
        wire('elec', [o, o + [0, 0, -2.5], mid_, q + [0, 0, -1.6], q], 0.38, col, pieces)
    # BMS: balance leads (B-, BM, B+) up over the boards and down into the left grip's cells, P- / P+ across toward the switch
    for k, col in enumerate((BK, WH, RD)):
        o = P(R_BMS, BMS_AT, (RP.BMS_PADS[k][0], 1.9, RP.BMS_PADS[k][1]))
        wire('elec', [o, o + [-0.6, -2.2, 0.8], [o[0] - 1.6, 574.0 - k * 0.7, -13.2 + k * 0.4], [436.2 + k * 0.9, 563.0, -12.0 + k * 0.4], [436.4 + k * 0.9, 558.6, -10.8],
                      [436.6 + k * 0.9, 554.5, -17.0], [437.0 + k * 0.9, 551.5, -26.0]], 0.5 if k != 1 else 0.38, col, pieces)
    for k, col in ((3, BK), (4, RD)):
        o = P(R_BMS, BMS_AT, (RP.BMS_PADS[k][0], 1.9, RP.BMS_PADS[k][1]))
        wire('elec', [o, o + [0.6, -2.4, 1.2], o + [3.0, -3.6, 5.0], [482.0, o[1] - 3.8 - (k - 3) * 1.4, -12.4], [486.5, o[1] - 4.2 - (k - 3) * 1.4, -10.6], [493.0, o[1] - 5.0 - (k - 3) * 1.4, -11.4]], 0.72, col, pieces)
    # XL4015 #1: IN from the power path along the stem wall, OUT up to the Pi's 5 V pins
    for k, col in ((0, BK), (1, RD)):
        o = P(R_DOWN, XL1_AT, RP.pad_xyz(RP.XL1, k))
        wire('power', [o, o + [-2.0, 0, -1.2], [488.6, o[1] + 3.0, -33.0], [488.4, 541.0 + k, -30.0], [490.0 + k * 1.2, 551.0, -26.0]], 0.72, col, pieces)
    for k, col in ((2, RD), (3, BK)):
        o = P(R_DOWN, XL1_AT, RP.pad_xyz(RP.XL1, k))
        wire('power', [o, o + [1.5, 0, -1.0], [543.6, o[1] - 6.0, -29.5], [542.6 - (k - 2) * 1.2, 516.0, -24.0], [541.2 - (k - 2) * 1.3, 507.0, -21.0]], 0.72, col, pieces)
    # fan: three thin leads from its corner to the Pi's fan socket
    fc = cad_pt(R_FAN, FAN_AT, (14.2, 8.5, -14.2))
    for k, col in enumerate((RD, BK, YE)):
        d = np.array([k * 0.75, 0, 0])
        wire('power', [fc + d, fc + d + [2.0, 2.0, 3.0], [533.0 + k * 0.7, 551.0, -25.0], [535.0 + k * 0.7, 558.5, -18.5], [535.6 + k * 0.7, 560.6, -16.4]], 0.34, col, pieces)
    # XL4015 #2 and the USB-C board (both standing in the left wing): short power leads up out of the wing
    for k, col in ((0, BK), (1, RD)):
        o = P(R_STAND, XL2_AT, RP.pad_xyz(RP.XL2, k))
        wire('elec', [o, o + [0.0, 1.6, 0.8], o + [-0.8, 3.4, 4.0], [o[0] - 1.0, o[1] + 3.6, -13.4 + k * 0.6], [o[0] + 4.0, o[1] + 3.0, -10.8]], 0.6, col, pieces)
    for k, col in ((2, RD), (3, BK)):
        o = P(R_STAND, XL2_AT, RP.pad_xyz(RP.XL2, k))
        wire('elec', [o, o + [0.0, 1.6, 0.8], o + [0.8, 3.2, 3.6], [o[0] + 2.0, o[1] + 3.4, -13.0 + (k - 2) * 0.6], [o[0] + 8.0, o[1] + 2.8, -10.8]], 0.6, col, pieces)
    for k, col in ((0, RD), (1, BK)):
        o = P(R_STAND, USB_AT, RP.USB_PADS[k])
        wire('elec', [o, o + [1.5, 1.4, 0.6], o + [4.0, 3.0, 3.0], [o[0] + 6.0, 571.6 + k * 0.9, -13.6], [o[0] + 9.0, 574.2 + k * 0.9, -12.6], [o[0] + 10.0, 575.2 + k * 0.9, -15.0]], 0.6, col, pieces)
    # joystick headers: five thin leads each, heading in toward the middle
    for side, x0, dx, xe in ((-1, 443.0, 1.0, 488.0), (1, 579.4, -1.0, 541.5)):
        for k, col in enumerate((BK, RD, PU, WH, OR)):
            y = 482.5 + k * 2.54; o = np.array([x0, y, -4.2])
            wire('sticks', [o + [-dx * 0.5, 0, 0], o + [dx * 3.0, 0, 0], o + [dx * 9.0, 1.0 + k * 0.3, -4.5], o + [dx * 20.0, 5.0 + k * 0.5, -10.0],
                            [(x0 + xe) / 2 + dx * 6.0, 491.5 + k * 0.5, -15.5 - k * 0.4], [xe - dx * 2.0, 497.5 + k * 0.7, -19.0 - k * 0.5]], 0.36, col, pieces)
    return bakes


def build(level):
    geom.setQ(3.0 if level == 'hi' else 1.0)
    pieces, screen_rect = cad_parts(level)
    print(level, 'cad parts', len(pieces), round(time.time() - t0, 1), 's')
    pi = RV.pi5(A, 'low')
    Rpi = np.array([[0, 0, -1], [0, -1, 0], [-1, 0, 0]], np.float64)
    pi.M(Rpi, (29.6, 35.1, 2.0))
    for (mat, g) in pi.p: pieces.append(('pi', mat, g))
    cells(pieces)
    bakes = new_parts(level, pieces)
    fan_page = (tfV(np.array([FAN_AT]))[0]).tolist()
    geom.setQ(1.0)
    return pieces, screen_rect, fan_page, pi.bk + bakes


def check(pieces):
    """report how much of every new part sits inside a CAD solid (a quick placement test)"""
    solids = {}
    for (grp, mat, g) in pieces:
        if mat == 'pla': solids.setdefault(grp, []).append(g)
    tms = {k: trimesh.Trimesh(merge(v).V, merge(v).F, process=True) for k, v in solids.items()}
    by = {}
    for (grp, mat, g) in pieces:
        if mat == 'pla' or grp in ('shell', 'screen', 'sticks', 'batt'): continue
        by.setdefault(grp + ':' + mat, []).append(g)
    for k, gs in by.items():
        V = merge(gs).V
        if len(V) > 6000: V = V[np.random.default_rng(1).choice(len(V), 6000, replace=False)]
        for s, tm in tms.items():
            try: inside = tm.contains(V)
            except Exception: continue
            if inside.mean() > 0.002: print('   overlap %-16s in %-7s %5.1f%%' % (k, s, inside.mean() * 100))


def bake_and_pack(level, pieces, screen_rect, fan_page, bakes, out_js, var, event):
    allg = merge([g for (_, _, g) in pieces]); occ = Occ(allg.V, allg.F)
    print(level, 'occluder tris', len(allg.F), round(time.time() - t0, 1), 's')
    K = 20 if FAST else (56 if level == 'hi' else 36)
    for (grp, mat, g) in pieces:
        if mat == 'emit': continue
        ao = occ.ao(g.V, g.N, K=K, maxd=14.0, power=1.6)
        fl = 0.42 if mat in ('metal', 'satin', 'gold') else (0.62 if grp == 'batt' and mat in ('label', 'metal') else 0.26)
        g.AO = shade_ao(ao, floor=fl)
    print(level, 'AO', round(time.time() - t0, 1), 's')
    if level == 'hi':
        step = 3 if FAST else 2
        from PIL import Image
        for (region, o, u, v, n) in bakes:
            if region in ('pi5',): continue                     # the Pi's top keeps the rover's bake
            x0, y0, x1, y1 = A.regions[region]; w, h = x1 - x0, y1 - y0
            gw, gh = max(2, w // step), max(2, h // step)
            ii, jj = np.meshgrid((np.arange(gw) + 0.5) / gw, (np.arange(gh) + 0.5) / gh)
            P = o[None, :] + ii.ravel()[:, None] * u[None, :] + jj.ravel()[:, None] * v[None, :]
            N = np.tile(n / np.linalg.norm(n), (len(P), 1))
            ao = occ.ao(P, N, K=K, maxd=14.0, eps=0.08, power=1.8).reshape(gh, gw)
            im = Image.fromarray((np.clip(ao, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.BILINEAR)
            A.ao[y0:y1, x0:x1] = shade_ao(np.asarray(im).astype(np.float32) / 255, floor=0.22)
        print(level, 'texel AO', round(time.time() - t0, 1), 's')
    for (grp, mat, g) in pieces:
        if g.UV is None: g.UV = np.full((len(g.V), 2), -1.0)
        m = g.UV[:, 0] < 0; g.UV[m] = A.white_uv()
    meshes = []; by = {}
    for (grp, mat, g) in pieces: by.setdefault((grp, mat), []).append(g)
    for (grp, mat), gs in by.items(): meshes.append({'n': f'{grp}:{mat}', 'part': grp, 'mat': mat, 'g': merge(gs)})
    extra = {'unit': 0.01, 'screen': [round(x, 3) for x in screen_rect] if screen_rect else None, 'fan': [round(x, 3) for x in fan_page], 'level': level}
    st = PK.pack(meshes, var, event, out_js, extra,
                 'DataLink Rover: the controller, from its CAD file (shell, screen, joysticks, buck support, covers, 21700 holders) with the parts it leaves out '
                 '(Pi 5, cells, switch, fan, XL4015 x2, INA219, ADS1015, 2S BMS, USB-C board, wiring). Per mesh, in triangle order: delta-coded positions, '
                 'colours with baked occlusion, atlas uv, indices; gzipped, base64.')
    print(level, st, round(time.time() - t0, 1), 's')


def main():
  levels = ONLY or ['hi', 'lo']
  for level in levels:
      pieces, screen_rect, fan_page, bakes = build(level)
      if CHECK:
          check(pieces); continue
      tris = sum(len(g.F) for (_, _, g) in pieces)
      print(level, 'triangles', tris, 'by group', {k: sum(len(g.F) for (gg, _, g) in pieces if gg == k) for k in sorted({p[0] for p in pieces})})
      if level == 'hi':
          bake_and_pack('hi', pieces, screen_rect, fan_page, bakes, f'{S}/build/remote-hi.js', 'DL_REMOTE_HI', 'dl-remote-hi')
          A.finish(f'{S}/build/atlas.webp', 86)
          print('atlas written', round(time.time() - t0, 1), 's')
      else:
          bake_and_pack('lo', pieces, screen_rect, fan_page, bakes, f'{S}/build/remote.js', 'DL_REMOTE', 'dl-remote')
      del pieces



if __name__ == '__main__':
    main()

# Notes on the placements (from the CAD and the build photos):
# - fan: the support's three bosses have 2 mm pilot holes on a 23.5 mm square; the back cover's window is right under them
# - XL4015 #1: the photos show its toroid through the fan blades and a 220 uF / 35 V cap just beside the fan, so it sits on the
#   bosses between the fan and the Pi, parts facing the fan
# - INA219 / ADS1015: right wing next to the switch, INA219 on top of the ADS1015 (photo)
# - BMS: the left wing's wall has two slot clips 41 mm apart (the BMS's length) at z -20; the photo of the inside shows a long green
#   board standing along that wall, so the BMS stands in the clips
# - XL4015 #2 and the USB-C board: standing in the left wing beside the BMS; the USB-C mouth faces the opening in the wing's outer wall
