import * as THREE from 'three';
import { glowTexture } from './textures.js';
import { mulberry } from './stars.js';

// Timeline of the GW170817 re-enactment, in seconds after trigger.
export const CHIRP = 2.8;        // final inspiral (compressed; the real signal swept ~100 s in band)
export const GRB_DELAY = 1.7;    // gamma rays arrived 1.7 s after the merger. That part is real.

const OMEGA0 = 2.2;              // idle orbital angular speed

// Orbital phase of the binary. During a chirp the frequency rises as tau^(-3/8),
// the leading-order post-Newtonian result, so the phase integrates analytically.
function orbitPhase(t) {
  if (t < 0) return OMEGA0 * t;
  const p = Math.min(t / CHIRP, 0.985);
  let ph = OMEGA0 * CHIRP * 1.6 * (1 - Math.pow(1 - p, 0.625));
  if (t > CHIRP * 0.985) ph += OMEGA0 / Math.pow(0.015, 0.375) * (t - CHIRP * 0.985);
  return ph;
}

export function createMerger() {
  const group = new THREE.Group();
  const glow = glowTexture();

  /* ---- spacetime fabric with quadrupole gravitational waves ---- */
  const gridU = {
    uT: { value: -1000 }, uC: { value: 26 }, uOm0: { value: OMEGA0 }, uChirp: { value: CHIRP },
    uMass: { value: 1 }, uOpacity: { value: 1 },
  };
  const grid = new THREE.Mesh(
    new THREE.PlaneGeometry(260, 260, 320, 320).rotateX(-Math.PI / 2),
    new THREE.ShaderMaterial({
      uniforms: gridU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
      vertexShader: /* glsl */`
        uniform float uT, uC, uOm0, uChirp, uMass;
        varying vec2 vXZ; varying float vH; varying float vR;
        float phaseAt(float t){
          if (t < 0.0) return uOm0 * t;
          float p = min(t / uChirp, 0.985);
          float ph = uOm0 * uChirp * 1.6 * (1.0 - pow(1.0 - p, 0.625));
          if (t > uChirp * 0.985) ph += uOm0 / pow(0.015, 0.375) * (t - uChirp * 0.985);
          return ph;
        }
        float ampAt(float t){
          if (t < 0.0) return 0.35;
          if (t < uChirp) { float p = t / uChirp; return 0.35 + 3.2 * p * p * p; }
          return 3.55 * exp(-(t - uChirp) * 2.2);
        }
        void main(){
          vec3 p = position;
          float r = length(p.xz);
          float phi = atan(p.z, p.x);
          float te = uT - r / uC;                     // retarded time
          float h = ampAt(te) * cos(2.0 * phi - 2.0 * phaseAt(te)) / (1.0 + r * 0.035);
          h *= smoothstep(2.0, 10.0, r);
          float well = -uMass * 7.0 / (1.0 + pow(r / 4.0, 2.0));
          p.y += h + well;
          vXZ = p.xz; vH = h; vR = r;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(p, 1.0);
        }`,
      fragmentShader: /* glsl */`
        uniform float uOpacity; varying vec2 vXZ; varying float vH; varying float vR;
        void main(){
          vec2 q = vXZ / 4.0;
          vec2 g = abs(fract(q - 0.5) - 0.5) / fwidth(q);
          float line = 1.0 - min(min(g.x, g.y), 1.0);
          float fade = 1.0 - smoothstep(55.0, 125.0, vR);
          vec3 base = mix(vec3(0.10, 0.22, 0.55), vec3(0.45, 0.85, 1.0), clamp(abs(vH) * 0.6, 0.0, 1.0));
          float a = line * fade * (0.35 + abs(vH) * 0.5) * uOpacity;
          gl_FragColor = vec4(base * a, 1.0);
        }`,
    }));
  grid.position.y = -5;
  grid.frustumCulled = false;
  group.add(grid);

  /* ---- the two neutron stars ---- */
  const starMat = new THREE.MeshBasicMaterial({ color: new THREE.Color(0.9, 0.95, 1.0).multiplyScalar(4) });
  const stars = [0, 1].map(() => {
    const m = new THREE.Mesh(new THREE.SphereGeometry(0.55, 32, 16), starMat);
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: 0x9fc4ff, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true }));
    s.scale.setScalar(7); m.add(s); group.add(m); return m;
  });

  /* ---- remnant + gamma-ray flash ---- */
  const remnant = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: 0xffd6a8, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 }));
  group.add(remnant);
  const flash = new THREE.Sprite(new THREE.SpriteMaterial({ map: glow, color: 0xffffff, blending: THREE.AdditiveBlending, depthWrite: false, transparent: true, opacity: 0 }));
  group.add(flash);

  // relativistic jets along the orbital axis
  const jetMat = new THREE.ShaderMaterial({
    uniforms: { uA: { value: 0 } }, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide,
    vertexShader: `varying float vY; void main(){ vY = uv.y; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);}`,
    fragmentShader: `uniform float uA; varying float vY; void main(){ float a = pow(vY, 1.5) * uA; gl_FragColor = vec4(vec3(0.75,0.85,1.0)*a, 1.0);}`,
  });
  const jets = [1, -1].map(sg => {
    const g = new THREE.CylinderGeometry(0.15, 2.4, 70, 32, 1, true).translate(0, -35, 0);
    const m = new THREE.Mesh(g, jetMat); m.rotation.x = sg > 0 ? Math.PI : 0; group.add(m); return m;
  });

  /* ---- the kilonova: a fast blue polar outflow and a slower red equatorial one ---- */
  const rnd = mulberry(5), K = 18000;
  const dir = new Float32Array(K * 3), spd = new Float32Array(K), kind = new Float32Array(K), sd = new Float32Array(K);
  const v = new THREE.Vector3();
  for (let i = 0; i < K; i++) {
    v.randomDirection();
    const polar = Math.abs(v.y);
    const blue = polar > 0.55 ? (rnd() < 0.85 ? 1 : 0) : (rnd() < 0.08 ? 1 : 0);
    if (!blue) { v.y *= 0.55; v.normalize(); }
    dir.set([v.x, v.y, v.z], i * 3);
    spd[i] = blue ? 0.6 + rnd() * 0.4 : 0.25 + rnd() * 0.35;   // blue ejecta ~0.3c, red ~0.1c
    kind[i] = blue; sd[i] = rnd();
  }
  const kg = new THREE.BufferGeometry();
  kg.setAttribute('position', new THREE.BufferAttribute(new Float32Array(K * 3), 3));
  kg.setAttribute('aDir', new THREE.BufferAttribute(dir, 3));
  kg.setAttribute('aSpd', new THREE.BufferAttribute(spd, 1));
  kg.setAttribute('aKind', new THREE.BufferAttribute(kind, 1));
  kg.setAttribute('aSeed', new THREE.BufferAttribute(sd, 1));
  const kU = { uAge: { value: -1 }, uPix: { value: 600 }, uOpacity: { value: 1 } };
  const kilonova = new THREE.Points(kg, new THREE.ShaderMaterial({
    uniforms: kU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute vec3 aDir; attribute float aSpd; attribute float aKind; attribute float aSeed;
      uniform float uAge; uniform float uPix;
      varying vec3 vC; varying float vA;
      void main(){
        float age = max(uAge, 0.0);
        float R = 26.0 * (1.0 - exp(-age / 5.0)) + age * 0.9;
        vec3 p = aDir * aSpd * R;
        p += 0.6 * aSpd * R * 0.06 * vec3(sin(aSeed*91.0+age*0.3), cos(aSeed*53.0+age*0.27), sin(aSeed*17.0-age*0.21));
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;
        gl_PointSize = clamp(1.6 * uPix / -mv.z, 1.0, 6.0);
        vec3 blue = vec3(0.55, 0.75, 1.0) * exp(-age / 4.0) * 1.6;
        vec3 red  = vec3(1.0, 0.36, 0.14) * smoothstep(0.0, 3.0, age) * exp(-age / 40.0) * 1.3;
        vC = mix(red, blue, aKind);
        vA = uAge < 0.0 ? 0.0 : 1.0;
      }`,
    fragmentShader: /* glsl */`
      uniform float uOpacity; varying vec3 vC; varying float vA;
      void main(){ float r = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.0, r);
        gl_FragColor = vec4(vC * a * vA * uOpacity, 1.0); }`,
  }));
  kilonova.frustumCulled = false;
  group.add(kilonova);

  let t0 = -1e9;
  const state = { phase: -1 };

  function trigger(now) { t0 = now; }

  // ageBoost lets scrolling push the debris forward in time (chapter II).
  function update(now, { opacity = 1, ageBoost = 0, pix = 600 } = {}) {
    const t = (now - t0) / 1000;
    const active = t >= 0 && t < 600;
    const tt = active ? t : -1000 + (now / 1000) % 1000;    // idle waves when never triggered
    state.phase = active ? t : -1;
    gridU.uT.value = tt; gridU.uOpacity.value = opacity;
    kU.uPix.value = pix; uOpacityAll(opacity);

    // binary
    const p = active ? Math.min(t / CHIRP, 1) : 0;
    const merged = active && t >= CHIRP;
    const sep = merged ? 0 : 7 * Math.pow(1 - Math.min(p, 0.985), 0.25);  // a ~ tau^(1/4)
    const psi = orbitPhase(tt);
    stars[0].position.set(Math.cos(psi) * sep / 2, 0, Math.sin(psi) * sep / 2);
    stars[1].position.set(-Math.cos(psi) * sep / 2, 0, -Math.sin(psi) * sep / 2);
    stars.forEach(s => (s.visible = !merged && opacity > 0.01));

    // remnant glow, gamma-ray flash and jets
    const sinceGrb = active ? t - CHIRP - GRB_DELAY : -1;
    remnant.material.opacity = merged ? opacity * (0.7 + (sinceGrb > 0 ? 0.3 * Math.exp(-sinceGrb / 6) : 0)) : 0;
    remnant.scale.setScalar(merged ? 9 + (sinceGrb > 0 ? 10 * Math.exp(-sinceGrb / 3) : 2 * Math.sin(t * 20)) : 1);
    const fl = sinceGrb > 0 ? Math.exp(-sinceGrb * 1.4) : 0;
    flash.material.opacity = fl * opacity; flash.scale.setScalar(20 + 160 * fl);
    jetMat.uniforms.uA.value = sinceGrb > 0 ? Math.exp(-sinceGrb * 0.45) * 1.4 * opacity : 0;
    jets.forEach(j => (j.visible = jetMat.uniforms.uA.value > 0.01));
    kU.uAge.value = sinceGrb > 0 ? sinceGrb * 1.4 + ageBoost : (ageBoost > 0 && !active ? ageBoost : -1);
    gridU.uMass.value = merged ? 1.25 : 1;
    return { flash: fl, sinceGrb, t: active ? t : -1 };
  }
  function uOpacityAll(o) { kU.uOpacity.value = o; group.visible = o > 0.003; }

  return { group, trigger, update, state };
}
