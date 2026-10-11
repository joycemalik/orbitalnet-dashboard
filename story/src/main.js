import './style.css';
import * as THREE from 'three';
import Lenis from 'lenis';
import { eciToScene, gmst, sunEci, NGC4993, radecToEci, RE_KM } from './astro.js';
import { createStars } from './scene/stars.js';
import { createMerger } from './scene/merger.js';
import { createEarth } from './scene/earth.js';
import { createSatellites } from './scene/satellites.js';
import { createPost } from './scene/post.js';
import { createHolo } from './scene/holo.js';
import { spikeTexture } from './scene/textures.js';
import { RUN_KNOWN, RUN_UNKNOWN } from './story/charts.js';
import { createScore } from './score.js';

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = s => document.querySelector(s);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const ease = t => t * t * (3 - 2 * t);
const ease2 = t => t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
const isSmall = () => innerWidth < 760;
const V3 = (x = 0, y = 0, z = 0) => new THREE.Vector3(x, y, z);

/* ================================================================ loading */
const loadBar = $('#loadBar'), loadTxt = $('#loadTxt');
const setProgress = p => { loadBar.style.width = (p * 100).toFixed(0) + '%'; loadTxt.textContent = `Acquiring signal · ${(p * 100).toFixed(0)}%`; };
const manager = new THREE.LoadingManager();
const texturesReady = new Promise(res => { manager.onLoad = res; });
manager.onProgress = (_, l, t) => setProgress(l / (t + 1));
const tl = new THREE.TextureLoader(manager);
const srgb = t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };
const tex = {
  day: srgb(tl.load('/textures/earth_atmos_2048.jpg')), night: srgb(tl.load('/textures/earth_lights_2048.png')),
  clouds: tl.load('/textures/earth_clouds_1024.png'), spec: tl.load('/textures/earth_specular_2048.jpg'),
};
tex.clouds.wrapS = THREE.RepeatWrapping;
const cube = new THREE.CubeTextureLoader(manager).setPath('/textures/milkyway/').load(['px', 'nx', 'py', 'ny', 'pz', 'nz'].map(s => `dark-s_${s}.jpg`));
cube.colorSpace = THREE.SRGBColorSpace;
const satData = await fetch('/data/sats.json').then(r => r.json());
await texturesReady;
setProgress(1);

/* ================================================================ renderer + world */
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, isSmall() ? 1.5 : 1.75));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
const scene = new THREE.Scene();
scene.background = cube; scene.backgroundIntensity = 0.35; scene.backgroundRotation.set(0.4, 1.1, 0);
const camera = new THREE.PerspectiveCamera(45, innerWidth / innerHeight, 0.01, 6000);
scene.add(camera);
const post = createPost(renderer, scene, camera);

const JD0 = satData.jdRef;
const sunE = sunEci(JD0), sun3 = eciToScene(...sunE).normalize();
const tgtE = radecToEci(NGC4993), F = eciToScene(...tgtE).normalize();
const MERGER_DIST = 1500, M = F.clone().multiplyScalar(MERGER_DIST);
const Y = V3(0, 1, 0), S = V3().crossVectors(F, Y).normalize(), U = V3().crossVectors(S, F).normalize();
const mp = (f, u, s) => M.clone().addScaledVector(F, f).addScaledVector(U, u).addScaledVector(S, s);

const stars = createStars(F, MERGER_DIST); scene.add(stars.points, stars.streaks);
const merger = createMerger();
merger.group.position.copy(M);
merger.group.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(S, U, F));
scene.add(merger.group);
const earth = createEarth(tex, sun3); scene.add(earth.group);
const sats = createSatellites(satData, tgtE, sunE); scene.add(sats.points, sats.links, sats.auction, sats.beams);
const beacon = new THREE.Sprite(new THREE.SpriteMaterial({ map: spikeTexture(), color: 0xffd2a0, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, sizeAttenuation: false }));
beacon.position.copy(M); scene.add(beacon);
const holo = createHolo(); camera.add(holo.root); holo.setOpacity(0);

/* ================================================================ "you": a real satellite */
const tmp = V3();
const satState = (k, t, p = V3(), v = V3()) => { sats.sceneAt(k, t, p); sats.sceneAt(k, t + 1, v); v.sub(p); return { p, v }; };
const sees = p => sats.seesTarget(p);
const inShadow = p => { const d = p.dot(sun3); return d < 0 && p.lengthSq() - d * d < 1; };
function pickYou(t) {
  // someone for whom NGC 4993 is just rising over the limb, ahead of them
  let best = -1, bestScore = -1e9;
  for (let k = 0; k < sats.count; k += 3) {
    const { p, v } = satState(k, t); const r = p.length(), rh = p.clone().divideScalar(r);
    const el = Math.asin(clamp(F.dot(rh), -1, 1)) * 180 / Math.PI, dip = Math.acos(1 / r) * 180 / Math.PI;
    const above = el + dip;
    if (above < 1.5 || above > 9) continue;
    const th = F.clone().addScaledVector(rh, -F.dot(rh)).normalize();
    const rising = th.dot(v.clone().normalize());
    const sc = rising * 2 - Math.abs(above - 4) * 0.2 + (inShadow(p) ? 0.6 : 0);
    if (sc > bestScore) { bestScore = sc; best = k; }
  }
  return best < 0 ? 0 : best;
}
function windows(k, t) {
  const p = V3(); let win = null, ecl = null;
  const shadowNow = inShadow(sats.sceneAt(k, t, p));
  for (let dt = 10; dt < 3 * 3600; dt += 10) {
    sats.sceneAt(k, t + dt, p);
    if (win === null && !sees(p)) win = dt;
    if (ecl === null && inShadow(p) !== shadowNow) ecl = dt;
    if (win !== null && ecl !== null) break;
  }
  return { win: win ?? 10800, ecl: ecl ?? 10800, shadowNow };
}
let you = -1, youWin = null;

