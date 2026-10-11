# space_research.joycemalik.com

The public home of the OrbitalNet research, built from this repository:

| Path | What | Source |
|---|---|---|
| `/` | Landing page with a live 3D Earth and all 10,109 orbits | `index.html`, `src/landing.*` |
| `/film/` | The film (below) | `film/index.html`, `src/main.js` |
| `/paper/` | The manuscript page, plus `/paper/manuscript.pdf` | copied from `../docs/` and the PDF at the repo root |
| `/paper/venues/` | Submission roadmap | copied from `../docs/venues/` |
| `/notebook/` | Lab notebook: phase log and research plan | rendered from `../research/LOG.md` and `../research/PLAN.md` |

`scripts/collect.mjs` copies and renders the `/paper/` and `/notebook/` pages into
`public/` before every `dev` and `build`, so they always match the repo. Those
generated folders are git-ignored; edit the sources, not the output.

# The film · Differential Diagnosis for the Sky

A scroll-driven, first-person 3D film about OrbitalNet, told in seven acts and
sixteen shots: the GW170817 neutron-star merger, the light's 130-million-year
crossing, a ride aboard one of the 10,109 real Starlink satellites in
`../satellites.txt` as the source rises over Earth's limb, the CNP auction
OrbitalNet runs today, and the open-world planner (with its explicit unknown, h₀)
that the research in `../research/` is building.

Built with Vite, Three.js (custom shaders, bloom, 3D holograms) and Lenis.
The score (`src/score.js`) is synthesised live with Web Audio on a lookahead
tempo grid: an additive pipe organ, a ticking clock, an organ ostinato, string
and choir pads, brass braams, taiko hits, risers and a Shepard tone. There are
no audio files.

The storyboard lives in `src/main.js` (`SHOTS`): each shot sets the camera move,
world state, subtitles and the music cue.

## Run

```bash
cd story
npm install
npm run dev        # http://localhost:5173  (/, /film/, /paper/, /notebook/)
npm run build      # production build in dist/
```

Deep links open a shot directly: `/#s0` … `/#s15`.

## Deploy on Vercel

Import the repo in Vercel and set **Root Directory** to `story`. Keep the project
setting *Include files outside the root directory in the Build Step* switched on
(it is by default): the build reads `../docs`, `../research` and the manuscript PDF.
Then add the domain `space_research.joycemalik.com` under Settings → Domains.

## What is real and what is illustrative

Computed from data:
- Satellite positions: every point is propagated on the GPU from its TLE elements
  (circular-orbit approximation) at 120× real time from the TLE epoch, 2026-04-07 08:29 UTC.
- Sun direction and Earth rotation (GMST) for that epoch. Satellites in Earth's shadow dim.
- The beacon sits at NGC 4993's real position (RA 13h09m48s, Dec −23°23′). The gold/grey
  colouring is a real line-of-sight test from each satellite to that direction.
- The 1.7 s gap between the gravitational-wave chirp and the gamma-ray flash.
- In Act III you are a real satellite, chosen because NGC 4993 is rising over its
  limb. Its altitude, speed, ground position, sunlight/eclipse state, time until
  Earth blocks the source and time until it enters Earth's shadow are all
  computed from its orbit.

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
