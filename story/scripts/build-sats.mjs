// Builds public/data/sats.json from the repo's TLE file (../satellites.txt).
// Each satellite becomes [number, inc*10, raan*10, u*10, meanMotion*1e4], where u is the
// argument of latitude (argp + M) propagated to a common reference epoch.
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../satellites.txt');
const out = resolve(here, '../public/data/sats.json');

const lines = readFileSync(src, 'utf8').split(/\r?\n/).filter(l => l.trim());
const sats = [];
for (let i = 0; i + 2 < lines.length; i += 3) {
  const name = lines[i].trim(), l1 = lines[i + 1], l2 = lines[i + 2];
  const yy = +l1.slice(18, 20), doy = +l1.slice(20, 32);
  sats.push({
    num: +(name.split('-')[1] || 0),
    year: yy < 57 ? 2000 + yy : 1900 + yy, doy,
    inc: +l2.slice(8, 16), raan: +l2.slice(17, 25), argp: +l2.slice(34, 42),
    M: +l2.slice(43, 51), n: +l2.slice(52, 63),
  });
}
const jdOf = (y, doy) => {
  // JD of Jan 1, 0h UT of year y, plus (doy - 1)
  const a = Math.floor((14 - 1) / 12), yy = y + 4800 - a, m = 1 + 12 * a - 3;
  const jdn = 1 + Math.floor((153 * m + 2) / 5) + 365 * yy + Math.floor(yy / 4) - Math.floor(yy / 100) + Math.floor(yy / 400) - 32045;
  return jdn - 0.5 + (doy - 1);
};
const jdRef = Math.max(...sats.map(s => jdOf(s.year, s.doy)));
const flat = [];
for (const s of sats) {
  const dt = jdRef - jdOf(s.year, s.doy);
  const u = (((s.argp + s.M + s.n * 360 * dt) % 360) + 360) % 360;
  flat.push(s.num, Math.round(s.inc * 10), Math.round(s.raan * 10), Math.round(u * 10), Math.round(s.n * 1e4));
}
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify({ jdRef, count: sats.length, el: flat }));
console.log(`wrote ${sats.length} satellites, jdRef=${jdRef.toFixed(5)} -> ${out}`);