/* ================================================================ camera language */
const pose = () => ({ pos: V3(), dir: V3(0, 0, -1), up: V3(0, 1, 0), fov: 45 });
const look = (pos, target, fov = 45, up = Y) => ({ pos: pos.clone(), dir: target.clone().sub(pos).normalize(), up: up.clone(), fov });
const slerpV = (a, b, t, out = V3()) => {
  const d = clamp(a.dot(b), -1, 1), th = Math.acos(d);
  if (th < 1e-4) return out.copy(a).lerp(b, t).normalize();
  const s = Math.sin(th);
  return out.copy(a).multiplyScalar(Math.sin((1 - t) * th) / s).addScaledVector(b, Math.sin(t * th) / s).normalize();
};
// spherical about Earth with log distance, so long trips pass through every power of ten
function blend(A, B, t) {
  const o = pose(), da = A.pos.length(), db = B.pos.length();
  slerpV(A.pos.clone().divideScalar(da), B.pos.clone().divideScalar(db), t, o.pos).multiplyScalar(Math.exp(lerp(Math.log(da), Math.log(db), t)));
  slerpV(A.dir, B.dir, t, o.dir); slerpV(A.up, B.up, t, o.up); o.fov = lerp(A.fov, B.fov, t);
  return o;
}
const lin = (A, B, t) => ({ pos: A.pos.clone().lerp(B.pos, t), dir: slerpV(A.dir, B.dir, t), up: slerpV(A.up, B.up, t), fov: lerp(A.fov, B.fov, t) });
const earthView = (aDeg, roll, dist, lookF, fov = 42) => {
  const a = aDeg * Math.PI / 180, side = S.clone().multiplyScalar(Math.cos(roll)).addScaledVector(U, Math.sin(roll));
  const pos = F.clone().multiplyScalar(-Math.cos(a)).addScaledVector(side, Math.sin(a)).normalize().multiplyScalar(dist);
  return look(pos, F.clone().multiplyScalar(lookF), fov);
};
function povPose(t) {
  const { p } = satState(you, t);
  const rh = p.clone().normalize();
  const th = F.clone().addScaledVector(rh, -F.dot(rh)).normalize();
  const el = Math.asin(clamp(F.dot(rh), -1, 1));
  const pitch = el - 0.1;                                   // aim a little below the source, so the limb sits in frame
  const dir = th.clone().multiplyScalar(Math.cos(pitch)).addScaledVector(rh, Math.sin(pitch)).normalize();
  const pos = p.clone().addScaledVector(rh, 0.0012).addScaledVector(th, -0.002);
  return { pos, dir, up: rh, fov: 58 };
}
let term = V3().crossVectors(sun3, Y).normalize(); if (term.dot(F) < 0) term.negate();
const O_ARRIVE = look(F.clone().multiplyScalar(.55).addScaledVector(term, .7).addScaledVector(Y, .3).normalize().multiplyScalar(4.4), V3(), 40);
const O4 = earthView(27, 0.6, 3.4, 0.8), O5 = earthView(23, 0.95, 2.6, 0.6), O6 = earthView(30, 0.15, 4.6, 1.0), O7 = earthView(38, -0.5, 5.4, 1.0);
const FINAL_DIR = term.clone().multiplyScalar(.7).addScaledVector(sun3, -.55).addScaledVector(Y, .35).normalize();
const O8 = look(FINAL_DIR.clone().multiplyScalar(9), V3(), 40), O9 = look(FINAL_DIR.clone().multiplyScalar(160), V3(), 40);
const MC = M.clone().addScaledVector(U, -1.5);
const P_MERGE_A = look(mp(36, 13, 12), MC, 45);
const orbitM = th => { const x = 36 * Math.cos(th) - 12 * Math.sin(th), z = 36 * Math.sin(th) + 12 * Math.cos(th); return look(mp(x, 13, z), MC, 45); };
const P_GRB_END = look(mp(85, 30, -40), M, 48);
const P_CLOCK_END = look(mp(100, 34, -52), M.clone().addScaledVector(S, -16), 48);
const P_LEAVE = look(F.clone().multiplyScalar(300).addScaledVector(U, 20), V3(), 50);

