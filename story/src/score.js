// The score. Everything is synthesised live with Web Audio: a pipe organ, a
// ticking clock, an organ ostinato, string and choir pads, brass "braams",
// taiko hits, risers and a Shepard tone for the crossing.
//
// Built to never stutter: every pitched voice is ONE oscillator (organ and choir
// timbres are baked into PeriodicWaves, the choir's formants live on a shared
// bus), and a lookahead scheduler plans 0.6 s ahead and skips, rather than
// bunches, any beats it misses while the page is busy rendering.
import { CHIRP, GRB_DELAY } from './scene/merger.js';

const mtof = m => 440 * Math.pow(2, (m - 69) / 12);
const LOOKAHEAD = 0.6, TICK_MS = 50;

const CH = {
  Am: [45, 52, 57, 60, 64], F: [41, 48, 57, 60, 65], C: [48, 55, 60, 64, 67], G: [43, 50, 59, 62, 67],
  Em: [40, 47, 55, 59, 64], Dm: [38, 45, 57, 62, 65], Bb: [46, 53, 58, 62, 65], E: [40, 47, 56, 59, 64],
  Fmaj7: [41, 48, 57, 64, 69], Cadd9: [48, 55, 62, 64, 67],
};
const PROG = {
  ripple: ['Am', 'F', 'C', 'G'], crossing: ['F', 'G', 'Am', 'Em'], you: ['Em', 'Cadd9', 'Am', 'Em'],
  auction: ['Dm', 'Bb', 'F', 'C'], diagnosis: ['Am', 'F', 'C', 'G'], unknown: ['F', 'G', 'Am', 'E'],
  finale: ['C', 'G', 'Am', 'Fmaj7'],
};
const OST = {
  ripple: [0, 2, 4, 2, 3, 2, 4, 2], you: [4, 3, 2, 3, 4, 3, 2, 1], auction: [0, 4, 0, 3, 0, 4, 0, 2],
  diagnosis: [0, 2, 4, 2, 3, 2, 4, 3], unknown: [0, 4, 3, 4, 2, 4, 3, 4], finale: [0, 2, 4, 3, 2, 3, 4, 2],
};

