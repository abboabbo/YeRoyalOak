
import streamlit as st


def render_camera_scoring():

    st.markdown("## 📷 Camera Darts Scoring")

    st.write(
        "Welcome to the Camera Scoring module. "
        "This will use your phone's rear camera "
        "to detect darts and calculate scores."
    )

    with st.container(border=True):

        st.subheader("🎯 Camera Setup")

        st.info(
            "Camera integration is coming in Phase 2. "
            "Your existing 301 Training module "
            "will remain unchanged."
        )

        st.metric("Remaining Score", 301)

        st.caption(
            "Development mode — automatic scoring "
            "is not yet active."
        )
