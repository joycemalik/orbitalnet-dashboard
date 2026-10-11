import * as THREE from 'three';

// Soft radial glow, used for stars, the remnant and flares.
export function glowTexture(stops = [[0, 'rgba(255,255,255,1)'], [0.18, 'rgba(255,255,255,0.55)'], [0.45, 'rgba(255,255,255,0.12)'], [1, 'rgba(255,255,255,0)']]) {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d');
  const grd = g.createRadialGradient(128, 128, 0, 128, 128, 128);
  stops.forEach(([o, col]) => grd.addColorStop(o, col));
  g.fillStyle = grd; g.fillRect(0, 0, 256, 256);
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// A point of light with telescope diffraction spikes.
export function spikeTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 512;
  const g = c.getContext('2d');
  g.globalCompositeOperation = 'lighter';
  const grd = g.createRadialGradient(256, 256, 0, 256, 256, 120);
  grd.addColorStop(0, 'rgba(255,255,255,1)'); grd.addColorStop(0.08, 'rgba(255,240,220,0.9)');
  grd.addColorStop(0.3, 'rgba(255,190,120,0.25)'); grd.addColorStop(1, 'rgba(255,150,80,0)');
  g.fillStyle = grd; g.fillRect(0, 0, 512, 512);
  for (let i = 0; i < 6; i++) {
    const a = i * Math.PI / 3 + Math.PI / 2;
    g.save(); g.translate(256, 256); g.rotate(a);
    const lg = g.createLinearGradient(0, 0, 250, 0);
    lg.addColorStop(0, 'rgba(255,245,230,0.9)'); lg.addColorStop(1, 'rgba(255,245,230,0)');
    g.fillStyle = lg; g.beginPath(); g.moveTo(0, -2.2); g.lineTo(250, 0); g.lineTo(0, 2.2); g.fill();
    g.restore();
  }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}

// Thin ring, for marking the auction leader and bidders.
export function ringTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 128;
  const g = c.getContext('2d');
  g.strokeStyle = 'rgba(255,255,255,1)'; g.lineWidth = 5;
  g.beginPath(); g.arc(64, 64, 52, 0, Math.PI * 2); g.stroke();
  g.lineWidth = 2; g.globalAlpha = 0.5;
  for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; g.beginPath(); g.moveTo(64 + Math.cos(a) * 56, 64 + Math.sin(a) * 56); g.lineTo(64 + Math.cos(a) * 64, 64 + Math.sin(a) * 64); g.stroke(); }
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; return t;
}
