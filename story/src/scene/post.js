import * as THREE from 'three';
import { EffectComposer } from 'three/addons/postprocessing/EffectComposer.js';
import { RenderPass } from 'three/addons/postprocessing/RenderPass.js';
import { UnrealBloomPass } from 'three/addons/postprocessing/UnrealBloomPass.js';
import { ShaderPass } from 'three/addons/postprocessing/ShaderPass.js';
import { OutputPass } from 'three/addons/postprocessing/OutputPass.js';

// Bloom for every light source, then a lens pass: vignette, film grain and
// chromatic aberration that grows with the camera's speed.
export function createPost(renderer, scene, camera) {
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(innerWidth, innerHeight), 0.9, 0.55, 0.62);
  composer.addPass(bloom);
  composer.addPass(new OutputPass());
  const lens = new ShaderPass({
    uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uWarp: { value: 0 }, uFlash: { value: 0 }, uFade: { value: 0 }, uGrad: { value: 0 } },
    vertexShader: `varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0);} `,
    fragmentShader: /* glsl */`
      uniform sampler2D tDiffuse; uniform float uTime, uWarp, uFlash, uFade, uGrad; varying vec2 vUv;
      float rand(vec2 c){ return fract(sin(dot(c, vec2(12.9898, 78.233))) * 43758.5453); }
      void main(){
        vec2 d = vUv - 0.5;
        float ca = 0.0015 + uWarp * 0.012;
        vec3 c;
        c.r = texture2D(tDiffuse, vUv + d * ca).r;
        c.g = texture2D(tDiffuse, vUv).g;
        c.b = texture2D(tDiffuse, vUv - d * ca).b;
        float vig = smoothstep(0.95, 0.25, length(d * vec2(1.15, 1.0)));
        c *= mix(0.55, 1.0, vig);
        c += (rand(vUv * 900.0 + fract(uTime) * 37.0) - 0.5) * 0.045;
        // film grade: cool shadows, warm highlights
        float l = dot(c, vec3(0.299, 0.587, 0.114));
        c = mix(c * vec3(0.92, 1.0, 1.08), c * vec3(1.06, 1.0, 0.93), smoothstep(0.15, 0.7, l));
        c += vec3(1.0, 0.95, 0.9) * uFlash * 0.6;
        // graduated filter: darken the side where the hologram floats, so it reads
        c *= 1.0 - uGrad * 0.4 * smoothstep(0.62, 0.08, vUv.x);
        c *= 1.0 - uFade;
        gl_FragColor = vec4(c, 1.0);
      }`,
  });
  composer.addPass(lens);
  const setSize = (w, h) => { composer.setSize(w, h); bloom.setSize(w, h); };
  return { composer, bloom, lens, setSize };
}
