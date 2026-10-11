// The score, generated live with Web Audio: a pad that changes chord with each
// chapter, a sub drone, filtered noise, chimes, and the merger's chirp.
import { CHIRP, GRB_DELAY } from './scene/merger.js';

const mtof = m => 440 * Math.pow(2, (m - 69) / 12);
const MOODS = [
  { pad: [38, 45, 52, 57, 64, 69], cut: 420, pluck: 0.15, noise: 0.035, sc: [62, 64, 69, 71, 74, 76] },
  { pad: [38, 45, 50, 54, 57, 61], cut: 900, pluck: 0.2, noise: 0.05, sc: [66, 69, 73, 76, 78, 81] },
  { pad: [35, 47, 50, 54, 57, 62], cut: 850, pluck: 0.5, noise: 0.03, sc: [62, 66, 69, 71, 74, 78] },
  { pad: [31, 43, 50, 54, 57, 66], cut: 1600, pluck: 2.2, noise: 0.025, sc: [74, 76, 78, 81, 83, 86, 88, 90] },
  { pad: [28, 40, 47, 55, 59, 64], cut: 700, pluck: 0.7, noise: 0.04, pulse: 1, sc: [64, 67, 71, 72, 76] },
  { pad: [33, 45, 52, 55, 61, 64], cut: 1100, pluck: 0.6, noise: 0.03, sc: [69, 73, 76, 79, 81] },
  { pad: [38, 50, 57, 61, 64, 66], cut: 1700, pluck: 1.0, noise: 0.02, sc: [66, 69, 73, 74, 76, 78, 81] },
  { pad: [36, 48, 54, 59, 64, 66], cut: 2300, pluck: 1.6, noise: 0.05, sc: [72, 74, 76, 78, 80, 82, 84], detune: 22 },
  { pad: [26, 38, 45, 54, 57, 64], cut: 2600, pluck: 0.5, noise: 0.03, sc: [62, 66, 69, 74, 76, 81, 86] },
];

