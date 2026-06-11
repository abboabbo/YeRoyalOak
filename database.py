import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = st.secrets["postgresql://postgres.dvpzvzznzskfflrcmupy:O9kfq99e1!!@aws-1-eu-central-1.pooler.supabase.com:6543/postgres"]

engine = create_engine(
    DATABASE_URL,
    echo=False
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)