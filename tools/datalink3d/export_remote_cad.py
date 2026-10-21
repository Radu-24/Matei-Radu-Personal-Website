# Controller CAD -> per-solid triangle meshes.
# usage: export_remote_cad.py CONTROLLER.step OUT_DIR
#   writes OUT_DIR/remote_cad.npz, OUT_DIR/remote_cad_names.json and OUT_DIR/designed.step (the designed solids only, for remesh.py)
#  * faceted solids (all faces planar): triangulated straight from the STEP topology (fast, no CAD kernel)
#  * designed solids (cylinders, fillets, splines): a subset STEP is written and meshed with OpenCascade
import os,sys,re,time,math,json,collections
import numpy as np
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from stepdb import load,refs,nums
src,out=sys.argv[1],sys.argv[2]
t0=time.time()
db=load(src);print('loaded',len(db),round(time.time()-t0,1),flush=True)
T=lambda i:db[i][0]
def sense(a):return a.rstrip(b') ').endswith(b'.T.')
def P(i):  # vertex or cartesian point -> xyz
    ty,a=db[i]
    if ty==b'VERTEX_POINT':ty,a=db[refs(a)[0]]
    return np.array(nums(a)[-3:])
def D(i):v=np.array(nums(db[i][1])[-3:]);return v/np.linalg.norm(v)
def axis2(i):
    r=refs(db[i][1]);loc=P(r[0]);z=D(r[1]);x=D(r[2]) if len(r)>2 else None
    return loc,z,x
solids=[i for i,(ty,a) in db.items() if ty in (b'MANIFOLD_SOLID_BREP',b'BREP_WITH_VOIDS')]
name={i:db[i][1].split(b"'")[1].decode('latin1') for i in solids}
def faces_of(s):
    f=[]
    for sh in refs(db[s][1]):
        if T(sh)==b'ORIENTED_CLOSED_SHELL':sh=refs(db[sh][1])[0]
        f+=refs(db[sh][1])
    return f
def surf_of(f):return refs(db[f][1])[-1]
planar_solids=[s for s in solids if all(T(surf_of(f))==b'PLANE' for f in faces_of(s))]
designed=[s for s in solids if s not in planar_solids]
print('planar',len(planar_solids),'designed',[name[s] for s in designed],flush=True)

def loop_pts(lp,orient):
    pts=[]
    for oe in refs(db[lp][1]):
        a=db[oe][1];ec=refs(a)[-1];o=sense(a)
        ea=db[ec][1];v1,v2,c=refs(ea)[:3];es=sense(ea)
        st,en=(v1,v2) if o else (v2,v1)
        ct=T(c)
        if ct==b'CIRCLE':
            ax=refs(db[c][1])[0];r=nums(db[c][1])[-1];C,Z,X=axis2(ax);Y=np.cross(Z,X)
            ps,pe=P(st),P(en);ang=lambda p:math.atan2(np.dot(p-C,Y),np.dot(p-C,X))
            a0,a1=ang(ps),ang(pe);fw=(o==es)
            if fw:
                if a1<=a0+1e-9:a1+=2*math.pi
            else:
                if a1>=a0-1e-9:a1-=2*math.pi
            n=max(2,int(abs(a1-a0)/(2*math.pi)*48))
            for k in range(n):t=a0+(a1-a0)*k/n;pts.append(C+r*(math.cos(t)*X+math.sin(t)*Y))
        else:pts.append(P(st))
    if not orient:pts.reverse()
    return pts
import mapbox_earcut as earcut
def tri_face(f):
    a=db[f][1];r=refs(a);surf=r[-1];bounds=r[:-1];ss=sense(a)
    C,Z,X=axis2(refs(db[surf][1])[0]);nrm=Z if ss else -Z
    loops=[]
    for b in bounds:
        ba=db[b][1];loops.append((T(b)==b'FACE_OUTER_BOUND',loop_pts(refs(ba)[0],sense(ba))))
    loops.sort(key=lambda x:not x[0])
    allp=[p for _,l in loops for p in l]
    if len(loops)==1 and len(allp)==3:tri=[(0,1,2)]
    else:
        Xb=X if X is not None else np.cross(nrm,[1,0,0] if abs(nrm[0])<.9 else [0,1,0]);Xb=Xb-np.dot(Xb,nrm)*nrm;Xb/=np.linalg.norm(Xb);Yb=np.cross(nrm,Xb)
        uv=np.array([[np.dot(p-C,Xb),np.dot(p-C,Yb)] for p in allp],dtype=np.float64)
        ends=np.cumsum([len(l) for _,l in loops]).astype(np.uint32)
        idx=earcut.triangulate_float64(uv,ends).reshape(-1,3);tri=[tuple(t) for t in idx]
    out=[]
    for i,j,k in tri:
        A,B,Cc=allp[i],allp[j],allp[k];cr=np.cross(B-A,Cc-A)
        if np.dot(cr,nrm)<0:out.append((A,Cc,B))
        else:out.append((A,B,Cc))
    return out