/* ================================================================ the storyboard */
// Each shot is one scroll "beat". Camera, world state, subtitles and score are keyed to it.
const ACTS = [
  { n: 'Act I', name: 'THE RIPPLE', line: 'NGC 4993 · 130 million years ago' },
  { n: 'Act II', name: 'THE CROSSING', line: '130 million light-years' },
  { n: 'Act III', name: 'YOU', line: 'Low Earth orbit · 7 April 2026' },
  { n: 'Act IV', name: 'THE AUCTION', line: 'How the fleet decides today' },
  { n: 'Act V', name: 'THE DIAGNOSIS', line: 'Look where the futures disagree' },
  { n: 'Act VI', name: 'THE UNKNOWN', line: 'h₀' },
  { n: 'Act VII', name: 'WATCHERS', line: 'A sky that watches itself' },
];
const W0 = { merger: 0, sats: 0, vis: 0, links: 0, auct: 0, h0: 0, tr: 0, bg: 0.32, ts: 120, holo: null, pov: false, shake: 0 };
const SHOTS = [
  { act: 0, w: { merger: 1, bg: .45 }, cue: { prog: 'ripple', tempo: 60, organ: .45, drone: .8, ticks: .6, ost: 0, strings: 0, choir: 0, shepard: 0, dbl: false },
    cam: t => lin(look(mp(420, 150, 130), M), look(mp(300, 105, 90), M), ease(t)),
    subs: [['This is a true story.', .34, .6], ['It began 130 million years ago.', .64, .96]] },
  { act: 0, w: { merger: 1, bg: .42 }, cue: { organ: .7, ticks: .8, ost: .45, strings: .3 },
    cam: t => lin(look(mp(300, 105, 90), M), P_MERGE_A, ease2(t)),
    subs: [['Two dead stars.', .05, .25], ['Each heavier than our Sun. Each no wider than a city.', .28, .6], ['Locked together. Falling inward.', .63, .96]] },
  { act: 0, w: { merger: 1, bg: .4 }, cue: { organ: .4, ticks: 1, ost: .75, strings: .6, dbl: true }, event: 'merger',
    cam: t => orbitM(ease(t) * 1.1),
    subs: [['In their final second, they circle each other hundreds of times.', .05, .42], ['Spacetime itself begins to shake.', .45, .72], ['Then, silence.', .76, .98]] },
  { act: 0, w: { merger: 1, bg: .4, shake: 1 }, cue: { organ: 1, strings: .9, choir: .6, ticks: 0, ost: 0, dbl: false },
    cam: t => lin(orbitM(1.1), P_GRB_END, ease(t)),
    subs: [['1.7 seconds.', .04, .22, 'big'], ['A flash of gamma rays. A fireball expanding at a third of the speed of light.', .26, .56], ['In the fire, atoms that did not exist a moment ago. Gold. Platinum. Uranium.', .6, .97]] },
  { act: 0, w: { merger: 1, bg: .4, holo: 'clocks' }, cue: { organ: .6, ticks: .8, ost: .3, strings: .5, choir: .2 },
    cam: t => lin(P_GRB_END, P_CLOCK_END, ease(t)),
    subs: [['Every explosion fades at its own pace.', .05, .3], ['Minutes. Hours. Days. Months.', .33, .55], ['How it fades is how you tell what it was.', .58, .78], ['Miss it, and the question is gone forever.', .8, .98]] },
  { act: 1, w: { merger: .6, bg: .45 }, cue: { prog: 'crossing', organ: .8, strings: .7, shepard: .6, ticks: .4, choir: .3, ost: 0 },
    cam: t => blend(P_CLOCK_END, P_LEAVE, ease2(t)),
    subs: [['The light leaves.', .32, .55], ['When it sets out, dinosaurs still walk the Earth.', .6, .96]] },
  { act: 1, w: { sats: 1, bg: .35, tr: .3 }, cue: { organ: 1, strings: 1, choir: .7, shepard: .9, ticks: .6, ost: .5 },
    cam: t => blend(P_LEAVE, O_ARRIVE, ease2(t)),
    subs: [['It crosses 130 million light-years of nothing.', .05, .32], ['In August 2017, light like this reached us, and some seventy observatories raced to catch it before it faded.', .36, .7], ['The next one could arrive tonight.', .74, .97]] },
  { act: 2, cut: true, w: { sats: 1, bg: .3, ts: 6, pov: true }, cue: { prog: 'you', tempo: 60, organ: .3, ticks: .7, ost: .35, strings: .2, choir: 0, shepard: 0, drone: .6, dbl: false },
    cam: (t, T) => povPose(T),
    subs: [['You are {ID}.', .32, .5], ['{ALT} kilometres up. {VEL} kilometres every second.', .53, .76], ['One of 10,109.', .79, .97]] },
  { act: 2, w: { sats: 1, bg: .3, ts: 6, pov: true, tr: 1 }, cue: { organ: .5, ticks: 1, dbl: true, ost: .6, strings: .5 }, event: 'alert',
    cam: (t, T) => povPose(T),
    subs: [['Something new rises over the edge of the world.', .05, .3], ['It was not there an hour ago.', .33, .55], ['It is already fading.', .58, .96, 'big']] },
  { act: 2, w: { sats: 1, bg: .3, ts: 6, pov: true, tr: 1 }, cue: { organ: .5, ticks: 1, dbl: true, ost: .8, strings: .7, drone: 1 },
    cam: (t, T) => povPose(T),
    subs: [['You can hold it in view for {WIN} more minutes. Then the Earth turns between you.', .04, .36], ['{ECL}', .4, .66], ['You cannot watch it alone.', .7, .97]] },
  { act: 2, w: { sats: 1, vis: 1, links: 1, bg: .3, ts: 40, tr: 1 }, cue: { organ: .9, strings: .9, choir: .6, ost: .6, dbl: false, drone: .6 },
    cam: (t, T) => blend(povPose(T), O4, ease2(t)),
    subs: [['But you are not alone.', .05, .28], ['Gold: the ones that can see it. Grey: the ones the Earth blinds.', .32, .6], ['Each sees a piece. None of you sees everything.', .64, .96]] },
  { act: 3, w: { sats: 1, vis: 1, links: .3, auct: 1, bg: .3, ts: 60, tr: 1 }, cue: { prog: 'auction', tempo: 72, ost: 1, ticks: .9, organ: .5, strings: .4, choir: 0 },
    cam: t => blend(O4, O5, ease(t)),
    subs: [['So you hold an auction.', .32, .48], ['A mission is posted. Everyone who can see it bids.', .5, .66], ['Closest. Most charge. Highest score wins.', .68, .8], ['Fast. Fair. And it never asks what the look would teach you.', .82, .98]] },
  { act: 4, w: { sats: 1, vis: .3, bg: .3, ts: 60, tr: 1, holo: 'known' }, cue: { prog: 'diagnosis', tempo: 60, organ: .8, ost: .8, strings: .8, choir: .4, ticks: .7 },
    cam: t => blend(O5, O6, ease(t)),
    subs: [['What is it?', .3, .42, 'big'], ['Each possibility predicts a different future.', .44, .6], ["So don't look where it's brightest. Look where the futures disagree.", .62, .8], ['That is expected information gain.', .82, .98]] },
  { act: 5, w: { sats: 1, vis: .15, bg: .3, ts: 60, tr: 1, h0: 1, holo: 'unknown' }, cue: { prog: 'unknown', organ: 1, ost: 1, strings: 1, choir: 1, ticks: 1, dbl: true },
    cam: t => blend(O6, O7, ease(t)),
    subs: [['Then the light does something none of them predicted.', .3, .5], ['Most systems would force an answer anyway.', .52, .66], ['This one keeps a door open.', .68, .8], ['<em>h₀</em>. Something we have no name for yet.', .82, .98]] },
  { act: 6, w: { sats: 1, bg: .4, tr: .4 }, cue: { prog: 'finale', organ: 1, strings: .8, choir: .8, ost: .4, ticks: .3, dbl: false },
    cam: t => blend(O7, O8, ease(t)),
    subs: [['The universe will not wait for us.', .3, .5], ['The next great discovery might last a few hours.', .53, .76], ['We want to be looking.', .79, .98, 'big']] },
  { act: 6, w: { sats: 1, bg: .5, tr: .2 }, cue: { organ: .5, strings: .3, choir: .3, ost: 0, ticks: .5 }, end: true,
    cam: t => blend(O8, O9, ease(t)), subs: [] },
];
SHOTS.forEach(s => (s.w = { ...W0, ...s.w }));
const actStart = ACTS.map((_, a) => SHOTS.findIndex(s => s.act === a));

