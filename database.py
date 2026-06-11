import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = st.secrets["DATABASE_URL"]

engine = create_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)