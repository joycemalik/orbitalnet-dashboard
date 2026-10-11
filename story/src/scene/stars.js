import * as THREE from 'three';

// A 3D star field with real depth: a wide shell around Earth plus a corridor of
// stars along the light's path from the merger, so the camera flies *through* them.
export function createStars(dirToMerger, mergerDist) {
  const rnd = mulberry(23);
  const pos = [], col = [], size = [], seed = [];
  const tint = () => {
    const t = rnd();
    if (t < 0.15) return [0.7, 0.8, 1.0];      // hot blue
    if (t < 0.75) return [1.0, 0.97, 0.92];    // white
    if (t < 0.92) return [1.0, 0.85, 0.65];    // yellow-orange
    return [1.0, 0.65, 0.5];                   // red dwarf
  };
  const push = (p, s) => { pos.push(p.x, p.y, p.z); col.push(...tint()); size.push(s); seed.push(rnd()); };

  // shell
  for (let i = 0; i < 5000; i++) {
    const v = new THREE.Vector3().randomDirection().multiplyScalar(160 + Math.pow(rnd(), 0.6) * 2600);
    push(v, 0.6 + Math.pow(rnd(), 6) * 4.5);
  }
  // corridor along the light path
  const f = dirToMerger.clone().normalize();
  const side = new THREE.Vector3().crossVectors(f, new THREE.Vector3(0, 1, 0)).normalize();
  const up = new THREE.Vector3().crossVectors(side, f);
  for (let i = 0; i < 4500; i++) {
    const along = 40 + rnd() * (mergerDist + 300);
    const r = 6 + Math.pow(rnd(), 0.5) * 160, a = rnd() * Math.PI * 2;
    const v = f.clone().multiplyScalar(along).addScaledVector(side, Math.cos(a) * r).addScaledVector(up, Math.sin(a) * r);
    push(v, 0.5 + Math.pow(rnd(), 5) * 3.5);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
  geo.setAttribute('aColor', new THREE.Float32BufferAttribute(col, 3));
  geo.setAttribute('aSize', new THREE.Float32BufferAttribute(size, 1));
  geo.setAttribute('aSeed', new THREE.Float32BufferAttribute(seed, 1));

  const uniforms = { uTime: { value: 0 }, uPix: { value: 600 }, uOpacity: { value: 1 } };
  const points = new THREE.Points(geo, new THREE.ShaderMaterial({
    uniforms, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute vec3 aColor; attribute float aSize; attribute float aSeed;
      uniform float uTime; uniform float uPix;
      varying vec3 vColor; varying float vA;
      void main(){
        vec4 mv = modelViewMatrix * vec4(position,1.0);
        gl_Position = projectionMatrix * mv;
        float d = -mv.z;
        float s = aSize * uPix / max(d, 0.001) * 0.9;
        float tw = 0.75 + 0.25 * sin(uTime * (1.2 + aSeed * 3.0) + aSeed * 60.0);
        vA = clamp(s, 0.25, 1.0) * tw;
        gl_PointSize = clamp(s, 1.4, 14.0);
        vColor = aColor;
      }`,
    fragmentShader: /* glsl */`
      uniform float uOpacity; varying vec3 vColor; varying float vA;
      void main(){
        vec2 c = gl_PointCoord - 0.5; float r = length(c);
        float core = smoothstep(0.5, 0.0, r); core = pow(core, 2.2);
        gl_FragColor = vec4(vColor * core * vA * uOpacity, 1.0);
      }`,
  }));
  points.frustumCulled = false;

  // warp streaks: the same stars as line segments whose tails trail the camera's velocity
  const lp = new Float32Array(pos.length * 2), tail = new Float32Array(pos.length / 3 * 2);
  for (let i = 0; i < pos.length / 3; i++) {
    for (let k = 0; k < 2; k++) { lp.set(pos.slice(i * 3, i * 3 + 3), (i * 2 + k) * 3); tail[i * 2 + k] = k; }
  }
  const lgeo = new THREE.BufferGeometry();
  lgeo.setAttribute('position', new THREE.BufferAttribute(lp, 3));
  lgeo.setAttribute('aTail', new THREE.BufferAttribute(tail, 1));
  const lu = { uVel: { value: new THREE.Vector3() }, uWarp: { value: 0 } };
  const streaks = new THREE.LineSegments(lgeo, new THREE.ShaderMaterial({
    uniforms: lu, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: /* glsl */`
      attribute float aTail; uniform vec3 uVel; varying float vT;
      void main(){ vT = aTail; vec3 p = position + uVel * aTail;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(p,1.0); }`,
    fragmentShader: /* glsl */`
      uniform float uWarp; varying float vT;
      void main(){ gl_FragColor = vec4(vec3(0.75,0.85,1.0) * (1.0 - vT) * uWarp, 1.0); }`,
  }));
  streaks.frustumCulled = false;

  return { points, streaks, uniforms, streakUniforms: lu };
}

export function mulberry(seed) {
  let s = seed >>> 0;
  return () => { s = (s + 0x6D2B79F5) >>> 0; let t = s; t = Math.imul(t ^ t >>> 15, t | 1); t ^= t + Math.imul(t ^ t >>> 7, t | 61); return ((t ^ t >>> 14) >>> 0) / 4294967296; };
}
