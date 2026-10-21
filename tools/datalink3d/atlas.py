# Texture atlas for the rover / controller: board tops, labels, the printed plate. Painted with PIL.
# Regions are allocated with a shelf packer; UV rects are returned in three.js convention (flipY: v = 1 - y/H).
import os, numpy as np, math, random
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'fonts', '')     # DejaVu Sans, shipped in tools/fonts
def font(sz, bold=False, mono=False):
    n = 'DejaVuSansMono' if mono else 'DejaVuSans'
    if bold: n += '-Bold'
    return ImageFont.truetype(FONT_DIR + n + '.ttf', max(6, int(sz)))

class Atlas:
    def __init__(s, W=2048, H=2048):
        s.W, s.H = W, H
        s.img = Image.new('RGB', (W, H), (255, 255, 255))
        s.x = 24; s.y = 0; s.row = 0; s.regions = {}
        s.ao = np.ones((H, W), np.float32)   # baked occlusion, multiplied in at the end (linear)
        s.gap = 4
    def alloc(s, name, w, h):
        w, h = int(math.ceil(w)), int(math.ceil(h))
        if s.x + w + s.gap > s.W:
            s.x = 24; s.y += s.row + s.gap; s.row = 0
        if s.y + h > s.H: raise RuntimeError('atlas full at ' + name)
        r = (s.x, s.y, s.x + w, s.y + h)
        s.x += w + s.gap; s.row = max(s.row, h)
        s.regions[name] = r
        return r
    def uv(s, name, inset=0.5):
        x0, y0, x1, y1 = s.regions[name]
        return ((x0 + inset) / s.W, 1 - (y0 + inset) / s.H, (x1 - inset) / s.W, 1 - (y1 - inset) / s.H)
    def sub(s, name):
        x0, y0, x1, y1 = s.regions[name]
        return s.img.crop((x0, y0, x1, y1))
    def put(s, name, im):
        x0, y0, x1, y1 = s.regions[name]
        s.img.paste(im.resize((x1 - x0, y1 - y0), Image.LANCZOS) if im.size != (x1 - x0, y1 - y0) else im, (x0, y0))
    def white_uv(s):
        # the 16x16 white block at the top-left corner (x 0..16)
        return (8 / s.W, 1 - 8 / s.H)
    def finish(s, path, quality=88):
        a = np.asarray(s.img).astype(np.float32) / 255
        lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
        lin *= s.ao[..., None]
        srgb = np.where(lin <= 0.0031308, lin * 12.92, 1.055 * np.power(np.clip(lin, 0, 1), 1 / 2.4) - 0.055)
        out = Image.fromarray(np.clip(srgb * 255 + 0.5, 0, 255).astype(np.uint8))
        # keep the white block pure white
        out.paste((255, 255, 255), (0, 0, 20, 20))
        out.save(path, 'WEBP', quality=quality, method=6)
        return out

# ---------------- painters ----------------
def rgb(h):
    h = h.lstrip('#'); return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

def mix(a, b, t):
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))

