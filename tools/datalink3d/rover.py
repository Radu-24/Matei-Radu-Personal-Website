# The DataLink rover, part by part, to real dimensions (mm). Layout from the thesis photos (Fig. 5.4, 5.5).
# World: ground y = 0, rover front +Z, rover's left +X.
import json, math, numpy as np
from geom import *
from atlas import *

# ---------- palette (sRGB hex) ----------
PLA = '#19191b'; PLA2 = '#202023'
ALU = '#2b2d32'            # black anodised aluminium (T101 frame)
STEEL = '#d3d6da'; TIN = '#c9cbcd'; GOLD = '#d4af5a'; BRASS = '#c49a44'; COPPER = '#c27a3e'
BLK = '#1e1f22'; BLK2 = '#2a2b2f'; WHITE = '#ecebe6'; BEIGE = '#e6dcc4'
TRACK = '#141416'; SPROCKET = '#8e9297'; IDLER = '#18181a'; IDLER_CAP = '#8e9297'     # grey plastic wheels (photos)
CAN = '#bcc0c5'; GEARBOX = '#cfd2d6'
YEL_HDR = '#e2b025'; BLUE_POT = '#2156d6'; CAP_SLV = '#2a2c31'; CAP_TOP = '#b8bbbf'
PURPLE = '#6b2b8f'; BLUE_PCB = '#1f4fa8'
FIBRE = '#f2c12e'; APC = '#2aa85a'; ETH = '#8f949c'; USBC = '#18191c'
RED = '#c8282c'; BLACKW = '#151515'; BROWN = '#6b3b22'; ORANGE = '#e8862a'

ATL = None
MATS = ['pla', 'plastic', 'rubber', 'pcb', 'metal', 'satin', 'gold', 'glass', 'emit', 'label']

class Comp:
    """a group of (mat, geometry) pieces in a local frame, plus atlas bake regions"""
    def __init__(s): s.p = []; s.bk = []
    def add(s, mat, g, col=None):
        if col is not None: g.col(col)
        elif g.C is None: g.col('#ffffff')
        s.p.append((mat, g)); return g
    def bake(s, region, x0, x1, z0, z1, y, ny=1):
        s.bk.append([region, np.array([x0, y, z0]), np.array([x1 - x0, 0, 0]), np.array([0, 0, z1 - z0]), np.array([0, ny, 0])])
    def M(s, R=None, t=(0, 0, 0)):
        for _, g in s.p: g.M(R, t)
        for b in s.bk:
            if R is not None:
                b[1] = np.asarray(R) @ b[1]; b[2] = np.asarray(R) @ b[2]; b[3] = np.asarray(R) @ b[3]; b[4] = np.asarray(R) @ b[4]
            b[1] = b[1] + np.asarray(t, np.float64)
        return s
    def extend(s, o):
        s.p += o.p; s.bk += o.bk; return s

def wtex(g, A):
    """non-textured: point every vertex at the atlas' white block"""
    if g.UV is None: g.UV = np.full((len(g.V), 2), -1.0)
    m = g.UV[:, 0] < 0
    g.UV[m] = A.white_uv()
    return g

# ---------------------------------------------------------------- small parts
def header_male(n, rows=1, pitch=2.54, pin_len=11.5, base_col=BLK, pin_col=GOLD, up=8.5):
    """male pin header lying on y=0 (board top), pins pointing up `up` mm"""
    c = Comp()
    L = n * pitch
    c.add('plastic', rbox(L, 2.5, rows * pitch, 0.25, 1, (L / 2 - pitch / 2, 1.25, (rows - 1) * pitch / 2)), base_col)
    for i in range(n):
        for j in range(rows):
            c.add('gold', box(0.64, up, 0.64, (i * pitch, up / 2 + 0.1, j * pitch)), pin_col)
    return c

def header_female(n, rows=1, pitch=2.54, h=8.5, col=BLK):
    c = Comp(); L = n * pitch
    c.add('plastic', rbox(L, h, rows * pitch, 0.3, 1, (L / 2 - pitch / 2, h / 2, (rows - 1) * pitch / 2)), col)
    for i in range(n):
        for j in range(rows):
            c.add('plastic', box(1.0, 0.2, 1.0, (i * pitch, h + 0.05, j * pitch)), '#050505')
    return c

def smd(c, x, z, w, d, h, col=BLK, y=0, mat='plastic', r=0.08):
    c.add(mat, rbox(w, h, d, min(r, h / 2 - .01, w / 2 - .01, d / 2 - .01), 1, (x, y + h / 2, z)) if r > 0 else box(w, h, d, (x, y + h / 2, z)), col)

def ecap(c, x, z, r, h, y=0, sleeve=CAP_SLV, top=CAP_TOP, stripe='#9aa0a8'):
    c.add('plastic', cyl(r, h - 0.6, 28, center=(x, y + (h - 0.6) / 2, z), bevel=0.4), sleeve)
    c.add('metal', cyl(r - 0.3, 0.6, 28, center=(x, y + h - 0.3, z)), top)
    # vent cross
    c.add('metal', box(r * 1.4, 0.08, 0.25, (x, y + h + 0.03, z)), '#7e838a'); c.add('metal', box(0.25, 0.08, r * 1.4, (x, y + h + 0.03, z)), '#7e838a')
    c.add('plastic', cyl(r + 0.02, h * 0.55, 28, center=(x, y + h * 0.45, z + 0.0)).sc(1, 1, 1).t(0, 0, 0), sleeve)
    return c

def screw_head(c, x, y, z, r=2.0, h=1.2, col=STEEL, axis='y'):
    g = cyl(r, h, 20, r2=r * 0.92, center=(0, h / 2, 0), bevel=0.25)
    s1 = box(r * 1.3, 0.35, 0.45, (0, h + 0.05, 0)); s2 = box(0.45, 0.35, r * 1.3, (0, h + 0.05, 0))
    gg = merge([g, s1.col('#5a5d62'), s2.col('#5a5d62')])
    if g.C is None: pass
    if axis == 'z': gg.r(90, 0, 0)
    elif axis == '-z': gg.r(-90, 0, 0)
    elif axis == 'x': gg.r(0, 0, -90)
    elif axis == '-x': gg.r(0, 0, 90)
    gg.t(x, y, z)
    c.add('metal', gg, None if gg.C is not None else col)
    if gg.C is not None:
        gg.C[:len(g.V)] = hexc(col)
    return c

# ---------------------------------------------------------------- Raspberry Pi 5
def pi5(A, hs_kind='tall'):
    """board frame: x 0..85 (PCIe edge -> USB/Ethernet edge), z 0..56 (GPIO edge -> HDMI edge), PCB y 0..1.6.
    hs_kind 'tall': finned heatsink (rover); 'low': the controller's flat 17 x 17 x 3.4 mm heatsink"""
    c = Comp(); T = 1.6
    pcb = rbox(85, T, 56, 0.6, 2, (42.5, T / 2, 28))
    # holes: carve visually with dark discs on top (texture) - geometry stays solid
    uv_top(pcb, A.uv('pi5'), 0, 85, 0, 56); c.add('pcb', side_col(pcb, '#1d6b33'))
    c.bake('pi5', 0, 85, 0, 56, T + 0.02)
    y = T
    # SoC BCM2712 (metal lid) + heatsink (silver fins)
    smd(c, 33, 26, 16.5, 16.5, 1.2, '#9aa0a6', y, 'metal', 0.4)
    hs = Comp()
    if hs_kind == 'low':
        hs.add('satin', rbox(17, 1.0, 17, 0.3, 1, (33, y + 1.2 + 0.5, 26)), '#c9ccd0')
        for i in range(8):
            hs.add('satin', rbox(0.9, 2.2, 16.6, 0.2, 1, (33 - 7.35 + i * 2.1, y + 1.2 + 1.0 + 1.1, 26)), '#cfd2d5')
    else:
        hs.add('satin', rbox(14, 2.2, 14, 0.4, 1, (33, y + 1.2 + 1.1, 26)), '#c9ccd0')
        for i in range(6):
            hs.add('satin', rbox(1.1, 5.2, 13.6, 0.3, 1, (33 - 6.3 + i * 2.52, y + 1.2 + 2.2 + 2.6, 26)), '#cfd2d5')
    c.extend(hs)
    # RAM, RP1, PMIC, wifi can
    smd(c, 15, 24, 12.5, 14, 1.0, '#141518', y, 'plastic', 0.2)
    smd(c, 54.5, 27.5, 11.5, 11.5, 1.0, '#141518', y, 'plastic', 0.2)
    smd(c, 12, 45, 6.5, 6.5, 0.9, '#141518', y, 'plastic', 0.15)
    smd(c, 67.5, 8, 8, 7, 0.9, '#141518', y, 'plastic', 0.15)
    c.add('metal', rbox(13, 1.6, 10.5, 0.3, 1, (10.5, y + 0.8, 33.5)), '#b9bdc2')   # wireless shield
    # GPIO header 2x20 (pins up)
    h = header_male(20, 2, pin_len=11, up=8.4).M(None, (7.1 + 1.27, y, 3.5 - 1.27)); c.extend(h)
    # USB 2 stack (black), USB 3 stack (blue), Ethernet - overhanging the x=85 edge by ~2.5
    def usb_stack(zc, tongue):
        u = Comp(); W, D, H = 17.6, 14.6, 16.0
        sh = Manifold.cube([W, H, D], True)
        for yy in (H * 0.27, -H * 0.24):
            sh = sh - Manifold.cube([3.0, 5.6, 12.6], True).translate([W / 2 - 1.2, yy, 0])
        g = from_manifold(sh.translate([85 + 2.6 - W / 2, y + H / 2, zc]), 25)
        u.add('metal', g, STEEL)
        xc = 85 + 2.6 - W / 2
        for dz in (-3.6, 3.6):    # spring tabs on top, seam and dimples on the sides
            u.add('metal', box(5.0, 0.25, 2.0, (xc + 4.0, y + H + 0.12, zc + dz)), '#b9bdc2')
        u.add('metal', box(W - 3, 0.3, 0.35, (xc, y + H + 0.15, zc)), '#aeb2b8')
        for sz in (-1, 1):
            for yy in (H * 0.27, -H * 0.24):
                u.add('metal', box(3.0, 1.2, 0.3, (xc + 3.5, y + H / 2 + yy, zc + sz * (D / 2 + 0.12))), '#b4b8be')
            u.add('metal', box(W - 2, 0.35, 0.3, (xc, y + H / 2, zc + sz * (D / 2 + 0.14))), '#a9adb3')
        for yy in (H * 0.27, -H * 0.24):
            u.add('plastic', box(12.0, 1.9, 11.0, (85 + 2.6 - 6.4, y + H / 2 + yy - 0.6, zc)), tongue)
            for k in range(4):
                u.add('gold', box(6.0, 0.15, 0.9, (85 + 2.6 - 4.5, y + H / 2 + yy + 0.4, zc - 3.6 + k * 2.4)), GOLD)
        return u
    c.extend(usb_stack(9.0, '#151618')); c.extend(usb_stack(27.0, '#2364d8'))
    # Ethernet
    e = Comp(); W, D, H = 21.3, 16.0, 13.6
    sh = Manifold.cube([W, H, D], True) - Manifold.cube([4, 8.2, 12.0], True).translate([W / 2 - 1.5, -0.8, 0])
    e.add('metal', from_manifold(sh.translate([85 + 2.7 - W / 2, y + H / 2, 45.5]), 25), STEEL)
    xc = 85 + 2.7 - W / 2
    for dz in (-4.5, 4.5): e.add('metal', box(6.0, 0.25, 2.2, (xc + 5.0, y + H + 0.12, 45.5 + dz)), '#b9bdc2')
    e.add('label', box(9.0, 0.15, 8.0, (xc - 3.0, y + H + 0.08, 45.5)), '#e9e9e4')
    for sz in (-1, 1): e.add('metal', box(W - 2, 0.35, 0.3, (xc, y + H / 2 + 2, 45.5 + sz * (D / 2 + 0.14))), '#a9adb3')
    e.add('plastic', box(9, 7.6, 11.4, (85 + 2.7 - 4.0 - 4.5, y + H / 2 - 0.8, 45.5)), '#1b1c1f')
    e.add('emit', box(0.4, 1.6, 2.6, (85 + 2.75, y + 2.0, 39.4)), '#2fe36a'); e.add('emit', box(0.4, 1.6, 2.6, (85 + 2.75, y + 2.0, 51.6)), '#ffb020')
    c.extend(e)
    # USB-C, 2x micro HDMI (front edge z=56)
    for (x, w, hh, col) in [(11.2, 9.0, 3.3, '#c7cacd'), (25.8, 7.5, 3.5, '#c7cacd'), (39.2, 7.5, 3.5, '#c7cacd')]:
        g = rbox(w, hh, 7.4, 1.0 if w == 9.0 else 0.6, 2, (x, y + hh / 2, 56 - 3.0))
        c.add('metal', g, col)
        c.add('plastic', box(w - 1.6, hh - 1.4, 0.4, (x, y + hh / 2, 56 + 0.6)), '#0c0c0e')
    # camera / display FPC connectors (2), beige with black latch
    for x in (47.5, 53.0):
        c.add('plastic', box(3.6, 1.2, 14.5, (x, y + 0.6, 45)), BEIGE)
        c.add('plastic', box(3.8, 0.7, 14.8, (x - 0.4, y + 1.45, 45)), '#2b2b2b')
    # PCIe FPC (x=0 edge), fan connector, power button, RTC, UART, LEDs
    c.add('plastic', box(3.6, 1.2, 13.5, (2.4, y + 0.6, 28)), BEIGE); c.add('plastic', box(3.8, 0.7, 13.8, (2.0, y + 1.45, 28)), '#2b2b2b')
    c.add('plastic', box(4.2, 3.0, 3.0, (64.5, y + 1.5, 4.8)), WHITE)
    c.add('plastic', box(2.8, 1.6, 3.6, (1.4, y + 0.8, 49.0)), '#e9e9e9'); c.add('plastic', box(2.0, 1.2, 2.4, (0.6, y + 1.9, 49.0)), '#222')
    c.add('plastic', box(4.0, 2.4, 3.0, (35.5, y + 1.2, 50.5)), WHITE)
    c.add('plastic', box(4.0, 2.4, 3.0, (60.0, y + 1.2, 18.0)), WHITE)
    c.add('emit', box(1.4, 0.5, 0.8, (2.0, y + 0.25, 44.0)), '#ff3b3b'); c.add('emit', box(1.4, 0.5, 0.8, (2.0, y + 0.25, 41.5)), '#30e060')
    # micro SD under the board
    c.add('metal', box(12, 1.4, 11.5, (5.5, -0.7, 28)), '#b3b7bb')
    return c

