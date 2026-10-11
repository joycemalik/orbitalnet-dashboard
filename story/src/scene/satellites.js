import * as THREE from 'three';
import { MU, RE_KM } from '../astro.js';
import { ringTexture } from './textures.js';

const hash = n => { n = Math.imul(n ^ 61 ^ (n >>> 16), 9); n ^= n >>> 4; n = Math.imul(n, 0x27d4eb2d); n ^= n >>> 15; return (n >>> 0) / 4294967296; };

// Every satellite is propagated on the GPU as a circular orbit from its TLE elements.
export function createSatellites(data, tgtEci, sunEci) {
  const N = data.count, el = data.el;
  const aEl = new Float32Array(N * 4), aR = new Float32Array(N), aShell = new Float32Array(N), aSeed = new Float32Array(N);
  const num = new Int32Array(N), batt = new Float32Array(N);
  for (let k = 0; k < N; k++) {
    const b = k * 5, inc = el[b + 1] / 10, n = el[b + 4] / 1e4, w = n * 2 * Math.PI / 86400;
    num[k] = el[b];
    aEl.set([inc * Math.PI / 180, el[b + 2] / 10 * Math.PI / 180, el[b + 3] / 10 * Math.PI / 180, w], k * 4);
    aR[k] = Math.cbrt(MU / (w * w)) / RE_KM;
    aShell[k] = inc < 48 ? 1 : inc < 60 ? 0 : inc < 80 ? 2 : 3;
    aSeed[k] = hash(k * 7 + 1);
    batt[k] = 0.35 + 0.65 * hash(el[b] * 2654435761);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(N * 3), 3));
  geo.setAttribute('aEl', new THREE.BufferAttribute(aEl, 4));
  geo.setAttribute('aR', new THREE.BufferAttribute(aR, 1));
  geo.setAttribute('aShell', new THREE.BufferAttribute(aShell, 1));
  geo.setAttribute('aSeed', new THREE.BufferAttribute(aSeed, 1));

  const uniforms = {
    uT: { value: 0 }, uTgt: { value: new THREE.Vector3(...tgtEci) }, uSunE: { value: new THREE.Vector3(...sunEci) },
    uVis: { value: 0 }, uOpacity: { value: 1 }, uPix: { value: 600 }, uSize: { value: 1 }, uH0: { value: 0 }, uTime: { value: 0 },
  };
  const points = new THREE.Points(geo, new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute vec4 aEl; attribute float aR; attribute float aShell; attribute float aSeed;
      uniform float uT, uVis, uPix, uSize, uH0, uTime; uniform vec3 uTgt, uSunE;
      varying vec3 vC; varying float vA;
      void main(){
        float u = aEl.z + aEl.w * uT;
        float ci = cos(aEl.x), si = sin(aEl.x), cO = cos(aEl.y), sO = sin(aEl.y), cu = cos(u), su = sin(u);
        vec3 e = aR * vec3(cO*cu - sO*su*ci, sO*cu + cO*su*ci, su*si);    // ECI
        vec3 p = vec3(e.x, e.z, -e.y);                                      // scene
        vec4 mv = modelViewMatrix * vec4(p, 1.0);
        gl_Position = projectionMatrix * mv;

        // can it see the target? (line of sight not blocked by the Earth)
        float pd = dot(e, uTgt);
        float see = (pd >= 0.0 || dot(e,e) - pd*pd > 1.0) ? 1.0 : 0.0;
        // is it sunlit or inside Earth's shadow cylinder?
        float ps = dot(e, uSunE);
        float lit = (ps >= 0.0 || dot(e,e) - ps*ps > 1.0) ? 1.0 : 0.28;

        vec3 shellC = aShell < 0.5 ? vec3(0.86,0.92,1.0) : aShell < 1.5 ? vec3(0.62,0.88,1.0) : aShell < 2.5 ? vec3(0.82,0.72,1.0) : vec3(1.0,0.82,0.62);
        vec3 visC = see > 0.5 ? vec3(1.0, 0.66, 0.30) * 1.3 : vec3(0.05, 0.06, 0.09);
        vC = mix(shellC * lit * 0.55, visC, uVis);
        vC = mix(vC, vec3(0.9, 0.95, 1.0) * (0.6 + 0.6 * sin(uTime * 3.0 + aSeed * 40.0)), uH0 * step(0.93, aSeed));
        vA = 1.0;
        float s = uSize * uPix * 0.007 / max(-mv.z, 0.001);
        gl_PointSize = clamp(s, 1.3, 7.0) * (see > 0.5 ? 1.0 + 0.35 * uVis : 1.0);
      }`,
    fragmentShader: /* glsl */`
      uniform float uOpacity; varying vec3 vC; varying float vA;
      void main(){ float r = length(gl_PointCoord - 0.5); float a = smoothstep(0.5, 0.05, r);
        gl_FragColor = vec4(vC * a * vA * uOpacity, 1.0); }`,
  }));
  points.frustumCulled = false;

  // CPU copy of the same propagation, for links, bids and beams
  const sceneAt = (k, t, out) => {
    const b = k * 4, u = aEl[b + 2] + aEl[b + 3] * t, ci = Math.cos(aEl[b]), si = Math.sin(aEl[b]);
    const cO = Math.cos(aEl[b + 1]), sO = Math.sin(aEl[b + 1]), cu = Math.cos(u), su = Math.sin(u), r = aR[k];
    const x = r * (cO * cu - sO * su * ci), y = r * (sO * cu + cO * su * ci), z = r * su * si;
    return out.set(x, z, -y);
  };
  const seesTarget = (p) => { // p in scene coords
    const t = uniforms.uTgt.value, e = [p.x, -p.z, p.y];
    const pd = e[0] * t.x + e[1] * t.y + e[2] * t.z, rr = e[0] ** 2 + e[1] ** 2 + e[2] ** 2;
    return pd >= 0 || rr - pd * pd > 1;
  };

  /* ---- inter-satellite links between neighbours in the same orbital plane ---- */
  const pairs = [];
  {
    const idx = [...Array(N).keys()].sort((a, b) =>
      (aShell[a] - aShell[b]) || (Math.round(aEl[a * 4 + 1] * 40) - Math.round(aEl[b * 4 + 1] * 40)) || (aEl[a * 4 + 2] - aEl[b * 4 + 2]));
    for (let i = 1; i < idx.length && pairs.length < 7000; i++) {
      const a = idx[i - 1], b = idx[i];
      if (aShell[a] !== aShell[b] || Math.abs(aEl[a * 4 + 1] - aEl[b * 4 + 1]) > 0.03 || Math.abs(aR[a] - aR[b]) > 0.01) continue;
      const du = Math.abs(aEl[a * 4 + 2] - aEl[b * 4 + 2]); if (du > 0.35 || du < 0.004) continue;
      pairs.push(a, b);
    }
  }
  const P = pairs.length / 2;
  const lgeo = new THREE.BufferGeometry();
  const lpos = new Float32Array(P * 6), lalpha = new Float32Array(P * 2);
  lgeo.setAttribute('position', new THREE.BufferAttribute(lpos, 3));
  lgeo.setAttribute('aA', new THREE.BufferAttribute(lalpha, 1));
  const linkU = { uOpacity: { value: 0 } };
  const links = new THREE.LineSegments(lgeo, new THREE.ShaderMaterial({
    uniforms: linkU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `attribute float aA; varying float vA; void main(){ vA = aA; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);} `,
    fragmentShader: `uniform float uOpacity; varying float vA; void main(){ gl_FragColor = vec4(vec3(0.45,0.82,1.0) * vA * uOpacity, 1.0);} `,
  }));
  links.frustumCulled = false;
  const va = new THREE.Vector3(), vb = new THREE.Vector3();
  function updateLinks(t, now) {
    if (linkU.uOpacity.value < 0.01) { links.visible = false; return; }
    links.visible = true;
    const epoch = Math.floor(now / 1600);
    for (let i = 0; i < P; i++) {
      sceneAt(pairs[i * 2], t, va); sceneAt(pairs[i * 2 + 1], t, vb);
      lpos.set([va.x, va.y, va.z, vb.x, vb.y, vb.z], i * 6);
      const up = va.distanceToSquared(vb) < 0.012 && hash(i * 7919 + epoch * 131) > 0.3 ? 0.3 : 0;
      lalpha[i * 2] = up; lalpha[i * 2 + 1] = up;
    }
    lgeo.attributes.position.needsUpdate = true; lgeo.attributes.aA.needsUpdate = true;
  }

  /* ---- the auction: bidders, leader, and bid packets ---- */
  const ringTex = ringTexture();
  const auction = new THREE.Group();
  const rings = Array.from({ length: 7 }, (_, i) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: ringTex, color: i ? 0xffb766 : 0xffd9a8, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending, sizeAttenuation: false }));
    s.scale.setScalar(i ? 0.022 : 0.04); auction.add(s); return s;
  });
  const bidGeo = new THREE.BufferGeometry();
  bidGeo.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6 * 2 * 3 + 6), 3));
  const bidLines = new THREE.LineSegments(bidGeo, new THREE.LineBasicMaterial({ color: 0xffb766, transparent: true, opacity: 0.55, blending: THREE.AdditiveBlending, depthWrite: false }));
  bidLines.frustumCulled = false; auction.add(bidLines);
  const packets = new THREE.Points(new THREE.BufferGeometry().setAttribute('position', new THREE.BufferAttribute(new Float32Array(6 * 3), 3)),
    new THREE.PointsMaterial({ color: 0xffe2b8, size: 4, sizeAttenuation: false, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false }));
  packets.frustumCulled = false; auction.add(packets);
  auction.visible = false;
  let bidders = [];

  function runAuction(t, camera, sampleStride = 5) {
    const v = new THREE.Vector3(), cand = [];
    for (let k = (Math.random() * sampleStride) | 0; k < N; k += sampleStride) {
      sceneAt(k, t, v);
      if (!seesTarget(v)) continue;
      // in front of the planet as seen from the camera, and on screen
      const toCam = camera.position.clone().sub(v);
      if (v.dot(toCam) < 0) continue;
      const ndc = v.clone().project(camera);
      if (Math.abs(ndc.x) > 0.8 || Math.abs(ndc.y) > 0.75) continue;
      cand.push(k);
    }
    const picks = new Set(); for (let i = 0; i < 12 && cand.length; i++) picks.add(cand[(Math.random() * cand.length) | 0]);
    const tg = uniforms.uTgt.value;
    bidders = [...picks].map(k => {
      sceneAt(k, t, v); const e = [v.x, -v.z, v.y], r = Math.hypot(...e);
      const geo = Math.min(1, Math.max(0, 0.5 + 0.5 * (e[0] * tg.x + e[1] * tg.y + e[2] * tg.z) / r));
      return { k, name: 'STARLINK-' + num[k], geo, bat: batt[k], score: 0.55 * geo + 0.45 * batt[k] };
    }).sort((a, b) => b.score - a.score).slice(0, 6);
    return bidders;
  }
  function updateAuction(t, now, opacity) {
    auction.visible = opacity > 0.01 && bidders.length > 0;
    if (!auction.visible) return;
    const pos = bidders.map(b => sceneAt(b.k, t, new THREE.Vector3()));
    rings.forEach((r, i) => { r.visible = i < pos.length; if (r.visible) { r.position.copy(pos[i]); r.material.opacity = opacity * (i ? 0.7 : 1); } });
    if (pos.length) rings[0].scale.setScalar(0.034 + 0.008 * Math.sin(now * 0.006));
    const lp = bidGeo.attributes.position.array, pp = packets.geometry.attributes.position.array;
    lp.fill(0); pp.fill(0);
    for (let i = 1; i < pos.length; i++) {
      lp.set([pos[i].x, pos[i].y, pos[i].z, pos[0].x, pos[0].y, pos[0].z], (i - 1) * 6);
      const q = (now * 0.0006 + i * 0.19) % 1;
      pp.set([pos[i].x + (pos[0].x - pos[i].x) * q, pos[i].y + (pos[0].y - pos[i].y) * q, pos[i].z + (pos[0].z - pos[i].z) * q], i * 3);
    }
    // leader's beam toward the event
    if (pos.length) {
      const d = new THREE.Vector3(tg0.x, tg0.y, tg0.z);
      lp.set([pos[0].x, pos[0].y, pos[0].z, pos[0].x + d.x * 6, pos[0].y + d.y * 6, pos[0].z + d.z * 6], 5 * 6);
    }
    bidGeo.attributes.position.needsUpdate = true; packets.geometry.attributes.position.needsUpdate = true;
    bidLines.material.opacity = 0.55 * opacity; packets.material.opacity = opacity;
  }
  const tg0 = (() => { const t = uniforms.uTgt.value; return new THREE.Vector3(t.x, t.z, -t.y); })();

  /* ---- observation beams: a satellite turning to look ---- */
  const beamU = [];
  const beams = new THREE.Group();
  for (let i = 0; i < 5; i++) {
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(6), 3));
    g.setAttribute('aT', new THREE.BufferAttribute(new Float32Array([0, 1]), 1));
    const u = { uA: { value: 0 }, uC: { value: new THREE.Color(0xffb766) } };
    const l = new THREE.Line(g, new THREE.ShaderMaterial({
      uniforms: u, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `attribute float aT; varying float vT; void main(){ vT = aT; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);} `,
      fragmentShader: `uniform float uA; uniform vec3 uC; varying float vT; void main(){ gl_FragColor = vec4(uC * (1.0 - vT) * uA * 1.6, 1.0);} `,
    }));
    l.frustumCulled = false; beams.add(l); beamU.push({ u, l, k: -1, born: -1e9 });
  }
  let beamNext = 0;
  function fireBeam(t, camera, color) {
    const v = new THREE.Vector3();
    for (let tries = 0; tries < 400; tries++) {
      const k = (Math.random() * N) | 0; sceneAt(k, t, v);
      if (!seesTarget(v) || v.dot(camera.position.clone().sub(v)) < 0) continue;
      const b = beamU[beamNext++ % beamU.length]; b.k = k; b.born = performance.now(); b.u.uC.value.set(color); return;
    }
  }
  function updateBeams(t, now) {
    const v = new THREE.Vector3();
    beamU.forEach(b => {
      const age = (now - b.born) / 1000; const a = age < 0 ? 0 : Math.exp(-age * 0.8) * Math.min(1, age * 6);
      b.u.uA.value = a; b.l.visible = a > 0.01 && b.k >= 0;
      if (!b.l.visible) return;
      sceneAt(b.k, t, v);
      b.l.geometry.attributes.position.array.set([v.x, v.y, v.z, v.x + tg0.x * 40, v.y + tg0.y * 40, v.z + tg0.z * 40]);
      b.l.geometry.attributes.position.needsUpdate = true;
    });
  }

  return {
    points, links, auction, beams, uniforms, linkU, count: N,
    updateLinks, runAuction, updateAuction, fireBeam, updateBeams,
  };
}
