/* Minimal → Alive nav: active underline via CSS, hover blob with smooth easing
   and live measurement so first-hover is accurate. */
(function () {
  const header = document.querySelector(".header");
  const nav = document.querySelector(".nav");
  const menu = document.querySelector(".menu");
  const links = Array.from(document.querySelectorAll(".menu a"));
  const blob = document.getElementById("hover-blob");
  const toggle = document.querySelector(".nav-toggle");

  // Mark current page active (underline via CSS ::after)
  const path = location.pathname.split("/").pop() || "index.html";
  (links.find(a => a.getAttribute("href").split("/").pop() === path) || links[0])
    .classList.add("active");

  // Keep header awake while pointer is around the bar
  let sleepTimer = null;
  function awaken() { clearTimeout(sleepTimer); header.classList.add("awake"); }
  function sleep()  { sleepTimer = setTimeout(() => header.classList.remove("awake"), 120); }
  header.addEventListener("pointerenter", awaken);
  header.addEventListener("pointerleave", sleep);

  // Which link is currently hovered
  let hoverEl = null;
  links.forEach(a => {
    a.addEventListener("mouseenter", () => { hoverEl = a; awaken(); });
    a.addEventListener("mouseleave", () => { hoverEl = null; sleep(); });
  });

  // ---- Blob animation (springy easing + live box measure) ----
  // target values (continuously updated from DOM)
  const target = { x: 0, y: 0, w: 0, vis: 0 };
  // animated state values
  const state  = { x: 0, y: 0, w: 0, vis: 0, vx: 0, vy: 0, vw: 0, vv: 0 };

  // spring params: tweak for snappiness
  const K = 0.25;      // stiffness
  const D = 0.70;      // damping

  function loop() {
    // live measure (includes hover scale/padding)
    if (hoverEl) {
      const r = hoverEl.getBoundingClientRect();
      const p = menu.getBoundingClientRect();
      target.x = r.left - p.left + r.width / 2;
      target.y = r.top  - p.top  + r.height / 2;
      target.w = r.width;
      target.vis = 1; // visible while hovering
    } else {
      target.vis = 0; // fade out when not hovering
    }

    // critically-damped spring-ish easing
    state.vx += (target.x - state.x) * K; state.vx *= D; state.x += state.vx;
    state.vy += (target.y - state.y) * K; state.vy *= D; state.y += state.vy;
    state.vw += (target.w - state.w) * K; state.vw *= D; state.w += state.vw;
    state.vv += ((target.vis ? 0.65 : 0) - state.vis) * 0.20; state.vv *= 0.75; state.vis += state.vv;

    // apply
    const scale = Math.max(state.w / 110, 0.6);
    blob.style.transform =
      `translate(${state.x}px, ${state.y}px) translate(-50%, -50%) scale(${scale})`;
    blob.style.opacity = String(state.vis);

    requestAnimationFrame(loop);
  }
  loop();

  // subtle scroll styling
  function onScroll() { header.classList.toggle("scrolled", window.scrollY > 6); }
  onScroll(); window.addEventListener("scroll", onScroll, { passive: true });

  // mobile toggle
  toggle?.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
    if (open) awaken(); else sleep();
  });
})();