# ---------------------------------------------------------------- Arduino Nano + IO shield
def nano(A):
    """board frame: x 0..43.2, z 0..17.8 ; USB at x = 43.2"""
    c = Comp(); T = 1.6
    g = rbox(43.2, T, 17.8, 0.4, 1, (21.6, T / 2, 8.9)); uv_top(g, A.uv('nano'), 0, 43.2, 0, 17.8); c.add('pcb', side_col(g, '#1a3f8c'))
    y = T
    c.add('plastic', rbox(7, 1.1, 7, 0.15, 1).r(0, 45, 0).t(21.0, y + 0.55, 8.9), '#121315')  # ATmega, turned 45 degrees
    for k in range(8):
        for sg in (-1, 1):
            for ax in (0, 1):
                d = -2.6 + k * 0.75
                p = np.array([d, 0, sg * 3.8]) if ax == 0 else np.array([sg * 3.8, 0, d])
                q = rot(0, 45, 0) @ p
                c.add('metal', box(0.3, 0.2, 0.3, (21.0 + q[0], y + 0.1, 8.9 + q[2])), TIN)
    smd(c, 33.5, 8.9, 3.9, 9.9, 1.4, '#121315', y, 'plastic', 0.15)   # CH340
    c.add('metal', rbox(4.6, 3.5, 3.7, 0.6, 2, (12.2, y + 1.75, 13.3)), '#c8ccd0')   # crystal-ish can
    c.add('metal', rbox(9.2, 3.9, 7.6, 1.2, 2, (43.2 - 3.0, y + 1.95, 8.9)), '#c4c8cc')  # USB connector
    c.add('plastic', box(6.0, 1.4, 6.0, (16.0, y + 0.7, 4.0)), '#d8d8d8'); c.add('plastic', cyl(1.3, 0.8, 16, center=(16.0, y + 1.8, 4.0)), '#222')   # reset button
    for k, cc in enumerate(['#ff4040', '#40ff70', '#ffd040', '#ffd040']):
        c.add('emit', box(1.0, 0.5, 0.6, (26 + k * 1.6, y + 0.25, 14.8)), cc)
    # pins under (into the shield socket)
    for i in range(15):
        for zz in (1.27, 16.53):
            c.add('gold', box(0.64, 6.0, 0.64, (1.0 + 1.27 + i * 2.54 + 1.4, -3.0, zz)), GOLD)
    return c

def nano_shield(A):
    """board frame: x 0..57, z 0..54, PCB y 0..1.6"""
    c = Comp(); T = 1.6
    g = rbox(57, T, 54, 0.5, 1, (28.5, T / 2, 27)); uv_top(g, A.uv('nanosh'), 0, 57, 0, 54); c.add('pcb', side_col(g, '#1a428c'))
    c.bake('nanosh', 0, 57, 0, 54, T + 0.02)
    y = T
    # Nano sockets (2 x 15 female) along x in the middle
    for zz in (19.0, 34.24):
        h = header_female(15, 1, h=8.5).M(None, (9.5, y, zz)); c.extend(h)
    # rows of male pins (G V S), yellow bases, along the z=4..12 and z=42..50 edges
    for (z0, n, x0) in [(6.5, 12, 8.0), (42.0, 8, 12.0)]:
        h = header_male(n, 3, up=6.0, base_col=YEL_HDR).M(None, (x0, y, z0)); c.extend(h)
    # side headers (I2C / power)
    h = header_male(4, 3, up=6.0, base_col=YEL_HDR).M(rot(0, 90, 0), (52.5, y, 36)); c.extend(h)
    # DC jack (black), at the far corner
    c.add('plastic', rbox(9.0, 11.0, 14.0, 0.6, 2, (50.0, y + 5.5, 7.5)), '#141416')
    c.add('plastic', cyl(3.2, 0.5, 20, axis='x', center=(57.0, y + 6.5, 7.5)), '#050505')
    # power LED + regulator
    c.add('emit', box(1.4, 0.5, 0.8, (45.0, y + 0.25, 16.5)), '#ff2a2a')
    smd(c, 45.0, 26.0, 6.5, 7.0, 2.3, '#111214', y, 'plastic', 0.2)
    c.add('metal', box(6.5, 0.4, 3.0, (45.0, y + 0.2, 21.8)), TIN)
    n = nano(A).M(None, (9.5 - 2.27 - 1.4 + 0.0, y + 8.5 + 3.0, 19.0 - 1.27)); c.extend(n)
    return c

# ---------------------------------------------------------------- XL4015
def xl4015(A, region='xl4015', bake=True):
    """board frame x 0..54 (IN end -> OUT end), z 0..23"""
    c = Comp(); T = 1.6
    g = rbox(54, T, 23, 0.4, 1, (27, T / 2, 11.5)); uv_top(g, A.uv(region), 0, 54, 0, 23); c.add('pcb', side_col(g, '#1a408a'))
    if bake: c.bake(region, 0, 54, 0, 23, T + 0.02)
    y = T
    ecap(c, 10.5, 6.5, 4.0, 10.5, y); ecap(c, 43.5, 6.5, 4.0, 10.5, y)
    # toroid inductor: yellow core + copper winding
    tor = torus(5.2, 2.6, 40, 14, (19.5, y + 2.6 + 0.3, 14.0)); c.add('plastic', tor, '#d6b02a')
    wind = torus(5.2, 2.75, 40, 10, (19.5, y + 2.6 + 0.3, 14.0))
    # winding: many thin strands -> approximate with darker copper band segments
    th = np.arctan2(wind.V[:, 2] - 14.0, wind.V[:, 0] - 19.5)
    keep = (np.sin(th * 9) > -0.1)
    wind.C = None; c.add('metal', wind, COPPER)
    # XL4015 IC + heatsink
    smd(c, 31.5, 9.5, 10.0, 9.0, 2.2, '#16171a', y, 'plastic', 0.2)
    hs = Comp(); hs.add('satin', rbox(11, 2, 10, 0.3, 1, (31.5, y + 2.2 + 1.0, 9.5)), '#c3c7cc')
    for i in range(5): hs.add('satin', rbox(1.0, 6.0, 9.6, 0.25, 1, (31.5 - 4.4 + i * 2.2, y + 4.2 + 3.0, 9.5)), '#cdd0d4')
    c.extend(hs)
    # diode, small caps
    smd(c, 26.0, 18.5, 5.5, 4.0, 2.2, '#121315', y, 'plastic', 0.15)
    smd(c, 38.0, 17.5, 3.2, 1.6, 1.2, '#b9926a', y, 'plastic', 0.1)
    # blue multi-turn trimpot with brass screw
    c.add('plastic', rbox(9.5, 9.8, 4.6, 0.4, 1, (27.5, y + 4.9, 18.0)), BLUE_POT)
    c.add('metal', cyl(1.1, 1.6, 14, axis='x', center=(22.0, y + 8.0, 18.0)), BRASS)
    c.add('emit', box(1.4, 0.5, 0.8, (40.5, y + 0.25, 19.8)), '#ff3030')
    return c