/* ================================================================ scroll */
const SHOT_VH = () => (isSmall() ? 150 : 170);
const track = $('#track');
const sizeTrack = () => (track.style.height = `${SHOTS.length * SHOT_VH() + 100}vh`);
sizeTrack();
const lenis = new Lenis({ lerp: RM ? 1 : 0.07, smoothWheel: true, wheelMultiplier: 0.8 });
lenis.stop();
const shotH = () => innerHeight * SHOT_VH() / 100;
const scrollToShot = (i, immediate) => { const y = Math.max(0, i * shotH() + 2); autoY = y; lenis.scrollTo(y, { immediate, duration: 2.5, force: true }); };
const actsNav = $('#acts');
ACTS.forEach((a, i) => { const b = document.createElement('button'); b.type = 'button'; b.title = `${a.n} · ${a.name}`; b.setAttribute('aria-label', b.title); b.onclick = () => scrollToShot(actStart[i]); actsNav.appendChild(b); });
const actBtns = [...actsNav.children];

/* ================================================================ score + events */
const score = createScore();
let simT = 0, shot = -1, mergerAt = -1e9, mergerSeen = false, alerted = false;
function playMerger() { mergerSeen = true; mergerAt = performance.now(); merger.trigger(mergerAt); score.merger(); }
function enterShot(i) {
  const s = SHOTS[i];
  const cue = {}; for (let k = 0; k <= i; k++) Object.assign(cue, SHOTS[k].cue);   // cues accumulate, like a cue sheet
  score.setCue(cue);
  actBtns.forEach((b, a) => b.classList.toggle('on', a === s.act));
  $('#actNow').textContent = `${ACTS[s.act].n} · ${ACTS[s.act].name}`;
  if (i > 2 && !mergerSeen) { mergerSeen = true; mergerAt = performance.now() - 40000; merger.trigger(mergerAt); }
  if (i >= 7) {
    if (you < 0 || (s.w.pov && !sees(sats.sceneAt(you, simT, tmp)))) you = pickYou(simT);
    youWin = windows(you, simT);
  }
  sats.uniforms.uHide.value = s.w.pov ? you : -1;
  if (s.event === 'alert' && !alerted) { alerted = true; score.alert(); }
  if (i < 7) alerted = false;
}
const soundBtn = $('#soundBtn'), soundLbl = $('#soundLbl');
const reflectSound = () => { soundBtn.classList.toggle('on', score.on); soundBtn.setAttribute('aria-pressed', score.on); soundLbl.textContent = score.on ? 'Sound on' : 'Sound off'; };
soundBtn.onclick = async () => { score.on ? score.stop() : await score.start(); reflectSound(); };
/* ---- phones play in landscape only ---- */
const portraitQ = matchMedia('(orientation: portrait) and (pointer: coarse)');
const coarse = matchMedia('(pointer: coarse)').matches;
let started = false, blocked = portraitQ.matches;
function applyGate() {
  blocked = portraitQ.matches;
  if (blocked) { lenis.stop(); score.suspend(); }
  else { if (started) lenis.start(); score.resume(); autoY = window.scrollY; }
}
portraitQ.addEventListener('change', applyGate);
const fsEl = document.documentElement;
const canFS = !!(fsEl.requestFullscreen || fsEl.webkitRequestFullscreen);
const inFS = () => !!(document.fullscreenElement || document.webkitFullscreenElement);
async function enterFullscreen() {
  // must run inside the click that starts the film; iPhone Safari has no page fullscreen, so it quietly stays as is
  try {
    if (!inFS()) await (fsEl.requestFullscreen ? fsEl.requestFullscreen({ navigationUI: 'hide' }) : fsEl.webkitRequestFullscreen());
  } catch {}
  if (coarse) { try { await screen.orientation?.lock?.('landscape'); } catch {} }
}
const fsBtn = $('#fsBtn');
fsBtn.hidden = !canFS;
fsBtn.onclick = () => (inFS() ? (document.exitFullscreen || document.webkitExitFullscreen).call(document) : enterFullscreen());

