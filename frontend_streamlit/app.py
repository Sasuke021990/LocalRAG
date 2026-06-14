"""
LocalRAG Frontend — OLED Dark Mode v3
Design: Custom big-tile nav, static API reference, glow accents
"""
import time
import requests
import streamlit as st

BACKEND_URL = "http://backend:8000"

st.set_page_config(
    page_title="LocalRAG — Private Knowledge Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ══════════════════════════════════════════════════════════════════════════════
# DESIGN SYSTEM — OLED Dark + Green Glow
# ══════════════════════════════════════════════════════════════════════════════
CSS = """
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {
    --bg:           #020617;
    --surface:      #0a1120;
    --card:         #0F172A;
    --card-hover:   #162032;
    --border:       #1e3a5f;
    --border-glow:  #22c55e44;
    --accent:       #22C55E;
    --accent-dim:   #16A34A;
    --accent-glow:  0 0 20px #22c55e55;
    --blue:         #38bdf8;
    --orange:       #fb923c;
    --red:          #f87171;
    --text:         #F1F5F9;
    --muted:        #64748B;
    --muted-lt:     #94A3B8;
    --r-sm:  8px;
    --r-md:  14px;
    --r-lg:  20px;
    --r-xl:  28px;
    --ease:  cubic-bezier(0.4, 0, 0.2, 1);
}

*, *::before, *::after { box-sizing: border-box; font-family: 'Fira Sans', sans-serif !important; }
code, pre, .mono { font-family: 'Fira Code', monospace !important; }

/* ── Base ──────────────────────────────────────────────────────────────────── */
.stApp { background: var(--bg) !important; color: var(--text) !important; }
[data-testid="stMainBlockContainer"] { max-width: 1280px; padding: 0 2rem 3rem !important; }
#MainMenu, footer, header, [data-testid="stDeployButton"],
[data-testid="stDecoration"], [data-testid="stToolbar"],
[data-testid="stSidebar"] { display: none !important; }

/* ── Topnav ────────────────────────────────────────────────────────────────── */
.topnav {
    display: flex; align-items: center; justify-content: space-between;
    padding: 1.25rem 2rem;
    background: linear-gradient(135deg, #0a1628 0%, #0f1e35 100%);
    border: 1px solid var(--border);
    border-radius: var(--r-xl);
    margin: 1.5rem 0 2rem;
    position: relative; overflow: hidden;
}
.topnav::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 1px;
    background: linear-gradient(90deg, transparent, var(--accent), transparent);
    opacity: 0.6;
}
.nav-brand { display: flex; align-items: center; gap: 0.875rem; }
.nav-logo-ring {
    width: 38px; height: 38px; border-radius: 10px;
    background: linear-gradient(135deg, #16a34a, #22c55e);
    display: flex; align-items: center; justify-content: center;
    box-shadow: var(--accent-glow);
}
.nav-logo-ring svg { width: 20px; height: 20px; fill: #020617; stroke: none; }
.brand-name { font-family: 'Fira Code', monospace !important; font-size: 1.3rem; font-weight: 700; color: var(--text); }
.brand-ver  { font-family: 'Fira Code', monospace !important; font-size: 0.75rem; color: var(--accent); margin-left: 8px; background: #22c55e18; padding: 2px 8px; border-radius: 99px; border: 1px solid #22c55e44; }
.nav-right { display: flex; align-items: center; gap: 0.75rem; }
.stat-chip {
    display: flex; align-items: center; gap: 6px;
    padding: 0.45rem 0.9rem; border-radius: 99px;
    background: #0d1e33; border: 1px solid var(--border);
    font-size: 0.82rem; color: var(--muted-lt);
    transition: all 0.2s var(--ease);
}
.stat-chip:hover { border-color: var(--accent); color: var(--text); }
.stat-chip svg { width: 13px; height: 13px; stroke: var(--muted); stroke-width: 2; fill: none; flex-shrink: 0; }
.stat-n { font-family: 'Fira Code', monospace !important; font-weight: 700; color: var(--text); }
.dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.dot-on  { background: var(--accent); box-shadow: 0 0 8px var(--accent); }
.dot-off { background: var(--red); }

/* ── Custom Tab Navigation — Big Tiles ─────────────────────────────────────── */
.tab-nav {
    display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem;
    margin-bottom: 2rem;
}
.tab-tile {
    display: flex; flex-direction: column; align-items: center; gap: 0.6rem;
    padding: 1.5rem 1rem;
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r-lg); cursor: pointer;
    transition: all 0.25s var(--ease);
    text-align: center; user-select: none;
}
.tab-tile:hover {
    border-color: var(--accent); background: var(--card-hover);
    transform: translateY(-2px);
    box-shadow: 0 8px 30px #22c55e18;
}
.tab-tile.active {
    border-color: var(--accent);
    background: linear-gradient(135deg, #0d2318 0%, #0F172A 100%);
    box-shadow: 0 0 0 1px var(--accent), 0 8px 30px #22c55e22;
}
.tab-icon {
    width: 40px; height: 40px; border-radius: 10px;
    background: #0d1e33; border: 1px solid var(--border);
    display: flex; align-items: center; justify-content: center;
    transition: all 0.25s var(--ease);
}
.tab-tile.active .tab-icon, .tab-tile:hover .tab-icon {
    background: #22c55e18; border-color: var(--accent);
}
.tab-icon svg { width: 20px; height: 20px; stroke: var(--muted); stroke-width: 2; fill: none; transition: stroke 0.2s; }
.tab-tile.active .tab-icon svg, .tab-tile:hover .tab-icon svg { stroke: var(--accent); }
.tab-label { font-family: 'Fira Code', monospace !important; font-size: 0.95rem; font-weight: 600; color: var(--muted-lt); transition: color 0.2s; }
.tab-tile.active .tab-label, .tab-tile:hover .tab-label { color: var(--accent); }
.tab-desc { font-size: 0.78rem; color: var(--muted); }

/* ── Panels ────────────────────────────────────────────────────────────────── */
.panel {
    background: var(--card); border: 1px solid var(--border);
    border-radius: var(--r-lg); padding: 1.75rem;
    margin-bottom: 1.5rem;
    position: relative; overflow: hidden;
}
.panel-accent::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
    background: linear-gradient(90deg, var(--accent), #38bdf8, transparent);
}
.ph {
    font-family: 'Fira Code', monospace !important;
    font-size: 1rem; font-weight: 600; color: var(--text);
    display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.25rem;
}
.ph svg { width: 18px; height: 18px; stroke: var(--accent); stroke-width: 2; fill: none; }
.ph-badge {
    font-size: 0.7rem; background: #22c55e18; color: var(--accent);
    padding: 2px 8px; border-radius: 99px; border: 1px solid #22c55e33;
    margin-left: auto; font-weight: 500;
}
.divider { border: none; border-top: 1px solid var(--border); margin: 1.25rem 0; }

/* ── Chat ──────────────────────────────────────────────────────────────────── */
.chat-empty {
    text-align: center; padding: 5rem 2rem;
    display: flex; flex-direction: column; align-items: center; gap: 1rem;
}
.chat-empty-icon {
    width: 64px; height: 64px; border-radius: 18px;
    background: #22c55e12; border: 1px solid #22c55e33;
    display: flex; align-items: center; justify-content: center;
}
.chat-empty-icon svg { width: 32px; height: 32px; stroke: var(--accent); stroke-width: 1.5; fill: none; }
.chat-empty-title { font-family: 'Fira Code', monospace !important; font-size: 1.25rem; font-weight: 600; color: var(--text); }
.chat-empty-sub { font-size: 0.9rem; color: var(--muted); max-width: 380px; line-height: 1.6; }
.chips { display: flex; flex-wrap: wrap; gap: 0.5rem; justify-content: center; margin-top: 0.5rem; }
.chip {
    padding: 0.5rem 1rem; border-radius: 99px;
    background: var(--card-hover); border: 1px solid var(--border);
    font-size: 0.82rem; color: var(--muted-lt); cursor: default;
    transition: all 0.2s;
}
.chip:hover { border-color: var(--accent); color: var(--accent); }

.msg { margin-bottom: 1.75rem; }
.msg-label { font-family: 'Fira Code', monospace !important; font-size: 0.78rem; color: var(--muted); display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.4rem; }
.msg-label svg { width: 12px; height: 12px; stroke: currentColor; stroke-width: 2; fill: none; }
.bubble-user {
    display: inline-block; max-width: 80%; float: right; clear: both;
    padding: 0.875rem 1.25rem;
    background: linear-gradient(135deg, #162032, #1e2d42);
    border: 1px solid var(--border); border-radius: var(--r-md) var(--r-md) 4px var(--r-md);
    color: var(--text); line-height: 1.65; font-size: 0.95rem;
}
.bubble-rag {
    display: block; clear: both;
    padding: 0.875rem 1.5rem;
    background: transparent;
    border-left: 2px solid var(--accent);
    color: var(--text); line-height: 1.75; font-size: 0.95rem;
    white-space: pre-wrap;
}
.clearfix::after { content: ''; display: block; clear: both; }

/* Source chips */
.src-card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-sm); padding: 1rem 1.25rem;
    margin: 0.6rem 0; transition: all 0.2s;
}
.src-card:hover { border-color: var(--accent); }
.src-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: 0.6rem; }
.src-file { font-family: 'Fira Code', monospace !important; font-size: 0.875rem; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 6px; }
.src-file svg { width: 13px; height: 13px; stroke: var(--muted); stroke-width: 2; fill: none; }
.src-cat { font-size: 0.72rem; background: #38bdf818; color: var(--blue); padding: 2px 8px; border-radius: 4px; border: 1px solid #38bdf833; white-space: nowrap; }
.src-score { font-family: 'Fira Code', monospace !important; font-size: 0.78rem; color: var(--accent); }
.score-bar-wrap { display: flex; align-items: center; gap: 8px; margin: 0.4rem 0; }
.score-bar { flex: 1; height: 3px; background: var(--border); border-radius: 99px; }
.score-fill { height: 3px; background: linear-gradient(90deg, var(--accent-dim), var(--accent)); border-radius: 99px; transition: width 0.4s; }
.src-snippet { font-size: 0.82rem; color: var(--muted); line-height: 1.6; margin-top: 0.5rem; }

/* ── Knowledge Base ─────────────────────────────────────────────────────────── */
.cat-row {
    display: flex; align-items: center; justify-content: space-between;
    padding: 0.875rem 1.1rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-sm); margin-bottom: 0.5rem; transition: all 0.2s;
}
.cat-row:hover { border-color: var(--border-glow); background: #0d1e33; }
.cat-name { font-family: 'Fira Code', monospace !important; font-size: 0.9rem; font-weight: 500; color: var(--text); display: flex; align-items: center; gap: 8px; }
.cat-name svg { width: 14px; height: 14px; stroke: var(--accent); stroke-width: 2; fill: none; }
.cnt-badge { font-family: 'Fira Code', monospace !important; font-size: 0.75rem; background: #22c55e18; color: var(--accent); padding: 3px 10px; border-radius: 99px; border: 1px solid #22c55e33; }

.doc-row {
    padding: 1rem 1.25rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-sm); margin-bottom: 0.5rem; transition: all 0.2s;
}
.doc-row:hover { border-color: var(--border-glow); }
.doc-name { font-family: 'Fira Code', monospace !important; font-size: 0.9rem; font-weight: 600; color: var(--text); display: flex; align-items: center; gap: 6px; margin-bottom: 0.35rem; }
.doc-name svg { width: 14px; height: 14px; stroke: var(--muted); stroke-width: 2; fill: none; }
.doc-meta { display: flex; gap: 0.5rem; flex-wrap: wrap; }
.tag { font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; background: var(--card); border: 1px solid var(--border); color: var(--muted); }
.tag-green { color: var(--accent) !important; border-color: #22c55e33 !important; background: #22c55e0d !important; }

/* ── API Reference ──────────────────────────────────────────────────────────── */
.api-method {
    display: inline-block; font-family: 'Fira Code', monospace !important;
    font-size: 0.72rem; font-weight: 700; padding: 3px 10px;
    border-radius: 5px; letter-spacing: 0.05em; margin-right: 0.75rem;
    vertical-align: middle;
}
.GET    { background: #22c55e1a; color: var(--accent);  border: 1px solid #22c55e44; }
.POST   { background: #38bdf81a; color: var(--blue);    border: 1px solid #38bdf844; }
.DELETE { background: #f871711a; color: var(--red);     border: 1px solid #f8717144; }

.api-row {
    display: flex; align-items: flex-start; gap: 1rem;
    padding: 1.1rem 1.5rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--r-sm); margin-bottom: 0.65rem;
    transition: all 0.2s;
}
.api-row:hover { border-color: var(--border-glow); background: #0d1e33; }
.api-path { font-family: 'Fira Code', monospace !important; font-size: 0.9rem; color: var(--text); font-weight: 500; }
.api-desc { font-size: 0.83rem; color: var(--muted); margin-top: 3px; line-height: 1.5; }
.api-link {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 0.5rem 1rem;
    background: #22c55e12; border: 1px solid #22c55e44; border-radius: var(--r-sm);
    font-family: 'Fira Code', monospace !important; font-size: 0.82rem;
    color: var(--accent); text-decoration: none; cursor: pointer;
    transition: all 0.2s;
}
.api-link:hover { background: #22c55e22; }
.api-link svg { width: 13px; height: 13px; stroke: currentColor; stroke-width: 2; fill: none; }

/* ── Streamlit widget overrides ─────────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    color: var(--text) !important; border-radius: var(--r-sm) !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: var(--accent) !important; box-shadow: 0 0 0 2px #22c55e22 !important;
}
[data-testid="stSelectbox"] > div > div {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    color: var(--text) !important; border-radius: var(--r-sm) !important;
}
[data-testid="baseButton-primary"] {
    background: linear-gradient(135deg, var(--accent-dim), var(--accent)) !important;
    color: #020617 !important; border: none !important;
    border-radius: var(--r-sm) !important; font-weight: 700 !important;
    font-family: 'Fira Code', monospace !important;
    box-shadow: 0 4px 15px #22c55e33 !important; transition: all 0.2s !important;
}
[data-testid="baseButton-primary"]:hover {
    transform: translateY(-1px) !important; box-shadow: 0 6px 20px #22c55e44 !important;
}
[data-testid="baseButton-secondary"] {
    background: var(--card-hover) !important; color: var(--text) !important;
    border: 1px solid var(--border) !important; border-radius: var(--r-sm) !important;
}
[data-testid="stSlider"] > div { color: var(--text) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background: var(--accent) !important;
}
[data-testid="stFileUploader"] {
    background: var(--surface) !important; border: 1px dashed var(--border) !important;
    border-radius: var(--r-md) !important;
}
label { color: var(--muted-lt) !important; }
[data-testid="stExpander"] {
    background: var(--surface) !important; border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
}
[data-testid="stExpander"] summary { color: var(--muted-lt) !important; }
[data-baseweb="popover"] div[role="listbox"] {
    background: var(--card) !important; border: 1px solid var(--border) !important;
}
[data-baseweb="popover"] li { color: var(--text) !important; }
[data-baseweb="popover"] li:hover { background: var(--card-hover) !important; }
[data-baseweb="popover"] li[aria-selected="true"] { color: var(--accent) !important; }

/* hide native tabs */
[data-testid="stTabs"] { display: none !important; }

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 99px; }
</style>
"""
st.markdown(CSS.replace("\n", " "), unsafe_allow_html=True)

# ── SVG Icon Library ──────────────────────────────────────────────────────────
def svg(path_d, size=18, color="currentColor", extra=""):
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" '
            f'stroke="{color}" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" xmlns="http://www.w3.org/2000/svg" {extra}>'
            f'{path_d}</svg>')

