/* Background light renderer.
   The same file runs in two places. As a Web Worker it draws into an OffscreenCanvas, so the light is produced on its own
   thread and keeps its frame rate even when the page's main thread is busy. Loaded as a normal script it only defines
   PrismLightEngine, which the page uses on the main thread when workers or OffscreenCanvas are unavailable. */
(function(){'use strict';
const sstep=(a,b,x)=>{const t=Math.min(1,Math.max(0,(x-a)/(b-a)));return t*t*(3-2*t)};

/* one draw call of soft capsule quads (beams, lamp, fringes) plus one fan mesh (continuous spectrum) */
const VS=`attribute vec4 aP,aAB,aL,aCol,aPar,aX;
uniform vec2 uRes,uZ;uniform float uCam;uniform vec3 uFr;
varying vec4 vA,vCol,vPar;varying vec3 vB;
void main(){float g=aAB.w,s=1.0;vec2 p;
  if(g<0.5){p=uZ+(aP.xy-uZ)*uCam;}
  else{s=g<1.5?uFr.x:(g<2.5?uFr.y:uFr.z);p=uZ+(aP.xy-uZ)*s+aP.zw;}
  vA=vec4(aAB.x*s+aAB.y,aAB.z,aL.x*s,aL.y);vB=vec3(aL.z,aL.w,aX.x);vCol=aCol;vPar=aPar;
  gl_Position=vec4(p.x/uRes.x*2.0-1.0,1.0-p.y/uRes.y*2.0,0.0,1.0);}`;
const FS=(P,K)=>`precision ${P} float;
#define K ${K}
uniform float uT,uV,uOff,uSw,uLam0,uHovT,uFade,uFrA;uniform vec2 uHov0,uHov1;uniform vec4 uS[K];
varying vec4 vA,vCol,vPar;varying vec3 vB;
float sig(float te){return te<uSw?1e4:max(2.0,300.0*exp(-(te-uSw)/60.0));}
float cmp(float te){return te<uSw?1.0:clamp(119.7/sig(te),1.0,6.0);}
float onA(float te){return smoothstep(0.0,12.0,te)*(1.0-smoothstep(uOff,uOff+12.0,te));}
float bump(float l,float te){float k=smoothstep(uHovT,uHovT+90.0,te),d0=l-uHov0.x,d1=l-uHov1.x;
  return 1.0+mix(uHov0.y*exp(-0.5*d0*d0/64.0),uHov1.y*exp(-0.5*d1*d1/64.0),k);}
float wgt(float l,float te){float s=sig(te),d=l-uLam0;return exp(-0.5*d*d/(s*s))*cmp(te)*bump(l,te);}
vec3 spec(float te){vec3 c=vec3(0.0);for(int k=0;k<K;k++){c+=uS[k].rgb*wgt(uS[k].w,te);}return c;}
float hash(vec2 p){return fract(sin(dot(p,vec2(12.9898,78.233)))*43758.5453);}
void main(){
  if(vA.w>2.5){float a=vA.x,len=vA.z,te=uT-(vPar.x+a)/uV,on=onA(te);
    if(on<0.0005){gl_FragColor=vec4(0.0);return;}
    float I=vB.y*on*vA.y*smoothstep(0.0,8.0,a)*(1.0-smoothstep(len-46.0,len,a))/(1.0+a/110.0);
    vec3 col=1.0-exp(-vCol.rgb*wgt(vCol.w,te)*(I*uFade*1.3));
    col=max(col+(hash(gl_FragCoord.xy)-0.5)*(1.0/255.0),0.0);
    gl_FragColor=vec4(col,max(max(col.r,col.g),col.b));return;}
  float a=vA.x,b=vA.y,len=vA.z,kind=vA.w,ac=clamp(a,0.0,len),d=length(vec2(a-ac,b)),spr=vPar.w,Rl=vB.x+3.0*ac*spr;
  if(d>=Rl){gl_FragColor=vec4(0.0);return;}
  float te=0.0,on=1.0;
  if(kind<1.5){te=uT-(vPar.x+ac*vPar.y)/uV;on=onA(te);if(on<0.0005){gl_FragColor=vec4(0.0);return;}spr*=clamp(sig(te)/9.0,0.0,1.0);}
  float w0=vPar.z,w=w0+ac*spr,core=exp(-0.5*d*d/(w*w))*sqrt(w0/w),x=d/Rl,f=(1.0-x)*(1.0-x);f*=f;
  float glow=f/(1.0+d*d/(9.0*w0*w0)),I=(1.6*core+0.45*glow)*(1.0-smoothstep(0.75,1.0,x))*vB.y*on;
  if(vB.z>0.0)I*=exp(-ac/vB.z);
  vec3 c=kind>1.5?vCol.rgb*uFrA:(kind<0.5?spec(te):vCol.rgb*wgt(vCol.w,te));
  vec3 col=1.0-exp(-c*(I*uFade*1.3));
  col=max(col+(hash(gl_FragCoord.xy)-0.5)*(1.0/255.0),0.0);
  gl_FragColor=vec4(col,max(max(col.r,col.g),col.b));}`;
const UN=['uRes','uZ','uCam','uFr','uT','uV','uOff','uSw','uLam0','uHovT','uFade','uFrA','uHov0','uHov1','uS'],AT=['aP','aAB','aL','aCol','aPar','aX'];

/* host: {K, post(msg), raf(cb), toDoc(rafTimestamp) -> page time}.  All state arrives as messages (see msg()). */
function PrismLightEngine(canvas,host){
  let gl=null,U={},vbo=null,nV=0,NEVER=1e7,cssW=1,cssH=1,vis=false,lost=false,dv=null;
  const st={on:-1e12,off:-1e12,sw:1e12,lam0:532,v:2,h0:[0,0],h1:[0,0],hT:-1e12};
  const clk={b:0,p:0,k:1,until:Infinity},sim=d=>Math.min(clk.until,clk.b+(d-clk.p)*clk.k);
  function init(){const o={alpha:true,premultipliedAlpha:true,antialias:false,depth:false,stencil:false,preserveDrawingBuffer:false,powerPreference:'low-power'};
    try{gl=canvas.getContext('webgl',o)||canvas.getContext('experimental-webgl',o)}catch(e){gl=null}
    if(!gl)return false;
    const hp=gl.getShaderPrecisionFormat(gl.FRAGMENT_SHADER,gl.HIGH_FLOAT),P=hp&&hp.precision>0?'highp':'mediump';if(P==='mediump')NEVER=6e4;
    const sh=(t,s)=>{const x=gl.createShader(t);gl.shaderSource(x,s);gl.compileShader(x);if(!gl.getShaderParameter(x,gl.COMPILE_STATUS)){console.warn(gl.getShaderInfoLog(x));return null}return x};
    const vs=sh(gl.VERTEX_SHADER,VS),fs=sh(gl.FRAGMENT_SHADER,FS(P,host.K));if(!vs||!fs){gl=null;return false}
    const pr=gl.createProgram();gl.attachShader(pr,vs);gl.attachShader(pr,fs);gl.linkProgram(pr);
    if(!gl.getProgramParameter(pr,gl.LINK_STATUS)){console.warn(gl.getProgramInfoLog(pr));gl=null;return false}
    gl.useProgram(pr);vbo=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vbo);
    AT.forEach((n,i)=>{const l=gl.getAttribLocation(pr,n);gl.enableVertexAttribArray(l);gl.vertexAttribPointer(l,4,gl.FLOAT,false,96,i*16)});
    UN.forEach(n=>U[n]=gl.getUniformLocation(pr,n));
    gl.disable(gl.DEPTH_TEST);gl.enable(gl.BLEND);gl.blendFunc(gl.ONE,gl.ONE);gl.clearColor(0,0,0,0);
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true});
    return true}
  /* the dive: the prism edges ride the portal as colour fringes and the beams fly past the camera.
     Same piecewise-linear scale curve as the page's clip-path keyframes, evaluated on this thread's frame clock. */
  function draw(t){gl.clear(gl.COLOR_BUFFER_BIT);
    let fade=1,cam=1,Z=[0,0],fr=[1,1,1],frA=0;
    if(dv){const k=dv.t0==null?0:Math.min(1,Math.max(0,(t-dv.t0)/dv.dur)),x=k*dv.N,i=Math.min(dv.N-1,Math.floor(x)),s=dv.S[i]+(dv.S[i+1]-dv.S[i])*(x-i),dd=.014*Math.min(1,s/5);
      fade=1-sstep(.15,.55,k);cam=Math.pow(s,.55);Z=dv.Z;fr=[s*(1-dd),s,s*(1+dd)];frA=1-sstep(.62,.95,k)}
    const r=t-st.on;      // event times are sent relative to ignition, so the GPU only ever sees small numbers
    gl.uniform2f(U.uRes,cssW,cssH);gl.uniform2f(U.uZ,Z[0],Z[1]);gl.uniform1f(U.uCam,cam);gl.uniform3f(U.uFr,fr[0],fr[1],fr[2]);
    gl.uniform1f(U.uT,r);gl.uniform1f(U.uV,st.v);gl.uniform1f(U.uOff,Math.min(st.off-st.on,NEVER));gl.uniform1f(U.uSw,Math.min(st.sw-st.on,NEVER));
    gl.uniform1f(U.uLam0,st.lam0);gl.uniform1f(U.uHovT,Math.max(st.hT-st.on,-NEVER));gl.uniform2f(U.uHov0,st.h0[0],st.h0[1]);gl.uniform2f(U.uHov1,st.h1[0],st.h1[1]);
    gl.uniform1f(U.uFade,fade);gl.uniform1f(U.uFrA,frA);if(nV)gl.drawArrays(gl.TRIANGLES,0,nV)}
  /* frame loop: runs only while light is moving; a frozen or unchanged clock draws nothing new */
  let raf=0,alive=-Infinity,last=0,frames=0,slow=0,drawnT=NaN,dirty=true;const pings=[];
  function loop(ts){raf=0;const t=sim(host.toDoc(ts));
    if(vis&&gl&&!lost&&(dirty||t!==drawnT)){draw(t);drawnT=t}
    dirty=false;
    if(pings.length)host.post({t:'pong',ids:pings.splice(0),drawnT,vis});
    if(last){const dt=ts-last;frames++;if(dt>45)slow++;if(frames>=30){if(slow/frames>.25)host.post({t:'jank'});frames=slow=0}}
    last=ts;if(t<alive)raf=host.raf(loop);else last=0}
  const wake=()=>{if(!raf)raf=host.raf(loop)};
  const ok=init();
  return{ok,msg(m){switch(m.t){
    case'size':canvas.width=m.w;canvas.height=m.h;cssW=m.cw;cssH=m.ch;if(gl)gl.viewport(0,0,m.w,m.h);break;
    case'geo':if(gl){gl.bindBuffer(gl.ARRAY_BUFFER,vbo);gl.bufferData(gl.ARRAY_BUFFER,m.verts,gl.STATIC_DRAW);nV=m.verts.length/24;gl.uniform4fv(U.uS,m.S)}break;
    case'st':Object.assign(st,m.st);break;
    case'clock':Object.assign(clk,m.c);break;
    case'dive':dv=m.d;break;
    case'vis':vis=m.on;if(!vis&&gl&&!lost)gl.clear(gl.COLOR_BUFFER_BIT);break;
    case'alive':alive=Math.max(alive,m.until);break;
    case'ping':pings.push(m.id);break;
    default:return}
    dirty=true;wake()}}}

const inWorker=typeof WorkerGlobalScope!=='undefined'&&self instanceof WorkerGlobalScope;
if(inWorker){let eng=null,delta=0;
  self.onmessage=e=>{const m=e.data;
    if(m.t==='init'){delta=performance.timeOrigin-m.docOrigin;     // worker clock -> page clock
      if(typeof self.requestAnimationFrame!=='function'){self.postMessage({t:'ready',ok:false,why:'no requestAnimationFrame in workers'});return}
      eng=PrismLightEngine(m.canvas,{K:m.K,post:x=>self.postMessage(x),raf:cb=>self.requestAnimationFrame(cb),toDoc:ts=>ts+delta});
      self.postMessage({t:'ready',ok:eng.ok,why:eng.ok?'':'no WebGL in workers'});return}
    if(eng&&eng.ok)eng.msg(m)}}
else self.PrismLightEngine=PrismLightEngine;
})();