/* ---- auto-play: the film scrolls itself until the viewer takes over ---- */
const AUTO_SEC_PER_SHOT = 15;
const autoChk = $('#autoChk');
let auto = autoChk.checked, autoY = 0;
function setAuto(v) { auto = v; autoChk.checked = v; if (v) autoY = window.scrollY; }
autoChk.addEventListener('change', () => setAuto(autoChk.checked));
const isOurs = e => e.target.closest?.('.controls, .acts, .endcard, .intro');
const takeOver = e => { if (auto && started && !isOurs(e)) setAuto(false); };
addEventListener('wheel', takeOver, { passive: true });
addEventListener('touchstart', takeOver, { passive: true });
addEventListener('keydown', e => { if (['ArrowDown', 'ArrowUp', 'PageDown', 'PageUp', 'Space', 'Home', 'End'].includes(e.code)) takeOver(e); });

function begin(withSound) {
  started = true;
  $('#intro').classList.add('gone'); document.body.classList.remove('locked');
  if (!blocked) lenis.start();
  enterFullscreen();
  autoY = window.scrollY;
  if (withSound) score.start().then(reflectSound);
}
$('#introActions').hidden = false; $('#loader').hidden = true;
$('#beginSound').onclick = () => begin(true);
$('#beginQuiet').onclick = () => begin(false);
$('#again').onclick = () => { mergerSeen = false; scrollToShot(0, true); setAuto(true); autoY = 0; };

