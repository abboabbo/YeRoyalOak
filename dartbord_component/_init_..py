import os
import streamlit.components.v1 as components

_component = components.declare_component(
    "interactive_dartboard",
    path=os.path.dirname(__file__)
)


def interactive_dartboard(key=None):
    return _component(
        key=key,
        default=None
    )