SEARCH_ICON = svg('<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>')
DB_ICON     = svg('<ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/><path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>')
API_ICON    = svg('<path d="M10 20l4-16"/><path d="M6.5 8.5L3 12l3.5 3.5"/><path d="M17.5 8.5L21 12l-3.5 3.5"/>')
FILE_ICON   = svg('<path d="M14.5 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7.5L14.5 2z"/><polyline points="14 2 14 8 20 8"/>')
FOLDER_ICON = svg('<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>')
BOT_ICON    = svg('<rect x="3" y="11" width="18" height="10" rx="2"/><circle cx="12" cy="5" r="2"/><path d="M12 7v4"/><line x1="8" y1="16" x2="8" y2="16"/><line x1="16" y1="16" x2="16" y2="16"/>')
USER_ICON   = svg('<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/>')
UPLOAD_ICON = svg('<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/>')
LINK_ICON   = svg('<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/>')
SETTINGS_ICON = svg('<circle cx="12" cy="12" r="3"/><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/>')

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"    not in st.session_state: st.session_state.messages = []
if "active_tab"  not in st.session_state: st.session_state.active_tab = "chat"

# ── API Helpers ───────────────────────────────────────────────────────────────
def api_get(path, default=None):
    try:
        r = requests.get(f"{BACKEND_URL}{path}", timeout=6)
        return r.json() if r.ok else default
    except Exception:
        return default

