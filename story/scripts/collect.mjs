// Gathers the rest of the research into the site at build time, so one deploy
// serves everything from orbitalnet.joycemalik.com:
//   /paper/            the manuscript page (from ../docs), plus /paper/manuscript.pdf
//   /paper/venues/     the submission roadmap (from ../docs/venues)
//   /notebook/         the lab notebook: research/LOG.md and research/PLAN.md, rendered
// Nothing here is hand-written: every page is copied or rendered from the repo.
import { cpSync, rmSync, mkdirSync, readFileSync, writeFileSync, existsSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import { marked } from 'marked';

const here = dirname(fileURLToPath(import.meta.url));
const repo = resolve(here, '../..');
const pub = resolve(here, '../public');
const PDF = 'Hypothesis-Discriminating Observation Campaigns for Distributed Space Observatories.pdf';

const HOME_BAR = `<a href="/" style="position:fixed;left:12px;bottom:12px;z-index:9999;font:500 11px/1 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.14em;text-transform:uppercase;color:#fff;background:#111;padding:9px 12px;border-radius:3px;text-decoration:none;opacity:.86">← OrbitalNet research</a>`;

/* ---------- paper + roadmap ---------- */
const paperOut = resolve(pub, 'paper');
rmSync(paperOut, { recursive: true, force: true });
cpSync(resolve(repo, 'docs'), paperOut, { recursive: true });
for (const f of ['index.html', 'venues/index.html']) {
  const p = resolve(paperOut, f);
  if (existsSync(p)) writeFileSync(p, readFileSync(p, 'utf8').replace(/<body([^>]*)>/i, m => m + '\n' + HOME_BAR));
}
if (existsSync(resolve(repo, PDF))) cpSync(resolve(repo, PDF), resolve(paperOut, 'manuscript.pdf'));

/* ---------- lab notebook ---------- */
const slug = s => s.toLowerCase().replace(/<[^>]+>/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
function render(md, prefix) {
  const toc = [];
  const renderer = new marked.Renderer();
  renderer.heading = ({ tokens, depth }) => {
    const text = marked.Parser.parseInline(tokens);
    const id = `${prefix}-${slug(text)}`;
    if (depth === 2) toc.push({ id, text });
    return `<h${depth} id="${id}">${text}</h${depth}>`;
  };
  return { html: marked.parse(md, { renderer, gfm: true }), toc };
}
const docs = [
  { key: 'log', title: 'Lab log', file: 'research/LOG.md', blurb: 'What was built in each phase, which tests pass, what surprised us, and what we distrust about every result.' },
  { key: 'plan', title: 'Research plan', file: 'research/PLAN.md', blurb: 'How the live OrbitalNet auction maps to the baselines, what is reused, and the design of each phase.' },
].filter(d => existsSync(resolve(repo, d.file)));
const parts = docs.map(d => {
  const md = readFileSync(resolve(repo, d.file), 'utf8');
  const updated = statSync(resolve(repo, d.file)).mtime.toISOString().slice(0, 10);
  return { ...d, updated, ...render(md, d.key) };
});
const nav = parts.map(p => `<section class="nav-group"><a class="nav-doc" href="#${p.key}">${p.title}</a>${p.toc.map(t => `<a href="#${t.id}">${t.text}</a>`).join('')}</section>`).join('');
const body = parts.map(p => `<article id="${p.key}" class="doc"><header class="doc-head"><div class="k">${p.file}</div><h1>${p.title}</h1><p>${p.blurb}</p></header>${p.html}</article>`).join('');
mkdirSync(resolve(pub, 'notebook'), { recursive: true });
writeFileSync(resolve(pub, 'notebook/index.html'), `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lab Notebook · OrbitalNet</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Ccircle cx='16' cy='16' r='7' fill='%23ffb766'/%3E%3Cellipse cx='16' cy='16' rx='14' ry='5' fill='none' stroke='%237fd0ff' stroke-width='1.5' transform='rotate(-25 16 16)'/%3E%3C/svg%3E">
<meta name="description" content="The OrbitalNet research lab notebook: phase logs, tests, decisions and doubts, rendered from the repository.">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Michroma&family=Barlow:ital,wght@0,300;0,400;0,500;1,300&family=JetBrains+Mono:wght@400;500&display=swap">
<style>
/* Layout: a sticky table of contents on the left, the rendered notebook on the right; one column on phones. */
:root{--bg:#05060a;--panel:#0b0e16;--ink:#e9edf4;--soft:#a7b0c2;--faint:#5f687b;--rule:#1b2131;--ember:#ffb766;--ice:#8fd3ff;
--f-title:'Michroma','Eurostile',sans-serif;--f-body:'Barlow','Helvetica Neue',Arial,sans-serif;--f-mono:'JetBrains Mono',ui-monospace,Menlo,monospace;color-scheme:dark}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font:400 17px/1.65 var(--f-body)}
a{color:var(--ice)}a:hover{color:var(--ember)}
.top{position:sticky;top:0;z-index:5;display:flex;justify-content:space-between;align-items:center;gap:16px;padding:14px clamp(16px,3vw,40px);background:rgba(5,6,10,.88);backdrop-filter:blur(10px);border-bottom:1px solid var(--rule)}
.top .brand{font-family:var(--f-title);font-size:12px;letter-spacing:.38em;color:var(--ink);text-decoration:none}
.top nav{display:flex;gap:18px;flex-wrap:wrap;font-family:var(--f-mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase}
.top nav a{color:var(--soft);text-decoration:none}.top nav a:hover{color:var(--ember)}
.wrap{display:grid;grid-template-columns:260px minmax(0,1fr);gap:48px;max-width:1240px;margin:0 auto;padding:32px clamp(16px,3vw,40px) 80px}
.toc{position:sticky;top:70px;align-self:start;max-height:calc(100vh - 90px);overflow:auto;font-size:14px;padding-right:8px}
.nav-group{display:grid;gap:6px;margin-bottom:24px}.nav-group a{color:var(--soft);text-decoration:none;line-height:1.35}.nav-group a:hover{color:var(--ember)}
.nav-doc{font-family:var(--f-mono);font-size:11px;letter-spacing:.2em;text-transform:uppercase;color:var(--ember)!important;margin-bottom:4px}
.doc{min-width:0;max-width:760px;margin-bottom:96px}
.doc-head{border-bottom:1px solid var(--rule);padding-bottom:18px;margin-bottom:28px}
.doc-head .k{font-family:var(--f-mono);font-size:11px;letter-spacing:.14em;color:var(--faint)}
.doc-head h1{font-family:var(--f-title);font-weight:400;font-size:clamp(24px,3vw,34px);letter-spacing:.16em;margin:.4em 0 .3em}
.doc-head p{color:var(--soft);margin:0}
h1,h2,h3,h4{text-wrap:balance;scroll-margin-top:80px}
.doc h1:not(.doc-head h1){display:none}
.doc h2{font-family:var(--f-title);font-weight:400;font-size:18px;letter-spacing:.1em;margin:2.4em 0 .8em;padding-top:1.2em;border-top:1px solid var(--rule)}
.doc h3{font-weight:500;font-size:19px;margin:1.8em 0 .5em;color:var(--ink)}
.doc p,.doc li{color:var(--soft)}.doc strong{color:var(--ink);font-weight:500}
.doc code{font-family:var(--f-mono);font-size:.85em;background:var(--panel);border:1px solid var(--rule);padding:.08em .35em;border-radius:3px;color:#d9e4f5}
.doc pre{background:var(--panel);border:1px solid var(--rule);padding:14px 16px;overflow:auto;border-radius:4px}.doc pre code{border:0;padding:0;background:none}
.doc table{border-collapse:collapse;display:block;overflow-x:auto;font-size:14px;font-variant-numeric:tabular-nums;margin:1em 0}
.doc th,.doc td{border:1px solid var(--rule);padding:6px 10px;text-align:left;vertical-align:top}.doc th{color:var(--ink);font-weight:500;background:var(--panel)}
.doc blockquote{margin:1em 0;padding:4px 16px;border-left:2px solid var(--ember);color:var(--soft)}
.doc hr{border:0;border-top:1px solid var(--rule);margin:2em 0}
.foot{font-family:var(--f-mono);font-size:11px;letter-spacing:.08em;color:var(--faint);border-top:1px solid var(--rule);padding:20px clamp(16px,3vw,40px);text-align:center}
:focus-visible{outline:2px solid var(--ember);outline-offset:3px}
@media (max-width:860px){.wrap{grid-template-columns:minmax(0,1fr);gap:8px}.toc{position:static;max-height:none;border-bottom:1px solid var(--rule);padding-bottom:12px}.nav-group a:not(.nav-doc){display:none}.nav-group{display:inline-grid;margin:0 18px 0 0}}
</style></head><body>
<header class="top"><a class="brand" href="/">ORBITALNET</a><nav><a href="/film/">Film</a><a href="/paper/">Paper</a><a href="/paper/venues/">Roadmap</a><a href="/notebook/" aria-current="page">Notebook</a><a href="https://github.com/joycemalik/orbitalnet-dashboard" target="_blank" rel="noopener">Code</a></nav></header>
<div class="wrap"><aside class="toc" aria-label="Contents">${nav}</aside><main>${body}</main></div>
<div class="foot">Rendered from ${parts.map(p => `${p.file} (updated ${p.updated})`).join(' · ')} at build time. Edit the markdown, not this page.</div>
</body></html>`);

console.log(`collected: paper (${existsSync(resolve(paperOut, 'manuscript.pdf')) ? 'with PDF' : 'no PDF'}), roadmap, notebook (${parts.map(p => p.title).join(', ')})`);
