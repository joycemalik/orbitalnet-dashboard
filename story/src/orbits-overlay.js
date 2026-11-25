// Thin labelled orbit arcs drawn around the live Earth. Each ring is one piece of the
// work, and later work sits on a higher orbit. The section in view lights its ring.
// Also: the section observer, the scroll ticks, the mobile menu and the numbers.
const NS = 'http://www.w3.org/2000/svg';
const $ = s => document.querySelector(s);
const mk = (tag, a = {}, p) => { const e = document.createElementNS(NS, tag); for (const k in a) e.setAttribute(k, a[k]); p?.appendChild(e); return e; };

const RINGS = [
  { k: 1.32, label: 'AUCTION · NOV 25', ang: -38 },
  { k: 1.62, label: 'LIVE TWIN · APR 26', ang: -58 },
  { k: 1.98, label: 'h₀ PLANNER · OCT 26', ang: -66 },
  { k: 2.42, label: 'FLEET · NOV 26', ang: -73 },
  { k: 2.95, label: 'PAPER · CODE', ang: -79 },
];

export const flight = { node: 0, h0: 0, links: 0, zoom: 0, place };

const svg = $('#arcs');
const defs = mk('defs', {}, svg);
const g = mk('radialGradient', { id: 'coneG', cx: '0', cy: '0.5', r: '1' }, defs);
mk('stop', { offset: '0', 'stop-color': '#ff7a2f', 'stop-opacity': '.55' }, g);
mk('stop', { offset: '1', 'stop-color': '#ff7a2f', 'stop-opacity': '0' }, g);
const root = mk('g', {}, svg);
const rings = RINGS.map((r, i) => {
  const ring = mk('circle', { class: 'ring' + (i % 2 ? ' dash' : '') }, root);
  const cone = mk('path', { class: 'cone' }, root);
  const node = mk('g', { class: 'node' }, root);
  mk('rect', { x: -4, y: -4, width: 8, height: 8, transform: 'rotate(45)' }, node);
  const t = mk('text', { x: 14, y: 4 }, node); t.textContent = r.label;
  return { ...r, ring, cone, node };
});
// the innermost dotted ring hugs the atmosphere
const atmo = mk('circle', { class: 'ring dash' }, root);

let last = '';
function place(cx, cy, R, op = 1) {
  svg.style.opacity = op.toFixed(2);
  const key = `${cx | 0},${cy | 0},${R | 0}`;
  if (key === last) return; last = key;
  atmo.setAttribute('cx', cx); atmo.setAttribute('cy', cy); atmo.setAttribute('r', R * 1.08);
  const H = innerHeight, Y = [0.5, 0.4, 0.3, 0.21, 0.13];
  rings.forEach((r, i) => {
    const rad = R * r.k;
    // put each node where its ring crosses a fixed screen height, so every label stays in view
    let dy = Math.min(rad * 0.98, Math.max(-rad * 0.98, cy - H * Y[i]));
    // never let a label run into the text column on the right
    const maxX = innerWidth * 0.46 - 160, dxNow = Math.sqrt(Math.max(0, rad * rad - dy * dy));
    if (cx + dxNow > maxX && rad > maxX - cx) dy = Math.sqrt(Math.max(0, rad * rad - (maxX - cx) ** 2));
    const a = -Math.asin(Math.min(1, dy / rad));
    r.ring.setAttribute('cx', cx); r.ring.setAttribute('cy', cy); r.ring.setAttribute('r', rad);
    const x = cx + Math.cos(a) * rad, y = cy + Math.sin(a) * rad;
    r.node.setAttribute('transform', `translate(${x} ${y})`);
    // a soft sensing cone from the node down toward the planet
    const spread = 0.07, inner = R * 1.02;
    const p1 = [cx + Math.cos(a - spread) * inner, cy + Math.sin(a - spread) * inner];
    const p2 = [cx + Math.cos(a + spread) * inner, cy + Math.sin(a + spread) * inner];
    r.cone.setAttribute('d', `M${x} ${y} L${p1} L${p2} Z`);
  });
}

function setNode(n) {
  flight.node = n;
  rings.forEach((r, i) => {
    const on = i + 1 === n || (n === 5 && i === 4);
    r.ring.classList.toggle('on', on); r.node.classList.toggle('on', on); r.cone.classList.toggle('on', on && n < 5);
  });
}

/* sections */
const secs = [...document.querySelectorAll('.sec')];
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  e.target.classList.add('in');
  setNode(+e.target.dataset.node);
}), { rootMargin: '-40% 0px -40% 0px' });
secs.forEach(s => io.observe(s));
secs[0].classList.add('in');

/* scroll ticks in the bottom bar */
const ticks = $('#ticks');
const N = 24;
ticks.innerHTML = '<b></b>'.repeat(N) + '<span>SCROLL</span>';
const bars = [...ticks.querySelectorAll('b')];
const onScroll = () => {
  const p = scrollY / Math.max(1, document.documentElement.scrollHeight - innerHeight);
  const k = Math.round(p * N);
  bars.forEach((b, i) => b.classList.toggle('on', i < Math.max(1, k)));
};
addEventListener('scroll', onScroll, { passive: true }); onScroll();

/* mobile menu */
const btn = $('.menu'), nav = $('#nav');
btn?.addEventListener('click', () => { const o = nav.classList.toggle('open'); btn.setAttribute('aria-expanded', o); });

/* numbers from the paper's generated macros */
fetch('/jaa/numbers.json').then(r => r.json()).then(Nm => {
  document.querySelectorAll('[data-n]').forEach(e => { e.textContent = Nm[e.dataset.n] ?? '—'; });
}).catch(() => {});