# ---------------------------------------------------------------- TCA9548A
def tca(A):
    """board frame x 0..32, z 0..21; mounting holes at (3.1, 10.5) and (28.9, 10.5); two rows of 12 pins, soldered pins-up (photo)"""
    c = Comp(); T = 1.6
    g = rbox(32, T, 21, 0.4, 1, (16, T / 2, 10.5)); uv_top(g, A.uv('tca'), 0, 32, 0, 21); c.add('pcb', side_col(g, '#55246f'))
    c.bake('tca', 0, 32, 0, 21, T + 0.02)
    y = T
    smd(c, 16, 10.5, 7.8, 4.4, 1.1, '#141518', y, 'plastic', 0.1)
    for i in range(12):
        for sg in (-1, 1):
            c.add('metal', box(0.25, 0.25, 0.9, (16 - 3.6 + i * 0.65, y + 0.12, 10.5 + sg * 2.6)), TIN)
    for zz in (1.6, 19.4):  # the headers: black bases on top, pins up
        h = header_male(12, 1, up=6.0).M(None, (16 - 5.5 * 2.54, y, zz)); c.extend(h)
        for i in range(12):   # solder joints under the board
            c.add('metal', cyl(0.55, 0.6, 10, center=(16 - 5.5 * 2.54 + i * 2.54, -0.3, zz)), TIN)
    smd(c, 9.0, 6.5, 1.6, 0.8, 0.5, '#2a2a2a', y); smd(c, 23.0, 6.5, 1.6, 0.8, 0.5, '#2a2a2a', y)
    c.add('emit', box(1.4, 0.5, 0.8, (27.5, y + 0.25, 7.0)), '#ff3a3a')
    return c

# ---------------------------------------------------------------- VL53L0X breakout (sensor facing +y in local)
def vl53(A):
    """VL53L0X breakout 25 x 10.7: board frame x 0..25 along the face, z 0..10.7 up, sensor toward +y.
    Holes at (2.5, 5.35) and (22.5, 5.35) take the plate's two pins; the 6-pin header runs along the bottom edge, pins out of the back."""
    c = Comp(); T = 1.2
    g = rbox(25, T, 10.7, 0.4, 1, (12.5, T / 2, 5.35)); uv_top(g, A.uv('vl53'), 0, 25, 0, 10.7); c.add('pcb', side_col(g, '#55246f'))
    y = T
    c.add('plastic', rbox(4.4, 1.0, 2.4, 0.15, 1, (12.5, y + 0.5, 6.6)), '#0e0e10')
    c.add('glass', box(0.9, 0.06, 0.9, (11.5, y + 1.02, 6.6)), '#1a0f0a'); c.add('glass', box(0.9, 0.06, 0.9, (13.6, y + 1.02, 6.6)), '#1a0f0a')
    smd(c, 8.0, 7.2, 2.9, 1.6, 1.0, '#141518', y)
    smd(c, 17.0, 7.6, 1.6, 0.8, 0.5, '#2e2e2e', y); smd(c, 17.0, 5.6, 1.6, 0.8, 0.5, '#2e2e2e', y)
    for (x, z) in ((2.5, 5.35), (22.5, 5.35)):
        c.add('metal', cyl(1.5, 0.08, 16, center=(x, y + 0.04, z)), TIN)
    for i in range(6):
        c.add('gold', box(0.64, 7.0, 0.64, (12.5 - 6.35 + i * 2.54, -3.3, 1.5)), GOLD)   # pins out of the back
    c.add('plastic', box(6 * 2.54, 2.5, 2.5, (12.5, -1.25, 1.5)), BLK)
    return c

# ---------------------------------------------------------------- camera board (lens toward +y local)
def camera(A):
    c = Comp(); T = 1.0
    g = rbox(25, T, 24, 0.5, 1, (12.5, T / 2, 12)); uv_top(g, A.uv('cam'), 0, 25, 0, 24); c.add('pcb', side_col(g, '#141516'))
    y = T
    c.add('plastic', rbox(8.6, 3.4, 8.6, 0.4, 1, (12.5, y + 1.7, 9.5)), '#101012')
    c.add('plastic', cyl(4.2, 3.6, 32, center=(12.5, y + 3.4 + 1.8, 9.5), bevel=0.4), '#0d0d0f')
    c.add('metal', cyl(3.0, 0.8, 32, center=(12.5, y + 7.0 + 0.4, 9.5)), '#2a2c30')
    c.add('glass', cyl(2.6, 0.3, 32, center=(12.5, y + 7.8, 9.5)), '#0a1424')
    c.add('emit', cyl(0.9, 0.05, 16, center=(12.5, y + 7.96, 9.5)), '#203a6a')
    # connector at the bottom edge (z=24), beige
    c.add('plastic', box(21, 2.2, 5.0, (12.5, -1.1, 21.0)), '#151515'); c.add('plastic', box(19, 0.8, 3.0, (12.5, -2.6, 21.5)), BEIGE)
    return c

# ---------------------------------------------------------------- MG90S servo (body along x, output shaft up)
def mg90s(A, ear_y=15.9):
    """frame: body bottom at y=0, centred x/z; output shaft at x=+5.9; the ears' underside at ear_y"""
    c = Comp()
    body = rbox(22.8, 22.7, 12.2, 0.8, 2, (0, 11.35, 0))
    c.add('plastic', body, '#1b1c20')
    lab = box(22.9, 4.0, 12.3, (0, 20.5, 0))   # the strip of label that shows above the tower
    uv_face(lab, A.uv('servo'), (0, 0, 1), (-11.4, 18.5, 6.15), (22.8, 0, 0), (0, 4.0, 0))
    uv_face(lab, A.uv('servo'), (0, 0, -1), (11.4, 18.5, -6.15), (-22.8, 0, 0), (0, 4.0, 0))
    c.add('label', side_col(lab, '#1b1c20'))
    # mounting ears
    c.add('plastic', rbox(32.2, 2.5, 12.2, 0.6, 1, (0, ear_y + 1.25, 0)), '#1b1c20')
    for sg in (-1, 1): c.add('plastic', cyl(1.1, 2.6, 12, center=(sg * 13.9, ear_y + 1.25, 0)), '#050505')
    # top gear housing
    c.add('plastic', cyl(6.0, 4.2, 32, center=(5.9, 22.7 + 2.1, 0), bevel=0.6), '#1b1c20')
    c.add('plastic', rbox(10, 3.6, 10, 2.0, 2, (-2, 22.7 + 1.8, 0)), '#1b1c20')
    c.add('gold', cyl(2.4, 3.2, 20, center=(5.9, 22.7 + 4.2 + 1.6, 0)), BRASS)
    # horn (double arm)
    hy = 22.7 + 4.2 + 2.6
    lobe = lambda dx: (CrossSection.circle(3.6, qs(32)) + CrossSection.circle(2.0, qs(24)).translate([dx, 0])).hull()
    horn = lobe(15.5) + lobe(-15.5)
    for k in range(1, 7):
        horn = horn - CrossSection.circle(0.55, qs(10)).translate([4.0 + k * 1.9, 0]) - CrossSection.circle(0.55, qs(10)).translate([-4.0 - k * 1.9, 0])
    hc = Comp()
    hg = extrude_cs(horn, 1.9, 0, 40).r(0, 90, 0).t(5.9, hy, 0)
    hc.add('plastic', hg, '#121214')
    hc.add('plastic', cyl(3.4, 3.0, 24, center=(5.9, hy - 1.0, 0)), '#121214')
    hc.add('metal', cyl(1.2, 0.6, 12, center=(5.9, hy + 2.2, 0)), STEEL)
    c.horn = hc
    return c, hy + 1.9

# ---------------------------------------------------------------- media converter (fibre side at z=0)
def converter(A, L=59.0):
    """board frame x 0..25 (DC jack side at x=25), z 0..L (fibre end at z=0, RJ45 at z=L)"""
    c = Comp(); T = 1.6
    g = rbox(25, T, L, 0.4, 1, (12.5, T / 2, L / 2)); uv_top(g, A.uv('conv'), 0, 25, 0, L); c.add('pcb', side_col(g, '#1a428e'))
    c.bake('conv', 0, 25, 0, L, T + 0.02)
    y = T
    # BiDi transceiver: black housing with grille slots, SC receptacle opening at z=0
    W, H, D = 24.2, 12.0, 31.0
    hb = Manifold.cube([W, H, D], True)
    for i in range(7):
        hb = hb - Manifold.cube([1.4, 3.0, 14.0], True).translate([-7.2 + i * 2.4, H / 2, 6.0])
    hb = hb - Manifold.cube([7.6, 7.6, 9.0], True).translate([0, 0.2, -D / 2 + 3.5])
    hg = from_manifold(hb.translate([12.5, y + H / 2, D / 2 - 1.5]), 30)
    c.add('plastic', hg, '#131315')
    c.add('plastic', cyl(1.3, 6.0, 20, axis='z', center=(12.5, y + H / 2 + 0.2, 2.5)), '#2f6fe0')  # ferrule sleeve
    lab = box(13, 0.2, 11, (12.5 + 4.0, y + H + 0.1, D - 1.5 - 7.5))
    uv_top(lab, A.uv('labB'), 12.5 + 4.0 - 6.5, 12.5 + 4.0 + 6.5, D - 1.5 - 13.0, D - 1.5 - 2.0)
    c.add('label', side_col(lab, '#e6e6e2'))
    # RJ45 + DC jack at the z = L end
    e = Manifold.cube([16.0, 13.4, 21.0], True) - Manifold.cube([12.0, 8.0, 4.0], True).translate([0, -1.0, 10.5])
    c.add('metal', from_manifold(e.translate([8.5, y + 6.7, L - 10.5 + 1.5]), 25), STEEL)
    c.add('plastic', box(11.4, 7.6, 7.0, (8.5, y + 5.7, L - 1.5)), '#1b1c1f')
    c.add('plastic', rbox(8.8, 10.8, 14.0, 0.6, 2, (20.6, y + 5.4, L - 7.0)), '#141416')
    c.add('plastic', cyl(2.9, 0.4, 20, axis='z', center=(20.6, y + 6.2, L + 0.05)), '#050505')
    smd(c, 12, 36 * L / 64, 10, 10, 1.1, '#151619', y)
    for k, cc in enumerate(['#30ff7a', '#30ff7a', '#ffb52a']):
        c.add('emit', box(1.4, 0.6, 0.9, (5 + k * 3, y + 0.3, 26.5 * L / 64)), cc)
    return c

# ---------------------------------------------------------------- perfboard (bare on top, as in the photos)
def perf(A):
    """board frame x 0..30, z 0..70: a double-sided prototype board; the wiring is underneath"""
    c = Comp(); T = 1.6
    g = rbox(30, T, 70, 0.5, 1, (15, T / 2, 35)); uv_top(g, A.uv('perf'), 0, 30, 0, 70); c.add('pcb', side_col(g, '#1b6a43'))
    c.bake('perf', 0, 30, 0, 70, T + 0.02)
    for (x, z) in [(1.6, 1.6), (28.4, 1.6), (1.6, 68.4), (28.4, 68.4)]:
        c.add('metal', cyl(1.6, 0.9, 16, center=(x, T + 0.45, z), bevel=0.2), '#c9ccd0')
    return c




