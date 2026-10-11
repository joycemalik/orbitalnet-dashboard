import './style.css';
import * as THREE from 'three';
import Lenis from 'lenis';
import { eciToScene, gmst, sunEci, NGC4993, radecToEci, RE_KM } from './astro.js';
import { createStars } from './scene/stars.js';
import { createMerger, CHIRP, GRB_DELAY } from './scene/merger.js';
import { createEarth } from './scene/earth.js';
import { createSatellites } from './scene/satellites.js';
import { createPost } from './scene/post.js';
import { spikeTexture } from './scene/textures.js';
import { sizeCanvas, drawFade, drawDx, beliefRows, RUN_KNOWN, RUN_UNKNOWN } from './story/charts.js';
import { createAudio } from './audio.js';

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = s => document.querySelector(s);
const clamp = (x, a, b) => Math.max(a, Math.min(b, x));
const lerp = (a, b, t) => a + (b - a) * t;
const smooth = t => t * t * (3 - 2 * t);
const isSmall = () => innerWidth < 760;

/* ------------------------------------------------------------------ loading */
const loadBar = $('#loadBar'), loadTxt = $('#loadTxt');
const setProgress = p => { loadBar.style.width = (p * 100).toFixed(0) + '%'; loadTxt.textContent = `Acquiring signal · ${(p * 100).toFixed(0)}%`; };
const manager = new THREE.LoadingManager();
const texturesReady = new Promise(res => { manager.onLoad = res; });
manager.onProgress = (_, l, t) => setProgress(l / (t + 1));
const tl = new THREE.TextureLoader(manager);
const srgb = t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 8; return t; };
const tex = {
  day: srgb(tl.load('/textures/earth_atmos_2048.jpg')),
  night: srgb(tl.load('/textures/earth_lights_2048.png')),
  clouds: tl.load('/textures/earth_clouds_1024.png'),
  spec: tl.load('/textures/earth_specular_2048.jpg'),
};
tex.clouds.wrapS = THREE.RepeatWrapping;
const cube = new THREE.CubeTextureLoader(manager).setPath('/textures/milkyway/')
  .load(['px', 'nx', 'py', 'ny', 'pz', 'nz'].map(s => `dark-s_${s}.jpg`));
cube.colorSpace = THREE.SRGBColorSpace;
const satData = await fetch('/data/sats.json').then(r => r.json());
await texturesReady;
setProgress(1);

/* ------------------------------------------------------------------ renderer */
const renderer = new THREE.WebGLRenderer({ canvas: $('#gl'), antialias: false, powerPreference: 'high-performance' });
renderer.setPixelRatio(Math.min(devicePixelRatio, isSmall() ? 1.5 : 1.75));
renderer.setSize(innerWidth, innerHeight);
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.0;
const scene = new THREE.Scene();
scene.background = cube;
scene.backgroundIntensity = 0.35;
scene.backgroundRotation.set(0.4, 1.1, 0);
const camera = new THREE.PerspectiveCamera(42, innerWidth / innerHeight, 0.005, 40000);
const post = createPost(renderer, scene, camera);

/* ------------------------------------------------------------------ the sky, computed */
const JD0 = satData.jdRef;                        // TLE reference epoch, 2026-04-07 08:29 UTC
const sunE = sunEci(JD0);
const sun3 = eciToScene(...sunE).normalize();
const tgtE = radecToEci(NGC4993);                 // where GW170817 really happened
const F = eciToScene(...tgtE).normalize();         // scene direction toward the merger
const MERGER_DIST = 1500;
const M = F.clone().multiplyScalar(MERGER_DIST);
const Y = new THREE.Vector3(0, 1, 0);
const S = new THREE.Vector3().crossVectors(F, Y).normalize();
const U = new THREE.Vector3().crossVectors(S, F).normalize();

const stars = createStars(F, MERGER_DIST);
scene.add(stars.points, stars.streaks);

const merger = createMerger();
merger.group.position.copy(M);
merger.group.quaternion.setFromRotationMatrix(new THREE.Matrix4().makeBasis(S, U, F));
scene.add(merger.group);

