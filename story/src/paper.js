// The JAA paper page. Every number comes from /jaa/numbers.json, which
// scripts/jaa_assets.py builds from research/papers/jaa/generated/*.tex.


/* sections drift in as they arrive */
const rv = new IntersectionObserver(es => es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); rv.unobserve(e.target); } }), { threshold: .12 });
document.querySelectorAll('.block, .tiles').forEach(el => { el.classList.add('reveal'); rv.observe(el); });

const N = await fetch('/jaa/numbers.json').then(r => r.json());
const num = k => N[k] ?? '—';

/* fill numbers, with a count-up on the big tiles */
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
function countUp(el, text) {
  const m = text.match(/^(\d+(?:\.\d+)?)(.*)$/);
  if (!m || reduce) { el.textContent = text; return; }
  const end = +m[1], dec = (m[1].split('.')[1] || '').length, rest = m[2];
  const t0 = performance.now();
  const step = t => {
    const p = Math.min(1, (t - t0) / 1100), e = 1 - (1 - p) ** 3;
    el.textContent = (end * e).toFixed(dec) + rest;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}
const io = new IntersectionObserver(es => es.forEach(e => {
  if (!e.isIntersecting) return;
  io.unobserve(e.target);
  countUp(e.target, num(e.target.dataset.n));
}));
document.querySelectorAll('[data-n]').forEach(el => {
  if (el.closest('.tile') && el.tagName === 'B') io.observe(el); else el.textContent = num(el.dataset.n);
});
document.querySelectorAll('.tile b span[data-n]').forEach(el => io.observe(el));

/* ---- 01 toy: closed world collapses, open world moves mass to h0 (illustrative) ---- */
{
  const like = [[.20, .08, .06, .05], [.22, .07, .05, .06], [.18, .09, .07, .05], [.21, .06, .06, .04], [.19, .08, .05, .05], [.2, .07, .06, .05]];
  const LH0 = .35, labels = ['A', 'B', 'C', 'D', 'h₀'];
  const box = document.getElementById('toyBars');
  box.innerHTML = labels.map((l, i) => `<div class="col"><div class="pair"><i class="closed" style="height:0"></i><i class="open" style="height:0"></i></div><span${i === 4 ? ' class="h0"' : ''}>${l}</span></div>`).join('');
  const draw = n => {
    let c = [.25, .25, .25, .25, 0], o = [.225, .225, .225, .225, .1];
    for (let s = 0; s < n; s++) {
      c = c.map((v, i) => i < 4 ? v * like[s][i] : 0); const cs = c.reduce((a, b) => a + b); c = c.map(v => v / cs);
      o = o.map((v, i) => v * (i < 4 ? like[s][i] : LH0)); const os = o.reduce((a, b) => a + b); o = o.map(v => v / os);
    }
    box.querySelectorAll('.col').forEach((col, i) => {
      col.querySelector('.closed').style.height = (c[i] * 100) + '%';
      col.querySelector('.open').style.height = (o[i] * 100) + '%';
    });
    document.getElementById('toyN').textContent = n;
  };
  const sl = document.getElementById('toy');
  sl.addEventListener('input', () => draw(+sl.value));
  draw(0);
  if (!reduce) { // play once when it scrolls into view
    const o2 = new IntersectionObserver(([e]) => {
      if (!e.isIntersecting) return; o2.disconnect();
      let n = 0; const id = setInterval(() => { sl.value = ++n; draw(n); if (n >= 6) clearInterval(id); }, 550);
    }, { threshold: .6 });
    o2.observe(box);
  }
}

/* ---- 02 ROC, from the simulation analysis file ---- */
{
  const roc = await fetch('/jaa/roc_sim.json').then(r => r.json());
  const svg = document.getElementById('roc'), W = 420, H = 380, L = 48, R = 14, T = 14, B = 44;
  const x = v => L + v * (W - L - R), y = v => H - B - v * (H - T - B);
  const S = [['P_p_h0', 'P · P(h₀)', 'var(--c-open)', 2.6], ['B3_entropy', 'B3 · entropy', 'var(--c-closed)', 1.6], ['B2_entropy', 'B2 · entropy', 'var(--c-third)', 1.4]];
  let g = '';
  for (let t = 0; t <= 1.001; t += .25) g += `<line x1="${x(t)}" x2="${x(t)}" y1="${T}" y2="${H - B}" class="gl"/><line y1="${y(t)}" y2="${y(t)}" x1="${L}" x2="${W - R}" class="gl"/><text x="${x(t)}" y="${H - B + 16}" class="tk" text-anchor="middle">${t}</text><text x="${L - 8}" y="${y(t) + 4}" class="tk" text-anchor="end">${t}</text>`;
  g += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" class="diag"/><line x1="${x(.05)}" x2="${x(.05)}" y1="${T}" y2="${H - B}" class="mark"/>`;
  g += `<text x="${(L + W - R) / 2}" y="${H - 6}" class="ax" text-anchor="middle">false alarms on known events</text><text transform="translate(12 ${(T + H - B) / 2}) rotate(-90)" class="ax" text-anchor="middle">unknowns caught</text>`;
  for (const [k, , c, w] of S) {
    const d = roc[k].map(([a, b], i) => `${i ? 'L' : 'M'}${x(a).toFixed(1)} ${y(b).toFixed(1)}`).join('');
    g += `<path d="${d}" fill="none" stroke="${c}" stroke-width="${w}" class="curve"/>`;
  }
  g += `<g id="cross" style="display:none"><line id="cx" class="cross" y1="${T}" y2="${H - B}"/>${S.map((s, i) => `<circle id="dot${i}" r="4" fill="${s[2]}"/>`).join('')}</g><rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" id="hit"/>`;
  svg.innerHTML = g;
  const at = (k, f) => { let best = 0; for (const [a, b] of roc[k]) if (a <= f) best = Math.max(best, b); return best; };
  const read = document.getElementById('rocRead'), cross = svg.querySelector('#cross');
  const show = f => {
    cross.style.display = ''; svg.querySelector('#cx').setAttribute('x1', x(f)); svg.querySelector('#cx').setAttribute('x2', x(f));
    read.innerHTML = `At <b>${(f * 100).toFixed(1)}%</b> false alarms: ` + S.map(([k, lab, c], i) => {
      const v = at(k, f); const dt = svg.querySelector('#dot' + i); dt.setAttribute('cx', x(f)); dt.setAttribute('cy', y(v));
      return `<span style="color:${c}">${lab} ${(v * 100).toFixed(0)}%</span>`;
    }).join(' · ');
  };
  svg.querySelector('#hit').addEventListener('pointermove', e => {
    const r = svg.getBoundingClientRect(); const px = (e.clientX - r.left) / r.width * W;
    show(Math.max(0, Math.min(1, (px - L) / (W - L - R))));
  });
  show(.05);
}

/* ---- 04 fleet bars ---- */
{
  const rows = [['Ideal links (oracle)', 'FleetAccO'], ['No links, each alone', 'FleetAccG'], ['Auction, links ≤ 5000 km', 'FleetAccA'], ['Knowledge only, ≤ 5000 km', 'FleetAccK'], ['Auction, links ≤ 1000 km', 'FleetAccAOne'], ['Spread planes (oracle)', 'FleetBAccOSparse'], ['One dense plane (oracle)', 'FleetBAccODense']];
  const el = document.getElementById('fleet');
  el.innerHTML = rows.map(([l, k]) => { const v = parseFloat(num(k)); return `<div class="hb" title="${l}: ${num(k)}"><span class="l">${l}</span><span class="track"><i data-w="${v}"></i></span><span class="v">${num(k)}</span></div>`; }).join('');
  const o3 = new IntersectionObserver(([e]) => { if (e.isIntersecting) { o3.disconnect(); el.querySelectorAll('i').forEach(i => i.style.width = i.dataset.w + '%'); } });
  o3.observe(el);
}

/* ---- 05 verdicts ---- */
{
  const V = [
    ['Simulation', 'H1', 'P identifies known events fastest', 'SimHOneVerdict'],
    ['Simulation', 'H2', 'Urgency matters more for fast events', 'SimHTwoVerdict'],
    ['Simulation', 'H3', '“None of the above” finds new types', 'SimHThreeVerdict'],
    ['Real ZTF', 'H1', 'Fewer confident errors on unknowns', 'RealCHOneVerdict'],
    ['Real ZTF', 'H2', 'Unknowns rank above supernovae', 'RealCHTwoVerdict'],
    ['Real ZTF', 'H3', 'No more confident errors on supernovae', 'RealCHThreeVerdict'],
    ['Real ZTF', 'H4', 'Colour helps', 'RealCHFourVerdict'],
    ['Real ZTF', 'H5', 'Supernova accuracy within 5 points', 'RealCHFiveVerdict'],
    ['Guarantee', 'HC1', 'False alarms within 10%', 'ConfHCOneVerdict'],
    ['Guarantee', 'HC2', 'More accurate than closed-world', 'ConfHCTwoVerdict'],
    ['Guarantee', 'HC3', 'No more confident errors', 'ConfHCThreeVerdict'],
    ['Guarantee', 'HC4', 'Fewer confident errors on unknowns', 'ConfHCFourVerdict'],
    ['Guarantee', 'HC5', 'Flags real unknowns', 'ConfHCFiveVerdict'],
    ['Guarantee', 'HC6', 'Lookahead ranks unknowns better', 'ConfHCSixVerdict'],
    ['Guarantee', 'HR1', 'False alarms within 10% on real supernovae', 'EHROneVerdict'],
    ['Guarantee', 'HR2', 'Catches real unknowns', 'EHRTwoVerdict'],
    ['Fleet', 'H4.1', 'Ideal links beat no links', 'FleetHFourOneVerdict'],
    ['Fleet', 'H4.2', 'Realistic links beat no links', 'FleetHFourTwoVerdict'],
    ['Fleet', 'H4.3', 'Ideal links beat realistic links', 'FleetHFourThreeVerdict'],
    ['Fleet', 'H4.4', 'Coordinating plans adds little', 'FleetHFourFourVerdict'],
    ['Fleet', 'HE1', 'Few false alarms per spacecraft', 'FleetHEOneVerdict'],
    ['Fleet', 'HE2', 'Few false alarms when combined', 'FleetHETwoVerdict'],
    ['Fleet', 'B1', 'Realistic links help at equal spending', 'FleetBOneVerdict'],
    ['Fleet', 'B2', 'Coordinating plans adds little', 'FleetBTwoVerdict'],
    ['Fleet', 'B3', 'When to spend matters', 'FleetBThreeVerdict'],
    ['Fleet', 'B4', 'A spread fleet beats one plane', 'FleetBFourVerdict'],
    ['Fleet', 'B5', 'It measures at more distinct times', 'FleetBFiveVerdict'],
  ];
  document.getElementById('verdicts').innerHTML = `<div class="vrow head"><span>Study</span><span>Prediction, in plain words</span><span>Outcome</span></div>` +
    V.filter(v => N[v[3]]).map(([s, id, t, k]) => { const ok = num(k) === 'pass'; return `<div class="vrow"><span class="st">${s} · ${id}</span><span>${t}</span><span class="pill ${ok ? 'ok' : 'no'}">${ok ? 'held' : 'failed'}</span></div>`; }).join('');
}

/* mobile menu */
const mb = document.querySelector('.menu'), nv = document.getElementById('nav');
mb?.addEventListener('click', () => { const o = nv.classList.toggle('open'); mb.setAttribute('aria-expanded', o); });