# ================================================================ Radu's CAD of the rover (Joystick - 2.step)
# The printed plate and the battery box come straight from the CAD file, re-meshed at two tolerances (cad/rover_cad_lo|hi.npz).
# CAD axes: x = rover's right, y = forward, z = up.  Model axes: X = rover's left = -x, Y = up = z + DY, Z = forward = y.
import geom as _gm
U_T = 2.0                  # T101 sheet thickness
# The printed chassis sits on top of the T101: the battery box stands on the aluminium deck and the plate rests on the box,
# exactly as the CAD has them; the motors hang under the deck (Radu's photos and description).
DECK_T = 2.0               # T101 sheet thickness
DECK_TOP = 49.5            # top of the deck, about 5 mm below the tracks' top run: the box's foot sits between the tracks
BOX_BOT = -30.12           # underside of the battery box (cad z)
DY = DECK_TOP - BOX_BOT    # cad z -> model y, for the box and the plate
BOX_DY = DY
PLB = 10.89 + DY           # plate underside = top of the box   (90.51)
PL_TOP = 12.89 + DY        # plate top                        (92.51)
PL_MID = 11.89 + DY        # mid-plane of the plate: the sensor pins
CADR = np.array([[-1.0, 0, 0], [0, 0, 1.0], [0, 1.0, 0]])
PW, PD = 173.84, 193.0     # the plate's painted rectangle (x across, z along, centred)
def cad_y(z): return z + DY
def box_y(z): return z + BOX_DY

import contextlib
@contextlib.contextmanager
def qcap(hi, lo=None):
    """build with a lower tessellation quality (parts that are hidden when the rover is assembled)"""
    old = _gm.Q
    _gm.setQ(min(old, hi) if old > 1.5 else min(old, lo if lo is not None else old))
    try: yield
    finally: _gm.setQ(old)

def wire(points, r=0.6, col=RED, mat='rubber'):
    """a cable through control points, with a fixed number of segments (so the detailed level does not explode)"""
    hi = _gm.Q > 1.5
    n = (12 + 8 * len(points)) if hi else (6 + 5 * len(points))
    return (mat, tube(spline(points, n, absolute=True), r, 10 if hi else 6, cap=True, absolute=True).col(col))

def cad_mesh(i, mesh_dir):
    lev = 'hi' if _gm.Q > 1.5 else 'lo'
    d = np.load(f'{mesh_dir}/rover_cad_{lev}.npz')
    return d[f'v{i}'] @ CADR.T + np.array([0, DY, 0]), d[f'f{i}']

def _sub(V, F, mask):
    f = F[mask]; u, inv = np.unique(f.ravel(), return_inverse=True)
    return V[u], inv.reshape(-1, 3)

def plate(A, mesh_dir):
    """the printed plate from the CAD: plate, servo tower, shelf, camera panel, Pi bosses, clips, rails and sensor pins.
    Its top face carries the painted print (each facet's lines in its own direction, as in the photos)."""
    c = Comp()
    V, F = cad_mesh(0, mesh_dir)
    m = trimesh.Trimesh(V, F, process=True)
    V, F = np.asarray(m.vertices), np.asarray(m.faces)
    fn = np.asarray(m.face_normals); ty = V[F][:, :, 1]
    top = (fn[:, 1] > 0.999) & (np.abs(ty - PL_TOP).max(1) < 0.02)
    bot = (fn[:, 1] < -0.999) & (np.abs(ty - PLB).max(1) < 0.02)
    Vt, Ft = _sub(V, F, top)
    gt = G(Vt, Ft, np.tile([0, 1.0, 0], (len(Vt), 1)))
    u0, v0, u1, v1 = A.uv('plate')
    gt.UV = np.stack([u0 + (Vt[:, 0] + PW / 2) / PW * (u1 - u0), v0 + (Vt[:, 2] + PD / 2) / PD * (v1 - v0)], 1)
    gt.C = np.ones((len(Vt), 3)); gt.AOFIX = np.ones(len(Vt))          # the top's occlusion is baked per texel
    c.add('pla', gt)
    Vb, Fb = _sub(V, F, bot)
    gb = G(Vb, Fb, np.tile([0, -1.0, 0], (len(Vb), 1))).col(PLA); gb.AOFIX = np.full(len(Vb), 0.5)
    c.add('pla', gb)
    Vr, Fr = _sub(V, F, ~(top | bot))
    c.add('pla', smooth(Vr, Fr, 28), PLA)
    c.bake('plate', -PW / 2, PW / 2, -PD / 2, PD / 2, PL_TOP + 0.02)
    return c

def battery_box(A, mesh_dir):
    """the printed battery box from the CAD: it stands on the T101's deck with the plate on top. Its right side (the Pi's side)
    is open above an 8 mm sill, so the two cell holders slide out sideways."""
    c = Comp(); V, F = cad_mesh(1, mesh_dir)
    c.add('pla', smooth(V, F, 28), PLA)
    return c

# footprints on the plate (x0, x1, z0, z1), from the CAD; the painted facets are a triangulation around them
FOOT = [(-72.42, -18.42, -15.66, 13.34),     # the hollow shelf under the 3.3 V XL4015 (the converter's power cord is coiled inside)
        (-9.15, 18.05, -4.35, 12.35),        # servo tower
        (-17.0, 17.0, 81.28, 86.5),          # front camera panel
        (-79.0, -20.0, -73.5, -20.0),        # rails under the Nano shield
        (18.5, 39.5, -63.15, -31.15),        # rails under the TCA9548A
        (53.14, 79.64, -54.23, 7.87),        # rails under the fibre converter
        (11.42, 46.92, -25.43, 50.07),       # perfboard clips
        (-79.95, 5.05, 16.0, 72.0),          # Pi 5 bosses
        (-2.52, 3.33, -33.73, -27.73), (-2.52, 3.33, -13.23, -7.23)]     # cable clips behind the tower
HOLES = [(64.87, 34.44, 5.0), (44.87, -72.56, 5.0)]

def plate_outline():
    r = 12.0; hw = PW / 2; hd = 88.0
    arc = lambda cx, cz, a0, a1, n=8: [(cx + r * math.cos(math.radians(a)), cz + r * math.sin(math.radians(a))) for a in np.linspace(a0, a1, n)]
    return np.array(arc(hw - r, -hd + r, -90, 0) + arc(hw - r, hd - r, 0, 90) + arc(-hw + r, hd - r, 90, 180) + arc(-hw + r, -hd + r, 180, 270))

def _inside(poly, p):
    x, z = p; n = len(poly); ins = False
    for i in range(n):
        x0, z0 = poly[i]; x1, z1 = poly[(i + 1) % n]
        if (z0 > z) != (z1 > z) and x < x0 + (z - z0) * (x1 - x0) / (z1 - z0): ins = not ins
    return ins

def plate_tri():
    """the facets of the printed top: a constrained Delaunay over the outline, the footprints and the holes, plus a few free points"""
    import triangle
    out = plate_outline()
    V = [tuple(p) for p in out]; segs = [(i, (i + 1) % len(V)) for i in range(len(V))]
    def poly(pts):
        b = len(V); V.extend(pts); segs.extend([(b + i, b + (i + 1) % len(pts)) for i in range(len(pts))])
    for (x0, x1, z0, z1) in FOOT: poly([(x0, z0), (x1, z0), (x1, z1), (x0, z1)])
    for (x, z, r) in HOLES: poly([(x + r * math.cos(a), z + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 20, endpoint=False)])
    rng = np.random.default_rng(5); pts = []; tries = 0
    while len(pts) < 9 and tries < 20000:
        tries += 1
        p = (rng.uniform(-80, 80), rng.uniform(-82, 82))
        if not _inside(out, p): continue
        if min(math.hypot(p[0] - q[0], p[1] - q[1]) for q in list(out)) < 12: continue
        if any(x0 - 9 < p[0] < x1 + 9 and z0 - 9 < p[1] < z1 + 9 for (x0, x1, z0, z1) in FOOT): continue
        if any(math.hypot(p[0] - x, p[1] - z) < r + 10 for (x, z, r) in HOLES): continue
        if any(math.hypot(p[0] - q[0], p[1] - q[1]) < 28 for q in pts): continue
        pts.append(p)
    V.extend(pts)
    holes = [(x, z) for (x, z, r) in HOLES] + [((x0 + x1) / 2, (z0 + z1) / 2) for (x0, x1, z0, z1) in FOOT]
    t = triangle.triangulate({'vertices': np.array(V), 'segments': np.array(segs), 'holes': np.array(holes)}, 'p')
    P = np.asarray(t['vertices'], np.float64); T = np.asarray(t['triangles'], np.int64)
    return P, T, np.zeros(len(P))

PLATE_TRI = None
def plate_geom():
    global PLATE_TRI
    if PLATE_TRI is None: PLATE_TRI = plate_tri()
    return PLATE_TRI

# ---------------------------------------------------------------- T101 chassis kit: 193 x 163 x 60 mm. One bent 2 mm aluminium sheet:
# a flat slotted deck, its two long edges bent down into the side walls that carry the axles (product photos).
# Two 33GB-520 gear motors (12 V, 320 rpm, from their labels) hang under the deck, one per track at opposite ends;
# a drive sprocket and an idler per side; ABS tracks.
RP = 21.3          # track pitch radius on the wheels
NT = 16            # sprocket teeth
PITCH = 2 * math.pi * RP / NT
AY = RP + 6.1      # axle height: the grousers touch the ground
NL = 49            # links per track
AZ = (NL * PITCH - 2 * math.pi * RP) / 4     # half the axle distance
TX = 70.0          # track centre line (x)
TW = 23.0          # track width
U_W = 110.0        # deck width over the side walls
U_L = 150.0        # deck length
U_WALL = 15.0      # bottom edge of the side walls
DECK_Y = DECK_TOP - DECK_T