class Board:
    """paints a PCB top in board millimetres (x right, z down) at `ppm` pixels per mm"""
    def __init__(s, w_mm, d_mm, ppm, mask='#1f7a3a', seed=1):
        s.w, s.d, s.ppm = w_mm, d_mm, ppm
        s.mask = rgb(mask)
        s.im = Image.new('RGB', (int(round(w_mm * ppm)), int(round(d_mm * ppm))), s.mask)
        s.g = ImageDraw.Draw(s.im)
        s.rnd = random.Random(seed)
        s.copper = mix(s.mask, (210, 235, 180), 0.22)      # copper under solder mask: a lighter mask tone
        s.silk = (238, 238, 232)
        s.pad = (205, 185, 120)                            # ENIG gold
        s.tin = (196, 198, 200)
    def P(s, x, z): return (x * s.ppm, z * s.ppm)
    def rect(s, x0, z0, x1, z1, fill=None, outline=None, width=1):
        s.g.rectangle([s.P(x0, z0), s.P(x1, z1)], fill=fill, outline=outline, width=width)
    def circle(s, x, z, r, fill=None, outline=None, width=1):
        s.g.ellipse([s.P(x - r, z - r), s.P(x + r, z + r)], fill=fill, outline=outline, width=width)
    def line(s, pts, col, w_mm):
        s.g.line([s.P(*p) for p in pts], fill=col, width=max(1, int(round(w_mm * s.ppm))), joint='curve')
    def text(s, x, z, t, size_mm, col=None, bold=False, anchor='lm', mono=False, rot=0):
        col = col or s.silk
        f = font(size_mm * s.ppm, bold, mono)
        if rot == 0:
            s.g.text(s.P(x, z), t, fill=col, font=f, anchor=anchor)
        else:
            tw = int(f.getlength(t)) + 4; th = int(size_mm * s.ppm * 1.4) + 4
            tmp = Image.new('RGBA', (tw, th), (0, 0, 0, 0)); ImageDraw.Draw(tmp).text((2, th / 2), t, fill=col + (255,), font=f, anchor='lm')
            tmp = tmp.rotate(rot, expand=True, resample=Image.BICUBIC)
            px, pz = s.P(x, z)
            s.im.paste(tmp, (int(px - tmp.width / 2), int(pz - tmp.height / 2)), tmp)
    def traces(s, n, region=None, w=0.18, avoid=()):
        """random orthogonal / 45 degree traces in a region (x0,z0,x1,z1)"""
        x0, z0, x1, z1 = region or (1, 1, s.w - 1, s.d - 1)
        for _ in range(n):
            x = s.rnd.uniform(x0, x1); z = s.rnd.uniform(z0, z1); pts = [(x, z)]
            for k in range(s.rnd.randint(2, 4)):
                L = s.rnd.uniform(2, 14); a = s.rnd.choice([0, 45, 90, 135, 180, 225, 270, 315])
                x = min(max(x + L * math.cos(math.radians(a)), x0), x1); z = min(max(z + L * math.sin(math.radians(a)), z0), z1)
                pts.append((x, z))
            s.line(pts, s.copper, w)
            if s.rnd.random() < 0.6:
                s.via(*pts[-1])
    def bus(s, x0, z0, x1, z1, n, pitch, w=0.15, horiz=True):
        for i in range(n):
            if horiz: s.line([(x0, z0 + i * pitch), (x1, z0 + i * pitch)], s.copper, w)
            else: s.line([(x0 + i * pitch, z0), (x0 + i * pitch, z1)], s.copper, w)
    def via(s, x, z, r=0.3):
        s.circle(x, z, r, fill=mix(s.copper, (255, 255, 255), .15)); s.circle(x, z, r * 0.45, fill=(40, 40, 30))
    def pads(s, x0, z0, nx, nz, px, pz, w, d, col=None):
        col = col or s.pad
        for i in range(nx):
            for j in range(nz):
                cx, cz = x0 + i * px, z0 + j * pz
                s.rect(cx - w / 2, cz - d / 2, cx + w / 2, cz + d / 2, fill=col)
    def hole(s, x, z, r, ring=0.6, col=None):
        s.circle(x, z, r + ring, fill=col or s.pad); s.circle(x, z, r, fill=(28, 28, 28))
    def outline(s, x0, z0, x1, z1, w=0.15):
        s.rect(x0, z0, x1, z1, outline=s.silk, width=max(1, int(w * s.ppm)))
    def noise(s, amt=6):
        a = np.asarray(s.im).astype(np.int16)
        rng = np.random.default_rng(3)
        n = rng.normal(0, amt, a.shape[:2])[..., None]
        s.im = Image.fromarray(np.clip(a + n, 0, 255).astype(np.uint8)); s.g = ImageDraw.Draw(s.im)

def raspberry(g, cx, cz, h, col):
    """the raspberry logo, very roughly: leaves + berry of circles"""
    r = h * 0.13
    for (dx, dz) in [(-1.2, -0.2), (0, -0.25), (1.2, -0.2), (-0.6, 0.85), (0.6, 0.85), (0, 1.9), (-1.25, 1.05), (1.25, 1.05)][:6]:
        g.circle(cx + dx * r * 1.1, cz + dz * r * 1.1 + h * 0.05, r, outline=col, width=max(1, int(0.12 * g.ppm)))
    g.line([(cx - r * 1.6, cz - r * 1.9), (cx, cz - r * 1.2), (cx + r * 1.6, cz - r * 1.9)], col, 0.14)

