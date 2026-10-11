import * as THREE from 'three';

// Scene units: 1 = one Earth radius. Three.js is y-up; ECI is z-up.
// ECI (x, y, z) -> scene (x, z, -y).
export const RE_KM = 6378.137;
export const MU = 398600.4418;
export const eciToScene = (x, y, z, out = new THREE.Vector3()) => out.set(x, z, -y);

const D2R = Math.PI / 180;

// Greenwich mean sidereal time (radians) for a Julian date.
export function gmst(jd) {
  const deg = 280.46061837 + 360.98564736629 * (jd - 2451545.0);
  return ((deg % 360) + 360) % 360 * D2R;
}

// Low-precision solar direction in ECI (unit vector), good to ~0.01 deg.
export function sunEci(jd) {
  const n = jd - 2451545.0;
  const L = (280.46 + 0.9856474 * n) * D2R;
  const g = (357.528 + 0.9856003 * n) * D2R;
  const lam = L + (1.915 * Math.sin(g) + 0.02 * Math.sin(2 * g)) * D2R;
  const eps = (23.439 - 0.0000004 * n) * D2R;
  return [Math.cos(lam), Math.cos(eps) * Math.sin(lam), Math.sin(eps) * Math.sin(lam)];
}

// NGC 4993, host galaxy of GW170817: RA 13h09m47.7s, Dec -23deg 23' 01"
export const NGC4993 = { ra: 197.4488 * D2R, dec: -23.3836 * D2R };
export const radecToEci = ({ ra, dec }) => [Math.cos(dec) * Math.cos(ra), Math.cos(dec) * Math.sin(ra), Math.sin(dec)];