meshes={}
for s in planar_solids:
    ts=time.time();tris=[]
    for f in faces_of(s):tris+=tri_face(f)
    V=np.array([p for t in tris for p in t]);F=np.arange(len(V)).reshape(-1,3)
    meshes[s]=(V,F);print(f'  {name[s][:30]:30} tris={len(F):6} {time.time()-ts:.1f}s',flush=True)

# ---- designed solids through OpenCascade: write a STEP with only those solids
def closure(start):
    seen=set();st=list(start)
    while st:
        i=st.pop()
        if i in seen or i not in db:continue
        seen.add(i);st+=refs(db[i][1])
    return seen
G=closure(solids)
skip=re.compile(rb'^(STYLED_ITEM|OVER_RIDING_STYLED_ITEM|PRESENTATION_|SURFACE_STYLE|SURFACE_SIDE_STYLE|FILL_AREA|COLOUR|DRAUGHTING|MECHANICAL_DESIGN_GEOMETRIC_PRESENTATION|INVISIBILITY|CURVE_STYLE)')
keep={i for i in db if i not in G and not skip.search(T(i) or b'COMPLEX')}|closure(designed)
holders=[i for i in keep if any(r in solids for r in refs(db[i][1]))]
print('entities referencing solids:',[(i,T(i)) for i in holders][:10],flush=True)
head=open(src,'rb').read(4000).split(b'DATA;')[0]
with open(out+'/designed.step','wb') as w:
    w.write(head+b'DATA;\n')
    for i in sorted(keep):
        ty,a=db[i]
        if i in holders:
            rs=[r for r in refs(a)];keepl=[r for r in rs if r not in solids or r in designed]
            # rebuild the item list keeping non-solid items and the designed solids
            m=re.match(rb"\('([^']*)',\((.*)\),(#\d+)\)$",a,re.S)
            if m:a=b"('"+m.group(1)+b"',("+b','.join(b'#%d'%r for r in refs(m.group(2)) if r not in solids or r in designed)+b"),"+m.group(3)+b")"
        w.write(b'#%d=%s%s;\n'%(i,ty,a))
    w.write(b'ENDSEC;\nEND-ISO-10303-21;\n')
from OCP.STEPControl import STEPControl_Reader
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopExp import TopExp_Explorer
from OCP.TopAbs import TopAbs_SOLID,TopAbs_FACE,TopAbs_REVERSED
from OCP.BRep import BRep_Tool
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS
ts=time.time();r=STEPControl_Reader();r.ReadFile(out+'/designed.step');r.TransferRoots();sh=r.OneShape()
BRepMesh_IncrementalMesh(sh,.12,False,.2,True)
occ=[];e=TopExp_Explorer(sh,TopAbs_SOLID)
while e.More():
    s=e.Current();V=[];F=[];fe=TopExp_Explorer(s,TopAbs_FACE)
    while fe.More():
        f=TopoDS.Face(fe.Current());loc=TopLoc_Location();t=BRep_Tool.Triangulation_s(f,loc)
        if t is not None:
            tr=loc.Transformation();o=len(V)
            for i in range(1,t.NbNodes()+1):p=t.Node(i).Transformed(tr);V.append((p.X(),p.Y(),p.Z()))
            rev=f.Orientation()==TopAbs_REVERSED
            for i in range(1,t.NbTriangles()+1):
                a,b,c=t.Triangle(i).Get();F.append((o+a-1,o+c-1,o+b-1) if rev else (o+a-1,o+b-1,o+c-1))
        fe.Next()
    occ.append((np.array(V),np.array(F)));e.Next()
print('occ solids',len(occ),round(time.time()-ts,1),'s',flush=True)
# match OCC solids to designed solids by bounding box (vertex bbox of STEP points)
def bbox_step(s):
    ps=[]
    for f in faces_of(s)[::3]:
        b=refs(db[f][1])[0];lp=refs(db[b][1])[0]
        for oe in refs(db[lp][1])[:2]:
            ec=refs(db[oe][1])[-1];ps.append(P(refs(db[ec][1])[0]))
    ps=np.array(ps);return (ps.min(0)+ps.max(0))/2
used=set()
for s in designed:
    c=bbox_step(s);best=min((i for i in range(len(occ)) if i not in used),key=lambda i:np.linalg.norm((occ[i][0].min(0)+occ[i][0].max(0))/2-c))
    used.add(best);meshes[s]=occ[best];print('  ',name[s],'->',best,len(occ[best][1]),'tris')
np.savez_compressed(out+'/remote_cad.npz',**{f'v{s}':meshes[s][0] for s in meshes},**{f'f{s}':meshes[s][1] for s in meshes})
json.dump({str(s):name[s] for s in meshes},open(out+'/remote_cad_names.json','w',encoding='utf-8'),ensure_ascii=False)
print('total',round(time.time()-t0,1),'s')