export function createAudio() {
  let ctx = null, master, padF, sub, noiseG, pluckBus, rev, on = false, mood = MOODS[0], pulseT = 0;
  const voices = [];
  const ir = sec => {
    const len = ctx.sampleRate * sec, b = ctx.createBuffer(2, len, ctx.sampleRate);
    for (let c = 0; c < 2; c++) { const d = b.getChannelData(c); for (let i = 0; i < len; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, 2.8); }
    return b;
  };
  function init() {
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    ctx = new AC();
    master = ctx.createGain(); master.gain.value = 0;
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -18; comp.ratio.value = 3;
    master.connect(comp); comp.connect(ctx.destination);
    rev = ctx.createConvolver(); rev.buffer = ir(5.5); const revG = ctx.createGain(); revG.gain.value = 0.75; rev.connect(revG); revG.connect(master);
    const dry = ctx.createGain(); dry.gain.value = 0.55; dry.connect(master);
    padF = ctx.createBiquadFilter(); padF.type = 'lowpass'; padF.frequency.value = 400; padF.Q.value = 0.6; padF.connect(dry); padF.connect(rev);
    const lfo = ctx.createOscillator(); lfo.frequency.value = 0.06; const lfoG = ctx.createGain(); lfoG.gain.value = 180; lfo.connect(lfoG); lfoG.connect(padF.frequency); lfo.start();
    for (let v = 0; v < 6; v++) {
      const g = ctx.createGain(); g.gain.value = 0.045; g.connect(padF);
      const os = [-7, 7].map(dt => { const o = ctx.createOscillator(); o.type = 'sawtooth'; o.detune.value = dt; o.frequency.value = mtof(mood.pad[v]); o.connect(g); o.start(); return o; });
      const tri = ctx.createOscillator(); tri.type = 'triangle'; tri.frequency.value = mtof(mood.pad[v]);
      const tg = ctx.createGain(); tg.gain.value = 0.6; tri.connect(tg); tg.connect(g); tri.start();
      voices.push({ os: [...os, tri] });
    }
    sub = ctx.createOscillator(); sub.type = 'sine'; sub.frequency.value = mtof(mood.pad[0] - 12);
    const sg = ctx.createGain(); sg.gain.value = 0.16; sub.connect(sg); sg.connect(dry); sub.start();
    const nb = ctx.createBuffer(1, ctx.sampleRate * 3, ctx.sampleRate), nd = nb.getChannelData(0);
    let lp = 0; for (let i = 0; i < nd.length; i++) { lp = lp * 0.97 + (Math.random() * 2 - 1) * 0.03; nd[i] = lp * 6; }
    const ns = ctx.createBufferSource(); ns.buffer = nb; ns.loop = true;
    const nf = ctx.createBiquadFilter(); nf.type = 'bandpass'; nf.frequency.value = 500; nf.Q.value = 0.5;
    noiseG = ctx.createGain(); noiseG.gain.value = 0; ns.connect(nf); nf.connect(noiseG); noiseG.connect(rev); noiseG.connect(dry); ns.start();
    pluckBus = ctx.createGain(); pluckBus.gain.value = 0.5; pluckBus.connect(dry); pluckBus.connect(rev);
    const dl = ctx.createDelay(2); dl.delayTime.value = 0.42; const fb = ctx.createGain(); fb.gain.value = 0.38;
    const dlf = ctx.createBiquadFilter(); dlf.frequency.value = 2400;
    pluckBus.connect(dl); dl.connect(dlf); dlf.connect(fb); fb.connect(dl); dlf.connect(rev);
    return true;
  }
  function applyMood(m, slow) {
    if (!ctx) return; const t = ctx.currentTime, tc = slow ? 2.2 : 1.2;
    voices.forEach((v, i) => {
      const n = m.pad[i % m.pad.length];
      v.os.forEach((o, j) => { o.frequency.setTargetAtTime(mtof(n), t, tc); if (j < 2) o.detune.setTargetAtTime((j ? 1 : -1) * (7 + (m.detune || 0)), t, 1.5); });
    });
    sub.frequency.setTargetAtTime(mtof(m.pad[0] - 12), t, tc);
    padF.frequency.setTargetAtTime(m.cut, t, 2);
    noiseG.gain.setTargetAtTime(m.noise, t, 2);
  }
  function pluck(f, vel = 0.18, when) {
    const t = when || ctx.currentTime;
    const o = ctx.createOscillator(), o2 = ctx.createOscillator(), g = ctx.createGain(), g2 = ctx.createGain();
    o.type = 'sine'; o.frequency.value = f; o2.type = 'triangle'; o2.frequency.value = f * 2; g2.gain.value = 0.25;
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(vel, t + 0.006); g.gain.exponentialRampToValueAtTime(0.0001, t + 2.8);
    o.connect(g); o2.connect(g2); g2.connect(g); g.connect(pluckBus); o.start(t); o2.start(t); o.stop(t + 3); o2.stop(t + 3);
  }
  function thump(t, f0 = 90, v = 0.5) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(f0, t); o.frequency.exponentialRampToValueAtTime(40, t + 0.25);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(v, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 0.6);
    o.connect(g); g.connect(master); o.start(t); o.stop(t + 0.7);
  }
  return {
    get on() { return on; },
    async start() {
      if (!ctx && !init()) return false;
      if (ctx.state !== 'running') await ctx.resume();
      on = true; master.gain.cancelScheduledValues(ctx.currentTime); master.gain.setTargetAtTime(0.9, ctx.currentTime, 1.2);
      applyMood(mood, false); return true;
    },
    stop() { if (!ctx) return; on = false; master.gain.setTargetAtTime(0, ctx.currentTime, 0.4); },
    mood(i) { mood = MOODS[i] || MOODS[MOODS.length - 1]; if (on) applyMood(mood, true); },
    tick(dt) {
      if (!on || !ctx) return;
      if (Math.random() < mood.pluck * dt) pluck(mtof(mood.sc[(Math.random() * mood.sc.length) | 0]), 0.05 + Math.random() * 0.1);
      if (mood.pulse) { pulseT -= dt; if (pulseT <= 0) { const t = ctx.currentTime + 0.05; thump(t, 80, 0.35); thump(t + 0.28, 70, 0.22); pulseT = 1.25; } }
    },
    blip() { if (!on) return; const t = ctx.currentTime;[0, 0.09, 0.18].forEach((d, i) => pluck(mtof(81 + i * 4), 0.07, t + d)); },
    ping(high) { if (!on) return; pluck(mtof(high ? 93 : 86), 0.12); },
    chirp() {
      if (!on) return; const t = ctx.currentTime;
      // gravitational-wave chirp, shifted up into hearing range
      const o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'sine';
      o.frequency.setValueAtTime(32, t); o.frequency.exponentialRampToValueAtTime(520, t + CHIRP);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.32, t + CHIRP * 0.95); g.gain.linearRampToValueAtTime(0, t + CHIRP + 0.02);
      o.connect(g); g.connect(master); o.start(t); o.stop(t + CHIRP + 0.1);
      // 1.7 s of silence, then the gamma rays
      const b = t + CHIRP + GRB_DELAY;
      thump(b, 110, 0.9);
      const nb = ctx.createBuffer(1, ctx.sampleRate * 3, ctx.sampleRate), d = nb.getChannelData(0);
      for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 3);
      const ns = ctx.createBufferSource(); ns.buffer = nb;
      const nf = ctx.createBiquadFilter(); nf.type = 'lowpass'; nf.frequency.setValueAtTime(6000, b); nf.frequency.exponentialRampToValueAtTime(200, b + 2.5);
      const ng = ctx.createGain(); ng.gain.value = 0.5; ns.connect(nf); nf.connect(ng); ng.connect(rev); ng.connect(master); ns.start(b);
      [74, 78, 81, 85, 88].forEach((n, i) => pluck(mtof(n), 0.12, b + 0.05 + i * 0.11));
    },
  };
}
