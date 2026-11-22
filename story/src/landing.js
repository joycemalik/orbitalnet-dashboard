// The home page is one continuous shot of the live Earth (10,109 real orbits).
// Scroll drives the camera through the work: a wide hero, a dive into a live
// auction, a pull-back to the whole constellation, a turn toward a new flare in
// the sky, then the fleet's links. Labels are pinned to real satellites.
import './landing.css';
import * as THREE from 'three';
import { eciToScene, gmst, sunEci, NGC4993, radecToEci } from './astro.js';
import { createStars } from './scene/stars.js';
import { createEarth } from './scene/earth.js';
import { createSatellites } from './scene/satellites.js';
import { createPost } from './scene/post.js';
import { flight } from './orbits-overlay.js';
import './cursor.js';

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = s => document.querySelector(s);
const tags = $('#tags');

/* scroll position as a continuous "shot" number: 0 hero, 1 auction, 2 twin, 3 h0, 4 fleet, 5 work */
const secs = [...document.querySelectorAll('.sec')];
function shot() {
  const mid = scrollY + innerHeight * 0.5;
  for (let i = 0; i < secs.length; i++) {
    const top = secs[i].offsetTop, h = secs[i].offsetHeight;
    if (mid < top + h) return i + Math.max(0, Math.min(1, (mid - top) / h)) - 0.5;
  }
  return secs.length - 1;
}

