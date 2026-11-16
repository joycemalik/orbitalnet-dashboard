"""OrbitalNet design system: carbon + Rosso Corsa. Pure presentation — no redis, no engines."""

from __future__ import annotations

import html as _html

import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

CARBON = "#07080A"
PANEL = "#0F1115"
LINE = "#1E222A"
TEXT = "#E8EAED"
MUTED = "#8A9099"
ROSSO = "#E10600"
GREEN = "#2BD67B"
AMBER = "#FFB020"
BLUE = "#4DA3FF"

_CSS = f"""
<link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap" rel="stylesheet">
<style>
:root {{ --carbon:{CARBON}; --panel:{PANEL}; --line:{LINE}; --text:{TEXT}; --muted:{MUTED};
        --rosso:{ROSSO}; --green:{GREEN}; --amber:{AMBER}; --blue:{BLUE}; }}
html, body, [class*="css"], .stApp, .stMarkdown, button, input, textarea, select {{
  font-family: 'Inter Tight', system-ui, sans-serif !important; }}
.stApp {{ background:
  radial-gradient(1200px 500px at 85% -10%, rgba(225,6,0,.10), transparent 60%),
  radial-gradient(900px 600px at -10% 110%, rgba(77,163,255,.05), transparent 60%), var(--carbon); }}
header[data-testid="stHeader"] {{ background: transparent; }}
#MainMenu, footer, [data-testid="stDecoration"], .stDeployButton, [data-testid="stAppDeployButton"] {{ display:none !important; }}
.block-container {{ padding-top: 2.2rem; max-width: 1480px; }}
h1, h2, h3 {{ letter-spacing: -0.02em; font-weight: 700 !important; }}
code, .mono, [data-testid="stMetricValue"] {{ font-family:'JetBrains Mono', monospace !important; font-variant-numeric: tabular-nums; }}

/* sidebar */
section[data-testid="stSidebar"] {{ background: #050607; border-right: 1px solid var(--line); }}
section[data-testid="stSidebar"] [data-testid="stSidebarNavSeparator"] {{ border-color: var(--line); }}
[data-testid="stSidebarNav"] a, [data-testid="stSidebarNavLink"] {{ border-radius: 4px; }}
[data-testid="stSidebarNavLink"][aria-current="page"] {{ background: rgba(225,6,0,.12) !important;
  box-shadow: inset 2px 0 0 var(--rosso); }}
[data-testid="stNavSectionHeader"] {{ font-size:.66rem !important; letter-spacing:.22em; color:var(--muted) !important;
  text-transform:uppercase; font-weight:600; }}

/* controls */
.stButton > button, .stLinkButton > a, .stDownloadButton > button {{ border-radius: 3px; border:1px solid var(--line);
  background: var(--panel); font-weight:600; letter-spacing:.06em; text-transform:uppercase; font-size:.78rem;
  transition: all .15s ease; }}
.stButton > button:hover, .stLinkButton > a:hover {{ border-color: var(--rosso); color: #fff; }}
.stButton > button[kind="primary"] {{ background: linear-gradient(180deg,#ff1a10,var(--rosso)); border-color:#ff2a20;
  color:#fff; box-shadow: 0 6px 24px -8px rgba(225,6,0,.7); }}
.stButton > button[kind="primary"]:hover {{ filter: brightness(1.1); transform: translateY(-1px); }}
[data-baseweb="slider"] [role="slider"] {{ background: var(--rosso) !important; box-shadow: 0 0 0 4px rgba(225,6,0,.18); }}
[data-baseweb="tab-list"] {{ gap: 2px; border-bottom: 1px solid var(--line); }}
[data-baseweb="tab"] {{ text-transform: uppercase; letter-spacing:.12em; font-size:.72rem !important; font-weight:600; }}
[data-baseweb="tab-highlight"] {{ background: var(--rosso) !important; }}
[data-testid="stMetric"] {{ background: var(--panel); border:1px solid var(--line); border-radius:4px; padding:14px 16px;
  position:relative; }}
[data-testid="stMetric"]::before {{ content:""; position:absolute; left:0; top:0; height:2px; width:36px; background:var(--rosso); }}
[data-testid="stMetricLabel"] p {{ font-size:.68rem !important; letter-spacing:.16em; text-transform:uppercase; color:var(--muted); }}
[data-testid="stExpander"] {{ border:1px solid var(--line) !important; border-radius:4px; background: var(--panel); }}
[data-testid="stDataFrame"], [data-testid="stTable"] {{ border:1px solid var(--line); border-radius:4px; }}
div[data-testid="stAlert"] {{ border-radius:4px; }}
[data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--line) !important; border-radius: 4px !important;
  background: rgba(15,17,21,.6); }}

/* components */
.on-hero {{ border-bottom:1px solid var(--line); padding: 4px 0 18px; margin-bottom: 22px; display:flex;
  justify-content:space-between; align-items:flex-end; gap:24px; flex-wrap:wrap; }}
.on-kicker {{ color:var(--rosso); font: 600 .7rem 'JetBrains Mono',monospace; letter-spacing:.28em; text-transform:uppercase; }}
.on-title {{ font-size: 2.35rem; font-weight: 800; letter-spacing:-.035em; line-height:1.05; margin:6px 0 4px; color:#fff; }}
.on-sub {{ color:var(--muted); font-size:.98rem; max-width: 760px; }}
.on-pill {{ display:inline-flex; align-items:center; gap:8px; border:1px solid var(--line); padding:6px 12px; border-radius:999px;
  font: 500 .72rem 'JetBrains Mono',monospace; letter-spacing:.12em; text-transform:uppercase; color:var(--text); background:var(--panel); }}
.on-dot {{ width:7px; height:7px; border-radius:50%; background:var(--green); box-shadow:0 0 10px var(--green); animation: on-blink 2s infinite; }}
.on-dot.bad {{ background:var(--rosso); box-shadow:0 0 10px var(--rosso); }}
@keyframes on-blink {{ 50% {{ opacity:.35; }} }}
.on-label {{ display:flex; align-items:center; gap:12px; margin: 26px 0 12px; font: 600 .72rem 'JetBrains Mono',monospace;
  letter-spacing:.24em; text-transform:uppercase; color:var(--muted); }}
.on-label b {{ color:var(--rosso); font-weight:700; }}
.on-label::after {{ content:""; flex:1; height:1px; background: linear-gradient(90deg,var(--line),transparent); }}
.on-kpis {{ display:grid; grid-template-columns: repeat(auto-fit,minmax(170px,1fr)); gap:10px; }}
.on-kpi {{ background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:14px 16px 12px; position:relative; overflow:hidden; }}
.on-kpi::before {{ content:""; position:absolute; left:0; top:0; height:2px; width:36px; background:var(--accent,var(--rosso)); }}
.on-kpi .l {{ font: 600 .64rem 'JetBrains Mono',monospace; letter-spacing:.18em; text-transform:uppercase; color:var(--muted); }}
.on-kpi .v {{ font: 700 1.9rem 'JetBrains Mono',monospace; color:#fff; margin-top:6px; font-variant-numeric:tabular-nums; }}
.on-kpi .v small {{ font-size:.8rem; color:var(--muted); margin-left:4px; font-weight:500; }}
.on-kpi .n {{ font-size:.76rem; color:var(--muted); margin-top:2px; }}
.on-card {{ background:var(--panel); border:1px solid var(--line); border-radius:4px; padding:20px 22px; height:100%; }}
.on-card h4 {{ margin:0 0 6px; font-size:1.05rem; color:#fff; }}
.on-card p {{ color:var(--muted); font-size:.9rem; margin:0; }}
.on-card .num {{ font: 700 .7rem 'JetBrains Mono',monospace; color:var(--rosso); letter-spacing:.2em; }}
.on-verdict {{ position:relative; overflow:hidden; border-radius:4px; padding:26px 30px; margin: 18px 0; border:1px solid;
  background: var(--panel); }}
.on-verdict .k {{ font: 700 .72rem 'JetBrains Mono',monospace; letter-spacing:.3em; text-transform:uppercase; }}
.on-verdict .t {{ font-size:2rem; font-weight:800; letter-spacing:-.03em; color:#fff; margin:6px 0 4px; }}
.on-verdict .d {{ color:var(--text); opacity:.85; max-width:900px; }}
.on-verdict.alert {{ border-color: var(--rosso); background: linear-gradient(90deg, rgba(225,6,0,.22), rgba(225,6,0,.04) 70%); }}
.on-verdict.alert .k {{ color: var(--rosso); }}
.on-verdict.alert::after {{ content:""; position:absolute; inset:0; background: linear-gradient(180deg, transparent, rgba(255,40,30,.25), transparent);
  height:40%; animation: on-scan 2.2s linear infinite; }}
@keyframes on-scan {{ from {{ transform: translateY(-100%); }} to {{ transform: translateY(260%); }} }}
.on-verdict.ok {{ border-color: var(--green); background: linear-gradient(90deg, rgba(43,214,123,.14), transparent 70%); }}
.on-verdict.ok .k {{ color: var(--green); }}
.on-verdict.warn {{ border-color: var(--amber); background: linear-gradient(90deg, rgba(255,176,32,.12), transparent 70%); }}
.on-verdict.warn .k {{ color: var(--amber); }}
.on-brand {{ font: 800 1.15rem 'Inter Tight'; letter-spacing:.32em; color:#fff; padding: 4px 0 2px; }}
.on-brand span {{ color: var(--rosso); }}
.on-side {{ font: 500 .7rem 'JetBrains Mono',monospace; color:var(--muted); letter-spacing:.08em; line-height:1.9;
  border-top:1px solid var(--line); border-bottom:1px solid var(--line); padding:10px 0; margin: 8px 0 4px; }}
.on-side b {{ color:var(--text); font-weight:500; }}
.on-matrix {{ display:grid; gap:6px; }}
.on-cell {{ font: 600 .72rem 'JetBrains Mono',monospace; letter-spacing:.1em; text-align:center; padding:10px 6px; border-radius:3px;
  border:1px solid var(--line); }}
.on-cell.pass {{ color:var(--green); background: rgba(43,214,123,.08); border-color: rgba(43,214,123,.35); }}
.on-cell.fail {{ color:var(--rosso); background: rgba(225,6,0,.08); border-color: rgba(225,6,0,.35); }}
.on-cell.na {{ color:var(--muted); }}
.on-cell.head {{ color:var(--muted); border:none; text-align:left; }}
</style>
"""


