# Mesh every solid in a STEP file with OpenCascade and save the triangles as an .npz (v0, f0, v1, f1, ...).
# usage: remesh.py SOURCE.step OUT.npz LINEAR_TOLERANCE_MM ANGULAR_TOLERANCE_RAD    (smaller tolerances, finer meshes)
# Made tools/cad/rover_cad_*.npz from the rover's CAD and tools/cad/remote_designed_*.npz from designed.step (see export_remote_cad.py).
import sys, time, numpy as np
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID, TopAbs_FACE, TopAbs_REVERSED
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
src, out, lin, ang = sys.argv[1], sys.argv[2], float(sys.argv[3]), float(sys.argv[4])
t0 = time.time(); r = STEPControl_Reader(); r.ReadFile(src); r.TransferRoots(); sh = r.OneShape()
BRepMesh_IncrementalMesh(sh, lin, False, ang, True)
res = {}; e = TopExp_Explorer(sh, TopAbs_SOLID); k = 0
while e.More():
    s = e.Current(); V = []; F = []; fe = TopExp_Explorer(s, TopAbs_FACE)
    while fe.More():
        f = TopoDS.Face_s(fe.Current()) if hasattr(TopoDS, 'Face_s') else TopoDS.Face(fe.Current())
        loc = TopLoc_Location(); t = BRep_Tool.Triangulation_s(f, loc)
        if t is not None:
            tr = loc.Transformation(); o = len(V)
            for i in range(1, t.NbNodes() + 1):
                p = t.Node(i).Transformed(tr); V.append((p.X(), p.Y(), p.Z()))
            rev = f.Orientation() == TopAbs_REVERSED
            for i in range(1, t.NbTriangles() + 1):
                a, b, c = t.Triangle(i).Get(); F.append((o + a - 1, o + c - 1, o + b - 1) if rev else (o + a - 1, o + b - 1, o + c - 1))
        fe.Next()
    V = np.array(V); F = np.array(F)
    res[f'v{k}'] = V; res[f'f{k}'] = F
    print(k, len(F), V.min(0).round(1), V.max(0).round(1), flush=True)
    k += 1; e.Next()
np.savez_compressed(out, **res)
print('done', round(time.time() - t0, 1), 's')