async function startGlobe() {
  const canvas = $('#hero-gl');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' }); }
  catch { canvas.remove(); document.body.classList.add('ready', 'landed'); return; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5));
  renderer.setSize(innerWidth, innerHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;

  const manager = new THREE.LoadingManager();
  const ready = new Promise(r => (manager.onLoad = r));
  const tl = new THREE.TextureLoader(manager);
  const srgb = t => { t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4; return t; };
  const tex = {
    day: srgb(tl.load('/textures/earth_atmos_2048.jpg')), night: srgb(tl.load('/textures/earth_lights_2048.png')),
    clouds: tl.load('/textures/earth_clouds_1024.png'), spec: tl.load('/textures/earth_specular_2048.jpg'),
  };
  tex.clouds.wrapS = THREE.RepeatWrapping;
  const cube = new THREE.CubeTextureLoader(manager).setPath('/textures/milkyway/').load(['px', 'nx', 'py', 'ny', 'pz', 'nz'].map(s => `dark-s_${s}.jpg`));
  cube.colorSpace = THREE.SRGBColorSpace;
  const data = await fetch('/data/sats.json').then(r => r.json());
  // count the orbits in while the textures finish loading
  const bootN = $('#bootN'), t0b = performance.now();
  const countIn = () => { const p = Math.min(1, (performance.now() - t0b) / 1400); bootN.textContent = Math.round(data.count * (1 - (1 - p) ** 3)).toLocaleString('en-US'); if (p < 1) requestAnimationFrame(countIn); };
  RM ? (bootN.textContent = data.count.toLocaleString('en-US')) : countIn();
  await ready;
  await new Promise(r => setTimeout(r, RM ? 0 : Math.max(0, 1500 - (performance.now() - t0b))));

  const scene = new THREE.Scene();
  scene.background = cube; scene.backgroundIntensity = 0.7; scene.backgroundRotation.set(0.4, 1.1, 0);
  const camera = new THREE.PerspectiveCamera(36, innerWidth / innerHeight, 0.01, 6000);
  const post = createPost(renderer, scene, camera);
  post.bloom.strength = 0.8;

  const JD0 = data.jdRef, sunE = sunEci(JD0), sun3 = eciToScene(...sunE).normalize();
  const F = eciToScene(...radecToEci(NGC4993)).normalize();          // where the new flare appears
  const stars = createStars(F, 1500);   // the real sky: Milky Way cube map plus a star field stars.streaks.visible = false; scene.add(stars.points);
  stars.uniforms.uCorr.value = 0;
  const earth = createEarth(tex, sun3); scene.add(earth.group);
  const sats = createSatellites(data, radecToEci(NGC4993), sunE);
  scene.add(sats.points, sats.links, sats.auction, sats.beams);
  $('#satCount').textContent = data.count.toLocaleString('en-US');

  /* the flare: a new point of light that was not in the sky before */
  const fc = document.createElement('canvas'); fc.width = fc.height = 128;
  const fx = fc.getContext('2d'), gr = fx.createRadialGradient(64, 64, 0, 64, 64, 64);
  gr.addColorStop(0, 'rgba(255,255,255,1)'); gr.addColorStop(.15, 'rgba(255,170,110,.9)'); gr.addColorStop(1, 'rgba(255,122,47,0)');
  fx.fillStyle = gr; fx.fillRect(0, 0, 128, 128);
  const flare = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(fc), transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  flare.position.copy(F).multiplyScalar(14); flare.scale.setScalar(0); scene.add(flare);

  /* camera keyframes, one per shot: direction from Earth, distance, where the planet sits on screen */
  const Y = new THREE.Vector3(0, 1, 0);
  const term = new THREE.Vector3().crossVectors(sun3, Y).normalize();
  const night = term.clone().multiplyScalar(0.75).addScaledVector(sun3, -0.6).addScaledVector(Y, 0.28).normalize();
  const side = new THREE.Vector3().crossVectors(F, Y).normalize();
  const towardF = side.clone().multiplyScalar(0.9).addScaledVector(F, -0.25).addScaledVector(Y, 0.2).normalize();   // beside Earth, the flare in frame
  const K = [
    { dir: night, dist: 3.3, ox: 0.3, oy: -0.42, look: 0 },                                         // hero
    { dir: night.clone().applyAxisAngle(Y, 0.5), dist: 1.55, ox: 0.18, oy: -0.05, look: 0 },       // auction: close to the limb
    { dir: night.clone().applyAxisAngle(Y, -0.4).add(new THREE.Vector3(0, 0.5, 0)).normalize(), dist: 6.2, ox: 0.18, oy: 0, look: 0 }, // twin: the whole shell
    { dir: towardF, dist: 2.4, ox: 0.05, oy: 0.1, look: 1 },                                       // h0: turn to the flare
    { dir: night.clone().applyAxisAngle(Y, 1.1), dist: 2.3, ox: 0.2, oy: -0.1, look: 0 },          // fleet
    { dir: night, dist: 4.4, ox: 0.4, oy: -0.5, look: 0 },                                          // work
  ];
  const ease = x => x * x * (3 - 2 * x);
  const cam = { dir: night.clone(), dist: 3.3, ox: 0.3, oy: -0.42, look: 0 };
  const tgt = new THREE.Vector3(), lookP = new THREE.Vector3();

  const resize = () => {
    renderer.setSize(innerWidth, innerHeight); post.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  };
  addEventListener('resize', resize);

  /* labels pinned to satellites */
  const pool = [...Array(8)].map(() => { const d = document.createElement('div'); d.className = 'tag'; tags.appendChild(d); return d; });
  const v = new THREE.Vector3();
  function pin(el, k, text, cls) {
    sats.sceneAt(k, simT, v);
    const facing = v.dot(camera.position.clone().sub(v)) > 0;
    v.project(camera);
    const on = facing && Math.abs(v.x) < 0.95 && Math.abs(v.y) < 0.9 && v.z < 1;
    el.style.opacity = on ? 1 : 0;
    el.className = 'tag ' + (cls || '');
    el.style.transform = `translate(${(v.x + 1) / 2 * innerWidth}px, ${(1 - v.y) / 2 * innerHeight}px)`;
    el.textContent = text;
  }

  const clock = $('#liveClock');
  let simT = 0, last = performance.now(), visible = true, auctionClock = 0, beamClock = 0, bids = [], belief = 0;
  document.addEventListener('visibilitychange', () => { visible = !document.hidden; last = performance.now(); });
  const c0 = new THREE.Vector3(), edge = new THREE.Vector3();

  function frame(now) {
    requestAnimationFrame(frame);
    if (!visible) return;
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    const s = shot(), i = Math.max(0, Math.min(K.length - 2, Math.floor(s))), f = ease(Math.max(0, Math.min(1, s - i)));
    const node = Math.round(Math.max(0, s)); flight.node = node;

    // time runs faster when we pull back to show the whole constellation
    const speed = RM ? 10 : 600 * (1 + 4 * Math.max(0, 1 - Math.abs(s - 2))) * (1 - 0.8 * Math.max(0, 1 - Math.abs(s - 1)));   // fast enough to see the planet turn
    simT += dt * speed;

    // camera: blend the two keyframes around the scroll position, then smooth
    const A = K[i], B = K[i + 1];
    tgt.copy(A.dir).lerp(B.dir, f).normalize();
    const want = { dist: A.dist + (B.dist - A.dist) * f, ox: A.ox + (B.ox - A.ox) * f, oy: A.oy + (B.oy - A.oy) * f, look: A.look + (B.look - A.look) * f };
    const k = RM ? 1 : 0.06;
    cam.dir.lerp(tgt, k).normalize();
    for (const p of ['dist', 'ox', 'oy', 'look']) cam[p] += (want[p] - cam[p]) * k;
    const narrow = innerWidth < 980;
    // opening: fly in from deep space, swinging round to the night side
    const ip = RM ? 1 : Math.min(1, (now - introT0) / 4200), ie = 1 - (1 - ip) ** 4;
    const swing = cam.dir.clone().applyAxisAngle(Y, (1 - ie) * 1.2);
    camera.position.copy(swing).multiplyScalar(cam.dist * (narrow ? 1.35 : 1) * (1 + (1 - ie) * 9));
    lookP.set(0, 0, 0).lerp(F.clone().multiplyScalar(4), cam.look * 0.6);
    camera.lookAt(lookP);
    if (narrow) camera.setViewOffset(innerWidth, innerHeight, innerWidth * cam.ox * 0.2, -innerHeight * (cam.oy * 0.5 + 0.2), innerWidth, innerHeight);
    else camera.setViewOffset(innerWidth, innerHeight, innerWidth * cam.ox, innerHeight * cam.oy, innerWidth, innerHeight);
    camera.updateProjectionMatrix();

    // what the satellites are doing in this shot
    const near = n => Math.max(0, 1 - Math.abs(s - n) * 1.6);
    const wA = near(1), wH = near(3), wL = near(4);
    flight.h0 += (wH - flight.h0) * 0.05;
    sats.uniforms.uH0.value = flight.h0;
    sats.linkU.uOpacity.value = wL; sats.updateLinks(simT, now);

    if (wA > 0.05) { auctionClock -= dt; if (auctionClock <= 0) { bids = sats.runAuction(simT, camera); auctionClock = 2.6; renderBids(bids); } }
    sats.updateAuction(simT, now, wA);
    if (wH > 0.4) { beamClock -= dt; if (beamClock <= 0) { sats.fireBeam(simT, camera, 0xff7a2f); beamClock = 0.7; belief = Math.min(6, belief + 1); renderBelief(belief); } }
    else if (wH < 0.1 && belief) { belief = 0; renderBelief(0); }
    sats.updateBeams(simT, now);
    flare.scale.setScalar(wH * (1.6 + Math.sin(now * 0.004) * 0.3));

    // pinned labels: the auction's bidders, otherwise none
    pool.forEach((el, j) => {
      if (wA > 0.3 && bids[j]) pin(el, bids[j].k, `${bids[j].name} · ${bids[j].score.toFixed(2)}`, j === 0 ? 'win' : '');
      else el.style.opacity = 0;
    });

    // the 2D orbit rings only belong to the wide views
    const wide = Math.max(near(0), near(5));
    flight.arcs = wide;
    c0.set(0, 0, 0).project(camera); edge.set(0, 1, 0).project(camera);
    flight.place((c0.x + 1) / 2 * innerWidth, (1 - c0.y) / 2 * innerHeight, Math.abs((edge.y - c0.y) / 2 * innerHeight), wide);

    earth.setRotation(gmst(JD0 + simT / 86400));
    earth.uniforms.uCloudShift.value = simT * 2e-6;
    const su = sats.uniforms; su.uT.value = simT; su.uTime.value = now / 1000; su.uPix.value = renderer.domElement.height;
    stars.uniforms.uTime.value = now / 1000; stars.uniforms.uPix.value = renderer.domElement.height;
    post.lens.uniforms.uTime.value = now / 1000;
    post.lens.uniforms.uFade.value = 0.2;
    const d = new Date(Date.UTC(2000, 0, 1, 12) + (JD0 - 2451545 + simT / 86400) * 86400000);
    clock.textContent = d.toISOString().slice(0, 16).replace('T', ' ');
    post.composer.render();
  }
  document.body.classList.add('ready');
  introT0 = performance.now();
  setTimeout(() => document.body.classList.add('landed'), RM ? 0 : 2600);
  requestAnimationFrame(frame);
}
let introT0 = 0;

/* the live bid table beside the auction */
function renderBids(b) {
  const el = $('#bids'); if (!el) return;
  el.innerHTML = b.slice(0, 5).map((x, i) => `<li class="${i ? '' : 'win'}"><span>${x.name}</span><i style="--w:${(x.score * 100).toFixed(0)}%"></i><b>${x.score.toFixed(2)}</b></li>`).join('');
}
/* the belief strip beside the flare: each new look moves probability toward h0 (illustrative) */
function renderBelief(n) {
  const el = $('#belief'); if (!el) return;
  const like = [.2, .08, .06, .05]; let c = [.225, .225, .225, .225, .1];
  for (let s = 0; s < n; s++) { c = c.map((p, j) => p * (j < 4 ? like[j] : .35)); const t = c.reduce((a, b) => a + b); c = c.map(p => p / t); }
  el.innerHTML = ['A', 'B', 'C', 'D', 'h₀'].map((l, j) => `<li class="${j === 4 ? 'h0' : ''}"><span>${l}</span><i style="--w:${(c[j] * 100).toFixed(0)}%"></i><b>${(c[j] * 100).toFixed(0)}%</b></li>`).join('');
}
renderBelief(0);
startGlobe();
