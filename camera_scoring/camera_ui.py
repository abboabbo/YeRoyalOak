
import streamlit as st
import streamlit.components.v1 as components

from pathlib import Path


def render_camera_scoring():

    st.markdown("## 📷 Camera Darts Scoring")

    st.write(
        "Use your phone's rear camera to capture "
        "your dartboard."
    )

    component_path = (
        Path(__file__).parent
        / "camera_component"
        / "index.html"
    )

    camera_html = component_path.read_text(
        encoding="utf-8"
    )

    components.html(
        camera_html,
        height=650,
        scrolling=False
    )

    st.info(
        "Phase 2: Live camera preview only. "
        "Automatic scoring is not yet active."
    )
