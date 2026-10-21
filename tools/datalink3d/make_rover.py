# build the rover twice (lo = page default, hi = ultra detail) and paint the shared texture atlas; writes work/rover.pkl
# usage: make_rover.py TOOLS_DIR [q_hi]     (tools/build_models.py runs it)
import sys, os, pickle, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import geom
from atlas import *
import rover as R
S = sys.argv[1]; QHI = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2][0].isdigit() else 3.0
t0 = time.time()
A = Atlas(2048, 2048)
REG = [('plate', R.PW * 3.5, R.PD * 3.5), ('pi5', 85 * 8, 56 * 8), ('nanosh', 57 * 7, 54 * 7), ('xl4015', 54 * 9, 23 * 9), ('nano', 43.2 * 10, 17.8 * 10),
       ('tca', 32 * 10, 21 * 10), ('vl53', 25 * 12, 10.7 * 12), ('perf', 30 * 8, 70 * 8), ('conv', 25 * 9, 59 * 9), ('cell', 68.2 * 5, 70 * 5),
       ('labB', 13 * 14, 11 * 14), ('mlabel', 104 * 5, 18 * 5), ('servo', 22.8 * 10, 4.0 * 10), ('cam', 25 * 10, 24 * 10),
       # controller boards
       ('xl4015k', 54 * 9, 23 * 9), ('xl4015k2', 36 * 9, 20 * 9), ('ina219', 25.5 * 14, 22.3 * 14), ('ads1015', 28 * 14, 17.8 * 14),
       ('bms2s', 41 * 10, 16 * 10), ('usbc', 36 * 12, 12 * 12),
       ('bms2s_r', 41 * 10, 16 * 10), ('usbc_r', 36 * 12, 12 * 12)]
REG.sort(key=lambda r: -r[2])
for n, w, h in REG: A.alloc(n, w, h)
A.put('plate', paint_plate(R.PW, R.PD, 3.5, tri=R.plate_geom())); A.put('pi5', paint_pi5(8)); A.put('nanosh', paint_nano_shield(7)); A.put('nano', paint_nano(10))
A.put('xl4015', paint_xl4015(9)); A.put('tca', paint_tca(10)); A.put('vl53', paint_vl53(12)); A.put('perf', paint_perf(30, 70, 8))
A.put('conv', paint_conv_pcb(9)); A.put('labB', paint_label_B(14)); A.put('cell', paint_cell(5)); A.put('mlabel', paint_motor_label(5))
A.put('servo', paint_servo_label(10)); A.put('cam', paint_cam(10))
import rparts as RP
for lay in (RP.XL1, RP.XL2):
    A.put(lay['region'], paint_xl4015k(9, lay['L'], lay['W'], lay['pads'], lay['text']))
A.put('ina219', paint_ina219(14)); A.put('ads1015', paint_ads1015(14)); A.put('bms2s', paint_bms2s(10, 41.0, 16.0)); A.put('usbc', paint_usbc(12))
A.put('bms2s_r', paint_bms2s(10, 41.0, 16.0)); A.put('usbc_r', paint_usbc(12))
print('atlas painted', round(time.time() - t0, 1), 's; used height', A.y + A.row)
if 'atlas-only' in sys.argv:
    pickle.dump(A, open(f'{S}/work/atlas_rv.pkl', 'wb')); print('atlas only'); sys.exit(0)
out = {'atlas': A}
for lev, q in (('lo', 1.0), ('hi', QHI)):
    geom.setQ(q)
    parts, wheels, meta = R.build(A, f'{S}/cad')
    for k, c in parts.items():
        for m, g in c.p: R.wtex(g, A)
    for k, c in wheels.items():
        for m, g in c.p: R.wtex(g, A)
    tris = sum(len(g.F) for c in parts.values() for _, g in c.p)
    print(lev, 'Q', q, 'parts', {k: sum(len(g.F) for _, g in c.p) for k, c in parts.items()}, 'total tris', tris)
    print(lev, 'wheels', {k: sum(len(g.F) for _, g in c.p) for k, c in wheels.items()})
    out[lev] = (parts, wheels, meta)
geom.setQ(1.0)
pickle.dump(out, open(f'{S}/work/rover.pkl', 'wb'))
print('done', round(time.time() - t0, 1), 's')
