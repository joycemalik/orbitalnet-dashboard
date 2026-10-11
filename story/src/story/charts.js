// 2D figures that sit inside the chapter cards.
import { mulberry } from '../scene/stars.js';

export const COL = { kn: '#ff7a59', grb: '#7ab8ff', flare: '#ffd166', tde: '#c79bff', h0: '#f4f6fb', faint: '#646d82', rule: '#1d2233', ember: '#ffb766' };

export function sizeCanvas(c, dpr) {
  c._h = c._h || +c.getAttribute('height');
  const w = c.clientWidth || 460;
  c.width = w * dpr; c.height = c._h * dpr; c.style.height = c._h + 'px'; c._w = w; c._dpr = dpr;
}

/* ---- II: every flash is a clock. Log time (minutes), brightness relative to peak ---- */
export const FADE = [
  { c: COL.flare, L: t => t < 2 ? t / 2 : Math.exp(-(t - 2) / 12) },
  { c: COL.grb, L: t => Math.min(1, t / 3) * Math.min(1, Math.pow(Math.max(t, 3) / 3, -1.2)) },
  { c: COL.kn, L: t => { const x = Math.log(t / 1440); return Math.exp(-x * x / (2 * (x < 0 ? 1.0 : 0.75) ** 2)); } },
  { c: COL.tde, L: t => { const p = 43200; return t < p ? Math.exp(-(Math.log(t / p) ** 2) / (2 * 0.8 ** 2)) : Math.pow(t / p, -5 / 3); } },
];
export function drawFade(c, prog) {
  const g = c.getContext('2d'), w = c._w, h = c._h; g.setTransform(c._dpr, 0, 0, c._dpr, 0, 0); g.clearRect(0, 0, w, h);
  const L = 34, R = 8, T = 10, B = 26, X = lx => L + (lx / 5.72) * (w - L - R), Y = ly => T + (-ly / 3) * (h - T - B);
  g.font = '10px "IBM Plex Mono",monospace'; g.fillStyle = COL.faint; g.strokeStyle = COL.rule; g.lineWidth = 1;
  [[0, '1 min'], [1.778, '1 hr'], [3.158, '1 day'], [4.636, '1 mo'], [5.72, '1 yr']].forEach(([v, l], i) => {
    g.beginPath(); g.moveTo(X(v), T); g.lineTo(X(v), h - B); g.stroke();
    g.textAlign = i === 0 ? 'left' : i === 4 ? 'right' : 'center'; g.fillText(l, X(v), h - 8);
  });
  g.textAlign = 'right';[[0, 'peak'], [-1, '10%'], [-2, '1%'], [-3, '0.1%']].forEach(([v, l]) => g.fillText(l, L - 5, Y(v) + 3));
  const upTo = 5.72 * prog;
  FADE.forEach(fd => {
    g.strokeStyle = fd.c; g.lineWidth = 1.8; g.beginPath(); let st = false;
    for (let lx = 0; lx <= upTo; lx += 0.02) {
      const ly = Math.log10(Math.max(fd.L(Math.pow(10, lx)), 1e-4)); if (ly < -3) { st = false; continue; }
      if (!st) { g.moveTo(X(lx), Y(ly)); st = true; } else g.lineTo(X(lx), Y(ly));
    }
    g.stroke();
  });
  g.strokeStyle = 'rgba(255,183,102,.6)'; g.setLineDash([3, 4]); g.beginPath(); g.moveTo(X(upTo), T); g.lineTo(X(upTo), h - B); g.stroke(); g.setLineDash([]);
}

/* ---- VI & VII: a live Bayesian sketch. Magnitudes relative to detection at t=0.5 h (bigger = fainter) ---- */
export const HYP = [
  { n: 'Kilonova', c: COL.kn, m: t => 0.045 * (t - 0.5) - 0.5 * (1 - Math.exp(-(t - 0.5) / 4)) },
  { n: 'GRB afterglow', c: COL.grb, m: t => 3.0 * Math.log10(t / 0.5) },
  { n: 'M-dwarf flare', c: COL.flare, m: t => Math.min(7, 1.0857 * (t - 0.5) / 0.4) },
  { n: 'Tidal disruption', c: COL.tde, m: t => -0.4 * (1 - Math.exp(-(t - 0.5) / 20)) + 0.004 * (t - 0.5) },
];
export const SIG = 0.15; const H0_DENS = 0.1, PRIOR = [0.225, 0.225, 0.225, 0.225, 0.1];
const weirdTruth = t => 0.03 * (t - 0.5) - 0.35 * (1 - Math.exp(-(t - 0.5) / 5)) - 1.3 * Math.exp(-(((t - 26) / 6) ** 2));

