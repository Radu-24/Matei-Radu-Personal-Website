/* DataLink Rover in 3D (three.js). One WebGL canvas for the whole site; it moves between the project card and the
   project page.
   The two models are real: the rover is built part by part to real dimensions (T101 frame, printed plate, Pi 5, Nano,
   sensors, cameras, fibre converter) and the controller comes straight from its CAD file. Both ship as packed data
   (assets/models/rover.js, remote.js) with baked occlusion and one texture atlas for the board tops and labels.
   One flat state object describes the whole picture (camera, objects, explode, focus, effects). Modes and the scroll
   position only decide the state the picture eases toward; a frame is drawn only while that state, the size, the pointer
   or a running effect changes, and at 30 fps on the lighter quality tiers. */
(function(){'use strict';
const PI=Math.PI,TAU=PI*2,clamp=(v,a=0,b=1)=>Math.min(b,Math.max(a,v)),lerp=(a,b,t)=>a+(b-a)*t,
  ss=(a,b,x)=>{const t=clamp((x-a)/(b-a));return t*t*(3-2*t)},s5=t=>{t=clamp(t);return t*t*t*(t*(t*6-15)+10)},
  wrap=a=>{a=(a+PI)%TAU;if(a<0)a+=TAU;return a-PI},easeIO=k=>k<.5?4*k*k*k:1-Math.pow(-2*k+2,3)/2;
let T=null,ren=null,scene,cam,cv=null,ready=null,ro=null,slot=null,tier=0,W=1,H=1,BW=0,BH=0,bufT=0;
let raf=0,last=0,lastDraw=0,force=0,shown=false,dirty=true,vt=0,tscale=1,spinR=0,mode='card',tw=null,fixedGoal=null,wC=1,wS=0;
const perf={ms:0,n:0},story={type:'hero',k:0,t:0},hov={r:0,m:0,l:0,rT:0,mT:0,lT:0,cx:0,cy:0,cxT:0,cyT:0},frameSubs=[];
/* card camera: the model fills its card slot the same way at any slot size (radius and centre come from the model) */
let R0=1.45,TGT=[0,.8,0];const DIR=(()=>{const v=[0,.34,1],l=Math.hypot(...v);return v.map(x=>x/l)})(),CFOV=26,tanH=d=>Math.tan(d*PI/360);
const cardDist=(w,h)=>Math.max(R0/tanH(CFOV),R0/(tanH(CFOV)*(w/h)))*1.04;
const RS=1.15;   /* the rover is drawn a little larger than life next to the controller, so the two read at the same size */

/* ---------- state ---------- */
const KEYS=['cx','cy','cz','tx','ty','tz','fov','px','py',
  'rX','rY','rZ','rYaw','rPitch','rS','rV','rEx','rDim','rF','rAct','rTurn','rSway',
  'mX','mY','mZ','mYaw','mPitch','mS','mV','mEx','mDim','mF','mAct','mSway',
  'lV','lP','pad','floor','warm','cool'];
const blank=()=>{const P={};for(const k of KEYS)P[k]=0;P.fov=30;P.px=P.py=.5;P.rS=P.mS=1;P.cz=10;P.ty=.7;P.warm=P.cool=1;return P};
const cur=blank();
const camAt=(P,tx,ty,tz,az,el,d,fov)=>{P.tx=tx;P.ty=ty;P.tz=tz;P.cx=tx+Math.sin(az)*Math.cos(el)*d;P.cy=ty+Math.sin(el)*d;P.cz=tz+Math.cos(az)*Math.cos(el)*d;P.fov=fov};
const mixCam=(P,A,B,t)=>{for(const k of ['cx','cy','cz','tx','ty','tz','fov','px','py'])P[k]=lerp(A[k],B[k],t)};
const fitD=(r,fov,fill)=>{const f=(H/2)/tanH(fov),m=Math.min(W,H);return f*2*r/(fill*m)};

/* ---------- models ---------- */
let rover=null,remote=null,link=null,floorM=null,padR=null,padM=null,lights={},atlas=null;
const CT={};   /* on a tall screen: where each part's card starts (fraction of the height), so the part can sit above it */
const v3=()=>new T.Vector3();
function partsOf(root){const out=[];root.children.forEach(g=>{if(g.userData&&g.userData.key)out.push(g)});return out}
/* every part gets its own copies of its materials, so it can be dimmed or faded on its own */
function ownMaterials(part){const map=new Map(),list=[];
  part.traverse(o=>{if(!o.isMesh)return;const one=m=>{if(!map.has(m)){const c=m.clone();map.set(m,c);list.push({m:c,c:c.color.clone(),e:c.emissiveIntensity||0,o:c.opacity,env:c.envMapIntensity??1,keepT:!!m.userData.keepT})}return map.get(m)};
    o.material=Array.isArray(o.material)?o.material.map(one):one(o.material)});
  part.userData.mats=list;part.userData.lastD=-1;part.userData.lastV=-1}
function shade(part,d,vis){const u=part.userData;if(Math.abs(u.lastD-d)<.003&&Math.abs(u.lastV-vis)<.003)return;u.lastD=d;u.lastV=vis;
  /* dimmed parts lose their reflections too (a dark part that still mirrors the studio lights reads as lit); the screen keeps
     its own glow (driven elsewhere) but fades with the rest */
  const k=1-.8*d,op=vis*(1-.8*d);for(const x of u.mats){x.m.color.copy(x.c).multiplyScalar(k);x.m.envMapIntensity=x.env*k;if(x.m.emissive&&!x.keepT)x.m.emissiveIntensity=x.e*(1-.7*d);
    const tr=op<.995;if(x.m.transparent!==tr){x.m.transparent=tr;x.m.needsUpdate=true}x.m.opacity=x.o*op;x.m.depthWrite=op>.6}}
/* centre and radius of a group of parts with everything exploded, in the model's own frame */
function stopBox(root,keys,ex=1){const b=new T.Box3(),tmp=new T.Box3();
  root.updateMatrixWorld(true);const inv=root.matrixWorld.clone().invert();
  keys.forEach(k=>{const g=root.userData.parts[k];if(!g)return;const keep=g.position.clone();g.position.copy(g.userData.base).addScaledVector(g.userData.off,ex);g.updateMatrixWorld(true);
    g.traverse(o=>{if(o.isMesh&&o.visible&&!o.isInstancedMesh){o.geometry.computeBoundingBox();tmp.copy(o.geometry.boundingBox).applyMatrix4(o.matrixWorld).applyMatrix4(inv);b.union(tmp)}});g.position.copy(keep)});
  root.updateMatrixWorld(true);const c=b.getCenter(v3()),s=b.getSize(v3());return{c,r:Math.max(.2,s.length()/2),lo:b.min.clone(),hi:b.max.clone()}}
/* where a stop's label points, taken apart (t) and put together (t0): the middle of its parts, or of the parts in s.tag,
   or the point s.at inside that box (fractions of its size) */
function tagPts(root,s){const k=s.tag||s.frame||s.parts,f=s.at||[.5,.5,.5],p=b=>new T.Vector3(b.lo.x+(b.hi.x-b.lo.x)*f[0],b.lo.y+(b.hi.y-b.lo.y)*f[1],b.lo.z+(b.hi.z-b.lo.z)*f[2]);
  s.t=p(stopBox(root,k));s.t0=p(stopBox(root,k,0))}

/* materials by class; every mesh carries its colour (with baked occlusion) per vertex, and board tops / labels sample the atlas */
const MP={pla:[.6,0,.85],plastic:[.42,0,1],blade:[.34,0,1.15],rubber:[.78,0,.7],pcb:[.34,0,1],metal:[.34,.88,1.15],satin:[.42,.8,1.1],gold:[.28,.95,1.1],glass:[.06,0,1.5],label:[.48,0,.9]};
const matCache=new Map();
function matFor(cls,uv){const key=cls+(uv?'+t':'');if(matCache.has(key))return matCache.get(key);let m;
  if(cls==='emit')m=new T.MeshBasicMaterial({vertexColors:true,toneMapped:false});
  else{const p=MP[cls]||[.5,0,1];m=new T.MeshStandardMaterial({vertexColors:true,roughness:p[0],metalness:p[1],envMapIntensity:p[2],map:uv?atlas:null})}
  matCache.set(key,m);return m}

/* ---------- unpacking the model data ----------
   per mesh: int16 positions (x, y, z runs), then either one byte of occlusion per vertex (the mesh has one colour) or sRGB
   colours, then optional atlas uv (uint16), then indices. Normals are rebuilt here (vertices are already split at sharp edges). */
let LUT=null;
async function unpack(M,slow){
  if(!M||!M.data)throw new Error('no model data');
  const s=atob(M.data),u8=new Uint8Array(s.length);for(let i=0;i<s.length;i++)u8[i]=s.charCodeAt(i);
  let buf=u8.buffer;
  if(M.gz){if(typeof DecompressionStream!=='function')throw new Error('this browser cannot unpack the model (no DecompressionStream)');
    buf=await new Response(new Blob([u8]).stream().pipeThrough(new DecompressionStream('gzip'))).arrayBuffer()}
  if(!LUT){LUT=new Float32Array(256);for(let i=0;i<256;i++){const c=i/255;LUT[i]=c<=.04045?c/12.92:Math.pow((c+.055)/1.055,2.4)}}
  return M.v>=4?unpack4(M,new Uint8Array(buf),slow):unpack3(M,buf)}
/* v4: delta-coded varints in triangle order (see pack.py) */
async function unpack4(M,B,slow){let p=0;const out=[];
  const vint=()=>{let x=0,sh=0,b;do{b=B[p++];x+=(b&127)*2**sh;sh+=7}while(b&128);return x};
  for(const m of M.meshes){const n=m.v,P=new Float32Array(n*3),C=new Float32Array(n*3);
    for(let c=0;c<3;c++){const lo=m.lo[c],sc=m.s||(m.hi[c]-m.lo[c])/65534,o=m.s?0:32767;let q=0;
      for(let k=0;k<n;k++){const z=vint();q+=(z%2?-(z+1)/2:z/2);P[k*3+c]=lo+(q+o)*sc}}
    if(m.c){const base=[LUT[m.c[0]],LUT[m.c[1]],LUT[m.c[2]]];let a=0;
      for(let k=0;k<n;k++){a=(a+B[p++])&255;const f=a/255;C[k*3]=base[0]*f;C[k*3+1]=base[1]*f;C[k*3+2]=base[2]*f}}
    else for(let c=0;c<3;c++){let a=0;for(let k=0;k<n;k++){a=(a+B[p++])&255;C[k*3+c]=LUT[a]}}
    const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(P,3));g.setAttribute('color',new T.BufferAttribute(C,3));
    if(m.uv){const U=new Float32Array(n*2);for(let c=0;c<2;c++){let q=0;for(let k=0;k<n;k++){const z=vint();q+=(z%2?-(z+1)/2:z/2);U[k*2+c]=q/65535}}
      g.setAttribute('uv',new T.BufferAttribute(U,2))}
    const I=n>65535?new Uint32Array(m.i):new Uint16Array(m.i);let hw=0;
    for(let k=0;k<m.i;k++){const cd=vint();I[k]=hw-cd;if(cd===0)hw++}
    g.setIndex(new T.BufferAttribute(I,1));g.computeVertexNormals();
    out.push({name:m.n,part:m.p,mat:m.m,uv:!!m.uv,g});if(slow)await new Promise(r=>setTimeout(r,0))}
  return out}
function unpack3(M,buf){
  let off=0;const al=()=>{off=(off+3)&~3},out=[];
  for(const p of M.meshes){const n=p.v,q=new Int16Array(buf,off,n*3);off+=n*6;al();
    const nc=p.c?1:3,cq=new Uint8Array(buf,off,n*nc);off+=n*nc;al();
    let uq=null;if(p.uv){uq=new Uint16Array(buf,off,n*2);off+=n*4;al()}
    const big=n>65535,I=(big?new Uint32Array(buf,off,p.i):new Uint16Array(buf,off,p.i)).slice();off+=p.i*(big?4:2);al();
    const P=new Float32Array(n*3),C=new Float32Array(n*3);
    for(let c=0;c<3;c++){const lo=p.lo[c],sc=(p.hi[c]-p.lo[c])/65534,o=c*n,base=p.c?LUT[p.c[c]]:0;
      for(let k=0;k<n;k++){P[k*3+c]=lo+(q[o+k]+32767)*sc;C[k*3+c]=p.c?base*cq[k]/255:LUT[cq[o+k]]}}
    const g=new T.BufferGeometry();g.setAttribute('position',new T.BufferAttribute(P,3));g.setAttribute('color',new T.BufferAttribute(C,3));
    if(uq){const U=new Float32Array(n*2);for(let k=0;k<n;k++){U[k*2]=uq[k]/65535;U[k*2+1]=uq[n+k]/65535}g.setAttribute('uv',new T.BufferAttribute(U,2))}
    g.setIndex(new T.BufferAttribute(I,1));g.computeVertexNormals();
    out.push({name:p.n,part:p.p,mat:p.m,uv:!!p.uv,g})}
  return out}
/* the data ships as plain scripts, loaded only when the 3D view starts: a page in the artifact viewer may not fetch data:
   URLs or compile WebAssembly, so the page unpacks the data itself (base64 -> gzip -> int16) */
function dataScript(src,glob,ev){return new Promise((res,rej)=>{if(window[glob])return res(window[glob]);
  addEventListener(ev,()=>res(window[glob]),{once:true});
  const sc=document.createElement('script');sc.src=src;sc.async=true;sc.onerror=()=>rej(new Error(src+' did not load'));document.head.appendChild(sc)})}

/* ---------- the rover ---------- */
/* explode offsets (scene units) and delays, per part */
/* the printed chassis sits on the T101: taken apart, the motors drop, the battery box lifts off the deck and the cells slide out of
   its open right side (as they do when the rover is switched off); the power boards from under the plate float between, and the
   plate lifts off the box with the boards above it */
const RV_PARTS={trackL:[.8,0,0,0],trackR:[-.8,0,0,0],motors:[0,-.42,0,.05],chassis:[0,0,0,.08],battery:[0,.24,0,.1],
  drv:[0,.6,.5,.14],cells:[-.98,.26,0,.13],power:[0,.5,-.25,.15],plate:[0,.95,0,.16],
  sensors:[0,1.15,.1,.2],fpv:[.1,1.21,.6,.3],pi:[-.16,1.45,.46,.22],driver:[.56,1.41,.12,.24],fibre:[.66,1.5,-.55,.28],fcable:[.66,1.5,-.55,.28],
  buck:[-.62,1.63,.02,.26],mast:[.08,1.71,-.04,.3],nano:[-.5,1.83,-.42,.27],head:[.08,1.99,.04,.34]};
function buildRover(meshes,M){
  const U=M.unit,tr=M.track,root=new T.Group(),parts={};root.userData.parts=parts;
  Object.entries(RV_PARTS).forEach(([key,o])=>{const g=new T.Group();g.userData={key,off:new T.Vector3(o[0],o[1],o[2]),base:new T.Vector3(),delay:o[3]};parts[key]=g;root.add(g)});
  /* the camera head turns on the servo shaft */
  const sh=M.track.shaft.map(x=>x*U),pivot=new T.Group(),inner=new T.Group();pivot.position.set(sh[0],sh[1],sh[2]);inner.position.set(-sh[0],-sh[1],-sh[2]);pivot.add(inner);parts.head.add(pivot);
  const wm={},emits=[];
  for(const m of meshes){
    if(m.part.startsWith('w_')){(wm[m.part.slice(2)]||(wm[m.part.slice(2)]=[])).push(m);continue}
    const g=parts[m.part];if(!g)continue;const o=new T.Mesh(m.g,matFor(m.mat,m.uv));
    (m.part==='head'?inner:g).add(o);if(m.mat==='emit')emits.push(o)}
  /* wheels and track links: one set per side */
  const spins=[],ims=[],AY=tr.AY*U;
  for(const w of M.wheels){const side=w.side,g=new T.Group(),s=new T.Group();g.position.set(w.x*U,AY,w.z*U);if(side<0)g.rotation.y=PI;g.add(s);
    (wm[w.w]||[]).forEach(m=>s.add(new T.Mesh(m.g,matFor(m.mat,m.uv))));s.userData.side=side;spins.push(s);(side>0?parts.trackL:parts.trackR).add(g)}
  for(const side of [1,-1])(wm.link||[]).forEach(m=>{const im=new T.InstancedMesh(m.g,matFor(m.mat,m.uv),tr.NL);im.userData.side=side;im.frustumCulled=false;ims.push(im);(side>0?parts.trackL:parts.trackR).add(im)});
  const PER=tr.NL*tr.PITCH,L=2*tr.AZ,arc=PI*tr.RP,pt=(s,o)=>{s=((s%PER)+PER)%PER;
    if(s<L){o[0]=tr.AY-tr.RP;o[1]=-tr.AZ+s;return o}s-=L;
    if(s<arc){const ph=-PI/2+s/tr.RP;o[0]=tr.AY+tr.RP*Math.sin(ph);o[1]=tr.AZ+tr.RP*Math.cos(ph);return o}s-=arc;
    if(s<L){o[0]=tr.AY+tr.RP;o[1]=tr.AZ-s;return o}s-=L;const ph=PI/2+s/tr.RP;o[0]=tr.AY+tr.RP*Math.sin(ph);o[1]=-tr.AZ+tr.RP*Math.cos(ph);return o};
  const M4=new T.Matrix4(),X=new T.Vector3(),Y=new T.Vector3(),Z=new T.Vector3(),a=[0,0],b=[0,0],mm=[0,0];
  /* d = how far the rover has driven (mm): the links run back along the bottom, the wheels turn */
  const placeTreads=d=>{for(let k=0;k<tr.NL;k++){const s0=-d+k*tr.PITCH;pt(s0,a);pt(s0+tr.PITCH,b);pt(s0+tr.PITCH/2,mm);
      let ty=b[0]-a[0],tz=b[1]-a[1];const l=Math.hypot(ty,tz);ty/=l;tz/=l;let ny=tz,nz=-ty;
      const cz=Math.max(-tr.AZ,Math.min(tr.AZ,mm[1]));if((mm[0]-tr.AY)*ny+(mm[1]-cz)*nz<0){ny=-ny;nz=-nz}
      Z.set(0,ty,tz);Y.set(0,ny,nz);X.crossVectors(Y,Z);M4.makeBasis(X,Y,Z);
      for(const im of ims){M4.setPosition(im.userData.side*tr.TX*U,(a[0]+b[0])/2*U,(a[1]+b[1])/2*U);im.setMatrixAt(k,M4)}}
    for(const im of ims)im.instanceMatrix.needsUpdate=true;
    for(const s of spins)s.rotation.x=d/tr.RP*s.userData.side};
  placeTreads(0);
  const shadow=blob(2.3,2.6,.6);root.add(shadow);
  Object.values(parts).forEach(g=>{g.userData.base.copy(g.position);ownMaterials(g)});
  const ledMats=new Set();emits.forEach(o=>ledMats.add(o.material));
  /* the story's stops: parts = what lights up, frame = what the camera fits (default: parts), tag / at = where the label points
     (see tagPts), az / el / fill = the camera's angle and how much of the screen the parts fill */
  const STOPS=[{key:'tracks',parts:['trackL','trackR','motors'],frame:['trackL','motors'],tag:['trackR','motors'],az:1.25,el:.28,fill:.6},
    {key:'chassis',parts:['chassis','battery','plate'],tag:['battery'],az:.7,el:.5,fill:.62},{key:'pi',parts:['pi'],az:-.5,el:.9,fill:.5},
    {key:'control',parts:['nano','driver','drv'],tag:['nano'],az:.15,el:.8,fill:.62},{key:'sensors',parts:['sensors'],at:[.5,.5,1],az:.35,el:.32,fill:.62},
    {key:'cameras',parts:['mast','head','fpv'],az:-.3,el:.22,fill:.62},{key:'power',parts:['cells','power','buck'],frame:['battery','cells','power'],tag:['cells'],az:-.75,el:.42,fill:.6},
    {key:'fibre',parts:['fibre'],az:2.55,el:.42,fill:.55}];
  const r={kind:'rover',root,parts,STOPS,placeTreads,pivot,shadow,ledMats:[...ledMats],trd:0,trdDrawn:-1,pan:0,
    ov:{py:.41,mul:1.22}};   // on a wide screen the tall taken-apart stack sits smaller and higher, above the card
  r.stopOf={};STOPS.forEach((s,i)=>s.parts.forEach(p=>r.stopOf[p]=i));
  r.measure=()=>{STOPS.forEach(s=>{Object.assign(s,stopBox(root,s.frame||s.parts));s.c0=stopBox(root,s.frame||s.parts,0).c;tagPts(root,s)});
    r.all=stopBox(root,Object.keys(parts).filter(k=>k!=='fcable'));r.body=stopBox(root,Object.keys(parts).filter(k=>k!=='fcable'),0)};
  r.measure();
  return r}

function blob(w,d,a){const c=document.createElement('canvas');c.width=c.height=128;const g=c.getContext('2d'),gr=g.createRadialGradient(64,64,4,64,64,64);
  gr.addColorStop(0,`rgba(0,0,0,${a})`);gr.addColorStop(.55,`rgba(0,0,0,${a*.45})`);gr.addColorStop(1,'rgba(0,0,0,0)');g.fillStyle=gr;g.fillRect(0,0,128,128);
  const m=new T.Mesh(new T.PlaneGeometry(w,d),new T.MeshBasicMaterial({map:new T.CanvasTexture(c),transparent:true,depthWrite:false}));m.rotation.x=-PI/2;m.position.y=.003;m.renderOrder=-1;return m}

/* ---------- the controller, from its CAD file ---------- */
const REMOTE_GROUPS={shell:[0,1.9,0],screen:[0,1.38,.02],sticks:[0,.98,.1],switch:[.45,.62,-.35],pi:[0,.48,0],elec:[0,.24,0],power:[0,.06,0],mid:[0,-.42,0],batt:[0,-.12,.4],bottom:[0,-.95,0]};
/* split a geometry in two by the side (x) its triangles sit on: the two battery holders move apart */
function splitX(g){const P=g.attributes.position.array,I=g.index.array,sides=[[],[]];
  for(let t=0;t<I.length;t+=3){const x=(P[I[t]*3]+P[I[t+1]*3]+P[I[t+2]*3])/3;sides[x<0?0:1].push(I[t],I[t+1],I[t+2])}
  return sides.map(ix=>{const h=g.clone();h.setIndex(ix);return h})}
function buildRemote(meshes,M){
  const U=M.unit,root=new T.Group(),inner=new T.Group();root.add(inner);inner.position.y=-.33;const parts={};root.userData.parts=parts;
  Object.entries(REMOTE_GROUPS).forEach(([k,off],i)=>{const g=new T.Group();g.userData={key:k,off:new T.Vector3(...off),base:new T.Vector3(),delay:i*.035};parts[k]=g;inner.add(g)});
  const battSide=[new T.Group(),new T.Group()];battSide[0].userData.side=-1;battSide[1].userData.side=1;parts.batt.add(...battSide);
  let fanBlades=null,fanLeds=[];
  for(const m of meshes){const g=parts[m.part];if(!g)continue;
    if(m.part==='batt'){splitX(m.g).forEach((h,i)=>battSide[i].add(new T.Mesh(h,matFor(m.mat,m.uv))));continue}
    const o=new T.Mesh(m.g,matFor(m.mat,m.uv));g.add(o);
    if(m.mat==='blade')fanBlades=o;if(m.part==='power'&&m.mat==='emit')fanLeds.push(o)}
  /* the fan's blades spin on its hub */
  let fan=null;if(fanBlades&&M.fan){const c=M.fan.map(x=>x*U),g=fanBlades.parent;fan=new T.Group();fan.position.set(c[0],0,c[2]);g.add(fan);fanBlades.position.set(-c[0],0,-c[2]);fan.add(fanBlades)}
  /* the screen: his own HUD (DataLink Rover, live video, picture-in-picture, proximity, battery), on the glass */
  const sr=M.screen;let scr=null;
  if(sr){const x0=sr[0]*U,x1=sr[1]*U,z0=sr[2]*U,z1=sr[3]*U,y=sr[4]*U,aw=1.542,ah=.859;   /* 7" panel: 154.2 x 85.9 mm active area */
    const mat=new T.MeshStandardMaterial({color:0x000000,roughness:.14,metalness:0,envMapIntensity:.42,emissive:0xffffff,emissiveMap:hudTexture(),emissiveIntensity:0});
    mat.userData.keepT=true;
    scr=new T.Mesh(new T.PlaneGeometry(aw,ah),mat);scr.rotation.x=-PI/2;scr.position.set((x0+x1)/2,y+.0015,(z0+z1)/2);parts.screen.add(scr)}
  Object.values(parts).forEach(g=>ownMaterials(g));
  const scrMat=scr?scr.material:null;
  const STOPS=[{key:'shell',parts:['shell'],az:.3,el:.55,fill:.78},{key:'screen',parts:['screen'],az:-.25,el:.78,fill:.6},{key:'sticks',parts:['sticks'],az:.35,el:.5,fill:.62},{key:'switch',parts:['switch'],az:1.0,el:.3,fill:.42,dmin:.7},
    {key:'pi',parts:['pi'],az:.55,el:-.78,fill:.55},{key:'power',parts:['power','elec'],az:-.62,el:-.55,fill:.74},{key:'batt',parts:['batt'],az:-1.05,el:.28,fill:.62},{key:'covers',parts:['mid','bottom'],az:.25,el:-.85,fill:.58}];
  const r={kind:'remote',root,parts,STOPS,inner,screen:scr,scrMat,battSide,fan,fanLeds,shadow:blob(3.2,2.8,.45)};r.stopOf={};STOPS.forEach((s,i)=>s.parts.forEach(p=>r.stopOf[p]=i));
  r.measure=()=>{STOPS.forEach(s=>{Object.assign(s,stopBox(root,s.parts));s.c0=stopBox(root,s.parts,0).c;tagPts(root,s)});r.all=stopBox(root,Object.keys(parts))};r.measure();
  return r}

/* his HUD, redrawn from the screenshots in the thesis (800 x 480, drawn at 1.5x): dark, cyan accents */
function hudTexture(){const k=1.5,w=800*k,h=480*k,c=document.createElement('canvas');c.width=w;c.height=h;const g=c.getContext('2d');g.scale(k,k);
  const CY='#18D8F5',PU='#8B6CF0',mono='600 11px "IBM Plex Mono",ui-monospace,monospace';
  /* the video: the overview camera looking across a wooden floor */
  const sky=g.createLinearGradient(0,30,0,480);sky.addColorStop(0,'#1d1a17');sky.addColorStop(.42,'#3b2c20');sky.addColorStop(.45,'#5a3d26');sky.addColorStop(1,'#8a5c35');g.fillStyle=sky;g.fillRect(0,30,800,450);
  g.save();g.beginPath();g.rect(0,30,800,450);g.clip();
  const hz=226;g.strokeStyle='rgba(30,16,8,.55)';g.lineWidth=1.2;
  for(let i=-24;i<=24;i++){g.beginPath();g.moveTo(400+i*18,hz);g.lineTo(400+i*150,480);g.stroke()}
  for(let j=1;j<14;j++){const y=hz+Math.pow(j/14,2.1)*(480-hz);g.strokeStyle=`rgba(255,220,170,${.04+j*.006})`;g.beginPath();g.moveTo(0,y);g.lineTo(800,y);g.stroke()}
  g.fillStyle='rgba(18,14,12,.85)';g.fillRect(70,120,180,106);g.fillRect(560,96,150,130);   /* furniture in the distance */
  g.fillStyle='rgba(255,236,200,.08)';g.fillRect(600,40,90,70);
  const vg=g.createRadialGradient(400,260,120,400,260,520);vg.addColorStop(0,'rgba(0,0,0,0)');vg.addColorStop(1,'rgba(0,0,0,.62)');g.fillStyle=vg;g.fillRect(0,30,800,450);
  g.restore();
  /* top bar */
  g.fillStyle='#14171d';g.fillRect(0,0,800,30);g.fillStyle=CY;g.fillRect(0,29,800,1.5);
  g.fillStyle='#22c55e';g.beginPath();g.arc(16,15,4.5,0,TAU);g.fill();g.font=mono;g.fillStyle='#22c55e';g.textBaseline='middle';g.fillText('LIVE',27,15.5);
  g.font='700 14px "IBM Plex Mono",ui-monospace,monospace';g.fillStyle=CY;g.textAlign='center';g.fillText('D A T A L I N K   R O V E R',400,15.5);
  g.textAlign='left';g.font='500 9.5px "IBM Plex Mono",ui-monospace,monospace';g.fillStyle='#9aa3b2';g.fillText('ROVER: WIFI',528,15.5);
  const batt=(x,lbl,p)=>{g.fillStyle='#9aa3b2';g.fillText(lbl,x,15.5);g.strokeStyle=CY;g.lineWidth=1.2;g.strokeRect(x+26,9,24,12);g.fillStyle=CY;g.fillRect(x+50,13,2,4);g.fillRect(x+28,11,20*p,8);g.fillStyle='#e8ecf2';g.fillText(Math.round(p*100)+'%',x+56,15.5)};
  batt(606,'RMT',.82);batt(690,'RVR',.74);
  g.font='600 11px "IBM Plex Mono",ui-monospace,monospace';g.fillStyle='#e8ecf2';g.textAlign='right';g.fillText('00:12:48',792,15.5);g.textAlign='left';
  /* picture in picture: the front camera */
  const px=12,py=40,pw=200,ph=124;g.fillStyle='#0c0e12';g.fillRect(px,py,pw,ph);
  const fl=g.createLinearGradient(0,py,0,py+ph);fl.addColorStop(0,'#2a221c');fl.addColorStop(.5,'#4b3423');fl.addColorStop(1,'#7c5332');g.fillStyle=fl;g.fillRect(px+2,py+2,pw-4,ph-4);
  g.strokeStyle='rgba(30,16,8,.5)';for(let i=-8;i<=8;i++){g.beginPath();g.moveTo(px+pw/2+i*6,py+ph*.45);g.lineTo(px+pw/2+i*40,py+ph);g.stroke()}
  g.strokeStyle=CY;g.lineWidth=1.5;g.strokeRect(px,py,pw,ph);g.lineWidth=3;g.beginPath();g.moveTo(px,py+12);g.lineTo(px,py);g.lineTo(px+12,py);g.moveTo(px+pw,py+ph-12);g.lineTo(px+pw,py+ph);g.lineTo(px+pw-12,py+ph);g.stroke();
  g.font=mono;g.fillStyle=CY;g.fillText('CAM 2',px+10,py+ph-12);g.lineWidth=1;g.strokeRect(px+pw-44,py+ph-21,34,15);g.font='600 9px "IBM Plex Mono",monospace';g.fillText('FPV',px+pw-37,py+ph-13);
  /* proximity: the rover from above with the five sensors' arcs */
  const cx=700,cy=98;g.font='600 9px "IBM Plex Mono",monospace';g.fillStyle=PU;g.textAlign='center';g.fillText('P R O X I M I T Y',cx,44);g.textAlign='left';
  g.strokeStyle='rgba(255,255,255,.14)';for(const rr of [44,34,24]){g.lineWidth=7;g.beginPath();g.arc(cx,cy,rr,-PI*.78,-PI*.22);g.stroke();g.beginPath();g.arc(cx,cy,rr,PI*.22,PI*.78);g.stroke()}
  g.strokeStyle='#ffb020';g.lineWidth=7;g.beginPath();g.arc(cx,cy,44,-PI*.68,-PI*.42);g.stroke();
  g.strokeStyle=PU;g.lineWidth=2;g.strokeRect(cx-11,cy-17,22,34);g.strokeRect(cx-15,cy-19,4,38);g.strokeRect(cx+11,cy-19,4,38);g.beginPath();g.arc(cx,cy,4,0,TAU);g.stroke();
  /* round buttons on the right */
  const btn=(y,col)=>{g.strokeStyle=col;g.lineWidth=2;g.fillStyle='rgba(20,22,30,.9)';g.beginPath();g.arc(774,y,17,0,TAU);g.fill();g.stroke()};
  btn(200,PU);btn(244,PU);btn(288,PU);btn(332,'#ff3b5c');
  g.strokeStyle='#fff';g.lineWidth=1.6;g.beginPath();g.moveTo(766,197);g.lineTo(782,197);g.moveTo(778,193);g.lineTo(782,197);g.lineTo(778,201);g.moveTo(782,204);g.lineTo(766,204);g.moveTo(770,200);g.lineTo(766,204);g.lineTo(770,208);g.stroke();
  g.beginPath();g.moveTo(767,239);g.lineTo(773,244);g.lineTo(767,249);g.moveTo(775,250);g.lineTo(782,250);g.stroke();
  g.strokeRect(767,281,6,6);g.strokeRect(776,281,6,6);g.strokeRect(767,290,6,6);g.strokeRect(776,290,6,6);
  g.strokeStyle='#ff3b5c';g.beginPath();g.arc(774,334,7,-PI*.3,PI*1.3);g.moveTo(774,324);g.lineTo(774,332);g.stroke();
  g.font='600 11px "IBM Plex Mono",monospace';g.fillStyle=CY;g.fillText('CAM 1 · OVERVIEW',14,466);
  const t=new T.CanvasTexture(c);t.colorSpace=T.SRGBColorSpace;t.anisotropy=4;return t}

/* ---------- the link: a glowing arc with commands flowing out and video + data flowing back ---------- */
const LINK_VS=`varying vec2 vUv;varying float vF;void main(){vUv=uv;vec4 mv=modelViewMatrix*vec4(position,1.);vec3 n=normalize(normalMatrix*normal);vF=abs(dot(n,normalize(-mv.xyz)));gl_Position=projectionMatrix*mv;}`;
const LINK_FS=`uniform float uT,uP,uV,uHot,uW;uniform vec3 uA,uB;varying vec2 vUv;varying float vF;
void main(){float u=vUv.x;if(u>uP)discard;float edge=smoothstep(uP,uP-.04,u);
  float core=pow(vF,uW);
  float p1=fract(u*3.-uT*(.42+uHot*.5)),f1=smoothstep(0.,.015,p1)*smoothstep(.16,.0,p1);
  float p2=fract(u*2.4+uT*(.3+uHot*.35)+.37),f2=smoothstep(.16,.0,p2)*smoothstep(0.,.015,p2);
  vec3 c=mix(uA,uB,u)*.55*core+uA*f1*core*1.8+uB*f2*core*1.4;
  float a=(.32*core+(f1+f2)*core*.9)*uV*edge*(.75+uHot*.6);
  gl_FragColor=vec4(c*uV*edge*(1.+uHot*.5),a);}`;
function buildLink(A,mid,B){
  const curve=new T.QuadraticBezierCurve3(A,mid,B),uni={uT:{value:0},uP:{value:1},uV:{value:1},uHot:{value:0},uW:{value:1.6},uA:{value:new T.Color(0x4DC8FF)},uB:{value:new T.Color(0xFF9F43)}};
  const mk=(r,w)=>{const u={...uni,uW:{value:w}};return new T.Mesh(new T.TubeGeometry(curve,96,r,10,false),new T.ShaderMaterial({uniforms:u,vertexShader:LINK_VS,fragmentShader:LINK_FS,transparent:true,depthWrite:false,blending:T.AdditiveBlending}))};
  const g=new T.Group(),core=mk(.022,1.2),glow=mk(.09,3.2);glow.material.uniforms.uV=core.material.uniforms.uV;g.add(core,glow);
  const ends=[A,B].map((p,i)=>{const s=new T.Sprite(new T.SpriteMaterial({map:dotTexture(),color:i?0xFF9F43:0x4DC8FF,transparent:true,depthWrite:false,blending:T.AdditiveBlending}));s.position.copy(p);s.scale.setScalar(.42);g.add(s);return s});
  return{g,curve,mats:[core.material,glow.material],ends}}
let _dot=null;function dotTexture(){if(_dot)return _dot;const c=document.createElement('canvas');c.width=c.height=64;const g=c.getContext('2d'),gr=g.createRadialGradient(32,32,0,32,32,32);
  gr.addColorStop(0,'rgba(255,255,255,1)');gr.addColorStop(.25,'rgba(255,255,255,.55)');gr.addColorStop(1,'rgba(255,255,255,0)');g.fillStyle=gr;g.fillRect(0,0,64,64);_dot=new T.CanvasTexture(c);return _dot}

/* ---------- select-screen floor: a soft pool of light and a ring under each object ---------- */
const PAD_FS=`uniform vec3 uC;uniform float uV,uHot,uT;varying vec2 vP;
void main(){float r=length(vP),a=atan(vP.y,vP.x);
  float ring=smoothstep(.035,0.,abs(r-1.28))*(.55+.45*step(.5,fract(a*9./6.2832-uT*.06)));
  float pool=smoothstep(1.9,0.,r)*.22;
  float k=(ring*(.55+uHot*.9)+pool*(.7+uHot*.8))*uV;gl_FragColor=vec4(uC*k,k);}`;
function buildPad(color){const m=new T.Mesh(new T.PlaneGeometry(4.2,4.2),new T.ShaderMaterial({uniforms:{uC:{value:new T.Color(color)},uV:{value:1},uHot:{value:0},uT:{value:0}},
  vertexShader:`varying vec2 vP;void main(){vP=position.xy;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,fragmentShader:PAD_FS,transparent:true,depthWrite:false,blending:T.AdditiveBlending}));
  m.rotation.x=-PI/2;m.position.y=.004;m.renderOrder=-2;return m}

/* ---------- lighting: a small photo studio (soft boxes around a dark room), turned into reflections once ---------- */
function studio(){const s=new T.Scene();const room=new T.Mesh(new T.BoxGeometry(1,1,1),new T.MeshBasicMaterial({color:0x0e1014,side:T.BackSide}));room.scale.set(30,16,30);room.position.y=4;s.add(room);
  const pane=(w,h,x,y,z,col,k)=>{const m=new T.Mesh(new T.PlaneGeometry(w,h),new T.MeshBasicMaterial({color:new T.Color(col).multiplyScalar(k),side:T.DoubleSide}));m.position.set(x,y,z);m.lookAt(0,0,0);s.add(m)};
  pane(9,6,6,9,7,'#ffffff',5.2);pane(6,8,-11,3,4,'#e9eef8',1.5);pane(14,3,0,12,0,'#ffffff',2.1);
  pane(5,9,-7,4,-10,'#ffd2b0',1.1);pane(5,9,9,4,-9,'#c4e4ff',1.0);pane(30,30,0,-3.5,0,'#26282d',1);
  for(let i=0;i<8;i++){const a=i/8*TAU;pane(5,2.2,Math.cos(a)*12,1.2,Math.sin(a)*12,'#cfd6e2',.5)}
  return s}

/* ---------- poses: what the picture should look like for a mode (and a scroll position) ---------- */
function stopWorld(obj,s,yaw,x,y,z,pitch=0,sc=1){const c=s.c.clone();c.applyEuler(new T.Euler(pitch,yaw,0,'YXZ')).multiplyScalar(sc);return c.add(new T.Vector3(x,y,z))}
function focusCam(P,obj,k,base,port){const s=obj.STOPS[k],sc=base.s||1,wp=stopWorld(obj,s,base.yaw,base.x,base.y,base.z,base.pitch||0,sc);
  let fill=(s.fill||.4)*(port?1.2:1),py=port?.34:.5;const ct=port&&CT[obj.kind]&&CT[obj.kind][k];
  if(ct){const top=76,bot=ct*H-10;fill=clamp((bot-top)*.94/Math.min(W,H),.36,fill);py=clamp((top+bot)/2/H,.2,.34)}   // between the island and the card
  const d=Math.max(s.dmin||1.6,fitD(s.r*sc,28,fill));camAt(P,wp.x,wp.y,wp.z,base.yaw+s.az,s.el,d,28);P.px=port?.5:.64;P.py=py}
function overviewCam(P,obj,base,port,mul=1){const sc=base.s||1,c=stopWorld(obj,obj.all,base.yaw,base.x,base.y,base.z,base.pitch||0,sc),ov=(!port&&obj.ov)||{};
  camAt(P,c.x,c.y,c.z,base.az,base.el,fitD(obj.all.r*sc,28,port?1.02:.98)*mul*(ov.mul||1),28);P.px=.5;P.py=port?.46:(ov.py||.5)}
function storyPose(P,obj,base,heroCam,port,pre){
  const s=story,n=obj.STOPS.length,O=blank(),A=blank(),B=blank();
  overviewCam(O,obj,base,port);
  P[pre+'V']=1;P[pre+'Yaw']=base.yaw;P[pre+'Pitch']=base.pitch||0;P[pre+'X']=base.x;P[pre+'Y']=base.y;P[pre+'Z']=base.z;P[pre+'S']=base.s||1;
  switch(s.type){
    case'hero':mixCam(P,heroCam,heroCam,0);P[pre+'Sway']=1;break;
    case'explode':P[pre+'Ex']=s5(s.t);P[pre+'Sway']=1-ss(0,.45,s.t);mixCam(P,heroCam,O,s5(s.t));break;
    case'part':{const k=s.k,e=ss(0,.42,s.t);P[pre+'Ex']=1;P[pre+'Dim']=k===0?e:1;P[pre+'F']=k-1+e;
      if(k===0)mixCam(A,O,O,0);else focusCam(A,obj,k-1,base,port);focusCam(B,obj,k,base,port);mixCam(P,A,B,s5(e));break}
    case'rebuild':P[pre+'Ex']=1-s5(ss(.1,1,s.t));P[pre+'Dim']=1-ss(0,.35,s.t);P[pre+'F']=n-1;focusCam(A,obj,n-1,base,port);mixCam(P,A,heroCam,s5(ss(0,.85,s.t)));break;
    case'action':P[pre+'Act']=s.t;mixCam(P,heroCam,heroCam,0);break;
    case'after':P[pre+'Act']=1;mixCam(P,heroCam,heroCam,0);break}}
function recede(P,port,obj){if(obj==='m'){if(port){P.mX=0;P.mY=3.3;P.mZ=-5.2}else{P.mX=-3.6;P.mY=1.1;P.mZ=-5.2}P.mPitch=.95;P.mYaw=.55;P.mS=.82}
  else{if(port){P.rX=0;P.rZ=-4.6}else{P.rX=3.7;P.rZ=-5}P.rYaw=-1.0;P.rS=.82*RS}}
function selectPose(P,port){P.rV=P.mV=P.lV=P.lP=P.pad=P.floor=1;P.rTurn=1;P.mSway=1;P.rS=RS;
  if(!port){P.rX=2.4;P.rZ=.3;P.rYaw=-.7;P.mX=-2.4;P.mY=1.12;P.mPitch=1.08;P.mYaw=.32;P.mS=.92;camAt(P,0,.95,0,0,.11,11.6,30);P.py=.54}
  else{P.rX=0;P.rZ=1.2;P.rYaw=-.7;P.rS=.86*RS;P.mX=0;P.mY=2.95;P.mZ=-1.4;P.mPitch=1.0;P.mYaw=.25;P.mS=.78;camAt(P,0,1.38,0,0,.16,16.5,34);P.py=.56}}
function pose(){const P=blank(),port=W/H<.9;recede(P,port,'m');recede(P,port,'r');
  if(mode==='card'){P.rX=P.rY=P.rZ=P.rYaw=0;P.rS=1;P.rV=1;P.rTurn=1;const d=cardDist(W,H);P.cx=TGT[0]+DIR[0]*d;P.cy=TGT[1]+DIR[1]*d;P.cz=TGT[2]+DIR[2]*d;P.tx=TGT[0];P.ty=TGT[1];P.tz=TGT[2];P.fov=CFOV;return P}
  if(mode==='select'){selectPose(P,port);return P}
  if(mode==='rover'&&rover){const s=RS,c=rover.body.c,base={x:0,y:0,z:0,yaw:.62,az:-.55,el:.42,s},H0=blank();recede(H0,port,'m');
    const hc=stopWorld(rover,{c},.62,0,0,0,0,s);camAt(H0,hc.x,hc.y,hc.z,-.55,.26,fitD(rover.body.r*s,26,port?.95:.78),26);H0.py=port?.6:.6;
    storyPose(P,rover,base,H0,port,'r');P.floor=1;P.warm=1.25;P.cool=.55;return P}
  if(mode==='remote'&&remote){const s=story,ex=s.type==='explode'?s5(s.t):s.type==='part'?1:s.type==='rebuild'?1-s5(ss(0,.9,s.t)):0;
    const base={x:0,y:lerp(1.05,1.3,ex),z:0,yaw:.38,pitch:lerp(1.0,.3,ex),az:.45,el:.42},H0=blank();
    camAt(H0,0,1.05,0,.12,.18,fitD(1.6,26,port?.95:.68),26);H0.py=port?.6:.58;
    storyPose(P,remote,base,H0,port,'m');P.floor=1;P.warm=.5;P.cool=1.3;return P}
  if(mode==='link'){P.floor=0;P.warm=.6;P.cool=1;const s=story;
    /* the diagram is drawn by the page; the 3D only comes back at the end, the controller and the rover with the link between them */
    if(s.type==='finale'||s.type==='after'){const Q=blank();selectPose(Q,port);const e=s.type==='after'?1:ss(.25,.9,s.t);
      for(const k of ['rX','rY','rZ','rYaw','rS','mX','mY','mZ','mYaw','mPitch','mS','rTurn','mSway'])P[k]=Q[k];mixCam(P,Q,Q,0);
      P.rV=P.mV=e;P.lV=e;P.lP=e;P.floor=e;P.rTurn=1}
    else{selectPose(P,port);P.rV=P.mV=P.lV=P.lP=P.pad=P.floor=0}
    return P}
  return P}
/* the card, seen from the full-size canvas: same picture as the card slot, drawn into that rectangle */
function cardPose(r){const P=blank(),port=W/H<.9,S=(()=>{const m=mode;mode='select';const q=pose();mode=m;return q})();
  for(const k of ['mX','mY','mZ','mPitch','mYaw','mS'])P[k]=S[k];P.mY-=.8;P.mV=0;
  P.rV=1;P.rTurn=1;const d=cardDist(r.width,r.height);
  P.cx=TGT[0]+DIR[0]*d;P.cy=TGT[1]+DIR[1]*d;P.cz=TGT[2]+DIR[2]*d;P.tx=TGT[0];P.ty=TGT[1];P.tz=TGT[2];
  P.fov=2*Math.atan(H/r.height*tanH(CFOV))*180/PI;P.px=(r.left+r.width/2)/W;P.py=(r.top+r.height/2)/H;return P}

/* ---------- apply the state to the scene ---------- */
let tmpV=null;
const BOOT=[[0,0],[.08,-1],[.15,-1],[.24,1],[.31,1],[.38,0]];   /* the servo's boot sweep from rover.py: full left, full right, centre */
function bootPan(t){if(t<=0||t>=BOOT[BOOT.length-1][0])return 0;for(let i=1;i<BOOT.length;i++)if(t<=BOOT[i][0]){const a=BOOT[i-1],b=BOOT[i],e=s5((t-a[0])/(b[0]-a[0]));return lerp(a[1],b[1],e)}return 0}
function apply(dt){
  const c=cur;
  cam.position.set(c.cx,c.cy,c.cz);cam.up.set(0,1,0);cam.lookAt(c.tx,c.ty,c.tz);cam.updateMatrixWorld();
  const f=(H/2)/tanH(c.fov),n=cam.near,fr=cam.far,px=c.px*W,py=c.py*H;
  cam.projectionMatrix.makePerspective(-px/f*n,(W-px)/f*n,py/f*n,-(H-py)/f*n,n,fr);cam.projectionMatrixInverse.copy(cam.projectionMatrix).invert();
  /* rover */
  const R=rover;
  if(R){const act=c.rAct,rv=c.rV*(1-ss(.84,1,act));R.root.visible=rv>.004;
  if(R.root.visible){
    const turn=ss(.42,.56,act),drive=Math.pow(ss(.52,1,act),1.35)*11;
    let yaw=c.rYaw+spinR*c.rTurn+c.rSway*.38*Math.sin(vt*.42)+hov.cx*.45*hov.r*wC;
    if(turn>0){const away=Math.atan2(c.tx-c.cx,c.tz-c.cz);yaw=lerp(yaw,yaw+wrap(away-yaw),turn)}
    R.root.position.set(c.rX+Math.sin(yaw)*drive,c.rY+hov.r*.06*wS,c.rZ+Math.cos(yaw)*drive);
    R.root.rotation.set(c.rPitch+hov.cy*.06*hov.r*wC,yaw,0,'YXZ');R.root.scale.setScalar(c.rS);
    partsOf(R.root).forEach(g=>{const u=g.userData,e=s5((c.rEx-u.delay)/(1-.38));g.position.copy(u.base).addScaledVector(u.off,e);
      const w=clamp(1-Math.abs((R.stopOf[u.key]??-9)-c.rF));shade(g,c.rDim*(1-w),rv)});
    R.shadow.material.opacity=rv*(1-c.rEx*.6);
    /* the camera head: the boot sweep when it switches on; on hover it turns to look at you */
    const look=Math.atan2(c.cx-R.root.position.x,c.cz-R.root.position.z)-yaw;
    const want=hov.r*(mode==='select'||mode==='card'?1:0)*clamp(wrap(look),-1.2,1.2)+bootPan(act)*1.45;
    R.pan+=(want-R.pan)*Math.min(1,dt*9);if(Math.abs(want-R.pan)<.0005)R.pan=want;R.pivot.rotation.y=R.pan;
    const blink=act>.02&&act<.5?(Math.sin(vt*18)>0?1:.25):1;R.ledMats.forEach(m=>m.color&&m.color.setScalar(blink));
    const trd=R.trd+drive*100+turn*60;
    if(Math.abs(trd-R.trdDrawn)>.05){R.placeTreads(trd);R.trdDrawn=trd}}}
  /* controller */
  if(remote){const M2=remote,a=c.mAct,mv=c.mV*(1-ss(.84,1,a));M2.root.visible=mv>.004;M2.shadow.visible=M2.root.visible;
    if(M2.root.visible){const away=ss(.58,1,a);
      const yaw=c.mYaw+c.mSway*.3*Math.sin(vt*.45)+away*.6,pitch=c.mPitch+c.mSway*.05*Math.sin(vt*.7)+away*.35-hov.m*.08;
      M2.root.position.set(c.mX-away*2.6,c.mY+c.mSway*.05*Math.sin(vt*.9)+hov.m*.1+away*1.4,c.mZ-away*4.5);
      M2.root.rotation.set(pitch,yaw,0,'YXZ');M2.root.scale.setScalar(c.mS*(1+hov.m*.035));
      const eb=s5((c.mEx-.28)/(1-.3));M2.battSide.forEach(w=>w.position.set(w.userData.side*.55*eb,0,.12*eb));
      partsOf(M2.inner).forEach(g=>{const u=g.userData,e=s5((c.mEx-u.delay)/(1-.3));g.position.copy(u.base).addScaledVector(u.off,e);
        const w=clamp(1-Math.abs((M2.stopOf[u.key]??-9)-c.mF));shade(g,c.mDim*(1-w),mv)});
      const on=Math.max(ss(.02,.16,a)*(1-ss(.9,1,a)),(mode==='select'?.35:0)+hov.m*.65,mode==='card'?0:0);
      if(M2.scrMat)M2.scrMat.emissiveIntensity=on*mv*(1-.75*c.mDim*(1-clamp(1-Math.abs(1-c.mF))))*1.15;
      if(M2.fan){M2.fan.rotation.y+=dt*on*28;M2.fanLeds.forEach(o=>o.material.color.setScalar(.25+on*.9))}
      M2.shadow.position.set(M2.root.position.x,.004,M2.root.position.z);M2.shadow.material.opacity=mv*clamp(1.4-M2.root.position.y*.45,.25,1)*(1-c.mEx*.7)}}
  /* link, pads, floor */
  if(link){link.g.visible=c.lV>.004;if(link.g.visible){link.mats.forEach(m=>{m.uniforms.uT.value=vt;m.uniforms.uP.value=c.lP;m.uniforms.uHot.value=hov.l});link.mats[0].uniforms.uV.value=c.lV;
    link.ends.forEach(s=>s.material.opacity=c.lV*clamp(c.lP*1.5))}}
  [padR,padM].forEach((p,i)=>{p.visible=c.pad>.004;const u=p.material.uniforms;u.uV.value=c.pad;u.uT.value=vt;u.uHot.value=i?hov.m:hov.r});
  padR.position.set(c.rX,.004,c.rZ);padM.position.set(c.mX,.004,c.mZ);
  floorM.visible=c.floor>.004;floorM.material.opacity=c.floor;
  lights.rimW.intensity=2.2*c.warm;lights.rimC.intensity=1.5*c.cool;
  const cd=Math.hypot(c.cx-c.tx,c.cy-c.ty,c.cz-c.tz)||1;lights.under.intensity=1.15*clamp((c.ty-c.cy)/cd*2.4)}

/* ---------- loop ---------- */
function goalNow(){return fixedGoal||pose()}
function settled(g){for(const k of KEYS)if(Math.abs(g[k]-cur[k])>(k==='fov'?.01:.0015))return false;return true}
function busyAnim(){
  if(mode==='card'||mode==='select')return true;
  if(Math.abs(wC)+Math.abs(wS)>.002&&hov.r>.002)return true;
  if(cur.lV>.01)return true;
  if((cur.rSway>.01&&cur.rV>.01)||(cur.mSway>.01&&cur.mV>.01))return true;
  if(cur.rAct>0&&cur.rAct<1||cur.mAct>0&&cur.mAct<1)return true;
  if(rover&&Math.abs(rover.pan)>.002)return true;
  return Math.abs(hov.r-hov.rT)+Math.abs(hov.m-hov.mT)+Math.abs(hov.l-hov.lT)>.002}
/* transitions follow real elapsed time (so they stay in step with the page's own animations even when frames are slow);
   smoothing and effects use a capped step */
let xtra=0;   /* test hook: time added to the next frame while the clock is frozen */
function frame(ts){raf=0;const raw=last?(ts-last)/1000:0;last=ts;const dt=Math.min(.05,raw)*tscale+Math.min(.05,xtra),dtT=Math.min(.5,raw)*tscale+xtra;xtra=0;vt+=dtT;
  if(lowUntil&&vt>=lowUntil){lowUntil=0;buffer()}
  const kh=1-Math.exp(-dt*7);wC+=((mode==='card'?1:0)-wC)*kh;wS+=((mode==='select'?1:0)-wS)*kh;hov.r+=(hov.rT-hov.r)*kh;hov.m+=(hov.mT-hov.m)*kh;hov.l+=(hov.lT-hov.l)*kh;hov.cx+=(hov.cxT-hov.cx)*kh;hov.cy+=(hov.cyT-hov.cy)*kh;
  if(cur.rTurn>.001)spinR+=dt*(mode==='select'?.32+hov.r*.5:.3+hov.r*.18);
  if(rover&&(mode==='card'||mode==='select'))rover.trd+=dt*hov.r*60;
  const g=goalNow();let moving=false;
  if(tw){if(tw.clock){const v=tw.clock();tw.k=Math.max(tw.k,v==null?1:clamp(v/tw.dur))}else tw.k=clamp(tw.k+dtT*1000/tw.dur);   /* a clock that stopped (null) means its animation is over */const e=tw.ease(tw.k);for(const k of KEYS)cur[k]=lerp(tw.from[k],g[k],e);moving=true;
    if(tw.k>=1){const r=tw.res;tw=null;r&&r()}}
  else if(!settled(g)){const a=1-Math.exp(-dt*10);for(const k of KEYS)cur[k]+=(g[k]-cur[k])*a;moving=true}
  const anim=busyAnim(),show=shown||vt<force;if(moving)lastMove=vt;if(show&&(moving||anim))watchLod(raw);
  if(show&&ren&&(moving||anim||dirty)&&(tier===0||moving||dirty||ts-lastDraw>31||mode==='card'&&hov.r>.02)){
    const p0=performance.now();apply(dt);ren.render(scene,cam);lastDraw=ts;dirty=false;for(const f of frameSubs)f();perf.ms+=performance.now()-p0;perf.n++}
  if(show&&(moving||anim||dirty||vt<force))raf=requestAnimationFrame(frame);else last=0}
const wake=()=>{if(!raf&&(shown||vt<force))raf=requestAnimationFrame(frame)};

/* ---------- size ---------- */
function frameTo(w,h){w=Math.max(1,Math.round(w));h=Math.max(1,Math.round(h));if(!ren||(w===W&&h===H))return;W=w;H=h;dirty=true;placeLink();wake()}
/* during big page transitions the view can draw at 1x for a moment (fewer pixels while everything moves), then sharpens */
let lowUntil=0;
function buffer(){if(!ren||!W)return;const caps=[2,1.5,1.25,1];let pr=Math.min(devicePixelRatio||1,caps[tier]||1);if(vt<lowUntil)pr=Math.min(pr,1);const bw=Math.round(W*pr),bh=Math.round(H*pr);
  if(bw===BW&&bh===BH)return;BW=bw;BH=bh;if(ren.getPixelRatio()!==pr)ren.setPixelRatio(pr);ren.setSize(W,H,false);dirty=true;wake()}
function setSize(w,h,now){frameTo(w,h);clearTimeout(bufT);if(now||!BW)buffer();else bufT=setTimeout(buffer,160)}
let linkKey='';
function placeLink(){if(!rover)return;const port=W/H<.9,k=port?'p':'l';if(k===linkKey&&link)return;linkKey=k;
  if(link){scene.remove(link.g);link.g.traverse(o=>{if(o.geometry)o.geometry.dispose()})}
  const P=blank();selectPose(P,port);const V=(x,y,z)=>new T.Vector3(x,y,z),top=(rover.body.c.y+rover.body.r*.55)*P.rS;let A,B,C;
  if(!port){A=V(P.mX+.1,P.mY+1.2,P.mZ-.35);B=V(P.rX,top,P.rZ);C=A.clone().add(B).multiplyScalar(.5);C.y+=1.45}
  else{A=V(P.mX+.95,P.mY-.45,P.mZ+.6);B=V(P.rX+.5,top*.92,P.rZ-.3);C=A.clone().add(B).multiplyScalar(.5);C.x+=2.3}
  link=buildLink(A,C,B);scene.add(link.g);dirty=true}

/* ---------- detail levels ----------
   The page starts with the light models. On capable devices (quality tiers 0 and 1) the ultra-detailed ones (rover-hi.js,
   remote-hi.js, about 1.4 M triangles for the controller alone) are fetched and decoded in idle time, one mesh at a time,
   and swapped in at a calm moment. If the device then cannot hold about 30 fps while the view moves, the light ones come back. */
const idle=f=>('requestIdleCallback' in window)?requestIdleCallback(f,{timeout:3000}):setTimeout(f,500);
const LOD={lo:{},hi:{},ready:{},level:'lo',watch:null,timer:0,off:false,started:false};
function maybeHi(){if(LOD.started||LOD.off||tier>1||matchMedia('(pointer:coarse)').matches||!remote||/[?&]lod=lo/.test(location.search))return;LOD.started=true;setTimeout(()=>idle(loadHi),1200)}
let lastMove=0;
async function loadHi(){
  try{const RM=await dataScript('assets/models/rover-hi.js','DL_ROVER_HI','dl-rover-hi');const rh=buildRover(await unpack(RM,true),RM);delete window.DL_ROVER_HI;LOD.ready.rover=rh;armSwap()}
  catch(e){console.info('DataLink: detailed rover unavailable, keeping the light one',e)}
  await new Promise(r=>idle(r));
  try{const MM=await dataScript('assets/models/remote-hi.js','DL_REMOTE_HI','dl-remote-hi');const mh=buildRemote(await unpack(MM,true),MM);delete window.DL_REMOTE_HI;LOD.ready.remote=mh;armSwap()}
  catch(e){console.info('DataLink: detailed controller unavailable, keeping the light one',e)}}
function armSwap(){if(LOD.timer)return;LOD.timer=setInterval(()=>{if(LOD.off){clearInterval(LOD.timer);LOD.timer=0;return}
  const calm=!shown||(!tw&&vt-lastMove>.35);if(!calm)return;
  const r=LOD.ready.rover,m=LOD.ready.remote;
  if(r){LOD.lo.rover=rover;put('rover',r);LOD.hi.rover=r;LOD.ready.rover=null}
  if(m){LOD.lo.remote=remote;put('remote',m);LOD.hi.remote=m;LOD.ready.remote=null}
  if(r||m){LOD.level='hi';LOD.watch={n:0,sum:0}}
  if(!LOD.ready.rover&&!LOD.ready.remote){clearInterval(LOD.timer);LOD.timer=0}},250)}
/* put a model in the scene in place of the current one (keeps the camera head's turn and the tread position) */
function put(kind,o){
  if(kind==='rover'){const old=rover;if(old===o)return;o.pan=old.pan;o.trd=old.trd;o.trdDrawn=-1;scene.remove(old.root);scene.add(o.root);rover=o}
  else{const old=remote;if(old===o)return;if(old){scene.remove(old.root,old.shadow)}scene.add(o.root,o.shadow);remote=o}
  dirty=true;wake()}
function watchLod(raw){const w=LOD.watch;if(!w||raw<=0||raw>.25)return;w.n++;w.sum+=raw;
  if(w.n<60)return;LOD.watch=null;const avg=w.sum/w.n;
  if(avg>(tier===0?.042:.034)){LOD.off=true;LOD.level='lo';if(LOD.lo.rover)put('rover',LOD.lo.rover);if(LOD.lo.remote)put('remote',LOD.lo.remote);
    console.info('DataLink: back to the light models ('+Math.round(avg*1000)+' ms a frame)')}}

/* ---------- init ---------- */
function init(t){tier=t|0;if(ready)return ready;
  ready=Promise.all([import('three'),import('three/addons/environments/RoomEnvironment.js')]).then(async([t3])=>{T=t3;
    cv=document.createElement('canvas');cv.className='dl3d';
    try{ren=new T.WebGLRenderer({canvas:cv,antialias:tier===0,alpha:true,powerPreference:'low-power'})}catch(e){console.info('3D: no WebGL',e);return false}
    ren.toneMapping=T.ACESFilmicToneMapping;ren.toneMappingExposure=1.05;ren.setClearColor(0,0);
    scene=new T.Scene();cam=new T.PerspectiveCamera(30,1,.05,80);
    scene.add(new T.HemisphereLight(0xdfe6ff,0x20160c,.45));
    const key=new T.DirectionalLight(0xffffff,1.5);key.position.set(3,6,5);scene.add(key);
    lights.rimW=new T.DirectionalLight(0xFF9F43,2.2);lights.rimW.position.set(-4,2.5,-3);scene.add(lights.rimW);
    lights.rimC=new T.DirectionalLight(0x4DC8FF,1.5);lights.rimC.position.set(4,2.2,-4);scene.add(lights.rimC);
    lights.under=new T.DirectionalLight(0xdfe6ff,0);lights.under.position.set(1,-4,3);scene.add(lights.under);   /* lights the undersides when the camera looks from below */
    const pm=new T.PMREMGenerator(ren);scene.environment=pm.fromScene(studio(),.035).texture;pm.dispose();
    atlas=new T.TextureLoader().load('assets/models/atlas.webp',()=>{dirty=true;wake()});atlas.colorSpace=T.SRGBColorSpace;atlas.anisotropy=tier===0?8:4;
    padR=buildPad(0xFF9F43);padM=buildPad(0x4DC8FF);scene.add(padR,padM);
    const fc=document.createElement('canvas');fc.width=fc.height=256;const fg=fc.getContext('2d'),gr=fg.createRadialGradient(128,128,0,128,128,128);
    gr.addColorStop(0,'rgba(150,170,210,.10)');gr.addColorStop(.5,'rgba(150,170,210,.04)');gr.addColorStop(1,'rgba(150,170,210,0)');fg.fillStyle=gr;fg.fillRect(0,0,256,256);
    floorM=new T.Mesh(new T.CircleGeometry(13,64),new T.MeshBasicMaterial({map:new T.CanvasTexture(fc),transparent:true,depthWrite:false}));floorM.rotation.x=-PI/2;floorM.renderOrder=-3;scene.add(floorM);
    cv.addEventListener('webglcontextlost',e=>e.preventDefault());
    /* the rover first (the project card needs it), then the controller */
    try{const RM=await dataScript('assets/models/rover.js','DL_ROVER','dl-rover');rover=buildRover(await unpack(RM),RM);scene.add(rover.root);
      const b=rover.body;R0=b.r*.98;TGT=[b.c.x,b.c.y,b.c.z]}
    catch(e){console.warn('DataLink: rover model unavailable',e);return false}
    Object.assign(cur,pose());
    dataScript('assets/models/remote.js','DL_REMOTE','dl-remote').then(unpack).then(ms=>{remote=buildRemote(ms,window.DL_REMOTE);scene.add(remote.root,remote.shadow);placeLink();dirty=true;wake();(api.onRemote||(()=>{}))();
        maybeHi()})
      .catch(e=>console.warn('DataLink: controller model unavailable',e));
    if(W>1)placeLink();
    return true}).catch(e=>{console.info('3D unavailable',e);return false});
  return ready}

/* ---------- public ---------- */
const P3=()=>tmpV||(tmpV=new T.Vector3());
function project(x,y,z){const v=P3().set(x,y,z).project(cam);return{x:(v.x*.5+.5)*W,y:(-v.y*.5+.5)*H,z:v.z,ok:v.z<1}}
const api=window.DL3D={init,
  get ok(){return !!ren&&!!rover},get canvas(){return cv},get mode(){return mode},get size(){return[W,H]},get remoteReady(){return !!remote},
  mount(el){if(!cv)return;slot=el;if(cv.parentNode!==el)el.appendChild(cv);
    if(!ro)ro=new ResizeObserver(es=>{for(const e of es)if(e.target===slot&&cv.parentNode===slot){const r=e.contentRect;if(r.width&&r.height)setSize(r.width,r.height)}});
    ro.disconnect();ro.observe(el);const r=el.getBoundingClientRect();if(r.width&&r.height)setSize(r.width,r.height,true)},
  setSize,setVis(v){shown=!!v;wake()},keep(ms){force=Math.max(force,vt+ms/1000);wake()},lowRes(ms){lowUntil=vt+ms/1000;buffer();wake()},
  /* go to a mode; with dur>0 the picture eases there from wherever it is now */
  go(m,{dur=900,ease=easeIO,from,goal,clock}={}){cur.rYaw+=spinR*cur.rTurn;spinR=0;mode=m;fixedGoal=goal||null;
    const g=goalNow();cur.rYaw=g.rYaw+wrap(cur.rYaw-g.rYaw);cur.mYaw=g.mYaw+wrap(cur.mYaw-g.mYaw);
    if(from){const y=cur.rYaw;Object.assign(cur,from);cur.rYaw=y}
    if(!dur){Object.assign(cur,g);tw=null;dirty=true;wake();return Promise.resolve()}
    return new Promise(res=>{tw={from:{...cur},k:0,dur,ease,res,clock};dirty=true;wake()})},
  cardPose,pose:()=>pose(),snap(){return{...cur}},release(){fixedGoal=null;dirty=true;wake()},
  story(s){Object.assign(story,s);dirty=true;wake()},
  hover(which){hov.rT=which==='rover'?1:0;hov.mT=which==='remote'?1:0;hov.lT=which==='link'?1:0;wake()},
  cardHover(on,x=0,y=0){hov.rT=on?1:0;hov.cxT=on?x:0;hov.cyT=on?y:0;wake()},
  /* screen positions for the page's labels */
  anchor(name){if(!ren||!rover)return null;
    if(name==='rover'){const s=cur.rS;return project(cur.rX,0,cur.rZ+(W/H<.9?1.4:1.9)*s)}
    if(name==='remote'){return project(cur.mX,W/H<.9?cur.mY-1.3*cur.mS:0,cur.mZ+(W/H<.9?.4:2.7))}
    if(name==='roverTop')return project(cur.rX,(rover.body.c.y+rover.body.r*.62)*cur.rS,cur.rZ);
    if(name==='remoteTop')return project(cur.mX,cur.mY+1.3*cur.mS,cur.mZ);
    if(name==='link'&&link){const p=link.curve.getPoint(.5);return project(p.x,p.y+.25,p.z)}
    const m=name.match(/^(rover|remote):(\w+)$/);if(m){const o=m[1]==='rover'?rover:remote;if(!o||!o.root.visible)return null;const s=o.STOPS.find(x=>x.key===m[2]);if(!s)return null;
      const ex=o===rover?cur.rEx:cur.mEx,c=s.t0.clone().lerp(s.t,s5(ex));o.root.updateMatrixWorld();const w=o.root.localToWorld(c);return project(w.x,w.y,w.z)}
    return null},
  stops(which){const o=which==='rover'?rover:remote;return o?o.STOPS.map(s=>s.key):[]},
  cardTops(which,a){CT[which]=a;dirty=true;wake()},
  onFrame(f){frameSubs.push(f)},
  setTier(t){tier=t;BW=0;buffer();maybeHi()},get lod(){return LOD.level},loadHi(){return loadHi()},setTimeScale(k){tscale=k},_advance(sec){xtra+=sec;dirty=true;wake()},_dbg:()=>({remote,rover,cur,scene,cam,T,LOD,tier,shown,tw}),_perf:()=>{const r={ms:perf.ms,n:perf.n,avg:perf.n?perf.ms/perf.n:0,calls:ren.info.render.calls,tris:ren.info.render.triangles};perf.ms=perf.n=0;return r}};
})();