def t101_frame():
    """the T101's frame: deck + two side walls with rounded bends, axle and motor holes, slots"""
    c = Comp(); hw = U_W / 2; R = 3.0
    fr = man_box(U_W - 2 * R, DECK_T, U_L, (0, DECK_Y + DECK_T / 2, 0))
    for sx in (-1, 1):
        fr = fr + man_box(DECK_T, DECK_TOP - R - U_WALL, U_L, (sx * (hw - DECK_T / 2), (DECK_TOP - R + U_WALL) / 2, 0))
        cx = sx * (hw - R)
        bend = (man_cyl(R, U_L, 'z', (cx, DECK_TOP - R, 0), 32) - man_cyl(R - DECK_T, U_L + 2, 'z', (cx, DECK_TOP - R, 0), 32))
        fr = fr + (bend ^ man_box(R, R, U_L, (sx * (hw - R / 2), DECK_TOP - R / 2, 0)))
        for z in (-U_L / 2, U_L / 2):    # rounded bottom corners of the walls
            corner = man_box(DECK_T + 2, 14.0, 14.0, (sx * (hw - DECK_T / 2), U_WALL + 7.0, z + (7.0 if z < 0 else -7.0))) - man_cyl(14.0, DECK_T + 4, 'x', (sx * (hw - DECK_T / 2), U_WALL + 14.0, z + (14.0 if z < 0 else -14.0)), 32)
            fr = fr - corner
    for (side, mz, iz) in ((1, -AZ, AZ), (-1, AZ, -AZ)):
        x = side * (hw - DECK_T / 2)
        fr = fr - man_cyl(4.0, 6, 'x', (x, AY, mz), 24)                              # motor bearing boss
        for dy in (-8.5, 8.5): fr = fr - man_cyl(1.6, 6, 'x', (x, AY + dy, mz), 12)   # motor screws
        fr = fr - man_cyl(2.2, 6, 'x', (x, AY, iz), 16)                              # idler axle
        for z in (-36.0, -12.0, 12.0, 36.0): fr = fr - man_box(6, 12, 16, (x, 36.0, z))
    # the deck: long slots and a grid of 3 mm holes
    for sx in (-1, 1):
        for (z0, z1) in ((-62.0, -22.0), (22.0, 62.0)): fr = fr - man_box(4.0, 6, z1 - z0, (sx * 42.0, DECK_Y + 1, (z0 + z1) / 2))
    for x in (-30.0, -10.0, 10.0, 30.0):
        for z in (-66.0, 66.0): fr = fr - man_cyl(1.6, 6, 'y', (x, DECK_Y + 1, z), 12)
    c.add('satin', from_manifold(fr, 30), ALU)
    for (side, mz) in ((1, -AZ), (-1, AZ)):
        for dy in (-8.5, 8.5): screw_head(c, side * hw, AY + dy, mz, 2.6, 1.5, '#3d4046', 'x' if side > 0 else '-x')
    return c

def sprocket():
    """drive sprocket in light grey plastic (photos): NT teeth on RP, ten curved spokes, a ring of rivets; the hub reaches 12 mm inward.
    Local axis z (+z = outer face), turned to x at the end."""
    pts = []
    for i in range(NT):
        a0 = 2 * math.pi * i / NT
        for (da, dr) in [(-0.45, -1.4), (-0.30, -0.6), (-0.17, 2.4), (0.17, 2.4), (0.30, -0.6), (0.45, -1.4)]:
            a = a0 + da * 2 * math.pi / NT; r = RP + dr
            pts.append([r * math.cos(a), r * math.sin(a)])
    teeth = Manifold.extrude(cs_poly(pts) - CrossSection.circle(RP - 5.6, qs(64)), 9.0).translate([0, 0, -4.5])
    web = CrossSection.circle(RP - 5.0, qs(64)) - CrossSection.circle(5.5, qs(32))
    NS, r0, r1 = 10, 8.6, RP - 7.0
    for k in range(NS):
        a0 = 2 * math.pi * k / NS; lead, trail = [], []
        for j in range(7):
            t = j / 6; r = r0 + (r1 - r0) * t; sw = 0.17 * t            # spokes curve a little as they go out
            lead.append([r * math.cos(a0 + 0.13 + sw), r * math.sin(a0 + 0.13 + sw)])
            trail.append([r * math.cos(a0 + 2 * math.pi / NS - 0.13 + sw), r * math.sin(a0 + 2 * math.pi / NS - 0.13 + sw)])
        web = web - cs_poly(lead + trail[::-1])
    webm = Manifold.extrude(web, 3.4).translate([0, 0, 1.1])
    rim = Manifold.extrude(CrossSection.circle(RP - 1.2, qs(64)) - CrossSection.circle(RP - 5.0, qs(64)), 12.0).translate([0, 0, -6])
    hub = Manifold.cylinder(18.0, 7.5, 7.5, qs(32)).translate([0, 0, -12.0]) + Manifold.cylinder(1.8, 6.2, 5.6, qs(32)).translate([0, 0, 6.0])
    hub = hub - Manifold.cylinder(30, 2.6, 2.6, qs(16)).translate([0, 0, -15])
    m = (teeth + webm + rim + hub)
    for k in range(16):                                             # rivets on the toothed ring's outer face
        a = 2 * math.pi * (k + 0.5) / 16
        m = m + Manifold.sphere(0.95, qs(10, 6)).scale([1, 1, 0.55]).translate([(RP - 3.3) * math.cos(a), (RP - 3.3) * math.sin(a), 4.5])
    m = m.rotate([0, 90, 0])   # z -> x
    c = Comp(); c.add('plastic', from_manifold(m, 32), SPROCKET)
    c.add('metal', cyl(1.5, 3.0, 12, axis='z', center=(-8.0, 7.6, 0)), STEEL)   # grub screw
    return c

def idler():
    """idler wheel: a black tyre on a light grey hub with six bosses round the centre (photos)"""
    c = Comp(); w = TW * 0.82; r = RP - 2.3
    c.add('plastic', cyl(r, w, 56, axis='x', bevel=1.2), IDLER)
    c.add('plastic', torus(r - 0.6, 0.9, 64, 8).r(0, 0, 90), '#0c0c0d')   # centre groove
    for sx in (-1, 1):
        c.add('plastic', cyl(15.4, 1.0, 48, axis='x', center=(sx * (w / 2 + 0.45), 0, 0), bevel=0.35), IDLER_CAP)
        c.add('plastic', cyl(6.4, 1.8, 32, axis='x', center=(sx * (w / 2 + 1.6), 0, 0), bevel=0.45), IDLER_CAP)
        for k in range(6):
            a = 2 * math.pi * k / 6
            c.add('plastic', cyl(1.35, 0.9, 12, axis='x', center=(sx * (w / 2 + 1.3), 9.8 * math.cos(a), 9.8 * math.sin(a)), bevel=0.25), IDLER_CAP)
        c.add('metal', cyl(3.4, 1.6, 6, axis='x', center=(sx * (w / 2 + 2.4), 0, 0)), STEEL)   # nut
    return c

def track_link():
    """one track link: x across, z along (pitch), y outward; pin line y=0"""
    c = Comp(); p = PITCH; k = TW / 36.0
    c.add('rubber', rbox(TW - 1.0, 2.6, p - 1.3, 0.5, 1, (0, 0.6, 0)), TRACK)
    rib = cs_poly([[-1.4, 0], [1.4, 0], [0.75, 4.3], [-0.75, 4.3]])    # (z, y) profile
    g = extrude_cs(rib, TW, 0, 40)
    perm(g, [1, 2, 0]).t(-TW / 2, 1.8, 0)
    c.add('rubber', g, TRACK)
    for sx in (-1, 1):
        c.add('rubber', rbox(5.0 * k, 2.2, 3.0, 0.6, 1, (sx * 12.5 * k, 3.0, -2.2)), TRACK)
    for (zz, segs) in [(p / 2, [(-17, -11), (-3, 3), (11, 17)]), (-p / 2, [(-11, -3), (3, 11)])]:
        for (a, b) in segs:
            c.add('rubber', cyl(1.9, (b - a) * k, 12, axis='x', center=((a + b) / 2 * k, -0.9, zz)), TRACK)
    c.add('metal', cyl(0.75, TW + 1.0, 8, axis='x', center=(0, -0.9, p / 2)), '#8d9298')
    c.add('rubber', rbox(5.0, 4.0, 4.0, 0.6, 1, (0, -2.6, 0)), TRACK)
    return c

MOT_GL, MOT_CL = 21.0, 38.0       # 33GB-520: gearbox and can lengths
MOT_END = -MOT_GL - 0.5 - MOT_CL  # the can's back end (motor frame x)

def motor_33gb():
    """33GB-520 gear motor (12 V, 320 rpm, its label as in the photos): 33 mm gearbox face at x = 0, body toward -x,
    5 mm D shaft along +x"""
    c = Comp(); R = 16.5; GL, CL = MOT_GL, MOT_CL
    c.add('satin', cyl(R, GL, 56, axis='x', center=(-GL / 2, 0, 0), bevel=0.6), GEARBOX)
    for i in range(2): c.add('satin', cyl(R + 0.06, 0.6, 56, axis='x', center=(-6.0 - i * 8.0, 0, 0)), '#b3b7bc')   # gearbox seams
    c.add('satin', cyl(6.0, 2.0, 32, axis='x', center=(1.0, 0, 0)), GEARBOX)                                      # bearing boss
    xc = -GL - 0.5 - CL / 2
    c.add('metal', cyl(R - 0.25, CL, 56, axis='x', center=(xc, 0, 0), bevel=0.8), CAN)
    xe = MOT_END; lx0 = xe + 3.0; LW = 18.0                       # the label, near the can's end
    lab = cyl(R - 0.17, LW, 56, axis='x', center=(lx0 + LW / 2, 0, 0), caps=False)
    ang = np.arctan2(lab.V[:, 2], lab.V[:, 1]); s = (ang + math.pi) / (2 * math.pi); t = 1.0 - (lab.V[:, 0] - lx0) / LW   # top row toward the gearbox
    u0, v0, u1, v1 = ATL.uv('mlabel'); lab.UV = np.stack([u0 + s * (u1 - u0), v0 + t * (v1 - v0)], 1)
    c.add('label', lab, '#ffffff')
    c.add('metal', cyl(R - 1.6, 1.4, 48, axis='x', center=(xe - 0.7, 0, 0), bevel=0.3), '#aeb2b7')        # end bell
    c.add('plastic', cyl(6.0, 1.8, 28, axis='x', center=(xe - 2.2, 0, 0), bevel=0.3), '#1d1e22')         # brush holder
    c.add('metal', cyl(1.6, 1.2, 12, axis='x', center=(xe - 3.6, 0, 0)), '#c9ccd0')                        # bearing
    for sz in (-1, 1): c.add('metal', box(0.5, 4.2, 2.4, (xe - 1.6, 9.5, sz * 6.0)), TIN)                  # terminals
    c.add('metal', cyl(2.5, 15.0, 20, axis='x', center=(9.0, 0, 0)), '#d9dcdf')                          # 5 mm D shaft
    return c

def coupler():
    c = Comp(); c.add('metal', cyl(5.0, TX - 12.0 - U_W / 2 - 0.4, 6, axis='x', center=(0, 0, 0), bevel=0.3), BRASS); return c

# terminals of the two motors in the world (the right motor drives the front sprocket, the left motor the rear one)
MOT_TERM = {'front': lambda sz: np.array([-(U_W / 2 - U_T) - (MOT_END - 1.6), AY + 11.6, AZ - sz * 6.0]),
            'rear': lambda sz: np.array([(U_W / 2 - U_T) + (MOT_END - 1.6), AY + 11.6, -AZ + sz * 6.0])}

