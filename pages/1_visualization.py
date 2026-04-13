import streamlit as st
import streamlit.components.v1 as components
import time

st.set_page_config(page_title="Global Asset Visualization (GAP)", layout="wide", initial_sidebar_state="collapsed")

# Remove default Streamlit padding so the globe fills the full viewport
st.markdown("""
<style>
    #MainMenu, header, footer { visibility: hidden; }
    .block-container { padding: 0 !important; margin: 0 !important; max-width: 100% !important; }
</style>
""", unsafe_allow_html=True)

# Read the raw HTML file fresh every load (no Streamlit cache)
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()

    # Inject a unique cache-bust comment so Streamlit's iframe always gets the latest version
    # Without this, Streamlit hashes the content and serves a stale cached iframe
    cache_bust = f"<!-- cache-bust: {int(time.time())} -->"
    html_code = html_code.replace("</body>", f"{cache_bust}\n</body>", 1)

    components.html(html_code, height=880, scrolling=False)

except FileNotFoundError:
    st.error("⚠️ `index.html` not found. Make sure it is in the project root directory.")
except Exception as e:
    st.error(f"Error loading visualization: {e}")