def api_post(path, json_data=None, data=None, files=None):
    try:
        r = requests.post(f"{BACKEND_URL}{path}", json=json_data, data=data, files=files, timeout=30)
        return r.json(), r.status_code
    except Exception as exc:
        return {"error": str(exc)}, 500

def api_delete(path):
    try:
        r = requests.delete(f"{BACKEND_URL}{path}", timeout=10)
        return r.json(), r.status_code
    except Exception as exc:
        return {"error": str(exc)}, 500

@st.cache_data(ttl=30)
def fetch_stats():
    """Cached stats fetch — only hits the backend once every 30 s."""
    docs   = api_get("/documents",  {"documents": [], "total": 0})
    cats   = api_get("/categories", {"categories": [], "total": 0})
    health = api_get("/health",     {"status": "offline"})
    return {
        "docs":      docs.get("total", 0),
        "cats":      cats.get("total", 0),
        "cats_list": cats.get("categories", []),
        "online":    health.get("status") == "healthy",
    }

@st.cache_data(ttl=20)
def fetch_all_docs():
    """Cached document list — avoids re-fetching on every widget touch."""
    return api_get("/documents", {"documents": []}).get("documents", [])

@st.cache_data(ttl=20)
def fetch_categories():
    """Cached categories list."""
    return api_get("/categories", {"categories": []}).get("categories", [])