/* ================================================================ overlays */
const subsEl = $('#subs'), subLine = document.createElement('div'); subLine.className = 'line'; subsEl.appendChild(subLine);
const tc = $('#titlecard'), tcAct = $('#tcAct'), tcName = $('#tcName'), tcLine = $('#tcLine');
const povEl = $('#pov'), reticle = $('#reticle'), retBox = $('#retBox'), bidsEl = $('#bids'), bidRows = $('#bidRows'), alertPanel = $('#pvAlert'), endcard = $('#endcard');
const PV = Object.fromEntries(['Id', 'Alt', 'Vel', 'LL', 'Bat', 'Sun', 'Src', 'El', 'Win', 'Ecl'].map(k => [k, $('#pv' + k)]));
let lastSub = '';
function youFacts() {
  if (you < 0) return null;
  const { p, v } = satState(you, simT); const r = p.length();
  return { id: 'STARLINK-' + sats.num[you], alt: (r - 1) * RE_KM, vel: v.length() * RE_KM, p, r };
}
function fillText(s) {
  const f = youFacts(); if (!f || !s.includes('{')) return s;
  const w = youWin || { win: 0, ecl: 0, shadowNow: false };
  const ecl = w.shadowNow ? "You are in Earth's shadow, running on batteries. The night side slides beneath you."
    : `In ${Math.round(w.ecl / 60)} minutes you pass into Earth's shadow and run on batteries.`;
  return s.replace('{ID}', f.id).replace('{ALT}', Math.round(f.alt).toLocaleString('en-US')).replace('{VEL}', f.vel.toFixed(2))
    .replace('{WIN}', Math.round(w.win / 60)).replace('{ECL}', ecl);
}
function updateSubs(s, t) {
  let text = '', a = 0, cls = '';
  for (const [tx, t0, t1, c] of s.subs) if (t >= t0 && t <= t1) { text = tx; cls = c || ''; a = Math.min(1, (t - t0) / 0.035, (t1 - t) / 0.035); break; }
  const full = fillText(text);
  if (full !== lastSub) { subLine.innerHTML = full; lastSub = full; }
  a = clamp(a, 0, 1);
  subLine.className = 'line ' + cls;
  subLine.style.opacity = a; subLine.style.transform = `translateY(${(1 - a) * 8}px)`; subLine.style.filter = `blur(${(1 - a) * 4}px)`;
}
function updateTitle(i, t) {
  const s = SHOTS[i], first = actStart[s.act] === i;
  let a = 0;
  if (first) a = t < 0.03 ? t / 0.03 : t < 0.22 ? 1 : Math.max(0, 1 - (t - 0.22) / 0.07);
  if (a > 0) {
    const A = ACTS[s.act]; tcAct.textContent = A.n; tcName.textContent = A.name;
    tcLine.textContent = s.act === 2 && you >= 0 ? `${Math.round(youFacts().alt)} km above the Earth · 7 April 2026` : A.line;
  }
  tc.style.opacity = a; tcName.style.letterSpacing = `${0.26 + (1 - a) * 0.15}em`;
  return a;
}
function updatePov(on, i) {
  povEl.classList.toggle('on', on);
  if (!on || you < 0) return;
  const f = youFacts(), w = youWin;
  const e = [f.p.x, -f.p.z, f.p.y];
  const g = gmst(JD0 + simT / 86400);
  const lat = Math.asin(e[2] / f.r) * 180 / Math.PI;
  let lon = (Math.atan2(e[1], e[0]) - g) * 180 / Math.PI; lon = ((lon % 360) + 540) % 360 - 180;
  const shadow = inShadow(f.p);
  PV.Id.textContent = f.id; PV.Alt.textContent = `${f.alt.toFixed(1)} km`; PV.Vel.textContent = `${f.vel.toFixed(3)} km/s`;
  PV.LL.textContent = `${Math.abs(lat).toFixed(2)}°${lat >= 0 ? 'N' : 'S'} ${Math.abs(lon).toFixed(2)}°${lon >= 0 ? 'E' : 'W'}`;
  PV.Bat.textContent = `${Math.round(sats.batt[you] * 100)}% · ${shadow ? 'DRAINING' : 'CHARGING'}`; PV.Bat.className = shadow ? 'warn' : '';
  PV.Sun.textContent = shadow ? 'ECLIPSE' : 'SUNLIT';
  const rh = f.p.clone().normalize(), el = Math.asin(clamp(F.dot(rh), -1, 1)) * 180 / Math.PI, dip = Math.acos(1 / f.r) * 180 / Math.PI;
  const alertOn = i >= 8;
  alertPanel.classList.toggle('alert', alertOn);
  PV.Src.textContent = alertOn ? 'UNKNOWN · FADING' : '—';
  PV.El.textContent = alertOn ? `${(el + dip).toFixed(1)}° above limb` : '—';
  if (w && alertOn) { PV.Win.textContent = `${Math.round(w.win / 60)} min`; PV.Win.className = w.win < 1800 ? 'crit' : 'warn'; PV.Ecl.textContent = w.shadowNow ? 'IN SHADOW' : `${Math.round(w.ecl / 60)} min`; }
  else { PV.Win.textContent = '—'; PV.Ecl.textContent = '—'; }
}
function renderBids(list) {
  bidRows.innerHTML = '<div class="r hd"><span>BIDDER</span><span>GEOM</span><span>BATT</span><span>SCORE</span></div>' +
    (list.length ? list.map((b, i) => `<div class="r${i ? '' : ' win'}${b.you ? ' you' : ''}"><span>${b.name}</span><span>${b.geo.toFixed(2)}</span><span>${Math.round(b.bat * 100)}%</span><span>${b.score.toFixed(3)}</span></div>`).join('')
      : '<div class="r"><span>Listening for bids…</span></div>');
}

/* ================================================================ resize */
let lastShotH = null;
function resize() {
  const g = lastShotH ? window.scrollY / lastShotH : 0;
  renderer.setSize(innerWidth, innerHeight); post.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix(); sizeTrack();
  if (lastShotH && Math.abs(lastShotH - shotH()) > 1) {
    const y = g * shotH(); autoY = y;
    lenis.resize?.(); lenis.scrollTo(y, { immediate: true, force: true });
  }
  lastShotH = shotH();
}
lastShotH = null;
addEventListener('resize', resize);