def paint_pi5(ppm=8):
    """Raspberry Pi 5 top, 85 x 56 mm. x = 0 at the PCIe edge, x = 85 at the USB/Ethernet edge; z = 0 at the GPIO edge, z = 56 at the power/HDMI edge."""
    b = Board(85, 56, ppm, '#23843d', seed=5)
    rnd = b.rnd
    # mounting holes (3.5 from edges; 58 x 49)
    for (x, z) in [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]:
        b.circle(x, z, 3.1, fill=b.tin); b.circle(x, z, 1.35, fill=(30, 30, 30))
    # traces and vias
    b.traces(110, (2, 8, 62, 52), 0.16)
    b.bus(14, 22, 26, 22, 6, 0.55, 0.14)   # RAM -> SoC
    b.bus(37, 26, 47, 26, 8, 0.5, 0.13)    # SoC -> RP1
    b.bus(48, 36, 48, 50, 7, 0.55, 0.13, horiz=False)
    for i in range(60): b.via(rnd.uniform(4, 62), rnd.uniform(8, 50), 0.22)
    # GPIO header footprint (2 x 20, 2.54)
    for i in range(20):
        for j in range(2):
            b.circle(7.1 + 1.27 + i * 2.54, 3.5 - 1.27 + j * 2.54, 0.85, fill=b.pad)
    # silkscreen
    b.text(18, 13.2, 'Raspberry Pi 5', 2.3, bold=False)
    b.text(17.5, 10.2, '© 2023', 1.2)
    raspberry(b, 10.5, 40.5, 6.0, b.silk)
    b.text(26, 51.6, 'HDMI', 2.0, bold=True, anchor='mm')
    b.text(46.5, 52.3, 'CAM/DISP 0  1', 1.0, anchor='mm')
    b.text(56, 9.8, 'FAN', 0.9, anchor='mm'); b.text(4.5, 30, 'PCIe', 0.9, anchor='mm', rot=90)
    b.text(70, 42, 'Raspberry Pi Ltd', 0.9); b.text(66, 46.5, 'Designed and Sold by', 0.75)
    for (x0, z0, x1, z1) in [(9, 17.5, 21, 30.5), (25, 18, 41, 34), (48, 21, 61, 34), (6, 44, 16.5, 52), (63, 4, 72, 12)]:
        b.outline(x0 - .6, z0 - .6, x1 + .6, z1 + .6, 0.12)
    # small passives (tiny pads with dark/brown parts)
    for i in range(140):
        x = rnd.uniform(4, 62); z = rnd.uniform(7, 51)
        w, d = rnd.choice([(0.6, 0.3), (1.0, 0.5), (0.5, 1.0), (1.6, 0.8)])
        c = rnd.choice([(52, 42, 30), (120, 96, 60), (30, 30, 32), (160, 140, 100)])
        b.rect(x - w / 2 - .12, z - d / 2, x - w / 2 + .1, z + d / 2, fill=b.tin); b.rect(x + w / 2 - .1, z - d / 2, x + w / 2 + .12, z + d / 2, fill=b.tin)
        b.rect(x - w / 2 + .1, z - d / 2, x + w / 2 - .1, z + d / 2, fill=c)
    b.noise(4)
    return b.im

def paint_plain(w, d, ppm, mask, silk_lines=(), seed=2, traces=30, holes=(), text=()):
    b = Board(w, d, ppm, mask, seed)
    b.traces(traces, (1, 1, w - 1, d - 1), 0.2)
    for (x, z, r) in holes: b.hole(x, z, r)
    for (x, z, t, sz, kw) in text: b.text(x, z, t, sz, **kw)
    b.noise(4)
    return b