const earth = createEarth(tex, sun3);
scene.add(earth.group);

const sats = createSatellites(satData, tgtE, sunE);
scene.add(sats.points, sats.links, sats.auction, sats.beams);

const beacon = new THREE.Sprite(new THREE.SpriteMaterial({ map: spikeTexture(), color: 0xffd2a0, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, sizeAttenuation: false }));
beacon.position.copy(M);
scene.add(beacon);

/* ------------------------------------------------------------------ camera keyframes, one per chapter */
// Positions are Earth-centred; interpolation is spherical with log distance, so the
// trip from NGC 4993 to Earth passes through every power of ten.
let term = new THREE.Vector3().crossVectors(sun3, Y).normalize();
if (term.dot(F) < 0) term.negate();
const earthView = (aDeg, roll, dist, lookF) => {
  const a = aDeg * Math.PI / 180;
  const side = S.clone().multiplyScalar(Math.cos(roll)).addScaledVector(U, Math.sin(roll));
  const pos = F.clone().multiplyScalar(-Math.cos(a)).addScaledVector(side, Math.sin(a)).normalize().multiplyScalar(dist);
  return { pos, look: F.clone().multiplyScalar(lookF) };
};
const KF = [
  { pos: M.clone().addScaledVector(F, 330).addScaledVector(U, 120).addScaledVector(S, 90), look: M, ox: .1, merger: 1, sats: 0, tr: 0, bg: .45 },
  { pos: M.clone().addScaledVector(F, 24).addScaledVector(U, 10).addScaledVector(S, 9), look: M.clone().addScaledVector(U, -1.5), ox: .15, merger: 1, sats: 0, tr: 0, bg: .4 },
  { pos: M.clone().addScaledVector(F, 80).addScaledVector(U, 30).addScaledVector(S, -36), look: M, ox: .15, merger: 1, sats: 0, tr: 0, bg: .4 },
  { pos: term.clone().multiplyScalar(.85).addScaledVector(Y, .32).addScaledVector(F, .4).normalize().multiplyScalar(3.9), look: new THREE.Vector3(), ox: .17, merger: 0, sats: 1, tr: .5, bg: .3 },
  { ...earthView(27, 0.6, 3.4, 0.8), ox: .16, merger: 0, sats: 1, vis: 1, links: 1, tr: 1, bg: .3 },
  { ...earthView(23, 0.95, 2.55, 0.6), ox: .17, merger: 0, sats: 1, vis: 1, links: .3, auct: 1, tr: 1, bg: .3 },
  { ...earthView(32, 0.2, 4.4, 1.0), ox: .2, merger: 0, sats: 1, vis: .35, tr: 1, bg: .3 },
  { ...earthView(36, -0.5, 5.0, 1.0), ox: .2, merger: 0, sats: 1, vis: .2, h0: 1, tr: 1, bg: .3 },
  { pos: term.clone().multiplyScalar(.7).addScaledVector(sun3, -.55).addScaledVector(Y, .35).normalize().multiplyScalar(9), look: new THREE.Vector3(), ox: .12, merger: 0, sats: 1, tr: .5, bg: .35 },
  { pos: term.clone().multiplyScalar(.7).addScaledVector(sun3, -.55).addScaledVector(Y, .35).normalize().multiplyScalar(90), look: new THREE.Vector3(), ox: 0, merger: 0, sats: 1, tr: .3, bg: .5 },
];
const PARAMS = ['ox', 'merger', 'sats', 'vis', 'links', 'auct', 'h0', 'tr', 'bg'];
KF.forEach(k => {
  k.dist = k.pos.length(); k.dir = k.pos.clone().divideScalar(k.dist);
  k.lookDir = k.look.clone().sub(k.pos).normalize();
  PARAMS.forEach(p => (k[p] = k[p] ?? 0));
});
const slerpV = (a, b, t, out) => {
  const d = clamp(a.dot(b), -1, 1), th = Math.acos(d);
  if (th < 1e-4) return out.copy(a).lerp(b, t).normalize();
  const s = Math.sin(th);
  return out.copy(a).multiplyScalar(Math.sin((1 - t) * th) / s).addScaledVector(b, Math.sin(t * th) / s).normalize();
};
const pose = { dir: new THREE.Vector3(), lookDir: new THREE.Vector3(), dist: 1 };
function poseAt(g) {
  const a = clamp(Math.floor(g - 0.5), 0, KF.length - 1), b = clamp(a + 1, 0, KF.length - 1);
  const t = smooth(clamp(g - 0.5 - a, 0, 1)), A = KF[a], B = KF[b];
  slerpV(A.dir, B.dir, t, pose.dir);
  slerpV(A.lookDir, B.lookDir, t, pose.lookDir);
  pose.dist = Math.exp(lerp(Math.log(A.dist), Math.log(B.dist), t));
  PARAMS.forEach(p => (pose[p] = lerp(A[p], B[p], t)));
  return pose;
}

