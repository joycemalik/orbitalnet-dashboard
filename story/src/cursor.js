// Cursor: a tiny Earth with a handful of micro satellites in orbit around it.
// The satellites trail behind and are pulled back toward the planet, so they swing
// around it as you move. Over a link the orbits tighten and turn orange. A click
// kicks them outward and they fall back in. Fine pointers only, off for reduced motion.
const fine = matchMedia('(pointer: fine)').matches;
const calm = matchMedia('(prefers-reduced-motion: reduce)').matches;

if (fine && !calm) {
  const cv = document.createElement('canvas');
  cv.setAttribute('aria-hidden', 'true');
  cv.style.cssText = 'position:fixed;inset:0;width:100%;height:100%;pointer-events:none;z-index:9999';
  document.body.appendChild(cv);
  const st = document.createElement('style');
  st.textContent = 'html.oc, html.oc * { cursor: none !important; } html.oc input, html.oc textarea { cursor: text !important; }';
  document.head.appendChild(st);
  document.documentElement.classList.add('oc');

  const ctx = cv.getContext('2d');
  let W = 0, H = 0, dpr = 1;
  const size = () => { dpr = Math.min(2, devicePixelRatio || 1); W = innerWidth; H = innerHeight; cv.width = W * dpr; cv.height = H * dpr; ctx.setTransform(dpr, 0, 0, dpr, 0, 0); };
  size(); addEventListener('resize', size);

  const m = { x: W / 2, y: H / 2, seen: false };
  const e = { x: m.x, y: m.y };                    // the planet eases toward the mouse
  let hot = 0, hotT = 0, press = 0;                 // link hover, mouse down
  const N = 6;
  const sats = Array.from({ length: N }, (_, i) => {
    const a = (i / N) * Math.PI * 2, r = 14 + (i % 3) * 5;
    return { x: m.x + Math.cos(a) * r, y: m.y + Math.sin(a) * r, vx: -Math.sin(a) * 1.6, vy: Math.cos(a) * 1.6, r, trail: [] };
  });

  addEventListener('pointermove', ev => {
    m.x = ev.clientX; m.y = ev.clientY;
    if (!m.seen) { m.seen = true; e.x = m.x; e.y = m.y; sats.forEach(s => { s.x += m.x - W / 2; s.y += m.y - H / 2; }); }
    hotT = ev.target.closest?.('a, button, [role="button"], summary, label') ? 1 : 0;
  }, { passive: true });
  document.addEventListener('pointerleave', () => { m.seen = false; });
  addEventListener('pointerdown', () => {
    press = 1;
    // kick: every satellite gets flung outward, then gravity brings it home
    sats.forEach(s => { const dx = s.x - e.x, dy = s.y - e.y, d = Math.hypot(dx, dy) || 1; s.vx += dx / d * 7 - dy / d * 2; s.vy += dy / d * 7 + dx / d * 2; });
  });
  addEventListener('pointerup', () => { press = 0; });

  const ACC = '255,122,47';
  (function tick() {
    requestAnimationFrame(tick);
    ctx.clearRect(0, 0, W, H);
    if (!m.seen) return;
    e.x += (m.x - e.x) * 0.35; e.y += (m.y - e.y) * 0.35;
    hot += (hotT - hot) * 0.15;
    const R = 4 - press * 1.2 + hot * 1.5;          // planet radius

    for (const s of sats) {
      // spring toward the preferred orbit radius, plus a sideways push to keep it circling
      const dx = s.x - e.x, dy = s.y - e.y, d = Math.hypot(dx, dy) || 1;
      const want = s.r * (1 - hot * 0.35);
      const pull = (d - want) * 0.045;
      s.vx += -dx / d * pull - dy / d * 0.09;
      s.vy += -dy / d * pull + dx / d * 0.09;
      s.vx *= 0.9; s.vy *= 0.9;
      s.x += s.vx; s.y += s.vy;
      s.trail.push(s.x, s.y); if (s.trail.length > 16) s.trail.splice(0, 2);
    }

    // faint orbit ring
    ctx.strokeStyle = `rgba(255,255,255,${0.12 + hot * 0.1})`; ctx.lineWidth = 1;
    ctx.setLineDash([1, 4]); ctx.beginPath(); ctx.arc(e.x, e.y, 19 * (1 - hot * 0.35), 0, Math.PI * 2); ctx.stroke(); ctx.setLineDash([]);

    // satellite trails and bodies
    for (const s of sats) {
      const t = s.trail;
      for (let i = 2; i < t.length; i += 2) {
        ctx.strokeStyle = hot > 0.5 ? `rgba(${ACC},${i / t.length * 0.5})` : `rgba(255,255,255,${i / t.length * 0.35})`;
        ctx.beginPath(); ctx.moveTo(t[i - 2], t[i - 1]); ctx.lineTo(t[i], t[i + 1]); ctx.stroke();
      }
      ctx.fillStyle = hot > 0.5 ? `rgb(${ACC})` : '#f2f2f2';
      ctx.fillRect(s.x - 1, s.y - 1, 2, 2);
    }

    // the planet: ink disc with an orange terminator glow
    const g = ctx.createRadialGradient(e.x - R * .4, e.y - R * .4, 0, e.x, e.y, R);
    g.addColorStop(0, '#ffffff'); g.addColorStop(0.7, '#cfd3da'); g.addColorStop(1, `rgb(${ACC})`);
    ctx.fillStyle = g; ctx.beginPath(); ctx.arc(e.x, e.y, R, 0, Math.PI * 2); ctx.fill();
  })();
}