def _register_plotly() -> None:
    t = go.layout.Template()
    t.layout = go.Layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter Tight, sans-serif", color=TEXT, size=12),
        title=dict(font=dict(size=13, color=MUTED), x=0, xanchor="left"),
        colorway=[ROSSO, BLUE, GREEN, AMBER, "#B07CFF", "#5EE6E6", "#FF7AB6"],
        xaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(family="JetBrains Mono", color=MUTED)),
        yaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(family="JetBrains Mono", color=MUTED)),
        legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED)),
        hoverlabel=dict(bgcolor=PANEL, bordercolor=ROSSO, font=dict(family="JetBrains Mono", color=TEXT)),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    pio.templates["orbitalnet"] = t
    pio.templates.default = "plotly_dark+orbitalnet"


def apply_theme() -> None:
    _register_plotly()
    st.markdown(_CSS, unsafe_allow_html=True)


def _e(s) -> str:
    return _html.escape(str(s))


def hero(kicker: str, title: str, sub: str = "", status: str | None = None, ok: bool = True) -> None:
    pill = (f'<div class="on-pill"><span class="on-dot{"" if ok else " bad"}"></span>{_e(status)}</div>'
            if status else "")
    st.markdown(f'<div class="on-hero"><div><div class="on-kicker">{_e(kicker)}</div>'
                f'<div class="on-title">{_e(title)}</div><div class="on-sub">{_e(sub)}</div></div>{pill}</div>',
                unsafe_allow_html=True)