/* ------------------------------------------------------------------ scroll */
const lenis = new Lenis({ lerp: RM ? 1 : 0.075, smoothWheel: true });
lenis.stop();
const sections = [...document.querySelectorAll('.ch')];
const rail = $('#rail');
sections.forEach(s => {
  const b = document.createElement('button'); b.type = 'button'; b.title = s.dataset.name; b.setAttribute('aria-label', s.dataset.name);
  b.onclick = () => lenis.scrollTo(s, { duration: RM ? 0 : 2.4 }); rail.appendChild(b);
});
const railBtns = [...rail.children];
let gpos = 0.5, gs = 0.5, active = -1;
const localT = sections.map(() => 0);
function readScroll() {
  const mid = innerHeight * 0.5; let g = 0;
  sections.forEach((s, i) => {
    const r = s.getBoundingClientRect(), t = clamp((mid - r.top) / r.height, 0, 1);
    localT[i] = t; if (r.top <= mid) g = i + t;
  });
  gpos = Math.max(g, 0.5);
  const a = clamp(Math.floor(g), 0, sections.length - 1);
  if (a !== active) { active = a; onChapter(a); }
}

/* ------------------------------------------------------------------ audio + story events */
const audio = createAudio();
const tlRows = [...document.querySelectorAll('#mergerTl div')];
let lastMerger = -1, mergerDone = false;
function playMerger() { mergerDone = true; lastMerger = performance.now(); merger.trigger(lastMerger); audio.chirp(); }
$('#replay').onclick = playMerger;
function onChapter(a) {
  sections.forEach((s, i) => s.classList.toggle('active', i === a));
  railBtns.forEach((b, i) => b.classList.toggle('on', i === a));
  audio.mood(a);
  if (a === 1 && (!mergerDone || performance.now() - lastMerger > 12000)) playMerger();
  // arrived past chapter I without seeing it (deep link): the merger has already happened
  if (a > 1 && !mergerDone) { mergerDone = true; lastMerger = performance.now() - 30000; merger.trigger(lastMerger); }
}
const soundBtn = $('#soundBtn'), soundLbl = $('#soundLbl');
const reflectSound = () => { soundBtn.classList.toggle('on', audio.on); soundBtn.setAttribute('aria-pressed', audio.on); soundLbl.textContent = audio.on ? 'Sound on' : 'Sound off'; };
soundBtn.onclick = async () => { audio.on ? audio.stop() : await audio.start(); reflectSound(); };
function begin(withSound) {
  $('#intro').classList.add('gone'); document.body.classList.remove('locked'); lenis.start();
  if (withSound) audio.start().then(reflectSound);
}
$('#introActions').hidden = false; $('#loader').hidden = true;
$('#beginSound').onclick = () => begin(true);
$('#beginQuiet').onclick = () => begin(false);

