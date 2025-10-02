/*
  Vertical side waves (SVG). 4–5 layers per side, blue→green palette,
  seeded randomness so shapes stay consistent across pages in one session.
  No external libraries.
*/
(function(){
  function mulberry32(a){ return function(){ var t = a += 0x6D2B79F5; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; } }
  function getSeed(){
    let s = sessionStorage.getItem("rgxWaveSeed");
    if(!s){ s = String(Math.floor(Math.random()*1e9)); sessionStorage.setItem("rgxWaveSeed", s); }
    return +s;
  }
  let rand = mulberry32(getSeed());

  const state = {
    layers: (innerWidth < 640 ? 4 : 5),
    left: null,
    right: null,
    lastW: 0,
    lastH: 0,
    rafId: 0
  };

  const palette = ["#1d4ed8","#0ea5e9","#06b6d4","#10b981","#22c55e"];

  const root = document.getElementById("bg");
  const left = makeSide("left");
  const right = makeSide("right");
  state.left = left; state.right = right;
  root.append(left.el, right.el);

  function makeSide(side){
    const el = document.createElementNS("http://www.w3.org/2000/svg","svg");
    el.classList.add("bg-side", side);
    el.setAttribute("preserveAspectRatio","none");
    const defs = document.createElementNS(el.namespaceURI, "defs");
    el.appendChild(defs);

    for(let i=0;i<state.layers;i++){
      const blur = document.createElementNS(el.namespaceURI,"filter");
      blur.setAttribute("id",`${side}-blur-${i}`);
      const fe = document.createElementNS(el.namespaceURI,"feGaussianBlur");
      fe.setAttribute("in","SourceGraphic");
      fe.setAttribute("stdDeviation", String(2 + (state.layers-i)*0.9));
      blur.appendChild(fe);
      defs.appendChild(blur);
    }

    const paths = [];
    for(let i=0;i<state.layers;i++){
      const p = document.createElementNS(el.namespaceURI,"path");
      p.setAttribute("fill", palette[i]);
      p.setAttribute("fill-opacity", String(0.65 - i*0.1));
      p.setAttribute("filter", `url(#${side}-blur-${i})`);
      el.appendChild(p);

      const r = () => rand();
      paths.push({
        p,
        baseFrac: 0.12 + i*0.05,
        ampFrac:  0.035 + i*0.013,
        speed:    0.25 + r()*0.5,
        phase:    r()*Math.PI*2,
        phase2:   r()*Math.PI*2,
        freq:     0.004 + r()*0.003,
        freq2:    0.006 + r()*0.004
      });
    }
    return { el, paths, side };
  }

  function resize(){
    const vw = Math.max(320, window.innerWidth);
    const vh = Math.max(320, window.innerHeight);
    if(vw === state.lastW && vh === state.lastH) return;
    state.lastW = vw; state.lastH = vh;

    const sideW = Math.min(Math.max(vw*0.40, 260), 560);
    [state.left, state.right].forEach(s=>{
      s.el.setAttribute("viewBox", `0 0 ${sideW} ${vh}`);
      s.el.setAttribute("width", sideW);
      s.el.setAttribute("height", vh);
      if(s.side === "left") { s.el.style.left = "0px"; s.el.style.right = ""; }
      else { s.el.style.right = "0px"; s.el.style.left = ""; }
    });
  }

  function draw(t){
    const W = +state.left.el.getAttribute("width");
    const H = +state.left.el.getAttribute("height");
    const steps = Math.max(16, Math.round(H/48));

    [state.left, state.right].forEach(side=>{
      for(const L of side.paths){
        const { p, baseFrac, ampFrac, speed, phase, phase2, freq, freq2 } = L;
        let d = "";
        if(side.side === "left"){
          d += `M 0 0 L ${baseFrac*W} 0 `;
          for(let s=0; s<=steps; s++){
            const y = s/steps*H;
            const s1 = Math.sin(y*freq + phase + t*speed);
            const s2 = Math.sin(y*freq2 + phase2 - t*speed*0.7);
            const off = baseFrac*W + ampFrac*W*(0.6*s1 + 0.4*s2);
            d += `L ${off.toFixed(1)} ${y.toFixed(1)} `;
          }
          d += `L 0 ${H} Z`;
        }else{
          d += `M ${W} 0 L ${(W - baseFrac*W)} 0 `;
          for(let s=0; s<=steps; s++){
            const y = s/steps*H;
            const s1 = Math.sin(y*freq + phase + t*speed*1.02);
            const s2 = Math.sin(y*freq2 + phase2 + t*speed*0.66);
            const off = W - (baseFrac*W + ampFrac*W*(0.6*s1 + 0.4*s2));
            d += `L ${off.toFixed(1)} ${y.toFixed(1)} `;
          }
          d += `L ${W} ${H} Z`;
        }
        p.setAttribute("d", d.trim());
      }
    });
  }

  function loop(now){
    draw(now/1000);
    requestAnimationFrame(loop);
  }

  window.addEventListener("resize", resize, {passive:true});
  resize();
  loop(performance.now());
})();