def label(num: str, text: str) -> None:
    st.markdown(f'<div class="on-label"><b>{_e(num)}</b>{_e(text)}</div>', unsafe_allow_html=True)


def kpis(items: list[tuple]) -> None:
    """items: (label, value, unit="", note="", color=None)"""
    cells = []
    for it in items:
        lab, val, unit, note, color = (list(it) + ["", "", None])[:5]
        acc = f' style="--accent:{color}"' if color else ""
        cells.append(f'<div class="on-kpi"{acc}><div class="l">{_e(lab)}</div>'
                     f'<div class="v">{_e(val)}<small>{_e(unit)}</small></div>'
                     f'<div class="n">{_e(note)}</div></div>')
    st.markdown(f'<div class="on-kpis">{"".join(cells)}</div>', unsafe_allow_html=True)


def card(num: str, title: str, body: str) -> None:
    st.markdown(f'<div class="on-card"><div class="num">{_e(num)}</div><h4>{_e(title)}</h4><p>{_e(body)}</p></div>',
                unsafe_allow_html=True)


def verdict(kind: str, kicker: str, title: str, detail: str = "") -> None:
    """kind: alert | ok | warn"""
    st.markdown(f'<div class="on-verdict {kind}"><div class="k">{_e(kicker)}</div><div class="t">{_e(title)}</div>'
                f'<div class="d">{_e(detail)}</div></div>', unsafe_allow_html=True)


def sidebar_brand(lines: list[tuple[str, str]], online: bool) -> None:
    rows = "".join(f"<div>{_e(k)} <b>{_e(v)}</b></div>" for k, v in lines)
    dot = '<span class="on-dot' + ("" if online else " bad") + '" style="display:inline-block;margin-right:8px"></span>'
    st.sidebar.markdown(f'<div class="on-brand">ORBITAL<span>NET</span></div>'
                        f'<div class="on-side">{dot}{"LINK NOMINAL" if online else "BUS OFFLINE"}{rows}</div>',
                        unsafe_allow_html=True)
