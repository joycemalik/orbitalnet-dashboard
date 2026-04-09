import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Global Asset Visualization (GAP)", layout="wide", initial_sidebar_state="collapsed")
st.title("📡 View 1: Global Asset Persistance (GAP)")
st.markdown("This route is purely for the visual proof of orbital physics. 60FPS WebGL native rendering.")

# Read the raw HTML file and inject it full-width
try:
    with open("index.html", "r", encoding="utf-8") as f:
        html_code = f.read()
        
    components.html(html_code, height=800, scrolling=False)
except Exception as e:
    st.error(f"Error loading visualization: {e}")