/* ------------------------------------------------------------------ charts + auction table */
const fadeC = $('#fadeChart'), knownC = $('#dxKnown'), unkC = $('#dxUnknown');
const bKnown = $('#bKnown'), bUnknown = $('#bUnknown'), modeTag = $('#modeTag'), bidsEl = $('#bids');
beliefRows(bKnown); beliefRows(bUnknown);
const sizeCharts = () => [fadeC, knownC, unkC].forEach(c => sizeCanvas(c, Math.min(devicePixelRatio, 2)));
let lastKnown = 0, lastUnknown = 0, auctionClock = 0;
function renderBids(list) {
  bidsEl.innerHTML = '<div class="hd"><span>Bidder</span><span>Geometry</span><span>Battery</span><span>Score</span></div>' +
    (list.length ? list.map((b, i) => `<div class="r${i ? '' : ' win'}"><span>${b.name}</span><span>${b.geo.toFixed(2)}</span><span>${Math.round(b.bat * 100)}%</span><span>${b.score.toFixed(3)}</span></div>`).join('')
      : '<div class="r"><span>Waiting for bidders in view…</span></div>');
}

/* ------------------------------------------------------------------ resize */
function resize() {
  renderer.setSize(innerWidth, innerHeight);
  post.setSize(innerWidth, innerHeight);
  camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  sizeCharts();
}
addEventListener('resize', resize);
resize();

/* ------------------------------------------------------------------ loop */
const hudClock = $('#tClock'), hudAlt = $('#tAlt');
const LY_KM = 9.4607e12, FAR_KM = 130e6 * LY_KM;
function fmtDistance(sceneDist) {
  // the scene is not to scale between galaxies, so the readout counts down in powers of ten
  let km;
  if (sceneDist > 40) {
    const t = clamp((Math.log(sceneDist) - Math.log(40)) / (Math.log(MERGER_DIST) - Math.log(40)), 0, 1);
    km = Math.exp(lerp(Math.log(40 * RE_KM), Math.log(FAR_KM), t));
  } else km = (sceneDist - 1) * RE_KM;
  if (km > 0.1 * LY_KM) { const ly = km / LY_KM; return ly > 1e6 ? `${(ly / 1e6).toFixed(ly > 1e8 ? 0 : 1)} million ly` : `${Math.round(ly).toLocaleString('en-US')} ly`; }
  if (km > 1.496e8 * 50) return `${Math.round(km / 1.496e8).toLocaleString('en-US')} AU`;
  return `${Math.round(km).toLocaleString('en-US')} km`;
}

