// UNIVERSAL NAVBAR LOCK – keeps header visible on all pages
(function(){
  const hdr = document.querySelector('.header');
  const nav = document.querySelector('.nav');
  if (!hdr) return;

  // Any class names that cause hiding/folding:
  const BAD = [
    /hidden/i,
    /hide/i,
    /up/i,
    /off/i,
    /compact/i,
    /scrolled/i,
    /collapse/i
  ];

  function stripBad(el) {
    if (!el) return;
    BAD.forEach(rx => {
      for (const c of [...el.classList]) {
        if (rx.test(c)) el.classList.remove(c);
      }
    });
  }

  function hardLock() {
    // Kill inline styles that might hide/move header
    hdr.style.transform = 'none';
    hdr.style.top = '0px';
    hdr.style.opacity = '1';
    hdr.style.visibility = 'visible';
    hdr.removeAttribute('hidden');

    // Remove any bad classes from header/nav
    stripBad(hdr);
    stripBad(nav);

    // Repeat every frame to override nav.js scroll logic
    requestAnimationFrame(hardLock);
  }

  // Start the loop
  hardLock();

  // Also catch style/class changes immediately
  const mo = new MutationObserver(() => {
    stripBad(hdr);
    stripBad(nav);
    hdr.style.transform = 'none';
    hdr.style.opacity = '1';
    hdr.style.visibility = 'visible';
  });

  mo.observe(hdr, { attributes: true, attributeFilter: ['class','style','hidden'] });
  if (nav) mo.observe(nav, { attributes: true, attributeFilter: ['class','style'] });
})();
