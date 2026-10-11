// The landing page: a live Earth with all 10,109 real Starlink orbits behind the title,
// built from the same scene modules as the film.
import './landing.css';
import * as THREE from 'three';
import { eciToScene, gmst, sunEci, NGC4993, radecToEci } from './astro.js';
import { createStars } from './scene/stars.js';
import { createEarth } from './scene/earth.js';
import { createSatellites } from './scene/satellites.js';
import { createPost } from './scene/post.js';

const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = s => document.querySelector(s);

// a solid nav once the hero scrolls away
const nav = $('.nav');
addEventListener('scroll', () => nav.classList.toggle('solid', scrollY > innerHeight * 0.6), { passive: true });

async function startGlobe() {
  const canvas = $('#hero-gl');
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: false, powerPreference: 'high-performance' }); }
  catch { canvas.remove(); return; }                         // no WebGL: the page still reads fine on black
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
  await ready;

  const scene = new THREE.Scene();
  scene.background = cube; scene.backgroundIntensity = 0.3; scene.backgroundRotation.set(0.4, 1.1, 0);
  const camera = new THREE.PerspectiveCamera(36, innerWidth / innerHeight, 0.05, 6000);
  const post = createPost(renderer, scene, camera);
  post.bloom.strength = 0.75;

  const JD0 = data.jdRef, sunE = sunEci(JD0), sun3 = eciToScene(...sunE).normalize();
  const F = eciToScene(...radecToEci(NGC4993)).normalize();
  const stars = createStars(F, 1500); stars.streaks.visible = false; scene.add(stars.points);
  stars.uniforms.uCorr.value = 0;
  const earth = createEarth(tex, sun3); scene.add(earth.group);
  const sats = createSatellites(data, radecToEci(NGC4993), sunE); scene.add(sats.points);
  $('#liveCount').textContent = data.count.toLocaleString('en-US');

  // look from the day/night boundary so city lights and sunlit oceans share the frame
  const Y = new THREE.Vector3(0, 1, 0);
  const term = new THREE.Vector3().crossVectors(sun3, Y).normalize();
  const base = term.clone().multiplyScalar(0.8).addScaledVector(sun3, 0.45).addScaledVector(Y, 0.3).normalize();

  const resize = () => {
    renderer.setSize(innerWidth, innerHeight); post.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight; camera.updateProjectionMatrix();
  };
  addEventListener('resize', resize);

  const clock = $('#liveClock');
  let simT = 0, last = performance.now(), visible = true;
  new IntersectionObserver(([e]) => (visible = e.isIntersecting)).observe($('.hero'));
  function frame(now) {
    const dt = Math.min(0.05, (now - last) / 1000); last = now;
    requestAnimationFrame(frame);
    if (!visible && scrollY > innerHeight * 1.5) return;     // the hero is far off screen: rest the GPU
    simT += dt * (RM ? 10 : 60);
    const narrow = innerWidth < 640;
    const dist = narrow ? 5.2 : 3.6;
    const yaw = (RM ? 0 : now * 0.000025);
    const dir = base.clone().applyAxisAngle(Y, yaw);
    camera.position.copy(dir).multiplyScalar(dist);
    camera.lookAt(0, 0, 0);
    // place the planet right of the title on wide screens, high on phones
    if (narrow) camera.setViewOffset(innerWidth, innerHeight, 0, innerHeight * 0.16, innerWidth, innerHeight);
    else camera.setViewOffset(innerWidth, innerHeight, -innerWidth * 0.2, 0, innerWidth, innerHeight);
    // drift a little as the page scrolls
    const sc = Math.min(1, scrollY / innerHeight);
    camera.position.multiplyScalar(1 + sc * 0.6);
    camera.updateProjectionMatrix();

    earth.setRotation(gmst(JD0 + simT / 86400));
    earth.uniforms.uCloudShift.value = simT * 2e-6;
    const su = sats.uniforms; su.uT.value = simT; su.uTime.value = now / 1000; su.uPix.value = renderer.domElement.height;
    stars.uniforms.uTime.value = now / 1000; stars.uniforms.uPix.value = renderer.domElement.height;
    post.lens.uniforms.uTime.value = now / 1000;
    post.lens.uniforms.uFade.value = sc * 0.55;
    const d = new Date(Date.UTC(2000, 0, 1, 12) + (JD0 - 2451545 + simT / 86400) * 86400000);
    clock.textContent = d.toISOString().slice(0, 16).replace('T', ' ');
    post.composer.render();
  }
  requestAnimationFrame(frame);
}
startGlobe();