# ---------------------------------------------------------------- the cells: two double 21700 holders in the box's two compartments
CELL_R, CELL_L = 10.55, 70.2
BOX_FLOOR = box_y(-17.62)          # inside floor of the box
BOX_SILL = box_y(-9.61)            # top of the sill on the box's open right side
BOX_X = 0.355                      # centre of the box's inside (x)
COMP_Z = (21.41, -28.49)           # front and rear compartments
HOLD = (77.6, 20.5, 45.0)          # double holder: length (x), height, width (z)
CELL_AY = 1.6 + CELL_R             # cell axis above the holder's bottom
HZ, HY = -64.0, PLB - 3.0          # the power harness: behind the box, just under the plate

def holder2():
    """double 21700 holder, open on top; local: centred in x/z, bottom at y = 0, cells along x at z = +-11"""
    c = Comp(); L, H, W = HOLD
    m = man_box(L, H, W, (0, H / 2, 0))
    for sz in (-1, 1):
        m = m - man_cyl(CELL_R + 0.35, L - 5.6, 'x', (0, CELL_AY, sz * 11.0), 40)
        m = m - man_box(30.0, 4.0, 7.0, (0, 0.0, sz * 11.0))                       # floor windows
    m = m - man_box(L - 5.6, H, 6.0, (0, H / 2 + 8.0, 0))                          # open between the cells
    c.add('plastic', from_manifold(m, 30), '#131315')
    for sz in (-1, 1):
        xs = -(L / 2 - 2.8)
        for k in range(5): c.add('metal', torus(3.0, 0.32, 24, 6).r(0, 0, 90).t(xs + 0.5 + k * 0.62, CELL_AY, sz * 11.0), '#c8ccd1')
        c.add('metal', cyl(3.3, 0.4, 24, axis='x', center=(xs + 3.4, CELL_AY, sz * 11.0)), '#cfd3d7')
        c.add('metal', box(0.4, 9.0, 8.0, (L / 2 - 2.9, CELL_AY, sz * 11.0)), '#cfd3d7')
        for x in (-L / 2 - 0.5, L / 2 + 0.5):
            c.add('metal', box(1.2, 0.4, 2.4, (x, 2.0, sz * 11.0)), TIN)                # solder tags under the ends
    return c

def cells(A):
    """the four cells in their holders (2S2P) and the series link between the holders at the left (+x) end"""
    import rparts as RPm
    c = Comp()
    for k, zc in enumerate(COMP_Z):
        h = holder2(); h.M(None, (BOX_X, BOX_FLOOR, zc)); c.extend(h)
        for sz in (-1, 1):
            cc = cell(A).M(rot(0, 180 if k else 0, 0), (BOX_X, BOX_FLOOR + CELL_AY + 0.15, zc + sz * 11.0)); c.extend(cc)
    top = BOX_FLOOR + CELL_AY + CELL_R + 0.25
    x1 = BOX_X + HOLD[0] / 2 + 0.9
    c.add(*wire([(x1, BOX_FLOOR + 3.0, COMP_Z[0]), (x1 + 0.4, BOX_FLOOR + 15.0, COMP_Z[0] - 16.0), (x1 + 0.4, top + 1.0, -3.5), (x1 + 0.4, BOX_FLOOR + 15.0, COMP_Z[1] + 16.0), (x1, BOX_FLOOR + 3.0, COMP_Z[1])], 0.9, RPm.WIRE_RED))
    return c

def cell(A, length=CELL_L, r=CELL_R):
    """21700 cell lying along x, centred"""
    c = Comp()
    body = cyl(r, length - 1.6, 48, axis='x', caps=False)
    ang = np.arctan2(body.V[:, 2], body.V[:, 1]); s = (ang + math.pi) / (2 * math.pi); t = (body.V[:, 0] + (length - 1.6) / 2) / (length - 1.6)
    u0, v0, u1, v1 = A.uv('cell'); body.UV = np.stack([u0 + s * (u1 - u0), v0 + t * (v1 - v0)], 1)
    c.add('label', body, '#ffffff')
    for sx in (-1, 1):
        c.add('label', cyl(r, 0.8, 48, axis='x', center=(sx * (length / 2 - 1.2), 0, 0), bevel=0.35), '#2f9e74')
        c.add('metal', cyl(r - 1.2, 0.5, 40, axis='x', center=(sx * (length / 2 - 0.4), 0, 0)), '#c8ccd1')
    c.add('metal', cyl(3.6, 1.2, 24, axis='x', center=(length / 2 + 0.3, 0, 0), bevel=0.3), '#d4d7db')
    return c

# ---------------------------------------------------------------- the power parts under the plate (Radu's description and photos)
# left, under the fibre converter: the 5.1 V XL4015 for the Pi (standing, parts outward) and the 2S BMS beside it, glued under the
# plate's edge. Right, under the Nano shield: the USB-C charging module, its port at the plate's edge. There is no power switch:
# the holders come out of the box's open right side.
PB_O = (60.0, 84.0, 2.0)            # Pi buck: board origin (its IN end at the front, z = 2)
BMS_O = (82.4, PLB - 16.0, -57.0)   # BMS: board origin (its B pads at the back, P pads at the front)
CHG_O = (-85.8, PLB - 12.0, -57.0)  # charger: board origin (its USB-C end flush with the plate's right edge)
R_STAND_IN = np.array([[0.0, 1, 0], [0, 0, -1], [-1, 0, 0]])     # board x -> -z, board normal -> +x, board z -> -y
R_STAND_OUT = np.array([[0.0, 1, 0], [0, 0, 1], [1, 0, 0]])      # board x -> +z, board normal -> +x, board z -> +y
R_BACK = np.array([[1.0, 0, 0], [0, 0, 1], [0, -1, 0]])          # board x -> +x, board normal -> -z, board z -> +y

def power(A):
    """the Pi's buck and the BMS on the left, the charger on the right, and the harness behind the box that joins them to the pack"""
    import rparts as RPm
    c = Comp()
    bk = xl4015(A, bake=False)                     # same module as the one on the shelf: it shares that one's painted top
    bk.M(R_STAND_IN, PB_O); c.extend(bk)
    bms = RPm.bms2s(A, 'bms2s_r'); bms.M(R_STAND_OUT, BMS_O); c.extend(bms)
    ch = RPm.usbc_board(A, 'usbc_r'); ch.M(R_BACK, CHG_O); c.extend(ch)
    bpad = lambda k: R_STAND_OUT @ np.array([RPm.BMS_PADS[k][0], 1.9, RPm.BMS_PADS[k][1]]) + BMS_O
    cpad = lambda k: R_BACK @ np.array(RPm.USB_PADS[k]) + CHG_O
    ipad = lambda zz: R_STAND_IN @ np.array([2.6, 1.9, zz]) + PB_O
    # BMS P- / P+ forward to the buck's IN pads
    for (k, col, zz) in ((3, RPm.WIRE_BLK, 5.0), (4, RPm.WIRE_RED, 10.0)):
        p, q = bpad(k), ipad(zz)
        c.add(*wire([p, p + [1.0, 0.6, 4.5], (78.0, (p[1] + q[1]) / 2 + 2.0, -5.0), (q[0] + 4.0, q[1] + 1.0, q[2] + 0.6), q], 0.75, col))
    # pack leads: out of the box's open right side, up into the cable channel along the box's top edge (the CAD's J hooks),
    # back to the rear corner, then behind the box under the plate to the BMS's B+ / B- pads
    CH_Y = box_y(4.0)                                          # inside the right-hand channel: x -46.9..-42.9, floor at cad z 2.9
    for (col, zc, dz, cx, k) in ((RPm.WIRE_RED, COMP_Z[1] - 11.0, 0.0, -44.0, 2), (RPm.WIRE_BLK, COMP_Z[0] - 11.0, -1.9, -45.9, 0)):
        x0 = BOX_X - HOLD[0] / 2 - 0.9
        e = bpad(k)
        pts = [(x0 + 0.3, BOX_FLOOR + 2.3, zc), (x0 - 0.7, BOX_FLOOR + 6.0, zc), (-41.9, BOX_SILL + 2.0, zc - 0.6), (-45.2, BOX_SILL + 3.0, zc - 1.8),
               (cx - 0.4, CH_Y - 3.0, zc - 6.0), (cx, CH_Y, zc - 11.0), (cx, CH_Y, -48.0), (cx + 0.4, CH_Y + 0.6, -57.0),
               (-38.0, HY + dz * 0.15, HZ + dz + 1.5), (-10.0, HY + dz * 0.15, HZ + dz), (40.0, HY + dz * 0.15, HZ + dz), (74.0, HY - 0.5, HZ + dz + 1.5),
               (86.0, e[1] + 0.5, -59.0), (e[0] + 0.6, e[1], e[2] - 0.6)]
        c.add(*wire(pts, 0.9, col))
    # charger output: along the same harness to the pack's B+ / B-
    for (kk, col, dz, k) in ((1, RPm.WIRE_RED, -3.6, 2), (0, RPm.WIRE_BLK, -5.2, 0)):
        p = cpad(kk); e = bpad(k)
        c.add(*wire([p, p + [3.0, 0.5, -1.8], (-44.0, HY + 0.4, HZ + dz + 1.5), (-10.0, HY + 0.4, HZ + dz), (40.0, HY + 0.4, HZ + dz),
                     (75.0, HY - 0.3, HZ + dz + 2.0), (86.4, e[1] - 0.7, -60.0), (e[0] + 0.6, e[1] - 0.6, e[2] - 1.0)], 0.55, col))
    return c

def drv8833():
    """the DRV8833 dual H-bridge module (a black board), glued to the front of the battery box"""
    c = Comp(); W, H, T = 18.5, 16.0, 1.2
    xc, yc, zb = DRV_C
    c.add('pcb', rbox(W, H, T, 0.5, 1, (xc, yc, zb + T / 2)), '#121315')
    zf = zb + T
    c.add('plastic', rbox(4.4, 5.0, 1.1, 0.15, 1, (xc + 0.5, yc + 1.2, zf + 0.55)), '#18191c')           # DRV8833 (HTSSOP-16)
    for k in range(8):
        for sx in (-1, 1): c.add('metal', box(0.25, 0.4, 0.2, (xc + 0.5 + sx * 2.45, yc + 1.2 - 2.2 + k * 0.63, zf + 0.1)), TIN)
    c.add('plastic', rbox(3.2, 1.6, 1.6, 0.15, 1, (xc + 4.6, yc - 4.6, zf + 0.8)), '#e0b11f')           # tantalum capacitor
    for (dx, dy) in ((-4.0, -4.5), (-4.0, 5.5), (4.8, 4.6), (0.5, -5.2)):
        c.add('plastic', box(1.6, 0.8, 0.5, (xc + dx, yc + dy, zf + 0.25)), '#2a2a2c')
    for k in range(6):                                                                                  # header holes, two rows
        for sx in (-1, 1):
            c.add('metal', cyl(0.85, 0.12, 12, axis='z', center=(xc + sx * 7.62, yc - 6.35 + k * 2.54, zf + 0.06)), TIN)
    for (sx, dy) in [(-1, 6.35), (-1, 3.81)] + [(1, d) for d in DRV_OUT]:                               # Dupont plugs, lying along the box
        c.add('plastic', rbox(13.0, 2.5, 2.5, 0.3, 1, (xc + sx * (7.62 + 7.0), yc + dy, zf + 1.6)), '#141416')
    return c