stats   = fetch_stats()
dot_cls = "dot-on"  if stats["online"] else "dot-off"
dot_lbl = "Online"  if stats["online"] else "Offline"

# ══════════════════════════════════════════════════════════════════════════════
# TOP NAVIGATION BAR
# ══════════════════════════════════════════════════════════════════════════════
st.markdown(f"""
<div class="topnav">
    <div class="nav-brand">
        <div class="nav-logo-ring">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="#020617" xmlns="http://www.w3.org/2000/svg">
                <polygon points="12,2 22,8.5 22,15.5 12,22 2,15.5 2,8.5"/>
                <line x1="12" y1="2" x2="12" y2="22" stroke="#02061780" stroke-width="1"/>
                <line x1="2" y1="8.5" x2="22" y2="8.5" stroke="#02061780" stroke-width="1"/>
                <line x1="2" y1="15.5" x2="22" y2="15.5" stroke="#02061780" stroke-width="1"/>
            </svg>
        </div>
        <span class="brand-name">LocalRAG</span>
        <span class="brand-ver">v2.0</span>
    </div>
    <div class="nav-right">
        <div class="stat-chip">{FILE_ICON}&nbsp;<span class="stat-n">{stats['docs']}</span>&nbsp;docs</div>
        <div class="stat-chip">{FOLDER_ICON}&nbsp;<span class="stat-n">{stats['cats']}</span>&nbsp;categories</div>
        <div class="stat-chip"><span class="dot {dot_cls}"></span>&nbsp;{dot_lbl}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# BIG TILE NAVIGATION (custom — replaces tiny st.tabs)
# ══════════════════════════════════════════════════════════════════════════════
t_chat, t_kb, t_api = st.columns(3, gap="medium")

def tab_tile_html(icon, label, desc, key):
    active_cls = "active" if st.session_state.active_tab == key else ""
    return f"""
<div class="tab-tile {active_cls}" id="tile-{key}">
    <div class="tab-icon">{icon}</div>
    <div class="tab-label">{label}</div>
    <div class="tab-desc">{desc}</div>
</div>"""

with t_chat:
    st.markdown(tab_tile_html(SEARCH_ICON, "Search & Chat", "Query your documents", "chat"), unsafe_allow_html=True)
    if st.button("Go to Search", key="nav_chat", use_container_width=True):
        st.session_state.active_tab = "chat"; st.rerun()

with t_kb:
    st.markdown(tab_tile_html(DB_ICON, "Knowledge Base", "Upload & manage docs", "kb"), unsafe_allow_html=True)
    if st.button("Go to Knowledge Base", key="nav_kb", use_container_width=True):
        st.session_state.active_tab = "kb"; st.rerun()

with t_api:
    st.markdown(tab_tile_html(API_ICON, "API Reference", "Browse all endpoints", "api"), unsafe_allow_html=True)
    if st.button("Go to API Reference", key="nav_api", use_container_width=True):
        st.session_state.active_tab = "api"; st.rerun()

# CSS: hide those nav buttons (they're just click triggers under the tiles)
st.markdown("""
<style>
[data-testid="baseButton-secondary"]:has(+ *) { display: none; }
div[data-testid="stButton"] > button[kind="secondary"] {
    opacity: 0; position: absolute; top: -120px; left: 0; right: 0; height: 120px;
    cursor: pointer; z-index: 10; border: none !important; background: transparent !important;
}
</style>
""", unsafe_allow_html=True)

active = st.session_state.active_tab

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — SEARCH & CHAT
# ══════════════════════════════════════════════════════════════════════════════
if active == "chat":
    col_cfg, col_chat = st.columns([1, 3], gap="large")

    with col_cfg:
        st.markdown(f'<div class="panel"><div class="ph">{SETTINGS_ICON} Parameters</div>', unsafe_allow_html=True)
        top_k    = st.slider("Retrieve (top-K)", 1, 20, 5,  key="top_k")
        rerank_k = st.slider("Re-rank (top-K)", 1, 10, 3,  key="rerank_k")
        if stats["cats_list"]:
            st.markdown('<hr class="divider">', unsafe_allow_html=True)
            st.selectbox("Category filter", ["All"] + stats["cats_list"], key="chat_cat")
        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        if st.button("Clear History", use_container_width=True, key="clear_hist"):
            st.session_state.messages = []
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    with col_chat:
        st.markdown('<div class="panel panel-accent">', unsafe_allow_html=True)

        if not st.session_state.messages:
            st.markdown(f"""
            <div class="chat-empty">
                <div class="chat-empty-icon">{SEARCH_ICON}</div>
                <div class="chat-empty-title">Ready to Search</div>
                <div class="chat-empty-sub">Ask anything about your private document knowledge base. Results are retrieved with BM25 + dense vectors, then re-ranked by Cross-Encoder.</div>
                <div class="chips">
                    <span class="chip">Summarise the Q3 report</span>
                    <span class="chip">Key risks in this contract?</span>
                    <span class="chip">Compare two policies</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            for msg in st.session_state.messages:
                if msg["role"] == "user":
                    st.markdown(f"""
                    <div class="msg clearfix">
                        <div class="msg-label" style="justify-content:flex-end;">{USER_ICON}&nbsp;You</div>
                        <div class="bubble-user">{msg['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="msg">
                        <div class="msg-label">{BOT_ICON}&nbsp;LocalRAG</div>
                        <div class="bubble-rag">{msg['content']}</div>
                    </div>
                    """, unsafe_allow_html=True)

                    srcs = msg.get("sources", [])
                    if srcs:
                        with st.expander(f"View {len(srcs)} source(s)", expanded=False):
                            all_scores = [s.get("score", 0.0) for s in srcs]
                            mx = max(all_scores) if all_scores and max(all_scores) > 0 else 1.0
                            for s in srcs:
                                fname   = s.get("file_name") or s.get("metadata", {}).get("file_name", "Unknown")
                                cat     = s.get("category")  or s.get("metadata", {}).get("category", "General")
                                score   = s.get("score", 0.0)
                                chunk   = s.get("chunk_index", "")
                                content = str(s.get("content", ""))[:300]
                                pct     = max(4, min(int((score / mx) * 100), 100))
                                chunk_lbl = f" · chunk #{chunk}" if chunk != "" else ""
                                st.markdown(f"""
                                <div class="src-card">
                                    <div class="src-head">
                                        <div class="src-file">{FILE_ICON}&nbsp;{fname}&nbsp;<span class="src-cat">{cat}</span></div>
                                        <div class="src-score">{score:.4f}{chunk_lbl}</div>
                                    </div>
                                    <div class="score-bar-wrap">
                                        <div class="score-bar"><div class="score-fill" style="width:{pct}%"></div></div>
                                    </div>
                                    <div class="src-snippet">{content}{"…" if len(str(s.get("content",""))) > 300 else ""}</div>
                                </div>
                                """, unsafe_allow_html=True)

        with st.form("chat_form", clear_on_submit=True):
            fc1, fc2 = st.columns([5, 1])
            with fc1:
                user_input = st.text_input("q", placeholder="Ask a question about your documents…", label_visibility="collapsed")
            with fc2:
                submitted = st.form_submit_button("Search →", type="primary", use_container_width=True)

        st.markdown('</div>', unsafe_allow_html=True)

        if submitted and user_input.strip():
            st.session_state.messages.append({"role": "user", "content": user_input.strip()})
            with st.spinner("Retrieving & Re-ranking…"):
                resp, code = api_post("/query", json_data={
                    "query":        user_input.strip(),
                    "top_k":        st.session_state.get("top_k", 5),
                    "rerank_top_k": st.session_state.get("rerank_k", 3),
                })
            if code == 200:
                sources = resp.get("sources", [])
                # Client-side category filter — applied after retrieval
                cat_sel = st.session_state.get("chat_cat", "All")
                if cat_sel and cat_sel != "All":
                    sources = [s for s in sources if s.get("category") == cat_sel]
                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": resp.get("answer", "No results found."),
                    "sources": sources,
                })
            else:
                st.session_state.messages.append({
                    "role":    "assistant",
                    "content": f"Error {code}: {resp.get('detail', 'Unknown error')}",
                    "sources": [],
                })
            st.rerun()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — KNOWLEDGE BASE