export function createScore() {
  let ctx = null, on = false;
  let master, dry, rev, organBus, stringBus, choirBus, choirIn, tickBus, ostBus, fxBus, droneG, drone, shepG;
  let organWave, choirWave, vib, clickBuf, noiseBuf, shaperCurve;
  const level = { organ: 0, ost: 0, ticks: 0, strings: 0, choir: 0, drone: 0, shepard: 0 };
  let cue = { prog: 'ripple', tempo: 60, ostKey: 'ripple', dbl: false };
  let nextBeat = 0, beat = 0, timer = null, silentUntil = 0, shepNext = 0;

  function makeIR(sec) {
    const sr = ctx.sampleRate, len = Math.floor(sr * sec), b = ctx.createBuffer(2, len, sr);
    for (let c = 0; c < 2; c++) {
      const d = b.getChannelData(c); let lp = 0;
      for (let i = 0; i < len; i++) {
        const t = i / len, n = Math.random() * 2 - 1;
        lp += (n - lp) * (0.55 - 0.45 * t);                     // the tail darkens as it decays
        d[i] = lp * Math.pow(1 - t, 2.4);
      }
    }
    return b;
  }
  function bus(gain, toRev, lp = 20000) {
    const g = ctx.createGain(); g.gain.value = gain;
    const f = ctx.createBiquadFilter(); f.type = 'lowpass'; f.frequency.value = lp;
    g.connect(f); f.connect(dry);
    const s = ctx.createGain(); s.gain.value = toRev; f.connect(s); s.connect(rev);
    return { in: g, f };
  }
  function wave(partials) {          // [[harmonic, amplitude], ...] -> one band-limited oscillator shape
    const n = Math.max(...partials.map(p => p[0])) + 1, real = new Float32Array(n), imag = new Float32Array(n);
    partials.forEach(([h, a]) => (imag[h] = a));
    return ctx.createPeriodicWave(real, imag);
  }

  function init() {
    const AC = window.AudioContext || window.webkitAudioContext; if (!AC) return false;
    ctx = new AC({ latencyHint: 'playback' });
    master = ctx.createGain(); master.gain.value = 0;
    const comp = ctx.createDynamicsCompressor(); comp.threshold.value = -14; comp.ratio.value = 4; comp.attack.value = 0.01; comp.release.value = 0.3;
    master.connect(comp); comp.connect(ctx.destination);
    dry = ctx.createGain(); dry.gain.value = 0.7; dry.connect(master);
    rev = ctx.createConvolver(); rev.buffer = makeIR(5.5);
    const rg = ctx.createGain(); rg.gain.value = 0.9; rev.connect(rg); rg.connect(master);
    organBus = bus(1, 0.85, 5200); stringBus = bus(1, 0.8, 1800); choirBus = bus(1, 1.0, 6000);
    tickBus = bus(0, 0.35); ostBus = bus(1, 0.9, 4200); fxBus = bus(1, 0.6);

    // pipe organ: 16' + 8' + 4' + 2 2/3' + 2' + mixture, built one octave down so the 16' fits
    organWave = wave([[1, 0.35], [2, 1], [4, 0.62], [6, 0.3], [8, 0.42], [10, 0.12], [12, 0.18], [16, 0.16]]);
    // a breathy "ah": a sawtooth-like spectrum, then shaped by the shared formant filters
    choirWave = wave(Array.from({ length: 24 }, (_, i) => [i + 1, 1 / (i + 1)]));
    choirIn = ctx.createGain(); choirIn.gain.value = 1;
    [[700, 7, 1], [1150, 9, 0.6], [2600, 12, 0.18]].forEach(([fr, q, a]) => {
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = fr; bp.Q.value = q;
      const g = ctx.createGain(); g.gain.value = a * 3; choirIn.connect(bp); bp.connect(g); g.connect(choirBus.in);
    });
    vib = ctx.createGain(); vib.gain.value = 6;                     // one shared vibrato for the whole choir
    const lfo = ctx.createOscillator(); lfo.frequency.value = 5.1; lfo.connect(vib); lfo.start();

    drone = ctx.createOscillator(); drone.type = 'sine'; drone.frequency.value = mtof(33);
    droneG = ctx.createGain(); droneG.gain.value = 0; drone.connect(droneG); droneG.connect(dry); drone.start();
    shepG = ctx.createGain(); shepG.gain.value = 0; shepG.connect(dry);
    const ss = ctx.createGain(); ss.gain.value = 0.7; shepG.connect(ss); ss.connect(rev);

    clickBuf = ctx.createBuffer(1, Math.floor(ctx.sampleRate * 0.03), ctx.sampleRate);
    { const d = clickBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / d.length, 8); }
    noiseBuf = ctx.createBuffer(1, ctx.sampleRate * 4, ctx.sampleRate);
    { const d = noiseBuf.getChannelData(0); for (let i = 0; i < d.length; i++) d[i] = Math.random() * 2 - 1; }
    shaperCurve = new Float32Array(1024); for (let i = 0; i < 1024; i++) shaperCurve[i] = Math.tanh((i / 512 - 1) * 3.2);

    nextBeat = ctx.currentTime + 0.2;
    timer = setInterval(schedule, TICK_MS);
    return true;
  }

  /* ------------------------------------------------ instruments (one oscillator per voice) */
  function env(g, t, peak, atk, hold, rel) {
    g.gain.setValueAtTime(0, t);
    g.gain.linearRampToValueAtTime(peak, t + atk);
    g.gain.setValueAtTime(peak, t + atk + hold);
    g.gain.linearRampToValueAtTime(0, t + atk + hold + rel);
    return t + atk + hold + rel + 0.05;
  }
  function voice(type, freq, t, peak, atk, hold, rel, dest, detune = 0) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    if (type === 'organ') o.setPeriodicWave(organWave); else if (type === 'choir') o.setPeriodicWave(choirWave); else o.type = type;
    o.frequency.value = freq; o.detune.value = detune;
    o.connect(g); g.connect(dest);
    const end = env(g, t, peak, atk, hold, rel);
    o.start(t); o.stop(end);
    o.onended = () => { o.disconnect(); g.disconnect(); };
    return o;
  }
  const organNote = (m, t, dur, vel, dest = organBus.in, atk = 0.18) => voice('organ', mtof(m) / 2, t, vel * 0.3, atk, Math.max(0, dur - atk), 1.4, dest);
  function stringsChord(notes, t, dur, vel) {
    notes.forEach(m => [-6, 6].forEach(dt => voice('sawtooth', mtof(m), t, vel * 0.045, 1.6, dur, 2.2, stringBus.in, dt)));
  }
  function choirChord(notes, t, dur, vel) {
    notes.slice(1).forEach(m => { const o = voice('choir', mtof(m + 12), t, vel * 0.07, 2.2, dur, 2.5, choirIn); vib.connect(o.detune); });
  }
  function tick(t, accent) {
    const n = ctx.createBufferSource(); n.buffer = clickBuf;
    const hp = ctx.createBiquadFilter(); hp.type = 'highpass'; hp.frequency.value = 2600;
    const g = ctx.createGain(); g.gain.value = accent ? 0.9 : 0.55;
    const p = ctx.createStereoPanner(); p.pan.value = beat % 2 ? 0.25 : -0.25;
    n.connect(hp); hp.connect(g); g.connect(p); p.connect(tickBus.in); n.start(t);
    const o = ctx.createOscillator(); o.frequency.value = accent ? 2100 : 1750;
    const og = ctx.createGain(); og.gain.setValueAtTime(0.25, t); og.gain.exponentialRampToValueAtTime(0.0001, t + 0.025);
    o.connect(og); og.connect(p); o.start(t); o.stop(t + 0.04);
    o.onended = () => { [n, hp, g, p, o, og].forEach(x => x.disconnect()); };
  }
  function hit(t, v = 1) {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(120, t); o.frequency.exponentialRampToValueAtTime(38, t + 0.6);
    g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.9 * v, t + 0.01); g.gain.exponentialRampToValueAtTime(0.0001, t + 2.2);
    o.connect(g); g.connect(fxBus.in); o.start(t); o.stop(t + 2.3);
    const n = ctx.createBufferSource(); n.buffer = noiseBuf;
    const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = 180; bp.Q.value = 0.8;
    const ng = ctx.createGain(); ng.gain.setValueAtTime(0.8 * v, t); ng.gain.exponentialRampToValueAtTime(0.0001, t + 0.4);
    n.connect(bp); bp.connect(ng); ng.connect(fxBus.in); n.start(t); n.stop(t + 0.45);
  }
  function braam(t, root = 33, v = 1, len = 5) {
    const ws = ctx.createWaveShaper(); ws.curve = shaperCurve;
    const lp = ctx.createBiquadFilter(); lp.type = 'lowpass'; lp.Q.value = 3;
    lp.frequency.setValueAtTime(120, t); lp.frequency.exponentialRampToValueAtTime(2400 * v, t + 0.45); lp.frequency.exponentialRampToValueAtTime(260, t + len);
    const g = ctx.createGain(); g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(0.32 * v, t + 0.06); g.gain.exponentialRampToValueAtTime(0.0001, t + len + 0.5);
    ws.connect(lp); lp.connect(g); g.connect(fxBus.in);
    [root, root + 12, root + 19].forEach(m => [-14, 0, 13].forEach(dt => {
      const o = ctx.createOscillator(); o.type = 'sawtooth'; o.frequency.value = mtof(m); o.detune.value = dt;
      const og = ctx.createGain(); og.gain.value = 0.22; o.connect(og); og.connect(ws); o.start(t); o.stop(t + len + 0.6);
    }));
    const sub = ctx.createOscillator(); sub.frequency.value = mtof(root - 12);
    const sg = ctx.createGain(); sg.gain.setValueAtTime(0, t); sg.gain.linearRampToValueAtTime(0.5 * v, t + 0.05); sg.gain.exponentialRampToValueAtTime(0.0001, t + len);
    sub.connect(sg); sg.connect(fxBus.in); sub.start(t); sub.stop(t + len + 0.1);
  }
  function riser(t, dur, v = 1) {
    const n = ctx.createBufferSource(); n.buffer = noiseBuf;
    const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.Q.value = 2.5;
    bp.frequency.setValueAtTime(250, t); bp.frequency.exponentialRampToValueAtTime(7000, t + dur);
    const g = ctx.createGain(); g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35 * v, t + dur); g.gain.linearRampToValueAtTime(0, t + dur + 0.05);
    n.connect(bp); bp.connect(g); g.connect(fxBus.in); n.start(t); n.stop(t + dur + 0.1);
  }
  // Shepard tone: six sines an octave apart, sliding up forever
  const SHEP_T = 7, SHEP_N = 6, SHEP_BASE = 55;
  const shepCurves = Array.from({ length: SHEP_N }, (_, i) => { const c = new Float32Array(64); for (let k = 0; k < 64; k++) { const x = (i + k / 63) / SHEP_N; c[k] = 0.06 * Math.exp(-Math.pow((x - 0.5) / 0.2, 2)); } return c; });
  function scheduleShepard(t) {
    for (let i = 0; i < SHEP_N; i++) {
      const o = ctx.createOscillator();
      o.frequency.setValueAtTime(SHEP_BASE * 2 ** i, t); o.frequency.exponentialRampToValueAtTime(SHEP_BASE * 2 ** (i + 1), t + SHEP_T);
      const g = ctx.createGain(); g.gain.setValueCurveAtTime(shepCurves[i], t, SHEP_T);
      o.connect(g); g.connect(shepG); o.start(t); o.stop(t + SHEP_T + 0.01);
    }
  }

  /* ------------------------------------------------ the tempo grid */
  function schedule() {
    if (!ctx || ctx.state !== 'running') return;
    const spb = 60 / cue.tempo, now = ctx.currentTime;
    // if the page stalled, skip the beats we missed instead of firing them all at once
    if (nextBeat < now) { const miss = Math.ceil((now - nextBeat) / spb); nextBeat += miss * spb; beat += miss; }
    while (nextBeat < now + LOOKAHEAD) {
      const t = nextBeat, silent = t < silentUntil;
      const chord = CH[PROG[cue.prog][Math.floor(beat / 8) % PROG[cue.prog].length]];
      if (beat % 8 === 0 && !silent) {                          // a new chord every two bars of 4/4
        const dur = spb * 8;
        if (level.organ > 0.01) chord.forEach((m, i) => organNote(m - (i === 0 ? 12 : 0), t, dur, 0.5 * level.organ, organBus.in, 0.6));
        if (level.strings > 0.01) stringsChord(chord.map(m => m + 12), t, dur, level.strings);
        if (level.choir > 0.01) choirChord(chord, t, dur, level.choir);
        drone.frequency.setTargetAtTime(mtof(chord[0] - 12), t, 0.8);
      }
      if (!silent && level.ticks > 0.01) { tick(t, beat % 4 === 0); if (cue.dbl) tick(t + spb / 2, false); }
      if (!silent && level.ost > 0.01) {
        const pat = OST[cue.ostKey] || OST.ripple;
        for (let s = 0; s < 2; s++) organNote(chord[pat[(beat * 2 + s) % pat.length]] + 12, t + s * spb / 2, spb * 0.42, 0.22 * level.ost, ostBus.in, 0.02);
      }
      nextBeat += spb; beat++;
    }
    if (level.shepard > 0.01) {
      if (shepNext < now) shepNext = now + 0.05;
      while (shepNext < now + LOOKAHEAD) { scheduleShepard(shepNext); shepNext += SHEP_T * 0.5; }
    }
  }
  function applyLevels() {
    if (!ctx) return; const t = ctx.currentTime;
    tickBus.in.gain.setTargetAtTime(level.ticks * 0.5, t, 0.3);
    droneG.gain.setTargetAtTime(level.drone * 0.22, t, 1.5);
    shepG.gain.setTargetAtTime(level.shepard, t, 1.0);
    stringBus.f.frequency.setTargetAtTime(600 + level.strings * 2800, t, 1.0);
  }

  return {
    get on() { return on; },
    async start() {
      if (!ctx && !init()) return false;
      if (ctx.state !== 'running') await ctx.resume();
      on = true; master.gain.cancelScheduledValues(ctx.currentTime); master.gain.setTargetAtTime(0.85, ctx.currentTime, 1.5);
      applyLevels(); return true;
    },
    stop() { if (!ctx) return; on = false; master.gain.setTargetAtTime(0, ctx.currentTime, 0.4); },
    // the phone was turned upright: freeze the music where it is
    suspend() { if (ctx && ctx.state === 'running') ctx.suspend(); },
    resume() { if (ctx && on && ctx.state === 'suspended') ctx.resume(); },
    // a cue: which progression, tempo and how loud each layer is (0..1)
    setCue(c) {
      const changed = Object.keys(c).some(k => (k in level ? level[k] : cue[k]) !== c[k]);
      if (!changed) return;
      cue = { ...cue, ...c };
      for (const k of Object.keys(level)) if (c[k] !== undefined) level[k] = c[k];
      applyLevels();
    },
    merger() {
      if (!on) return; const t = ctx.currentTime + 0.05;
      const o = ctx.createOscillator(), g = ctx.createGain(); o.type = 'sine';
      o.frequency.setValueAtTime(30, t); o.frequency.exponentialRampToValueAtTime(480, t + CHIRP);
      g.gain.setValueAtTime(0.0001, t); g.gain.exponentialRampToValueAtTime(0.35, t + CHIRP * 0.96); g.gain.linearRampToValueAtTime(0, t + CHIRP + 0.01);
      o.connect(g); g.connect(fxBus.in); o.start(t); o.stop(t + CHIRP + 0.05);
      riser(t, CHIRP, 0.8);
      // 1.7 s of nothing at all: duck the music bus, keep the reverb tail
      silentUntil = t + CHIRP + GRB_DELAY;
      dry.gain.cancelScheduledValues(t);
      dry.gain.setValueAtTime(dry.gain.value, t); dry.gain.setValueAtTime(0.7, t + CHIRP - 0.02);
      dry.gain.linearRampToValueAtTime(0.0, t + CHIRP + 0.05);
      dry.gain.setValueAtTime(0.0, t + CHIRP + GRB_DELAY - 0.02); dry.gain.linearRampToValueAtTime(0.7, t + CHIRP + GRB_DELAY);
      const b = t + CHIRP + GRB_DELAY;
      braam(b, 33, 1.2, 7); hit(b, 1.2);
      nextBeat = Math.max(nextBeat, b + 1.5);
    },
    alert() { if (!on) return; const t = ctx.currentTime + 0.05; hit(t, 0.8); braam(t, 40, 0.6, 3.5); },
    braam(root = 33, v = 1) { if (!on) return; const t = ctx.currentTime + 0.05; braam(t, root, v, 6); hit(t, v); },
    riser(d = 3) { if (!on) return; riser(ctx.currentTime + 0.05, d, 1); },
    ping(high) { if (!on) return; organNote(high ? 88 : 81, ctx.currentTime + 0.03, 0.25, 0.25, ostBus.in, 0.005); },
  };
}