DRV_C = (-1.5, 64.5, 47.13 + 0.35)   # DRV8833: board centre (x, y) and the z of its back face (on the box's front wall)
DRV_OUT = (1.27, -1.27, -3.81, -6.35)   # its motor outputs (y offsets on the right edge): front motor, rear motor

def motor_leads():
    """the DRV8833's two motor pairs: down the front of the box, through the deck's left front slot and under the deck"""
    import rparts as RPm
    c = Comp(); xc, yc, zb = DRV_C; zf = zb + 1.2
    for (which, cols, pins) in (('front', (RED, BLACKW), DRV_OUT[:2]), ('rear', (RPm.WIRE_BLU, BLACKW), DRV_OUT[2:])):
        for j, (col, sz, yy) in enumerate(zip(cols, (1, -1), pins)):
            s = np.array([xc + 7.62 + 13.5, yc + yy, zf + 1.6]); t = MOT_TERM[which](sz)
            off = j * 1.1 + (2.4 if which == 'rear' else 0.0)
            pts = [s, s + [3.0, -1.6, 0.8], (30.0 + off, 55.5, 51.5 + off * 0.5), (37.0 + off, DECK_TOP + 1.2, 54.5 + off), (42.0 + off * 0.3, DECK_Y - 1.5, 56.0 + off)]
            if which == 'front':
                pts += [(30.0, DECK_Y - 4.0, 60.0 + off), (t[0] + 6.0, t[1] + 4.0, t[2] + 2.0 * sz), t]
            else:
                pts += [(40.0 + off, DECK_Y - 2.5, 30.0), (38.0 + off, DECK_Y - 2.5, -36.0), (16.0, DECK_Y - 2.4, -50.5 + off), (-2.0, DECK_Y - 2.4, t[2] + 4.0 * sz),
                        (t[0] - 2.4, t[1] + 6.0, t[2]), (t[0] - 0.5, t[1] + 0.8, t[2]), t]
            c.add(*wire(pts, 0.55, col))
    return c

# ---------------------------------------------------------------- positions on the plate (from the CAD's mounts)
PI_X, PI_Z, PI_Y = -79.95, 16.0, cad_y(19.89)          # Pi 5 on the four bosses (58 x 49)
SH_X, SH_Z, SH_Y = -78.5, -74.0, cad_y(18.85)          # Nano shield on its rails
XL_X, XL_Z, XL_Y = -72.42, -12.66, cad_y(37.85) + 1.5  # 3.3 V XL4015 (fibre converter) on the shelf (foam tape)
PERF_X, PERF_Z, PERF_Y = 14.17, -22.68, cad_y(15.89)   # perfboard in the four corner clips
TCA_X, TCA_Z, TCA_Y = 39.5, -63.15, cad_y(18.85)       # TCA9548A on its rails, pegs through its holes
CONV_X, CONV_Z, CONV_Y, CONV_L = 54.65, -54.2, cad_y(18.85), 59.0   # fibre converter between its pegs and the front stop
FPV_X, FPV_Z, FPV_Y = 0.0, 88.0, cad_y(41.5)           # front camera on the camera panel's front face
SERVO_X, SERVO_Z, SERVO_Y = 0.0, 4.0, cad_y(52.89)     # servo output shaft (x, z) and body bottom, from the CAD's servo
# the five VL53L0X on the plate's sensor pins: (x, z) of the mounting face and its outward normal
TOF = [(0.0, 88.0, 0.0, 1.0), (-44.58, 85.45, -0.495, 0.868), (44.58, 85.45, 0.495, 0.868), (-38.18, -86.06, -0.341, -0.940), (38.18, -86.06, 0.341, -0.940)]
CAM0 = (PI_X + 47.5, PI_Y + 1.6 + 1.2, PI_Z + 45.0)    # Pi 5 FPC connectors (the ribbons come in from +x)
CAM1 = (PI_X + 53.0, PI_Y + 1.6 + 1.2, PI_Z + 45.0)

def shelf_cord():
    """the fibre converter's power cord: from the 3.3 V buck on the shelf, coiled up inside the hollow shelf (it was too long),
    then behind the tower and across the plate to the converter's DC jack"""
    c = Comp(); r = 1.45; yc = cad_y(24.6); zc = -1.16; R = 8.0
    xa, xb, turns = -27.0, -63.0, 6.5
    n = int(turns * (28 if _gm.Q > 1.5 else 16))
    coil = [(xa + (xb - xa) * i / n, yc + R * math.cos(2 * math.pi * turns * i / n), zc + R * math.sin(2 * math.pi * turns * i / n)) for i in range(n + 1)]
    bo = np.array([XL_X + 52.0, XL_Y + 1.6, XL_Z + 19.5])          # OUT end of the shelf's XL4015
    lead = [bo, bo + [3.0, -1.5, 1.2], (-16.4, XL_Y - 3.5, 7.5), (-16.6, yc + R + 1.6, 3.0), (xa + 4.0, yc + R * 0.98, zc + 1.0), coil[0]]
    back = [coil[-1], (xb + 4.0, cad_y(14.7) + 2.0, zc + 5.0), (xb + 12.0, cad_y(14.7), zc + 6.0), (-24.0, cad_y(14.7), zc + 6.0), (-17.0, PL_TOP + 1.6, zc + 5.0)]
    jack = np.array([CONV_X + 20.6, CONV_Y + 1.6 + 6.2, CONV_Z + CONV_L])
    across = [(-17.0, PL_TOP + 1.6, zc + 5.0), (-13.5, PL_TOP + 1.6, -8.5), (-6.0, PL_TOP + 1.6, -19.5), (2.0, PL_TOP + 1.6, -24.0), (10.0, PL_TOP + 1.6, -28.2),
              (30.0, PL_TOP + 1.6, -28.4), (47.5, PL_TOP + 1.6, -28.0), (51.0, PL_TOP + 1.7, -16.0), (51.0, PL_TOP + 2.0, 6.0), (52.0, PL_TOP + 3.0, 24.0),
              (60.0, PL_TOP + 6.5, 32.5), (70.0, jack[1] - 2.3, 31.0), (jack[0], jack[1], 26.0), (jack[0], jack[1], jack[2] + 16.2)]
    hi = _gm.Q > 1.5
    c.add('rubber', tube(spline(lead, 30 if hi else 16, absolute=True), r, 10 if hi else 6, absolute=True), '#141416')
    c.add('rubber', tube(np.array(coil), r, 10 if hi else 6, cap=False, absolute=True), '#141416')
    c.add('rubber', tube(spline(back, 30 if hi else 16, absolute=True), r, 10 if hi else 6, cap=False, absolute=True), '#141416')
    c.add('rubber', tube(spline(across, 90 if hi else 50, absolute=True), r, 10 if hi else 6, absolute=True), '#141416')
    # barrel plug in the converter's DC jack
    c.add('plastic', cyl(4.0, 11.0, 24, axis='z', center=(jack[0], jack[1], jack[2] + 5.55), bevel=0.6), '#151517')
    c.add('plastic', cyl(2.5, 5.2, 16, axis='z', r2=1.8, center=(jack[0], jack[1], jack[2] + 13.65)), '#151517')
    return c

def bracket_cad(mesh_dir):
    d = json.load(open(f'{mesh_dir}/camera_mount.json', encoding='utf-8'))
    out = []
    for s in d:
        V = np.array(s['v']).reshape(-1, 3); F = np.array(s['f']).reshape(-1, 3)
        out.append(smooth(V, F, 30))     # identity mapping: hole axis along y, arm rises along +y, camera face toward +z
    return out

def mast(A, mesh_dir):
    """the MG90S in the plate's tower (pose from the CAD), and the camera head on its horn"""
    c = Comp()
    sv, horn_top = mg90s(A, ear_y=14.0)
    sv.M(rot(0, 180, 0), (SERVO_X + 5.9, SERVO_Y, SERVO_Z)); c.extend(sv)
    head = Comp(); sv.horn.M(rot(0, 180, 0), (SERVO_X + 5.9, SERVO_Y, SERVO_Z)); head.extend(sv.horn)
    shaft = np.array([SERVO_X, SERVO_Y + horn_top, SERVO_Z])
    for g in bracket_cad(mesh_dir):
        g.t(shaft[0], shaft[1] + 32.0, shaft[2]); head.add('pla', g, PLA)
    # overview camera on the bracket's sloped face (looks forward and ~7 degrees down)
    a = math.degrees(math.atan2(4.5, 36.5))
    n = np.array([0, -math.sin(math.radians(a)), math.cos(math.radians(a))])
    cam = camera(A)
    cam.M(None, (-12.5, 0, -12.0)); cam.M(rot(90, 0, 0)); cam.M(rot(a, 0, 0))
    face = np.array([shaft[0], shaft[1] + 32.0 - 8.75, shaft[2] + 22.25])
    cam.M(None, face + n * 3.2)
    for sx in (-1, 1):
        for sy in (-1, 1):
            q = rot(a, 0, 0) @ np.array([sx * 10.5, sy * 6.0, 0])
            g = cyl(1.3, 3.2, 8, axis='z'); g.M(rot(a, 0, 0), face + q + n * 1.6); head.add('metal', g, '#d2d5d8')
    head.extend(cam)
    c.head = head
    # ribbon: down the front of the bracket arm to the horn and in to the shaft (it turns with the head) ...
    p = face + n * 2.2 + np.array([0, -12.6, 0])
    ar = shaft[2] + 21.0
    up = spline([p + [0, 0, -0.6], (shaft[0], shaft[1] + 8.0, ar + 0.6), (shaft[0], shaft[1] + 3.2, ar - 3.0), (shaft[0], shaft[1] + 2.4, shaft[2] + 11.0), (shaft[0], shaft[1] + 2.4, shaft[2] + 4.0)], 40)
    head.add('rubber', ribbon(up, 11.0, 0.35, (0, 1, 0)), '#dedad0')
    # ... then over the tower's front wall, down its face and across the Pi to CAM/DISP 0
    tw = cad_y(66.89)
    dn = spline([(shaft[0], shaft[1] + 2.4, shaft[2] + 4.0), (shaft[0], shaft[1] - 3.0, 9.6), (shaft[0] + 1.0, tw + 1.2, 11.6), (shaft[0] + 1.0, tw - 4.0, 12.9),
                 (shaft[0], PI_Y + 26.0, 13.0), (-7.0, PI_Y + 20.0, 19.0), (-16.5, PI_Y + 19.0, 34.0), (-23.0, PI_Y + 12.0, 51.0),
                 (CAM0[0] + 5.0, CAM0[1] + 4.0, CAM0[2] + 1.0), (CAM0[0] + 1.6, CAM0[1] + 0.9, CAM0[2])], 80)
    c.add('rubber', ribbon(dn, 11.0, 0.35, (0, 1, 0)), '#dedad0')
    return c, shaft

