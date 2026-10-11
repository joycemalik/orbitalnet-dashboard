import * as THREE from 'three';

// Earth with day/night shading, city lights, ocean glint, drifting clouds and
// an atmosphere that scatters toward the sun. Radius 1 (scene units).
export function createEarth(tex, sunDir) {
  const group = new THREE.Group();
  const uniforms = {
    uDay: { value: tex.day }, uNight: { value: tex.night }, uSpec: { value: tex.spec }, uClouds: { value: tex.clouds },
    uSun: { value: sunDir.clone() }, uCloudShift: { value: 0 }, uOpacity: { value: 1 },
  };
  const surface = new THREE.Mesh(
    new THREE.SphereGeometry(1, 128, 64),
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: /* glsl */`
        varying vec2 vUv; varying vec3 vN; varying vec3 vW;
        void main(){
          vUv = uv; vN = normalize(mat3(modelMatrix) * normal);
          vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
          gl_Position = projectionMatrix * viewMatrix * w;
        }`,
      fragmentShader: /* glsl */`
        uniform sampler2D uDay, uNight, uSpec, uClouds; uniform vec3 uSun; uniform float uCloudShift, uOpacity;
        varying vec2 vUv; varying vec3 vN; varying vec3 vW;
        void main(){
          vec3 N = normalize(vN); vec3 V = normalize(cameraPosition - vW);
          float d = dot(N, uSun);
          float day = smoothstep(-0.12, 0.22, d);
          vec3 albedo = texture2D(uDay, vUv).rgb;
          vec3 lights = texture2D(uNight, vUv).rgb;
          float cloud = texture2D(uClouds, vUv + vec2(uCloudShift, 0.0)).a;
          float spec = texture2D(uSpec, vUv).r;

          vec3 col = albedo * (0.02 + 0.85 * max(d, 0.0));
          col = mix(col, vec3(0.78), cloud * 0.8 * clamp(d * 1.4 + 0.1, 0.0, 1.0));
          // city lights on the night side, dimmed under clouds
          col += lights * vec3(1.0, 0.78, 0.48) * 1.8 * (1.0 - day) * (1.0 - cloud * 0.8);
          // sun glint on the oceans
          vec3 H = normalize(uSun + V);
          col += vec3(1.0, 0.92, 0.8) * pow(max(dot(N, H), 0.0), 120.0) * spec * 0.55 * day * (1.0 - cloud);
          // thin blue limb, warm at the terminator
          float fr = pow(1.0 - max(dot(N, V), 0.0), 3.0);
          vec3 rim = mix(vec3(1.0, 0.45, 0.2), vec3(0.3, 0.6, 1.0), smoothstep(-0.1, 0.4, d));
          // the limb glow belongs to the view from afar; from low orbit nearly everything is grazing
          col += rim * fr * smoothstep(-0.35, 0.2, d) * 0.5 * smoothstep(1.15, 2.2, length(cameraPosition));
          gl_FragColor = vec4(col * uOpacity, 1.0);
        }`,
    }));
  group.add(surface);

  const atmoU = { uSun: uniforms.uSun, uOpacity: uniforms.uOpacity };
  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(1.16, 96, 48),
    new THREE.ShaderMaterial({
      uniforms: atmoU, side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */`
        varying vec3 vNv; varying vec3 vNw; varying vec3 vW;
        void main(){ vNv = normalize(normalMatrix * normal); vNw = normalize(mat3(modelMatrix) * normal);
          vW = (modelMatrix * vec4(position, 1.0)).xyz;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0); }`,
      fragmentShader: /* glsl */`
        uniform vec3 uSun; uniform float uOpacity; varying vec3 vNv; varying vec3 vNw; varying vec3 vW;
        void main(){
          // back faces: 0 at the shell's outer edge, 1 where the line of sight grazes the planet
          float i = pow(clamp(-dot(normalize(vNv), vec3(0.0, 0.0, 1.0)) / 0.507, 0.0, 1.0), 3.0);
          vec3 V = normalize(cameraPosition - vW);
          vec3 np = normalize(vNw - dot(vNw, V) * V);
          float lit = smoothstep(-0.5, 0.6, dot(np, uSun));
          vec3 c = mix(vec3(0.25, 0.12, 0.35), vec3(0.32, 0.62, 1.0), lit);
          gl_FragColor = vec4(c * i * (0.12 + 0.7 * lit) * uOpacity, 1.0);
        }`,
    }));
  group.add(atmosphere);

  // the thin bright layer seen edge-on at the horizon from orbit: blue by day,
  // orange at the terminator, the faint green oxygen airglow by night
  const limb = new THREE.Mesh(
    new THREE.SphereGeometry(1.012, 160, 80),
    new THREE.ShaderMaterial({
      uniforms: atmoU, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: /* glsl */`
        varying vec3 vN; varying vec3 vW;
        void main(){ vN = normalize(mat3(modelMatrix) * normal); vec4 w = modelMatrix * vec4(position, 1.0); vW = w.xyz;
          gl_Position = projectionMatrix * viewMatrix * w; }`,
      fragmentShader: /* glsl */`
        uniform vec3 uSun; uniform float uOpacity; varying vec3 vN; varying vec3 vW;
        void main(){
          vec3 V = normalize(cameraPosition - vW);
          float graze = pow(1.0 - abs(dot(normalize(vN), V)), 7.0);
          float d = dot(normalize(vN), uSun);
          vec3 day = vec3(0.35, 0.62, 1.0) * 1.3, dusk = vec3(1.0, 0.5, 0.22) * 1.4, night = vec3(0.18, 0.55, 0.28) * 0.35;
          vec3 c = mix(night, dusk, smoothstep(-0.25, 0.0, d));
          c = mix(c, day, smoothstep(0.0, 0.3, d));
          gl_FragColor = vec4(c * graze * uOpacity, 1.0);
        }`,
    }));
  group.add(limb);

  return {
    group, surface, uniforms,
    setRotation(angle) { surface.rotation.y = angle; },
    setInside(inside) { atmosphere.visible = !inside; },
    setOpacity(o) { uniforms.uOpacity.value = o; group.visible = o > 0.003; },
  };
}