/* ================================================================ loop */
const hudClock = $('#tClock'), hudAlt = $('#tAlt');
const LY_KM = 9.4607e12, FAR_KM = 130e6 * LY_KM;
function fmtDistance(d) {
  let km;
  if (d > 40) { const t = clamp((Math.log(d) - Math.log(40)) / (Math.log(MERGER_DIST) - Math.log(40)), 0, 1); km = Math.exp(lerp(Math.log(40 * RE_KM), Math.log(FAR_KM), t)); }
  else km = (d - 1) * RE_KM;
  if (km > 0.1 * LY_KM) { const ly = km / LY_KM; return ly > 1e6 ? `${(ly / 1e6).toFixed(ly > 1e8 ? 0 : 1)} million ly` : `${Math.round(ly).toLocaleString('en-US')} ly`; }
  if (km > 1.496e8 * 50) return `${Math.round(km / 1.496e8).toLocaleString('en-US')} AU`;
  return `${Math.round(km).toLocaleString('en-US')} km`;
}
let holoFrame = 0, last = performance.now(), gs = 0, prevPos = null, auctionClock = 0, lastObs = -1, lastHolo = null, wasExplore = false, snap = 0;
const vel = V3(), w = { ...W0 };
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  if (blocked) { last = now; requestAnimationFrame(frame); return; }   // upright phone: nothing plays
  if (auto && started && !RM) {
    const end = (SHOTS.length - 0.3) * shotH();
    autoY = Math.min(end, Math.max(autoY, window.scrollY - 2) + dt * shotH() / AUTO_SEC_PER_SHOT);
    lenis.scrollTo(autoY, { immediate: true, force: true });
    if (autoY >= end) setAuto(false);
  }
  lenis.raf(now);
  const g = clamp(window.scrollY / shotH(), 0, SHOTS.length - 0.001);
  gs = RM || snap > 0 ? g : lerp(gs, g, 1 - Math.exp(-dt * 4)); if (snap > 0) snap--;
  const i = Math.floor(gs), t = gs - i, s = SHOTS[i];
  if (i !== shot) { shot = i; enterShot(i); }

  // world state eases toward the shot's settings
  const k = 1 - Math.exp(-dt * 2.5);
  for (const key of ['merger', 'sats', 'vis', 'links', 'auct', 'h0', 'tr', 'bg', 'shake']) w[key] = lerp(w[key], s.w[key], k);
  simT += dt * (RM ? Math.min(s.w.ts, 30) : s.w.ts);

  // camera
  if (s.event === 'merger' && t > 0.12 && (!mergerSeen || now - mergerAt > 20000)) playMerger();
  const P = s.cam(t, simT);
  const m = merger.update(now, { opacity: w.merger, ageBoost: i === 4 ? t * 40 : i > 4 ? 40 : 0, pix: renderer.domElement.height });
  // portrait screens see less sideways, so the camera stands further back from the planet
  const portrait = innerWidth < innerHeight && !s.w.pov && P.pos.length() < 30;
  camera.position.copy(P.pos).multiplyScalar(portrait ? 1.6 : 1);
  const dist = camera.position.length();
  const shakeAmt = RM ? 0 : w.shake * (m.flash * 2.2 + (m.sinceGrb > 0 && m.sinceGrb < 3 ? 0.4 : 0));
  if (shakeAmt > 0) camera.position.add(V3(Math.random() - .5, Math.random() - .5, Math.random() - .5).multiplyScalar(shakeAmt * Math.min(dist, 60) * 0.02));
  camera.up.copy(P.up);
  if (holoFrame > 0.01) P.dir.applyAxisAngle(P.up.clone().normalize(), 0.42 * holoFrame);   // pan: the planet slides right, the instrument stays
  if (portrait) P.dir.lerp(camera.position.clone().negate().normalize(), 0.7).normalize();   // keep the planet centred on tall screens
  camera.lookAt(tmp.copy(camera.position).add(P.dir));
  camera.fov = P.fov;
  camera.near = clamp((dist - 1) * 0.3, 0.0004, 1);
  // hologram shots: reframe so the planet sits right and the instrument floats over dark space
  holoFrame = lerp(holoFrame, s.w.holo && !isSmall() ? 1 : 0, 1 - Math.exp(-dt * 2));
  if (isSmall() && !s.w.pov) camera.setViewOffset(innerWidth, innerHeight, 0, -innerHeight * 0.08, innerWidth, innerHeight);
  else camera.clearViewOffset();
  post.lens.uniforms.uGrad.value = holoFrame;
  camera.updateProjectionMatrix();
  if (!prevPos) prevPos = camera.position.clone();
  vel.copy(camera.position).sub(prevPos).divideScalar(Math.max(dt, 1e-3)); prevPos.copy(camera.position);
  const speed = s.w.pov ? 0 : vel.length();
  stars.streakUniforms.uVel.value.copy(vel).multiplyScalar(0.045).clampLength(0, 300);
  stars.streakUniforms.uWarp.value = RM || s.w.pov ? 0 : clamp(speed / 150, 0, 0.9);
  post.lens.uniforms.uWarp.value = RM || s.w.pov ? 0 : clamp(speed / 600, 0, 1);

  // cuts fade through black
  let fade = 0;
  if (s.cut) fade = Math.max(fade, 1 - ease(clamp(t / 0.08, 0, 1)));
  if (SHOTS[i + 1]?.cut) fade = Math.max(fade, ease(clamp((t - 0.9) / 0.1, 0, 1)));
  post.lens.uniforms.uFade.value = fade;
  post.lens.uniforms.uFlash.value = m.flash * w.merger;
  post.bloom.strength = 0.9 + m.flash * 1.6 * w.merger;
  post.lens.uniforms.uTime.value = now / 1000;

  const pix = renderer.domElement.height;
  scene.backgroundIntensity = w.bg;
  stars.uniforms.uTime.value = now / 1000; stars.uniforms.uPix.value = pix;
  stars.uniforms.uCorr.value = clamp((dist - 20) / 120, 0, 1);       // the light's corridor dissolves near Earth
  stars.uniforms.uOpacity.value = s.w.pov ? 0.7 : 1; stars.uniforms.uSizeK.value = dist < 1.3 ? 0.45 : 1;
  earth.setInside(dist < 1.17);

  // earth + satellites
  earth.setRotation(gmst(JD0 + simT / 86400));
  earth.uniforms.uCloudShift.value = simT * 2e-6;
  const su = sats.uniforms;
  su.uT.value = simT; su.uTime.value = now / 1000; su.uPix.value = pix;
  su.uVis.value = w.vis; su.uH0.value = w.h0; su.uOpacity.value = w.sats; sats.points.visible = w.sats > 0.01;
  sats.linkU.uOpacity.value = w.links; sats.updateLinks(simT, now);
  if (w.auct > 0.05) { auctionClock -= dt; if (auctionClock <= 0) { renderBids(sats.runAuction(simT, camera, you)); auctionClock = 2.6; if (i === 11) score.ping(false); } }
  sats.updateAuction(simT, now, w.auct);
  sats.updateBeams(simT, now);
  bidsEl.classList.toggle('on', i === 11 && t > 0.3);

  // the source in the sky
  let tr = w.tr;
  if (i === 8) tr = s.w.tr * ease(clamp(t / 0.12, 0, 1));
  if (i === 7) tr = 0;
  if (i > 8 && s.w.pov) tr = 1;
  beacon.visible = tr > 0.01; beacon.material.opacity = clamp(tr, 0, 1);
  const flick = w.h0 > 0.01 ? 1 + 0.4 * w.h0 * Math.sin(now * 0.013) * Math.sin(now * 0.0071) : 1;
  beacon.scale.setScalar((s.w.pov ? 0.07 : 0.11) * flick * (0.6 + 0.4 * tr) * (1 + 0.08 * Math.sin(now * 0.004)));
  beacon.material.color.setRGB(1, lerp(0.82, 0.97, w.h0), lerp(0.63, 1, w.h0));

  // holograms
  const hmode = s.w.holo;
  if (hmode && hmode !== lastHolo) { if (hmode === 'clocks') holo.showClocks(); else holo.showDiagnosis(hmode === 'unknown'); lastObs = -1; lastHolo = hmode; }
  const holoA = hmode ? ease(clamp(t / 0.15, 0, 1)) * ease(clamp((1 - t) / 0.08, 0, 1)) : 0;
  if (hmode === 'clocks') { if (isSmall()) holo.layout(-0.66, -0.7, -5, -0.15, 0.5); else holo.layout(0.05, -0.42, -2.6, -0.42); holo.reveal(clamp((t - 0.05) / 0.75, 0.01, 1)); }
  if (hmode === 'known' || hmode === 'unknown') {
    if (isSmall()) holo.layout(-0.66, -0.95, -5, 0.12, 0.5); else holo.layout(-1.42, -0.36, -2.7, 0.3, 0.58);
    const run = hmode === 'known' ? RUN_KNOWN : RUN_UNKNOWN;
    const nShown = Math.min(run.obs.length, Math.floor(clamp((t - 0.12) / 0.8, 0, 1) * (run.obs.length + 1)));
    const r = holo.updateDiagnosis(run, nShown, now);
    if (nShown > lastObs && lastObs >= 0) { sats.fireBeam(simT, camera, r.explore ? 0xf4f6fb : 0xffb766); score.ping(r.explore); }
    if (hmode === 'unknown' && r.explore && !wasExplore) score.braam(41, 1);
    wasExplore = hmode === 'unknown' && r.explore;
    lastObs = nShown;
  }
  holo.setOpacity(holoA, now, hmode === 'unknown' ? w.h0 * (wasExplore ? 0.4 : 1) : 0);

  // overlays
  const titleA = updateTitle(i, t);
  updateSubs(s, t);
  subsEl.style.visibility = titleA > 0.5 ? 'hidden' : 'visible';
  updatePov(s.w.pov && (i > 7 || t > 0.25), i);
  if (s.w.pov && i >= 8) {
    const pr = beacon.position.clone().project(camera);
    const onScreen = pr.z < 1 && Math.abs(pr.x) < 1.1 && Math.abs(pr.y) < 1.1;
    reticle.style.opacity = onScreen ? clamp(i === 8 ? (t - 0.08) / 0.1 : 1, 0, 1) : 0;
    reticle.style.transform = `translate(${(pr.x * .5 + .5) * innerWidth}px, ${(-pr.y * .5 + .5) * innerHeight}px)`;
    retBox.style.transform = `rotate(${i === 8 && t < 0.3 ? (now * 0.3) % 360 : 45}deg) scale(${i === 8 && t < 0.3 ? 1.6 - t * 2 : 1})`;
  } else reticle.style.opacity = 0;
  endcard.classList.toggle('on', !!s.end && t > 0.25);

  const d = new Date(Date.UTC(2000, 0, 1, 12) + (JD0 - 2451545 + simT / 86400) * 86400000);
  hudClock.textContent = d.toISOString().slice(0, 19).replace('T', ' ');
  hudAlt.textContent = fmtDistance(dist);

  post.composer.render();
  requestAnimationFrame(frame);
}

// deep links: #s0 … #s15 open a shot directly (handy for review)
const deep = /^#s(\d+)$/.exec(location.hash);
if (deep && SHOTS[+deep[1]]) { begin(false); requestAnimationFrame(() => { scrollToShot(+deep[1] + 0.45, true); snap = 4; }); }
lastShotH = shotH();
requestAnimationFrame(frame);
