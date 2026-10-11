# OrbitalNet · Differential Diagnosis for the Sky

A scroll-driven 3D story about OrbitalNet: the GW170817 neutron-star merger, the
10,109 real Starlink satellites in `../satellites.txt`, the CNP auction OrbitalNet
runs today, and the open-world planner (with its explicit unknown, h₀) that the
research in `../research/` is building.

Built with Vite, Three.js (custom shaders + bloom) and Lenis. The music is
synthesised live with Web Audio; there are no audio files.

## Run

```bash
cd story
npm install
npm run dev        # http://localhost:5173
npm run build      # production build in dist/
```

Deep links open a chapter directly: `/#ch0` … `/#ch8`.

## Deploy on Vercel

Import the repo in Vercel and set **Root Directory** to `story`. The framework
(Vite), build command and output directory are picked up from `vercel.json`.

## What is real and what is illustrative

Computed from data:
- Satellite positions: every point is propagated on the GPU from its TLE elements
  (circular-orbit approximation) at 120× real time from the TLE epoch, 2026-04-07 08:29 UTC.
- Sun direction and Earth rotation (GMST) for that epoch. Satellites in Earth's shadow dim.
- The beacon sits at NGC 4993's real position (RA 13h09m48s, Dec −23°23′). The gold/grey
  colouring is a real line-of-sight test from each satellite to that direction.
- The 1.7 s gap between the gravitational-wave chirp and the gamma-ray flash.

Illustrative, and labelled as such on the page:
- The merger animation (timescale compressed), light-curve shapes, auction battery levels,
  and the two Bayesian sketches in chapters VI and VII (synthetic data). The page reports
  no research results.

## Data

`public/data/sats.json` is generated from the repo's TLE file:

```bash
npm run data       # reads ../satellites.txt
```

Earth and Milky Way textures in `public/textures/` come from the three.js examples
(r169), originally derived from NASA imagery.
