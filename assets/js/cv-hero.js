// Smooth hero morph without popup:
// - Avatar slides next to the name then gracefully fades out
// - Final state: Name + small meta chips, centered under navbar
// - Exact docking uses a sentinel that never transforms

(function(){
  const anchor = document.querySelector('.cv-hero-anchor');
  const stick  = document.querySelector('.cv-hero-stick');
  const rail   = document.querySelector('.cv-hero-rail');
  const avatar = document.querySelector('.cv-avatar');
  const titles = document.querySelector('.cv-titles');
  const nameEl = document.querySelector('.cv-name');
  const subEl  = document.querySelector('.cv-sub');
  const metaEl = document.querySelector('.cv-meta');
  if (!anchor || !stick || !rail || !avatar || !titles || !nameEl || !subEl || !metaEl) return;

  // Spacer to preserve flow height when stick becomes fixed
  let spacer = stick.nextElementSibling;
  if (!spacer || !spacer.classList.contains('cv-hero-spacer')) {
    spacer = document.createElement('div');
    spacer.className = 'cv-hero-spacer';
    stick.insertAdjacentElement('afterend', spacer);
  }

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const NAV_H = parseInt(getComputedStyle(document.documentElement).getPropertyValue('--nav-height')) || 72;

  // Morph distance after the anchor hits the nav (px)
  let RANGE = 360;            // increase for slower/longer morph
  const LERP = 0.16;          // smoothing lag

  // Live geometry
  let avatarW = 160;
  let gap = 16;
  let stickHeight = 0;

  function measure(){
    avatarW = avatar.getBoundingClientRect().width || avatarW;
    const gv = getComputedStyle(rail).getPropertyValue('--gap').trim();
    gap = parseFloat(gv) || 16;
    stickHeight = stick.getBoundingClientRect().height || stickHeight;
  }

  // target progress from anchor position
  let target = 0, s = 0;
  let docked = false, anchorTop = 0;

  function computeTarget(){
    anchorTop = anchor.getBoundingClientRect().top;
    const passed = (NAV_H - anchorTop);   // >0 once anchor reaches nav
    target = Math.min(1, Math.max(0, passed / RANGE));
  }

  // cubic easing for fades
  const ease = t => t*t*(3-2*t);

  function apply(progress){
    // "effective" avatar width shrinks as it fades out, so the name ends centered by itself
    const fadeOut = ease(Math.min(1, progress * 1.15));    // fade a bit faster than morph
    const effAvatarW = avatarW * (1 - fadeOut);            // 1->0 across the morph

    // 1) Slide name block to where the avatar would be (diminishing as avatar disappears)
    const endX  = (effAvatarW * 0.5) + gap;                // when avatar gone => just 'gap'
    const tx    = endX * progress;

    // 2) Vertical alignment: line the NAME's center with avatar center early on,
    //    but taper to zero as the avatar disappears so the final is perfectly centered horizontally.
    const ar = avatar.getBoundingClientRect();
    const nr = nameEl.getBoundingClientRect();
    const aCenter = ar.top + ar.height / 2;
    const nCenter = nr.top + nr.height / 2;
    const deltaY  = aCenter - nCenter;
    const ty      = (deltaY * (1 - fadeOut)) * progress;

    titles.style.transform = `translate(${tx}px, ${ty}px)`;
    titles.style.willChange = 'transform';

    // 3) Keep the whole group centered while titles slide
    rail.style.setProperty('--txc', `${-tx/2}px`);

    // 4) Avatar fade + shrink
    rail.style.setProperty('--avatarAlpha', String(1 - fadeOut)); // 1 -> 0
    // (scale is already driven by --avatarScale in CSS)

    // 5) Text fades: subtitle goes out quickly; meta stays
    const subFade = Math.max(0, 1 - progress * 2.0); // gone by ~p=0.5
    subEl.style.opacity = subFade.toFixed(3);

    // 6) global scale/gap
    rail.style.setProperty('--p', progress.toFixed(4));
  }

  // RAF loop
  function loop(){
    s += (target - s) * LERP;
    if (reduce) s = target;
    apply(s);

    // Docking toggles fixed position exactly when the anchor hits the nav
    if (!docked && anchorTop <= NAV_H + 0.5){
      docked = true;
      stick.classList.add('docked');
      spacer.style.height = `${stickHeight}px`;
    } else if (docked && anchorTop > NAV_H + 0.5){
      docked = false;
      stick.classList.remove('docked');
      spacer.style.height = '0px';
    }
    requestAnimationFrame(loop);
  }

  // Listeners
  function onScroll(){ computeTarget(); }
  const io = new IntersectionObserver(() => computeTarget(), { root: null, threshold: [0, 1] });
  io.observe(anchor);

  window.addEventListener('resize', () => { measure(); computeTarget(); }, { passive:true });
  window.addEventListener('scroll', onScroll, { passive:true });

  // Init
  measure();
  computeTarget();
  loop();
})();