def fpv(A):
    """the driving camera on the front panel (stood off it on four spacers); its ribbon drops through the panel's slot to CAM/DISP 1"""
    c = Comp(); cz = FPV_Z + 2.5
    cam = camera(A)
    cam.M(None, (-12.5, 0, -12.0)); cam.M(rot(90, 0, 0)); cam.M(None, (FPV_X, FPV_Y, cz))
    c.extend(cam)
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.add('metal', cyl(1.3, 2.5, 8, axis='z', center=(FPV_X + sx * 10.5, FPV_Y + sy * 6.0, FPV_Z + 1.25)), '#d2d5d8')
            c.add('metal', cyl(1.9, 0.8, 12, axis='z', center=(FPV_X + sx * 10.5, FPV_Y + sy * 6.0, cz + 1.4)), '#d2d5d8')
    slot = cad_y(22.1)
    path = spline([(FPV_X, FPV_Y - 9.5, cz - 1.3), (FPV_X, FPV_Y - 14.0, cz - 1.0), (FPV_X, slot + 1.0, FPV_Z + 1.0), (FPV_X, slot, FPV_Z - 1.0),
                   (FPV_X, slot, FPV_Z - 4.5), (-8.0, slot + 0.8, 79.0), (-17.0, CAM1[1] + 2.5, 70.0), (CAM1[0] + 6.0, CAM1[1] + 2.0, CAM1[2] + 2.0),
                   (CAM1[0] + 1.6, CAM1[1] + 0.9, CAM1[2])], 70)
    c.add('rubber', ribbon(path, 11.0, 0.35, (0, 1, 0)), '#d9d4c6')
    return c

def tof_set(A):
    c = Comp()
    for (x, z, nx, nz) in TOF:
        b = vl53(A)
        b.M(None, (-12.5, 0, -5.35)); b.M(rot(0, 180, 0) @ rot(-90, 0, 0))
        b.M(rot(0, math.degrees(math.atan2(nx, nz)), 0), (x, PL_MID, z))
        c.extend(b)
    t = tca(A)
    t.M(rot(0, -90, 0), (TCA_X, TCA_Y, TCA_Z))
    c.extend(t)
    return c

def cables():
    """Ethernet patch (Pi -> converter), USB (Pi -> Nano) and the servo lead"""
    out = {}
    e = Comp()
    pj = np.array([PI_X + 85 + 2.7, PI_Y + 1.6 + 6.0, PI_Z + 45.5])
    e.add('plastic', rbox(14.0, 9.0, 12.0, 1.2, 2, (pj[0] + 6.0, pj[1], pj[2])), '#c9d2dd')
    cj = np.array([CONV_X + 8.5, CONV_Y + 1.6 + 6.0, CONV_Z + CONV_L + 1.5])
    e.add('plastic', rbox(12.0, 9.0, 14.0, 1.2, 2, (cj[0], cj[1], cj[2] + 6.0)), '#c9d2dd')
    path = spline([pj + [13, 0, 0], pj + [24, 1.5, -3], (44.0, PL_TOP + 15.0, 50.0), (58.0, PL_TOP + 14.0, 38.0), (cj[0] - 0.5, cj[1] + 0.5, cj[2] + 24.0), cj + [0, 0, 13.0]], 90 if _gm.Q > 1.5 else 60, absolute=True)
    e.add('rubber', tube(path, 2.6, 16 if _gm.Q > 1.5 else 10, absolute=True), '#8a96a3')
    out['fibre'] = e
    u = Comp()
    pu = np.array([PI_X + 85 + 2.6, PI_Y + 1.6 + 12.3, PI_Z + 9.0])
    u.add('metal', rbox(10.0, 5.0, 12.4, 0.8, 2, (pu[0] + 4.0, pu[1], pu[2])), '#c3c7cb')
    u.add('plastic', rbox(14.0, 8.0, 15.5, 1.8, 2, (pu[0] + 15.0, pu[1], pu[2])), '#1b1c1f')
    nx = np.array([SH_X + 5.83 + 43.2 + 1.2, SH_Y + 16.65, SH_Z + 26.63])
    u.add('plastic', rbox(13.0, 7.0, 11.0, 1.8, 2, (nx[0] + 6.5, nx[1], nx[2])), '#1b1c1f')
    path = spline([pu + [22, 0, 0], pu + [28, -2, -6], (28.0, PI_Y + 12.0, 4.0), (22.0, PI_Y + 10.0, -14.0), (6.0, PI_Y + 12.0, -24.0), (-6.0, nx[1] + 2.0, -40.0), nx + [21, 1, 0], nx + [13, 0, 0]], 110 if _gm.Q > 1.5 else 70, absolute=True)
    u.add('rubber', tube(path, 1.8, 14 if _gm.Q > 1.5 else 9, absolute=True), '#18191b')
    out['nano'] = u
    s = Comp()
    sp = np.array([SH_X + 12.0 + 4 * 2.54, SH_Y + 1.6, SH_Z + 42.0 + 2.54])     # servo plug on the shield's front G-V-S row
    s.add('plastic', rbox(2.6, 14.0, 7.6, 0.4, 1, (sp[0], sp[1] + 2.5 + 7.0, sp[2])), '#141416')
    tw = cad_y(66.89)
    base = [(SERVO_X + 15.0, SERVO_Y + 3.0, SERVO_Z), (17.6, tw - 3.0, SERVO_Z), (18.0, tw + 0.6, SERVO_Z - 0.5), (19.6, tw - 2.0, SERVO_Z - 1.5), (19.6, PL_TOP + 22.0, -2.0),
            (12.0, PL_TOP + 3.0, -8.5), (0.4, cad_y(18.35) + 0.9, -10.2), (0.4, cad_y(22.35) + 0.9, -30.7), (-10.0, PL_TOP + 14.0, -31.0), (-26.0, sp[1] + 24.0, sp[2] + 0.5),
            sp + [0, 26.0, 0], sp + [0, 16.5, 0]]
    for k, col in enumerate([BROWN, RED, ORANGE]):
        off = np.array([0, 0, (k - 1) * 0.95])
        s.add('rubber', tube(spline([np.array(p) + off for p in base], 130 if _gm.Q > 1.5 else 80, absolute=True), 0.48, 8 if _gm.Q > 1.5 else 5, absolute=True), col)
    out['mast'] = s
    return out

def fibre_cable():
    c = Comp()
    sc = np.array([CONV_X + 12.5, CONV_Y + 1.6 + 6.2, CONV_Z - 1.5])
    c.add('plastic', rbox(9.0, 7.4, 22.0, 0.8, 2, (sc[0], sc[1], sc[2] - 9.0)), APC)
    c.add('plastic', cyl(2.6, 16.0, 16, axis='z', r2=1.8, center=(sc[0], sc[1], sc[2] - 27.0)), '#e8e8e4')
    path = spline([sc + [0, 0, -34], sc + [-4, -4, -46], (sc[0] - 14, sc[1] - 30.0, -102.0), (sc[0] - 20, 30.0, -112.0), (sc[0] - 24, 8.0, -122.0),
                   (sc[0] - 27, 1.6, -142.0), (sc[0] - 31, 1.6, -162.0), (sc[0] - 38, 1.6, -182.0)], 130 if _gm.Q > 1.5 else 75, absolute=True)
    c.add('rubber', tube(path, 1.5, 12 if _gm.Q > 1.5 else 8, absolute=True), FIBRE)
    return c

# ================================================================ assembly
def build(A, mesh_dir):
    global ATL
    ATL = A
    parts = {}
    def put(part, comp):
        parts.setdefault(part, Comp()).extend(comp)
    put('chassis', t101_frame())
    hw = U_W / 2
    for side in (1, -1):
        m = motor_33gb()
        zc = -AZ if side > 0 else AZ
        if side > 0: m.M(None, (hw - U_T, AY, zc))                       # left motor: rear axle, body toward -x
        else: m.M(rot(0, 180, 0), (-(hw - U_T), AY, zc))                  # right motor: front axle
        put('motors', m)
        cp = coupler(); cp.M(None, (side * (U_W / 2 + (TX - 12.0 - U_W / 2) / 2), AY, zc)); put('motors', cp)
    for side in (1, -1):   # idler axle bolts (M4)
        zc = AZ if side > 0 else -AZ
        b = Comp(); b.add('metal', cyl(2.0, 34.0, 12, axis='x', center=(side * (U_W / 2 - DECK_T + 17.0), AY, zc)), '#5d6168')
        screw_head(b, side * (TX + TW * 0.41 + 3.4), AY, zc, 3.4, 2.6, '#3d4046', 'x' if side > 0 else '-x'); put('motors', b)
    with qcap(1.4, 0.45): put('motors', motor_leads())
    put('plate', plate(A, mesh_dir))
    with qcap(1.5, 0.45): put('plate', shelf_cord())
    put('battery', battery_box(A, mesh_dir))
    with qcap(1.5, 0.45): put('cells', cells(A))
    with qcap(1.4, 0.45):
        put('power', power(A))
        put('drv', drv8833())
    pi = pi5(A); pi.M(None, (PI_X, PI_Y, PI_Z)); put('pi', pi)
    sh = nano_shield(A); sh.M(None, (SH_X, SH_Y, SH_Z)); put('nano', sh)
    bk = xl4015(A); bk.M(None, (XL_X, XL_Y, XL_Z)); put('buck', bk)
    tp = Comp()
    for x in (6.0, 48.0): tp.add('plastic', rbox(10.0, 1.5, 18.0, 0.3, 1, (XL_X + x, XL_Y - 0.75, XL_Z + 11.5)), '#d8d8d2')   # foam tape
    put('buck', tp)
    pf = perf(A); pf.M(None, (PERF_X, PERF_Y, PERF_Z)); put('driver', pf)
    put('sensors', tof_set(A))
    mc, shaft = mast(A, mesh_dir); put('mast', mc); put('head', mc.head)
    put('fpv', fpv(A))
    cv = converter(A, CONV_L); cv.M(None, (CONV_X, CONV_Y, CONV_Z)); put('fibre', cv)
    put('fcable', fibre_cable())
    for k, v in cables().items(): put(k, v)
    # moving parts (packed separately, placed by the page)
    wheels = {'sprocket': sprocket(), 'idler': idler(), 'link': track_link()}
    meta = {'AY': AY, 'RP': RP, 'NT': NT, 'NL': NL, 'AZ': AZ, 'TX': TX, 'TW': TW, 'PITCH': PITCH, 'shaft': shaft.tolist(),
            'wheels': [{'w': 'sprocket', 'x': TX, 'z': -AZ, 'side': 1}, {'w': 'idler', 'x': TX, 'z': AZ, 'side': 1},
                       {'w': 'sprocket', 'x': -TX, 'z': AZ, 'side': -1}, {'w': 'idler', 'x': -TX, 'z': -AZ, 'side': -1}]}
    return parts, wheels, meta
