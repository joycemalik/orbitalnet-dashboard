import * as THREE from 'three';
import { HYP, FADE, SIG, COL } from '../story/charts.js';

// A holographic instrument panel floating in front of the camera: light curves
// as glowing tubes in 3D, observations as points, and belief as pillars of light.
const W = 1.7, H = 0.9;

function textSprite(text, { size = 40, color = '#cfe8ff', font = '500 {s}px "JetBrains Mono", monospace', align = 'left', scale = 0.0011 } = {}) {
  const c = document.createElement('canvas'), g = c.getContext('2d');
  const draw = (t, col = color) => {
    const f = font.replace('{s}', size); g.font = f;
    const w = Math.ceil(g.measureText(t).width) + 8;
    const h = Math.ceil(size * 1.4);
    if (c.width !== w || c.height !== h) { c.width = w; c.height = h; tex && tex.dispose(); }
    g.font = f; g.fillStyle = col; g.textBaseline = 'middle'; g.fillText(t, 4, c.height / 2);
    tex.needsUpdate = true;
    spr.scale.set(c.width * scale, c.height * scale, 1);
    spr.center.set(align === 'left' ? 0 : align === 'right' ? 1 : 0.5, 0.5);
  };
  const tex = new THREE.CanvasTexture(c); tex.colorSpace = THREE.SRGBColorSpace;
  const spr = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false, depthWrite: false }));
  spr.renderOrder = 20; draw(text); spr.userData.set = draw;
  return spr;
}
const glowMat = (hex, k = 1.6) => new THREE.MeshBasicMaterial({ color: new THREE.Color(hex).multiplyScalar(k), transparent: true, depthTest: false, depthWrite: false, blending: THREE.AdditiveBlending });

