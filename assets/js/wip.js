/* NON-CV pages: centered excavator card.
   CV page: tiny bottom popup (no animations, no close button). */
(function () {
  const onCV =
    /\/pages\/cv\.html$/.test(location.pathname) ||
    /(^|\/)cv\.html$/.test(location.pathname);

  if (onCV) {
    // ---- CV PAGE: small fixed pill only ----
    const pill = document.createElement("div");
    pill.className = "wip-pill";
    pill.setAttribute("role", "status");
    pill.setAttribute("aria-live", "polite");
    pill.innerHTML = `
      <span class="wip-emoji">🚧</span>
      <strong>Work in progress</strong>
      <span class="wip-emoji">⚠️</span>
    `;
    document.body.appendChild(pill);
    return;
  }

  // ---- OTHER PAGES: centered glass card with excavator canvas ----
  const main = document.querySelector("main") || document.body;
  const wrap = document.createElement("section");
  wrap.className = "wip-wrap";
  wrap.innerHTML = `
    <article class="wip-card" aria-live="polite">
      <h2 class="wip-title">Work in progress</h2>
      <canvas class="wip-canvas" width="340" height="200"></canvas>
    </article>`;
  main.appendChild(wrap);

  const canvas = wrap.querySelector("canvas");
  const ctx = canvas.getContext("2d");

  // Fit DPI/size
  const BASE_W = 340, BASE_H = 200;
  function fit(){
    const cssW = canvas.clientWidth || canvas.parentElement.getBoundingClientRect().width;
    const cssH = Math.round(cssW * (BASE_H/BASE_W));
    canvas.style.height = cssH + "px";
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr,0,0,dpr,0,0);
    ctx.scale(cssW/BASE_W, cssW/BASE_W);
  }
  new ResizeObserver(fit).observe(canvas); fit();

  // Helpers
  const BLUE="#13348f", Y1="#facc15", Y2="#f59e0b", PURPLE="#6366f1", PURPLE_D="#3f46c5";
  const d2r=d=>d*Math.PI/180;
  function rrect(x,y,w,h,r){const rr=Math.min(r,Math.min(w,h)/2);ctx.beginPath();ctx.moveTo(x+rr,y);ctx.arcTo(x+w,y,x+w,y+h,rr);ctx.arcTo(x+w,y+h,x,y+h,rr);ctx.arcTo(x,y+h,x,y,rr);ctx.arcTo(x,y,x+w,y,rr);ctx.closePath();}
  function stroke(fill,lw=8){ctx.lineWidth=lw;ctx.strokeStyle=BLUE;ctx.lineJoin="round";ctx.lineCap="round";if(fill){ctx.fillStyle=fill;ctx.fill();}ctx.stroke();}
  function grad(x0,y0,x1,y1,c0=Y1,c1=Y2){const g=ctx.createLinearGradient(x0,y0,x1,y1);g.addColorStop(0,c0);g.addColorStop(1,c1);return g;}

  // Geometry
  const TRACK={x:70,y:152,w:200,h:32,r:16}, INNER={x:82,y:160,w:176,h:16,r:8};
  const PLATFORM={x:138,y:136,w:62,h:22,r:11}, BODY={x:112,y:106,w:84,h:34,r:16};
  const CAB={x:192,y:90,w:46,h:34,r:15}, BASE={x:178,y:110};
  const L1=70, L2=56;

  // Arm keyframes
  const KF=[{t:0.0,a1:-28,a2:42,a3:30},{t:0.6,a1:-26,a2:24,a3:12},{t:1.3,a1:-22,a2:18,a3:0},{t:2.0,a1:-25,a2:36,a3:34},{t:2.8,a1:-31,a2:48,a3:42},{t:3.6,a1:-28,a2:42,a3:30}];
  const CYCLE=3.6, ease=t=>t*t*(3-2*t);
  const sampleAngles = sec => {
    const t=sec%CYCLE;
    for(let i=0;i<KF.length-1;i++){
      const a=KF[i], b=KF[i+1];
      if(t>=a.t && t<=b.t){
        const u=ease((t-a.t)/(b.t-a.t));
        return { a1:d2r(a.a1+(b.a1-a.a1)*u),
                 a2:d2r(a.a2+(b.a2-a.a2)*u),
                 a3:d2r(a.a3+(b.a3-a.a3)*u) };
      }
    }
    const z=KF[KF.length-1]; return {a1:d2r(z.a1),a2:d2r(z.a2),a3:d2r(z.a3)};
  };

  const reduceMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
  const T0 = performance.now(); let treadShift=0;

  function draw(now){
    const tg=(now-T0)/1000*0.55, ta=(now-T0)/1000;
    ctx.clearRect(0,0,BASE_W,BASE_H);

    // ground
    ctx.strokeStyle="rgba(120,170,160,.35)"; ctx.lineWidth=3;
    ctx.beginPath(); ctx.moveTo(TRACK.x-6,TRACK.y+12.5); ctx.lineTo(TRACK.x+TRACK.w+6,TRACK.y+12.5); ctx.stroke();

    // tiny bounce
    const pulse=Math.pow((1-Math.cos(tg*1.2))*0.5,3);
    const bounce=reduceMotion?0:1.0*pulse;

    // track
    ctx.save(); ctx.translate(0,bounce);
    rrect(TRACK.x,TRACK.y,TRACK.w,TRACK.h,TRACK.r); stroke(PURPLE,8);
    rrect(INNER.x,INNER.y,INNER.w,INNER.h,INNER.r); ctx.clip();
    ctx.fillStyle=PURPLE_D; ctx.fillRect(INNER.x,INNER.y,INNER.w,INNER.h);
    if(!reduceMotion) treadShift=(tg*24)%12;
    ctx.fillStyle="rgba(255,255,255,.08)";
    for(let x=INNER.x-treadShift; x<INNER.x+INNER.w; x+=12) ctx.fillRect(x,INNER.y,6,INNER.h);
    ctx.restore();

    // platform
    ctx.save(); ctx.translate(0,bounce);
    rrect(PLATFORM.x,PLATFORM.y,PLATFORM.w,PLATFORM.h,PLATFORM.r); stroke(grad(PLATFORM.x,PLATFORM.y,PLATFORM.x+PLATFORM.w,PLATFORM.y+PLATFORM.h),8);
    ctx.restore();

    // body
    ctx.save(); ctx.translate(0,bounce);
    rrect(BODY.x,BODY.y,BODY.w,BODY.h,BODY.r); stroke(grad(BODY.x,BODY.y,BODY.x+BODY.w,BODY.y+BODY.h),8);
    ctx.beginPath(); ctx.moveTo(BODY.x+12,BODY.y-8); ctx.lineTo(BODY.x+12,BODY.y);
    ctx.lineWidth=8; ctx.strokeStyle=BLUE; ctx.lineCap="round"; ctx.stroke();
    ctx.restore();

    // cab
    ctx.save(); ctx.translate(0,bounce);
    rrect(CAB.x,CAB.y,CAB.w,CAB.h,CAB.r); stroke("#0b1020",8);
    const glass=ctx.createLinearGradient(CAB.x+6,CAB.y+6,CAB.x+CAB.w-8,CAB.y+CAB.h-8);
    glass.addColorStop(0,"#a5e3ff"); glass.addColorStop(1,"#6ee7b7");
    rrect(CAB.x+6,CAB.y+6,CAB.w-12,CAB.h-12,10); ctx.fillStyle=glass; ctx.fill();
    ctx.lineWidth=4; ctx.strokeStyle=BLUE; ctx.stroke();
    ctx.restore();

    // arm
    const {a1,a2,a3}=sampleAngles(ta);
    const baseX=BASE.x, baseY=BASE.y+bounce;

    ctx.save(); ctx.translate(baseX,baseY); ctx.rotate(a1);
    rrect(0,-8,L1,16,8); stroke(grad(0,-8,L1,8),8);
    ctx.beginPath(); ctx.arc(0,0,6,0,Math.PI*2); ctx.fillStyle=BLUE; ctx.fill();
    ctx.restore();

    const sx=baseX+Math.cos(a1)*L1, sy=baseY+Math.sin(a1)*L1;
    ctx.save(); ctx.translate(sx,sy); ctx.rotate(a2);
    rrect(0,-7,L2,14,7); stroke(grad(0,-7,L2,7),8);
    ctx.beginPath(); ctx.arc(0,0,6,0,Math.PI*2); ctx.fillStyle=BLUE; ctx.fill();

    ctx.save(); ctx.translate(L2,0); ctx.rotate(a3);
    ctx.beginPath(); ctx.moveTo(0,-2); ctx.lineTo(16,-7); ctx.quadraticCurveTo(26,-3,22,10); ctx.lineTo(3,8); ctx.closePath();
    stroke("#fbbf24",8);
    ctx.restore(); ctx.restore();

    requestAnimationFrame(draw);
  }
  if (!reduceMotion) requestAnimationFrame(draw); else draw(performance.now());
})();