def paint_nano_shield(ppm=7):
    """Arduino Nano IO shield, 57 x 54 mm, blue. Nano socket along x in the middle."""
    b = Board(57, 54, ppm, '#1f50a8', seed=8)
    b.traces(70, (2, 2, 55, 52), 0.25)
    for (x, z) in [(2.8, 2.8), (54.2, 2.8), (2.8, 51.2), (54.2, 51.2)]: b.hole(x, z, 1.5, 0.9, b.tin)
    # pin rows: three rows (G V S) along both long edges
    labels = ['2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12', '13']
    for i, l in enumerate(labels):
        b.text(8 + i * 2.54, 13.6, l, 0.9, anchor='mm')
    for i, l in enumerate(['A0', 'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7']):
        b.text(12 + i * 2.54, 40.2, l, 0.75, anchor='mm')
    b.text(5.6, 6.5, 'G', 1.0, anchor='mm'); b.text(5.6, 9.04, 'V', 1.0, anchor='mm'); b.text(5.6, 11.58, 'S', 1.0, anchor='mm')
    b.text(28.5, 48.5, 'NANO  IO  SHIELD  V3', 1.6, bold=True, anchor='mm')
    b.text(48, 44, 'IIC', 1.1, anchor='mm'); b.text(50, 14, 'PWR', 1.1, anchor='mm')
    b.noise(4)
    return b.im

def paint_nano(ppm=10):
    """Arduino Nano (clone), 43.2 x 17.8 mm, blue"""
    b = Board(43.2, 17.8, ppm, '#1e4fb6', seed=11)
    b.traces(40, (5, 2, 40, 16), 0.16)
    for i in range(15):
        for j in (1.27, 16.53):
            b.hole(1.0 + 1.27 + i * 2.54 + 1.4, j, 0.45, 0.5, b.pad)
    b.text(21.6, 3.3, 'NANO V3.0', 1.25, anchor='mm'); b.text(12, 14.3, 'D13 3V3 REF A0 A1', 0.9, anchor='lm')
    b.text(28, 6.0, 'RX TX', 0.8, anchor='mm')
    b.noise(4)
    return b.im

def paint_xl4015(ppm=9):
    """XL4015 buck module, 54 x 23 mm, blue"""
    b = Board(54, 23, ppm, '#1d4ea6', seed=13)
    b.traces(30, (8, 2, 46, 21), 0.6)
    b.rect(0.5, 1.5, 6.5, 8.5, fill=b.tin); b.rect(0.5, 14.5, 6.5, 21.5, fill=b.tin)
    b.rect(47.5, 1.5, 53.5, 8.5, fill=b.tin); b.rect(47.5, 14.5, 53.5, 21.5, fill=b.tin)
    b.text(3.5, 11.5, 'IN+', 1.3, anchor='mm', rot=90); b.text(50.5, 11.5, 'OUT+', 1.3, anchor='mm', rot=90)
    b.text(3.5, 0.9, 'IN-', 0.9, anchor='mm'); b.text(50.5, 0.9, 'OUT-', 0.9, anchor='mm')
    b.text(31, 20.8, 'XL4015  5A  DC-DC', 1.25, anchor='mm')
    b.noise(4)
    return b.im

def paint_tca(ppm=10):
    """TCA9548A breakout, 32 x 21 mm, purple"""
    b = Board(32, 21, ppm, '#6b2b8f', seed=17)
    b.traces(24, (3, 4, 29, 17), 0.18)
    names_l = ['VIN', 'GND', 'SDA', 'SCL', 'RST', 'A0', 'A1', 'A2']
    names_r = ['SD0', 'SC0', 'SD1', 'SC1', 'SD2', 'SC2', 'SD3', 'SC3']
    for i in range(8):
        b.hole(6.1 + i * 2.54, 1.6, 0.5, 0.55, b.pad); b.hole(6.1 + i * 2.54, 19.4, 0.5, 0.55, b.pad)
        b.text(6.1 + i * 2.54, 4.0, names_l[i], 0.7, anchor='mm', rot=90)
        b.text(6.1 + i * 2.54, 17.0, names_r[i], 0.7, anchor='mm', rot=90)
    b.hole(2.2, 10.5, 1.2, 0.6, b.tin); b.hole(29.8, 10.5, 1.2, 0.6, b.tin)
    b.text(16, 8.0, 'TCA9548A', 1.3, anchor='mm', bold=True)
    b.noise(4)
    return b.im

def paint_vl53(ppm=12):
    """GY-VL53L0XV2, 25 x 10.7 mm, purple. Sensor near x = 21."""
    b = Board(25, 10.7, ppm, '#6a2a8c', seed=19)
    for i, n in enumerate(['VIN', 'GND', 'SCL', 'SDA', 'GPIO1', 'XSHUT']):
        b.hole(1.8, 1.0 + 1.27 + i * 1.5, 0.35, 0.35, b.pad)
    b.traces(10, (3, 1, 18, 9.7), 0.18)
    b.text(10, 9.2, 'VL53L0X', 0.95, anchor='mm', bold=True)
    b.noise(3)
    return b.im