const prevPos = new THREE.Vector3(), vel = new THREE.Vector3(), tmpV = new THREE.Vector3();
let simT = 0, last = performance.now(), first = true, snap = 0;
function frame(now) {
  const dt = Math.min(0.05, (now - last) / 1000); last = now;
  lenis.raf(now);
  readScroll();
  gs = RM || snap > 0 ? gpos : lerp(gs, gpos, 1 - Math.exp(-dt * 3.2)); if (snap > 0) snap--;
  const p = poseAt(gs);
  simT += dt * (RM ? 30 : 120);

  // camera
  camera.position.copy(p.dir).multiplyScalar(p.dist * (isSmall() && p.dist < 30 ? 1.7 : 1));
  camera.lookAt(tmpV.copy(camera.position).add(p.lookDir));
  const W = innerWidth, H = innerHeight;
  if (isSmall()) camera.setViewOffset(W, H, 0, -H * 0.16, W, H);
  else camera.setViewOffset(W, H, -p.ox * W, 0, W, H);
  if (first) { prevPos.copy(camera.position); first = false; }
  vel.copy(camera.position).sub(prevPos).divideScalar(Math.max(dt, 1e-3));
  prevPos.copy(camera.position);
  const speed = vel.length();
  stars.streakUniforms.uVel.value.copy(vel).multiplyScalar(0.045).clampLength(0, 300);
  stars.streakUniforms.uWarp.value = RM ? 0 : clamp(speed / 150, 0, 0.9);
  post.lens.uniforms.uWarp.value = RM ? 0 : clamp(speed / 600, 0, 1);

  const pix = renderer.domElement.height;
  scene.backgroundIntensity = p.bg;
  stars.uniforms.uTime.value = now / 1000; stars.uniforms.uPix.value = pix;

  // the merger
  const m = merger.update(now, { opacity: p.merger, ageBoost: active === 2 ? localT[2] * 40 : active > 2 ? 40 : 0, pix });
  post.lens.uniforms.uFlash.value = m.flash * p.merger;
  post.bloom.strength = 0.9 + m.flash * 1.5 * p.merger;
  if (m.t >= 0) {
    const marks = [0, CHIRP, CHIRP + GRB_DELAY, CHIRP + GRB_DELAY + 3.5];
    tlRows.forEach((r, i) => r.classList.toggle('lit', m.t > marks[i]));
  }

  // earth + satellites
  earth.setRotation(gmst(JD0 + simT / 86400));
  earth.uniforms.uCloudShift.value = simT * 2e-6;
  const su = sats.uniforms;
  su.uT.value = simT; su.uTime.value = now / 1000; su.uPix.value = pix;
  su.uVis.value = p.vis; su.uH0.value = p.h0; su.uOpacity.value = p.sats;
  sats.points.visible = p.sats > 0.01;
  sats.linkU.uOpacity.value = p.links;
  sats.updateLinks(simT, now);
  if (p.auct > 0.05) {
    auctionClock -= dt;
    if (auctionClock <= 0) { renderBids(sats.runAuction(simT, camera)); auctionClock = 2.6; if (active === 5) audio.blip(); }
  }
  sats.updateAuction(simT, now, p.auct);
  sats.updateBeams(simT, now);

  // the event, seen from Earth
  beacon.material.opacity = clamp(p.tr, 0, 1);
  beacon.visible = p.tr > 0.01;
  const flick = p.h0 > 0.01 ? 1 + 0.35 * p.h0 * Math.sin(now * 0.013) * Math.sin(now * 0.0071) : 1;
  beacon.scale.setScalar(0.11 * flick * (0.6 + 0.4 * p.tr));
  beacon.material.color.setRGB(1, lerp(0.82, 0.97, p.h0), lerp(0.63, 1, p.h0));

  // charts
  if (active >= 1 && active <= 3) drawFade(fadeC, RM ? 1 : clamp(localT[2] * 1.6, 0.04, 1));
  if (active >= 5 && active <= 7) {
    const r = drawDx(knownC, RUN_KNOWN, RM ? 1 : clamp(localT[6] * 1.2, 0, 1), bKnown);
    if (active === 6 && r.nShown > lastKnown) { sats.fireBeam(simT, camera, 0xffb766); audio.ping(false); }
    lastKnown = r.nShown;
  }
  if (active >= 6) {
    const r = drawDx(unkC, RUN_UNKNOWN, RM ? 1 : clamp(localT[7] * 1.2, 0, 1), bUnknown);
    modeTag.classList.toggle('explore', r.explore);
    modeTag.textContent = r.explore ? 'Mode · characterize the unknown' : 'Mode · discriminate';
    if (active === 7 && r.nShown > lastUnknown) { sats.fireBeam(simT, camera, r.explore ? 0xf4f6fb : 0xffb766); audio.ping(r.explore); }
    lastUnknown = r.nShown;
  }

  // HUD
  const d = new Date(Date.UTC(2000, 0, 1, 12) + (JD0 - 2451545 + simT / 86400) * 86400000);
  hudClock.textContent = d.toISOString().slice(0, 19).replace('T', ' ');
  hudAlt.textContent = fmtDistance(camera.position.length());

  post.lens.uniforms.uTime.value = now / 1000;
  post.composer.render();
  audio.tick(dt);
  requestAnimationFrame(frame);
}
// deep links: #ch0 … #ch8 skip the intro and open a chapter
const deep = /^#ch(\d)$/.exec(location.hash);
if (deep && sections[+deep[1]]) {
  begin(false);
  const s = sections[+deep[1]];
  requestAnimationFrame(() => { lenis.scrollTo(s.offsetTop + s.offsetHeight * 0.3, { immediate: true }); snap = 4; });
}
readScroll();
requestAnimationFrame(frame);