export function createHolo() {
  const root = new THREE.Group(); root.renderOrder = 10;
  const panel = new THREE.Group(); root.add(panel);
  const frame = new THREE.Group(); panel.add(frame);
  const lineMat = new THREE.LineBasicMaterial({ color: new THREE.Color(0x6fb8ff).multiplyScalar(0.7), transparent: true, opacity: 0.55, depthTest: false, blending: THREE.AdditiveBlending });
  const faintMat = lineMat.clone(); faintMat.opacity = 0.16;
  const seg = (pts, m) => { const l = new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), m); l.renderOrder = 11; frame.add(l); return l; };
  const V = (x, y, z = 0) => new THREE.Vector3(x, y, z);
  // a glass back-plate for depth
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(W + 0.2, H + 0.3), new THREE.MeshBasicMaterial({ color: 0x0a1830, transparent: true, opacity: 0.35, depthTest: false, depthWrite: false }));
  plate.position.set(W / 2, H / 2 - 0.05, -0.02); plate.renderOrder = 9; panel.add(plate);
  seg([V(0, 0), V(W, 0), V(0, 0), V(0, H)], lineMat);
  const corners = []; [[-0.1, -0.2], [W + 0.1, -0.2], [-0.1, H + 0.1], [W + 0.1, H + 0.1]].forEach(([x, y]) => {
    const sx = x < W / 2 ? 1 : -1, sy = y < H / 2 ? 1 : -1;
    corners.push(V(x, y), V(x + 0.08 * sx, y), V(x, y), V(x, y + 0.08 * sy));
  });
  seg(corners, lineMat);

  let gridLines = null; const labels = new THREE.Group(); panel.add(labels);
  const title = textSprite('', { size: 44, color: '#ffb766' }); title.position.set(0, H + 0.13, 0); panel.add(title);
  const sub = textSprite('', { size: 34, color: '#7f8aa3' }); sub.position.set(0, H + 0.0, 0); panel.add(sub);

  // curves: tubes whose draw range reveals them progressively
  const curves = [];
  function setCurves(fns, xOf, yOf, colors, samples = 160, tStart, tEnd) {
    curves.forEach(c => { panel.remove(c.mesh); c.mesh.geometry.dispose(); });
    curves.length = 0;
    fns.forEach((fn, i) => {
      const pts = [];
      for (let k = 0; k <= samples; k++) {
        const t = tStart + (tEnd - tStart) * k / samples, y = fn(t);
        if (y === null) continue;
        pts.push(V(xOf(t), yOf(y), 0.02 * i));
      }
      if (pts.length < 2) return;
      const geo = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), pts.length * 2, 0.0065, 6, false);
      const mesh = new THREE.Mesh(geo, glowMat(colors[i])); mesh.renderOrder = 12;
      panel.add(mesh); curves.push({ mesh, segs: pts.length * 2 });
    });
  }
  function reveal(f) { curves.forEach(c => c.mesh.geometry.setDrawRange(0, Math.floor(c.segs * f) * 6 * 6)); }
  function setCurveAlpha(i, a) { if (curves[i]) curves[i].mesh.userData.alpha = a; }

  function grid(xs, ys) {
    if (gridLines) frame.remove(gridLines);
    const pts = []; xs.forEach(x => pts.push(V(x, 0), V(x, H))); ys.forEach(y => pts.push(V(0, y), V(W, y)));
    gridLines = seg(pts, faintMat);
  }
  function axisLabels(items) {
    labels.clear();
    items.forEach(([text, x, y, align]) => { const s = textSprite(text, { size: 30, color: '#7f8aa3', align: align || 'center' }); s.position.set(x, y, 0); labels.add(s); });
  }

  /* ---------------- mode 1: fading clocks (log time) ---------------- */
  const LX = lx => lx / 5.72 * W, LY = ly => (ly + 3) / 3 * H;
  function showClocks() {
    title.userData.set('EVERY FLASH IS A CLOCK'); sub.userData.set('brightness vs. time since the flash · log scales · illustrative shapes');
    grid([0, 1.778, 3.158, 4.636, 5.72].map(LX), [0, 1, 2, 3].map(v => v / 3 * H));
    axisLabels([['1 MIN', LX(0), -0.06], ['1 HR', LX(1.778), -0.06], ['1 DAY', LX(3.158), -0.06], ['1 MONTH', LX(4.636), -0.06], ['1 YR', LX(5.72), -0.06],
      ['PEAK', -0.04, H, 'right'], ['10%', -0.04, H * 2 / 3, 'right'], ['1%', -0.04, H / 3, 'right'], ['0.1%', -0.04, 0, 'right']]);
    setCurves(FADE.map(fd => lx => { const ly = Math.log10(Math.max(fd.L(10 ** lx), 1e-5)); return ly < -3 ? null : ly; }),
      LX, LY, FADE.map(f => f.c), 220, 0, 5.72);
    const names = ['M-DWARF FLARE', 'GRB AFTERGLOW', 'KILONOVA', 'TIDAL DISRUPTION'];
    names.forEach((n, i) => { const s = textSprite(n, { size: 30, color: FADE[i].c }); s.position.set(W + 0.06, H - i * 0.09, 0); labels.add(s); });
    pillars.visible = false; obsGroup.visible = false; marker.visible = false; modeTag.visible = false; h0Tube.visible = false;
  }

  /* ---------------- mode 2: diagnosis (hours, magnitudes) ---------------- */
  const DX = t => t / 72 * W, DY = m => (1 - (m + 1.5) / 7.5) * H;
  const obsGroup = new THREE.Group(); panel.add(obsGroup);
  const obsDots = Array.from({ length: 16 }, () => { const m = new THREE.Mesh(new THREE.SphereGeometry(0.009, 12, 8), glowMat(0xffffff, 1.1)); m.renderOrder = 13; m.visible = false; obsGroup.add(m); return m; });
  const marker = new THREE.Mesh(new THREE.PlaneGeometry(0.004, H), glowMat(0xffb766, 1.2)); marker.renderOrder = 12; panel.add(marker);
  const markerLabel = textSprite('NEXT LOOK', { size: 30, color: '#ffb766' }); marker.add(markerLabel); markerLabel.position.set(0.012, H / 2 - 0.03, 0);
  const pillars = new THREE.Group(); panel.add(pillars);
  const PCOL = [...HYP.map(h => h.c), COL.h0], PNAME = ['KILONOVA', 'GRB', 'FLARE', 'TDE', 'h₀ UNKNOWN'];
  const pill = PCOL.map((c, i) => {
    const g = new THREE.Group(); g.position.set(W + 0.16 + i * 0.13, 0, 0.05); pillars.add(g);
    const bar = new THREE.Mesh(new THREE.BoxGeometry(0.05, 1, 0.05).translate(0, 0.5, 0), glowMat(c, 0.75)); bar.renderOrder = 12; g.add(bar);
    const base = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.004, 0.07), glowMat(c, 0.6)); g.add(base);
    const lab = textSprite(PNAME[i], { size: 24, color: c, align: 'center' }); lab.position.set(0, -0.05, 0); g.add(lab);
    const pct = textSprite('—', { size: 30, color: '#e8ebf2', align: 'center' }); g.add(pct);
    return { bar, pct, last: '' };
  });
  const modeTag = textSprite('MODE · DISCRIMINATE', { size: 34, color: '#e8ebf2' }); modeTag.position.set(W + 0.12, H + 0.06, 0); panel.add(modeTag);
  const h0Tube = new THREE.Mesh(new THREE.BufferGeometry(), glowMat(0xf4f6fb, 2.6)); h0Tube.renderOrder = 13; panel.add(h0Tube);
  let h0Key = '';

  function showDiagnosis(unknown) {
    title.userData.set(unknown ? 'SOMETHING NEW' : 'WHAT IS IT?');
    sub.userData.set('predicted brightness for each explanation · white = measurements · synthetic sketch');
    grid([0, 12, 24, 36, 48, 60, 72].map(DX), [-1, 0, 2, 4, 6].map(DY));
    axisLabels([...[0, 24, 48, 72].map(t => [`${t} H`, DX(t), -0.06]), ['BRIGHTER', -0.04, DY(-1), 'right'], ['+6 MAG', -0.04, DY(6), 'right']]);
    setCurves(HYP.map(h => t => { const m = h.m(t); return m > 6 ? null : m; }), DX, DY, HYP.map(h => h.c), 140, 0.5, 72);
    reveal(1);
    pillars.visible = true; obsGroup.visible = true; marker.visible = true; modeTag.visible = true; h0Tube.visible = false;
  }
  function updateDiagnosis(run, nShown, now) {
    const p = run.posts[nShown];
    HYP.forEach((_, i) => setCurveAlpha(i, 0.12 + 0.88 * p[i]));
    obsDots.forEach((d, i) => {
      d.visible = i < nShown && i < run.obs.length;
      if (d.visible) { const [t, y] = run.obs[i]; d.position.set(DX(t), DY(y), 0.04); }
    });
    if (nShown < run.nexts.length) {
      marker.visible = true; const ex = run.modes[nShown] === 2;
      marker.position.set(DX(run.nexts[nShown]), H / 2, 0.03);
      marker.material.color.set(ex ? 0xf4f6fb : 0xffb766).multiplyScalar(1.2);
      markerLabel.userData.set(run.modes[nShown] === 0 ? 'FOLLOW-UP' : ex ? 'SCAN' : 'NEXT LOOK', ex ? '#f4f6fb' : '#ffb766');
      marker.scale.x = 1 + 0.4 * Math.sin(now * 0.008);
    } else marker.visible = false;
    pill.forEach((pl, i) => {
      const h = Math.max(0.004, p[i] * H);
      pl.bar.scale.y += (h - pl.bar.scale.y) * 0.12;
      pl.pct.position.set(0, pl.bar.scale.y + 0.04, 0);
      const txt = (p[i] * 100).toFixed(p[i] < 0.1 ? 1 : 0) + '%';
      if (txt !== pl.last) { pl.pct.userData.set(txt); pl.last = txt; }
    });
    const explore = p[4] > 0.5;
    modeTag.userData.set(explore ? 'MODE · CHARACTERIZE THE UNKNOWN' : 'MODE · DISCRIMINATE', explore ? '#ffffff' : '#9fb0c8');
    // the unknown's own curve, threaded through the measurements
    const key = explore ? String(nShown) : '';
    if (key !== h0Key) {
      h0Key = key;
      if (explore && nShown >= 3) {
        const pts = run.obs.slice(0, nShown).map(([t, y]) => V(DX(t), DY(y), 0.05));
        h0Tube.geometry.dispose(); h0Tube.geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(pts), 120, 0.007, 6, false);
        h0Tube.visible = true;
      } else h0Tube.visible = false;
    }
    return { explore };
  }

  // layout: angled into depth like a cockpit display
  root.position.set(0.15, -0.45, -2.6);
  root.rotation.set(-0.06, -0.42, 0);
  let opacity = 0;
  function setOpacity(o, now = 0, glitch = 0) {
    opacity = o; root.visible = o > 0.01;
    root.traverse(ob => { if (ob.material && ob.material.userData.base === undefined) ob.material.userData.base = ob.material.opacity ?? 1; });
    root.traverse(ob => { if (ob.material) ob.material.opacity = ob.material.userData.base * o * (ob.userData.alpha ?? 1) * (glitch > 0 && Math.random() < glitch * 0.15 ? 0.2 : 1); });
    panel.position.x = glitch > 0 ? (Math.random() - 0.5) * 0.02 * glitch : 0;
  }
  root.scale.setScalar(0.78);
  return { root, showClocks, showDiagnosis, updateDiagnosis, reveal, setOpacity, layout(x, y, z, ry, sc = 0.78) { root.position.set(x, y, z); root.rotation.y = ry; root.scale.setScalar(sc); } };
}