def paint_perf(w=30, d=70, ppm=8):
    """double-sided FR4 prototype board, 2.54 grid of tinned pads"""
    b = Board(w, d, ppm, '#1d7a4c', seed=23)
    nx, nz = int((w - 2.5) // 2.54), int((d - 2.5) // 2.54)
    ox = (w - (nx - 1) * 2.54) / 2; oz = (d - (nz - 1) * 2.54) / 2
    for i in range(nx):
        for j in range(nz):
            x, z = ox + i * 2.54, oz + j * 2.54
            b.circle(x, z, 0.85, fill=(205, 207, 210)); b.circle(x, z, 0.42, fill=(22, 26, 24))
    for (x, z) in [(1.6, 1.6), (w - 1.6, 1.6), (1.6, d - 1.6), (w - 1.6, d - 1.6)]:
        b.circle(x, z, 1.1, fill=(22, 26, 24))
    b.noise(3)
    return b.im

def paint_conv_pcb(ppm=9):
    """fibre media converter PCB, 25 x 64 mm, blue (x across, z along: z=0 at the fibre end)"""
    b = Board(25, 64, ppm, '#1f4eaa', seed=29)
    b.traces(40, (2, 28, 23, 46), 0.18)
    b.rect(7, 31, 17, 41, fill=(28, 28, 30)); b.outline(6.4, 30.4, 17.6, 41.6, 0.12)
    for i in range(10):
        b.rect(6.2, 31.5 + i * 0.95, 7.0, 31.9 + i * 0.95, fill=b.tin); b.rect(17.0, 31.5 + i * 0.95, 17.8, 31.9 + i * 0.95, fill=b.tin)
    b.text(12, 43.8, 'RTL8211', 0.8, anchor='mm', col=(200, 200, 200))
    b.text(4, 27, 'LINK', 0.8, anchor='mm'); b.text(20, 27, 'PWR', 0.8, anchor='mm')
    b.noise(4)
    return b.im

def paint_label_B(ppm=14, letter='B'):
    """white label on the BiDi transceiver: big letter + small text. 13 x 11 mm"""
    w, d = 13, 11
    im = Image.new('RGB', (int(w * ppm), int(d * ppm)), (236, 236, 232)); g = ImageDraw.Draw(im)
    g.text((1.0 * ppm, 5.6 * ppm), letter, fill=(40, 70, 160), font=font(8.5 * ppm, True), anchor='lm')
    g.text((7.8 * ppm, 3.0 * ppm), '1.25G', fill=(40, 40, 40), font=font(1.6 * ppm), anchor='lm')
    g.text((7.8 * ppm, 5.3 * ppm), 'TX1550', fill=(40, 40, 40), font=font(1.1 * ppm), anchor='lm')
    g.text((7.8 * ppm, 7.0 * ppm), 'RX1310', fill=(40, 40, 40), font=font(1.1 * ppm), anchor='lm')
    g.text((7.8 * ppm, 8.7 * ppm), 'SM 3KM', fill=(40, 40, 40), font=font(1.1 * ppm), anchor='lm')
    return im

def paint_cell(ppm=5):
    """Samsung INR21700-50S wrap, unrolled: circumference 68.2 (x) by 70 (z)"""
    w, d = 68.2, 70
    im = Image.new('RGB', (int(w * ppm), int(d * ppm)), rgb('#2f9e74')); g = ImageDraw.Draw(im)
    # lighter band with text
    g.rectangle([0, 18 * ppm, w * ppm, 52 * ppm], fill=rgb('#e9ece6'))
    f = font(3.4 * ppm, True); f2 = font(2.2 * ppm)
    tmp = Image.new('RGBA', (int(34 * ppm), int(w * ppm)), (0, 0, 0, 0)); tg = ImageDraw.Draw(tmp)
    tg.text((2 * ppm, 10 * ppm), 'INR21700-50S', fill=(30, 30, 30, 255), font=f, anchor='lm')
    tg.text((2 * ppm, 16 * ppm), '+ 3.6V 5000mAh 18.0Wh', fill=(40, 40, 40, 255), font=f2, anchor='lm')
    tg.text((2 * ppm, 45 * ppm), 'SAMSUNG SDI', fill=(30, 30, 30, 255), font=f2, anchor='lm')
    tmp = tmp.rotate(90, expand=True)
    im.paste(tmp, (0, int(18 * ppm)), tmp)
    return im

def paint_motor_label(ppm=5):
    """white label around the 33 mm motor can (33GB-520), unrolled: 104 (around) x 18 (along). The top row
    is the side toward the gearbox: the lines run round the can, MODEL nearest the gearbox, as on the real label."""
    w, d = 104, 18
    im = Image.new('RGB', (int(w * ppm), int(d * ppm)), (232, 233, 234)); g = ImageDraw.Draw(im)
    f = font(2.3 * ppm)
    for k, t in enumerate(['MODEL:33GB-520-18.7F', 'DC:12V   320RPM\u00b110%', 'DATE:  24.12.20  dolt.am']):
        for x0 in (16.0, 68.0):                                   # printed twice round the can
            g.text((x0 * ppm, (4.2 + k * 4.8) * ppm), t, fill=(34, 34, 36), font=f, anchor='lm')
    return im

def paint_servo_label(ppm=10):
    w, d = 22.8, 4.0
    im = Image.new('RGB', (int(w * ppm), int(d * ppm)), (26, 27, 31)); g = ImageDraw.Draw(im)
    g.text((1.4 * ppm, 2.1 * ppm), 'TowerPro', fill=(200, 200, 200), font=font(1.9 * ppm, True), anchor='lm')
    g.text((21.2 * ppm, 2.1 * ppm), 'MG90S', fill=(225, 64, 64), font=font(2.1 * ppm, True), anchor='rm')
    return im

def paint_cam(ppm=10):
    """IMX219-120 camera board, 25 x 24, black"""
    b = Board(25, 24, ppm, '#141516', seed=31)
    b.copper = (32, 34, 36)
    b.traces(14, (2, 2, 23, 22), 0.2)
    for (x, z) in [(2, 2), (23, 2), (2, 14.5), (23, 14.5)]: b.hole(x, z, 1.1, 0.5, b.pad)
    b.text(12.5, 22.2, 'IMX219-120', 1.0, anchor='mm')
    b.noise(3)
    return b.im

def paint_plate(w_mm, d_mm, ppm, seed=7, tri=None):
    """the printed plate's top: black PLA, each facet printed with its lines in its own direction (as in the photos).
    tri = (P, T, H) from rover.plate_tri(): P in plate coordinates (x across, z along, centred), the facets the geometry uses"""
    W, H = int(w_mm * ppm), int(d_mm * ppm)
    rng = np.random.default_rng(seed)
    base = np.full((H, W), 26.0)
    yy, xx = np.mgrid[0:H, 0:W]
    X = (xx + 0.5) / ppm; Z = (yy + 0.5) / ppm
    if tri is None:
        from scipy.spatial import Delaunay
        pts = [[0, 0], [w_mm, 0], [0, d_mm], [w_mm, d_mm], [w_mm / 2, 0], [w_mm / 2, d_mm], [0, d_mm / 2], [w_mm, d_mm / 2]]
        for _ in range(16): pts.append([rng.uniform(10, w_mm - 10), rng.uniform(10, d_mm - 10)])
        pts = np.array(pts); dl = Delaunay(pts); simp_list = dl.simplices
    else:
        P, T, Hh = tri
        pts = np.stack([P[:, 0] + w_mm / 2, P[:, 1] + d_mm / 2], 1); simp_list = T
    period = 0.42 * ppm
    for k, (a, b, c) in enumerate(simp_list):
        pa, pb, pc = pts[a], pts[b], pts[c]
        lo = np.floor(np.minimum(np.minimum(pa, pb), pc) * ppm).astype(int) - 1; hi = np.ceil(np.maximum(np.maximum(pa, pb), pc) * ppm).astype(int) + 2
        i0, i1 = max(0, lo[0]), min(W, hi[0]); j0, j1 = max(0, lo[1]), min(H, hi[1])
        if i1 <= i0 or j1 <= j0: continue
        xs, zs = X[j0:j1, i0:i1], Z[j0:j1, i0:i1]
        d = (pb[1] - pc[1]) * (pa[0] - pc[0]) + (pc[0] - pb[0]) * (pa[1] - pc[1])
        if abs(d) < 1e-12: continue
        l1 = ((pb[1] - pc[1]) * (xs - pc[0]) + (pc[0] - pb[0]) * (zs - pc[1])) / d
        l2 = ((pc[1] - pa[1]) * (xs - pc[0]) + (pa[0] - pc[0]) * (zs - pc[1])) / d
        m = (l1 >= -0.002) & (l2 >= -0.002) & (1 - l1 - l2 >= -0.002)
        ang = rng.uniform(0, np.pi)
        ph = (xx[j0:j1, i0:i1] * np.cos(ang) + yy[j0:j1, i0:i1] * np.sin(ang)) / period
        lines = 0.5 + 0.5 * np.cos(ph * 2 * np.pi)
        sub = base[j0:j1, i0:i1]; sub[m] = (22 + rng.uniform(-2.5, 6.0) + lines * 4.2)[m]
    img = Image.fromarray(np.clip(base, 0, 255).astype(np.uint8)).convert('RGB')
    g = ImageDraw.Draw(img)
    for (a, b, c) in simp_list:
        p = [tuple(pts[i] * ppm) for i in (a, b, c)]
        g.line(p + [p[0]], fill=(44, 44, 47), width=1)
    img = img.filter(ImageFilter.GaussianBlur(0.6))
    a = np.asarray(img).astype(np.int16) + rng.normal(0, 2.0, (H, W))[..., None].astype(np.int16)
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

# ---------------- controller boards (black XL4015, INA219, ADS1015, 2S BMS, USB-C board) ----------------
def paint_xl4015k(ppm=9, L=54.0, W=23.0, pads=(), text=None, seed=41):
    """the black XL4015 module (as in the controller photos), L x W mm; pads = [(x0, z0, x1, z1, label)], text = (x, z)"""
    b = Board(L, W, ppm, '#141517', seed=seed)
    b.copper = (36, 38, 42); b.silk = (232, 232, 228)
    b.traces(26, (6, 3, L - 6, W - 3), 0.9)
    for (x0, z0, x1, z1, lab) in pads:
        b.rect(x0 - 0.8, z0 - 0.8, x1 + 0.8, z1 + 0.8, fill=(30, 31, 35))
    for (x0, z0, x1, z1, lab) in pads:
        b.rect(x0, z0, x1, z1, fill=b.tin)
        xm = x1 + 1.4 if x0 < L / 2 else x0 - 1.4
        b.text(xm, (z0 + z1) / 2, lab, 0.95, anchor='mm', rot=90)
    if text: b.text(text[0], text[1], 'XL4015  5A  DC-DC', 1.05, anchor='mm')
    for i in range(18):
        x = b.rnd.uniform(8, L - 8); z = b.rnd.uniform(3, W - 3); b.via(x, z, 0.32)
    b.noise(3)
    return b.im

def paint_ina219(ppm=14):
    """INA219 current sensor breakout, 25.5 x 22.3 mm, dark blue; z = 0 at the screw-terminal edge, x = 0 at the left as printed"""
    b = Board(25.5, 22.3, ppm, '#1b2f73', seed=43)
    b.copper = (40, 66, 140)
    b.traces(22, (2, 7, 23.5, 15), 0.25)
    for (x, z) in [(2.2, 2.2), (23.3, 2.2)]: b.hole(x, z, 1.4, 0.6, b.tin)
    # the shunt footprint (the resistor itself is painted where it sits: black body, R100)
    b.rect(8.6, 3.9, 16.9, 7.7, fill=b.tin)
    b.rect(9.9, 4.15, 15.6, 7.45, fill=(18, 18, 20)); b.text(12.75, 5.85, 'R100', 1.45, col=(236, 236, 236), anchor='mm', bold=True)
    b.text(3.6, 9.4, 'Current', 1.25, anchor='lm'); b.text(3.6, 11.3, 'Sensor', 1.25, anchor='lm')
    b.text(19.4, 9.6, 'I2C Address', 0.95, anchor='mm'); b.text(17.4, 11.3, 'A0', 0.8, anchor='mm'); b.text(21.6, 11.3, 'A1', 0.8, anchor='mm')
    for (x, z) in [(16.6, 12.6), (18.2, 12.6), (20.8, 12.6), (22.4, 12.6)]: b.rect(x - .45, z - .55, x + .45, z + .55, fill=b.pad)
    b.text(12.9, 9.8, 'R5', 0.8, anchor='mm')
    # header pads along the far edge, labels
    names = ['Vcc', 'Gnd', 'Scl', 'Sda', 'Vin-', 'Vin+']
    for i, n in enumerate(names):
        x = 6.4 + i * 2.54
        b.hole(x, 20.4, 0.5, 0.55, b.pad); b.text(x, 17.6, n, 0.72, anchor='mm', rot=90)
    b.text(4.0, 16.0, 'Gnd', 0.95, anchor='mm'); b.text(12.0, 16.0, 'Sda', 0.95, anchor='mm'); b.text(20.5, 16.0, 'Vin+', 0.95, anchor='mm')
    b.noise(3)
    return b.im

def paint_ads1015(ppm=14):
    """GY-ADS1015/ADS1115 breakout, 28 x 17.8 mm, purple; z = 0 at the header edge"""
    b = Board(28, 17.8, ppm, '#4b2477', seed=47)
    b.copper = (92, 56, 140)
    b.traces(18, (3, 5, 25, 15), 0.22)
    for (x, z) in [(2.2, 15.3), (25.8, 15.3)]: b.hole(x, z, 1.4, 0.55, b.tin)
    names = ['VDD', 'GND', 'SCL', 'SDA', 'ADDR', 'ALRT', 'A0', 'A1', 'A2', 'A3']
    for i, n in enumerate(names):
        x = 2.57 + i * 2.54
        b.hole(x, 1.6, 0.5, 0.55, b.pad); b.text(x, 4.6, n, 0.62, anchor='mm', rot=90)
    b.text(14, 16.3, 'GY-ADS1015/ADS1115', 1.0, anchor='mm', bold=True)
    b.outline(11.6, 8.6, 16.4, 13.4, 0.1)
    b.noise(3)
    return b.im

def paint_bms2s(ppm=10, L=41.0, W=16.0):
    """2S 20 A protection board with balancing (41 x 16 mm, green), balance pads B-, BM, B+ at one end, P- / P+ at the other"""
    b = Board(L, W, ppm, '#1d5a35', seed=53)
    b.copper = (40, 104, 66)
    b.rect(7.5, 1.0, L - 7.5, W / 2 - 0.6, fill=(34, 92, 58)); b.rect(7.5, W / 2 + 0.6, L - 7.5, W - 1.0, fill=(34, 92, 58))
    for (x, z, n) in [(3.2, W * 0.18, 'B-'), (3.2, W * 0.5, 'BM'), (3.2, W * 0.82, 'B+'), (L - 3.2, W * 0.27, 'P-'), (L - 3.2, W * 0.73, 'P+')]:
        b.rect(x - 2.3, z - 1.25, x + 2.3, z + 1.25, fill=b.tin); b.text(x + (3.9 if x < L / 2 else -3.9), z, n, 0.95, anchor='mm')
    b.text(L / 2, W / 2, '2S 20A', 1.1, anchor='mm', bold=True)
    for i in range(8): b.via(b.rnd.uniform(9, L - 9), b.rnd.uniform(1.5, W - 1.5), 0.28)
    b.noise(3)
    return b.im

def paint_usbc(ppm=12, L=36.0, W=12.0):
    """small black USB-C board (as in the controller photos), USB-C at x = 0"""
    b = Board(L, W, ppm, '#121315', seed=59)
    b.copper = (34, 36, 40)
    b.traces(12, (11, 2, L - 4, W - 2), 0.3)
    b.rect(L - 4.2, 1.2, L - 0.8, 4.8, fill=b.tin); b.rect(L - 4.2, W - 4.8, L - 0.8, W - 1.2, fill=b.tin)
    b.text(L - 6.2, 3.0, 'B+', 0.95, anchor='mm'); b.text(L - 6.2, W - 3.0, 'B-', 0.95, anchor='mm')
    b.text(17, W - 1.3, 'TYPE-C  IN', 0.9, anchor='mm')
    b.noise(3)
    return b.im