# ══════════════════════════════════════════════════════════════════════════════
elif active == "kb":
    cats_fresh = fetch_categories()
    docs_all   = fetch_all_docs()

    kb_l, kb_r = st.columns([1, 2.5], gap="large")

    with kb_l:
        # Category creator
        st.markdown(f'<div class="panel"><div class="ph">{FOLDER_ICON} Categories <span class="ph-badge">{len(cats_fresh)}</span></div>', unsafe_allow_html=True)
        with st.form("new_cat_form", clear_on_submit=True):
            new_cat = st.text_input("name", placeholder="New category name…", label_visibility="collapsed")
            if st.form_submit_button("+ Create Category", use_container_width=True, type="primary"):
                if new_cat.strip():
                    res, code = api_post("/categories", json_data={"name": new_cat.strip()})
                    if code == 200:
                        st.success(f"'{new_cat.strip()}' created")
                        time.sleep(0.4); st.rerun()
                    else:
                        st.error(res.get("detail", str(res)))

        st.markdown('<hr class="divider">', unsafe_allow_html=True)
        if cats_fresh:
            for cat in cats_fresh:
                cnt = sum(1 for d in docs_all if d.get("category") == cat)
                st.markdown(f"""
                <div class="cat-row">
                    <div class="cat-name">{FOLDER_ICON}&nbsp;{cat}</div>
                    <span class="cnt-badge">{cnt}</span>
                </div>""", unsafe_allow_html=True)
        else:
            st.markdown('<p style="color:var(--muted);font-size:0.875rem;text-align:center;padding:1rem;">No categories yet. Create one above.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with kb_r:
        # Ingest panel
        st.markdown(f'<div class="panel panel-accent"><div class="ph">{UPLOAD_ICON} Ingest Documents</div>', unsafe_allow_html=True)
        up_cat = st.selectbox("Target category", ["General"] + cats_fresh, key="up_cat")
        cc1, cc2 = st.columns(2)
        chunk_sz = cc1.number_input("Chunk size",    128, 2048, 512, 64,  key="chunk_sz")
        chunk_ov = cc2.number_input("Chunk overlap",   0,  256,  50,  10, key="chunk_ov")
        uploaded = st.file_uploader(
            "drop",
            type=["pdf", "txt", "docx", "csv", "md", "json", "html", "xml"],
            accept_multiple_files=True, label_visibility="collapsed",
        )
        if uploaded:
            if st.button(f"Ingest {len(uploaded)} file(s)", type="primary", key="ingest_btn"):
                for uf in uploaded:
                    with st.status(f"Ingesting {uf.name}…", expanded=True) as sw:
                        res, code = api_post(
                            "/upload",
                            data={"category": up_cat, "chunk_size": str(chunk_sz), "chunk_overlap": str(chunk_ov)},
                            files={"file": (uf.name, uf.getvalue(), uf.type or "application/octet-stream")},
                        )
                        if code == 200:
                            sw.update(label=f"✓ {uf.name} queued in '{up_cat}'", state="complete")
                        else:
                            sw.update(label=f"✗ {uf.name}: {res.get('detail','Error')}", state="error")
                st.info("Processing runs in the background. Refresh shortly to see new documents.")
        st.markdown('</div>', unsafe_allow_html=True)

        # Document library
        st.markdown(f'<div class="panel"><div class="ph">{DB_ICON} Document Library <span class="ph-badge">{len(docs_all)}</span></div>', unsafe_allow_html=True)
        sc1, sc2 = st.columns([3, 1])
        srch    = sc1.text_input("s", placeholder="Search by filename…", label_visibility="collapsed", key="lib_srch")
        lib_cat = sc2.selectbox("f", ["All"] + cats_fresh, label_visibility="collapsed", key="lib_cat")

        filtered = [
            d for d in docs_all
            if (lib_cat == "All" or d.get("category") == lib_cat)
            and (not srch or srch.lower() in d.get("file_name", "").lower())
        ]

        if filtered:
            st.markdown(f'<p style="color:var(--muted);font-size:0.8rem;margin-bottom:0.75rem;">{len(filtered)} of {len(docs_all)} documents</p>', unsafe_allow_html=True)
            for doc in filtered:
                fname  = doc.get("file_name", "Unknown")
                cat    = doc.get("category", "General")
                chunks = doc.get("chunk_count", 0)
                dim    = doc.get("embedding_dimension", 0)
                proc   = (doc.get("processed_at") or "")[:10] or "—"
                dc1, dc2 = st.columns([9, 1])
                with dc1:
                    st.markdown(f"""
                    <div class="doc-row">
                        <div class="doc-name">{FILE_ICON}&nbsp;{fname}</div>
                        <div class="doc-meta">
                            <span class="tag tag-green">{cat}</span>
                            <span class="tag">{chunks} chunks</span>
                            <span class="tag">{dim}d</span>
                            <span class="tag">{proc}</span>
                        </div>
                    </div>""", unsafe_allow_html=True)
                with dc2:
                    if st.button("✕", key=f"del_{cat}_{fname}", help=f"Delete {fname}"):
                        res, code = api_delete(f"/documents/{fname}?category={cat}")
                        if code == 200:
                            st.success("Deleted"); time.sleep(0.3); st.rerun()
                        else:
                            st.error("Failed to delete")
        else:
            st.markdown('<p style="color:var(--muted);font-size:0.875rem;text-align:center;padding:2rem 1rem;">No documents found. Upload files above to get started.</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — API REFERENCE  (static — iframe blocked by X-Frame-Options)
# ══════════════════════════════════════════════════════════════════════════════
elif active == "api":
    API_BASE = "http://localhost:8000"

    st.markdown(f"""
    <div class="panel panel-accent">
        <div class="ph">{API_ICON} API Reference</div>
        <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1.25rem;">
            Base URL: <code style="font-family:'Fira Code',monospace;color:var(--accent);background:#22c55e12;padding:2px 8px;border-radius:4px;">{API_BASE}</code>
            &nbsp;·&nbsp; FastAPI auto-docs:
            <a class="api-link" href="{API_BASE}/docs" target="_blank">{LINK_ICON}&nbsp;Swagger UI</a>
            &nbsp;
            <a class="api-link" href="{API_BASE}/redoc" target="_blank">{LINK_ICON}&nbsp;ReDoc</a>
        </p>
    </div>
    """, unsafe_allow_html=True)

    ENDPOINTS = [
        ("GET",    "/",                   "Health check & API version info"),
        ("GET",    "/health",             "Detailed system health — Redis, models, index status"),
        ("GET",    "/categories",         "List all document categories"),
        ("POST",   "/categories",         "Create a new category. Body: {\"name\": \"string\"}"),
        ("GET",    "/documents",          "List all indexed documents with metadata"),
        ("DELETE", "/documents/{name}",   "Delete a document by filename. Query param: ?category="),
        ("POST",   "/upload",             "Upload & queue a file for ingestion. Form fields: file, category, chunk_size, chunk_overlap"),
        ("POST",   "/query",              "Hybrid search + cross-encoder re-rank + semantic cache. Body: {query, top_k, rerank_top_k}"),
        ("GET",    "/progress/{task_id}", "Server-Sent Events stream of ingestion progress"),
    ]

    sections = {
        "System": [e for e in ENDPOINTS if e[1] in ("/", "/health")],
        "Categories": [e for e in ENDPOINTS if "categories" in e[1]],
        "Documents": [e for e in ENDPOINTS if "documents" in e[1] or "upload" in e[1]],
        "Search": [e for e in ENDPOINTS if "query" in e[1] or "progress" in e[1]],
    }

    SECTION_ICONS = {
        "System": svg('<path d="M22 12h-4l-3 9L9 3l-3 9H2"/>'),
        "Categories": FOLDER_ICON,
        "Documents": FILE_ICON,
        "Search": SEARCH_ICON,
    }

    for section, eps in sections.items():
        st.markdown(f'<div class="panel"><div class="ph">{SECTION_ICONS[section]}&nbsp;{section}</div>', unsafe_allow_html=True)
        for method, path, desc in eps:
            st.markdown(f"""
            <div class="api-row">
                <div style="flex-shrink:0;">
                    <span class="api-method {method}">{method}</span>
                </div>
                <div>
                    <div class="api-path">{path}</div>
                    <div class="api-desc">{desc}</div>
                </div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown(f"""
    <div class="panel">
        <div class="ph">{LINK_ICON}&nbsp;Interactive Docs</div>
        <p style="color:var(--muted);font-size:0.875rem;margin-bottom:1rem;">
            Open the full interactive Swagger or ReDoc UI in a new tab. These are served directly by FastAPI at the backend port.
        </p>
        <a class="api-link" href="{API_BASE}/docs" target="_blank">{LINK_ICON}&nbsp;Open Swagger UI</a>
        &nbsp;&nbsp;
        <a class="api-link" href="{API_BASE}/redoc" target="_blank">{LINK_ICON}&nbsp;Open ReDoc</a>
    </div>
    """, unsafe_allow_html=True)