function buildRun(truth, seed, nMax, stopWhenSure) {
  const r = mulberry(seed);
  const gauss = () => { let u = 0; while (!u) u = r(); return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r()); };
  // posts[i] = belief after i observations; nexts[i] = time of observation i+1; modes: 0 follow-up, 1 planner, 2 explore
  const obs = [], posts = [], nexts = [], modes = [];
  const logp = PRIOR.map(Math.log);
  const post = () => { const m = Math.max(...logp); const e = logp.map(x => Math.exp(x - m)); const s = e.reduce((a, b) => a + b); return e.map(x => x / s); };
  const add = t => {
    const y = truth(t) + SIG * gauss(); obs.push([t, y]);
    HYP.forEach((hh, i) => { const d = y - hh.m(t); logp[i] += -0.5 * d * d / (SIG * SIG) - Math.log(SIG * Math.sqrt(2 * Math.PI)); });
    logp[4] += Math.log(H0_DENS);
  };
  for (const t of [0.5, 0.8, 1.2]) { posts.push(post()); nexts.push(t); modes.push(0); add(t); }
  for (let n = 0; n < nMax; n++) {
    const p = post(); posts.push(p);
    if (stopWhenSure && Math.max(...p.slice(0, 4)) > 0.995) break;
    const tl = obs[obs.length - 1][0];
    let best = tl + 3, bs = -1; const explore = p[4] > 0.5;
    if (!explore) {
      const sk = 1 - p[4];
      for (let t = tl + 0.5; t <= 72; t += 0.5) {
        let mean = 0; HYP.forEach((hh, i) => (mean += p[i] / sk * hh.m(t)));
        let v = 0; HYP.forEach((hh, i) => { const d = hh.m(t) - mean; v += p[i] / sk * d * d; });
        // Gaussian information gain, discounted because the source is fading
        const eig = 0.5 * Math.log(1 + v / (SIG * SIG)) * Math.exp(-(t - tl) / 14);
        if (eig > bs) { bs = eig; best = t; }
      }
      if (bs < 1e-3) best = tl + 6;
    }
    if (best > 72) break;
    nexts.push(best); modes.push(explore ? 2 : 1); add(best);
  }
  if (posts.length === obs.length) posts.push(post());
  return { obs, posts, nexts, modes };
}
export const RUN_KNOWN = buildRun(t => HYP[0].m(t), 42, 6, true);
export const RUN_UNKNOWN = buildRun(weirdTruth, 7, 10, false);

export function beliefRows(el) {
  el.innerHTML = [...HYP.map(h => [h.n, h.c]), ['h₀ · unknown', COL.h0]]
    .map(([n, c]) => `<div class="row"><span>${n}</span><div class="bar"><i style="background:${c}"></i></div><span>—</span></div>`).join('');
}
function setBeliefs(el, p) {
  [...el.children].forEach((row, i) => {
    row.querySelector('i').style.width = (p[i] * 100).toFixed(1) + '%';
    row.lastElementChild.textContent = (p[i] * 100).toFixed(p[i] < 0.1 ? 1 : 0) + '%';
  });
}
// returns how many observations are shown, so the 3D scene can fire a beam on each new one
export function drawDx(c, run, prog, belEl) {
  const g = c.getContext('2d'), w = c._w, h = c._h; g.setTransform(c._dpr, 0, 0, c._dpr, 0, 0); g.clearRect(0, 0, w, h);
  const L = 50, R = 8, T = 10, B = 24, X = t => L + t / 72 * (w - L - R), Y = m => T + (m + 1.5) / 7.5 * (h - T - B);
  g.font = '10px "IBM Plex Mono",monospace'; g.strokeStyle = COL.rule; g.fillStyle = COL.faint; g.lineWidth = 1;
  [0, 12, 24, 36, 48, 60, 72].forEach((t, i) => {
    g.beginPath(); g.moveTo(X(t), T); g.lineTo(X(t), h - B); g.stroke();
    g.textAlign = i === 0 ? 'left' : i === 6 ? 'right' : 'center'; g.fillText(t + ' h', X(t), h - 8);
  });
  g.textAlign = 'right';[[-1, 'bright'], [0, '0'], [2, '+2'], [4, '+4'], [6, '+6 mag']].forEach(([m, l]) => g.fillText(l, L - 4, Y(m) + 3));
  const nShown = Math.min(run.obs.length, Math.floor(prog * 1.2 * (run.obs.length + 1)));
  const p = run.posts[nShown];
  setBeliefs(belEl, p);
  HYP.forEach((hh, i) => {
    g.strokeStyle = hh.c; g.globalAlpha = 0.15 + 0.85 * p[i]; g.lineWidth = 1.2 + 1.6 * p[i]; g.beginPath();
    for (let t = 0.5; t <= 72; t += 0.5) { const m = hh.m(t); if (m > 6) break; t === 0.5 ? g.moveTo(X(t), Y(m)) : g.lineTo(X(t), Y(m)); }
    g.stroke();
  });
  g.globalAlpha = 1; g.fillStyle = COL.h0; g.strokeStyle = 'rgba(244,246,251,.5)';
  run.obs.slice(0, nShown).forEach(([t, y]) => {
    g.beginPath(); g.moveTo(X(t), Y(y - SIG)); g.lineTo(X(t), Y(y + SIG)); g.stroke();
    g.beginPath(); g.arc(X(t), Y(y), 2.6, 0, Math.PI * 2); g.fill();
  });
  if (nShown < run.nexts.length) {
    const tn = run.nexts[nShown], md = run.modes[nShown], ex = md === 2, right = X(tn) > w - 90;
    g.strokeStyle = g.fillStyle = ex ? COL.h0 : COL.ember;
    g.setLineDash([3, 4]); g.beginPath(); g.moveTo(X(tn), T); g.lineTo(X(tn), h - B); g.stroke(); g.setLineDash([]);
    g.textAlign = right ? 'right' : 'left';
    g.fillText(md === 0 ? 'follow-up' : ex ? 'next: scan' : 'next look', X(tn) + (right ? -5 : 5), T + 10);
  }
  return { nShown, explore: p[4] > 0.5 };
}
