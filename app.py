from curses import wrapper

import streamlit as st
import pandas as pd
import os
import base64
import streamlit.components.v1 as components

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

from PIL import Image
from itertools import combinations
from datetime import date

from database import SessionLocal
from models import (
    User,
    Player,
    Tournament,
    TournamentPlayer,
    Fixture,
    KnockoutMatch,
    Announcement
)


def image_to_base64(path):

    if not path:

        return None

    if path.startswith("http"):

        return path

    if not os.path.exists(path):

        return None

    with open(path, "rb") as image_file:

        encoded = base64.b64encode(
            image_file.read()
        ).decode()

    return f"data:image/png;base64,{encoded}"

def get_news_ticker_text():

    db = SessionLocal()

    players = db.query(Player).all()

    player_lookup = {
        p.id: display_player_name(p)
        for p in players
    }

    upcoming = db.query(Fixture).filter(
        Fixture.played == 0
    ).order_by(
        Fixture.round_number,
        Fixture.id
    ).limit(5).all()

    recent = db.query(Fixture).filter(
        Fixture.played == 1
    ).order_by(
        Fixture.id.desc()
    ).limit(5).all()

    ticker_items = []

    for fixture in upcoming:

        p1 = player_lookup.get(
            fixture.player1_id,
            "Unknown"
        )

        p2 = player_lookup.get(
            fixture.player2_id,
            "Unknown"
        )

        ticker_items.append(
            f"Upcoming: Round {fixture.round_number} - {p1} vs {p2}"
        )

    for fixture in recent:

        p1 = player_lookup.get(
            fixture.player1_id,
            "Unknown"
        )

        p2 = player_lookup.get(
            fixture.player2_id,
            "Unknown"
        )

        ticker_items.append(
            f"Result: {p1} {fixture.player1_legs} - {fixture.player2_legs} {p2}"
        )

    db.close()

    if not ticker_items:

        return "Welcome to Ye Royal Oak Darts League"

    return "   |   ".join(ticker_items)

def generate_round_robin(player_ids):

    players = player_ids.copy()

    if len(players) % 2 != 0:
        players.append(None)

    rounds = []

    total_rounds = len(players) - 1
    matches_per_round = len(players) // 2

    for round_number in range(1, total_rounds + 1):

        round_matches = []

        for match_index in range(matches_per_round):

            player1 = players[match_index]
            player2 = players[-(match_index + 1)]

            if player1 is not None and player2 is not None:

                round_matches.append(
                    (
                        round_number,
                        player1,
                        player2
                    )
                )

        players = [
            players[0]
        ] + [
            players[-1]
        ] + players[1:-1]

        rounds.extend(round_matches)

    return rounds

def display_player_name(player):

    if player.nickname:

        return player.nickname

    return player.name

def dashboard_card(title, value, subtitle=""):

    st.markdown(
        f"""
        <div class="royal-card">
            <div class="royal-card-title">{title}</div>
            <div class="royal-card-value">{value}</div>
            <div class="royal-card-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True
    )


def match_card(title, line1, score_or_vs, line2):

    st.markdown(
        f"""
        <div class="royal-card match-card">
            <div class="royal-card-title">{title}</div>
            <div class="match-player">{line1}</div>
            <div class="match-score">{score_or_vs}</div>
            <div class="match-player">{line2}</div>
        </div>
        """,
        unsafe_allow_html=True
    )

def gold_card(title, body):

    st.markdown(
        f"""
        <div style="
            background: linear-gradient(145deg, #111827, #050b12);
            border: 1px solid rgba(245,197,66,0.45);
            border-radius: 18px;
            padding: 20px;
            box-shadow: 0 0 22px rgba(245,197,66,0.08);
            margin-bottom: 18px;
        ">
            <h3 style="color:#f5c542; margin-bottom:10px;">{title}</h3>
            {body}
        </div>
        """,
        unsafe_allow_html=True
    )

def create_fixtures_pdf(fixture_rows, tournament_name):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        f"{tournament_name} - Fixtures",
        styles["Title"]
    )

    elements.append(title)
    elements.append(Spacer(1, 16))

    rounds = sorted(
        set(
            row.get("Round", "")
            for row in fixture_rows
        )
    )

    for round_number in rounds:

        round_title = Paragraph(
            f"Round {round_number}",
            styles["Heading2"]
        )

        elements.append(round_title)
        elements.append(Spacer(1, 6))

        table_data = [
            [
                "Player 1",
                "Result",
                "Player 2",
                "Date",
                "AVG 1",
                "AVG 2"
            ]
        ]

        for row in fixture_rows:

            if row.get("Round", "") == round_number:

                table_data.append(
                    [
                        row.get("Player 1", ""),
                        row.get("Result", ""),
                        row.get("Player 2", ""),
                        row.get("Date Played", ""),
                        row.get("Status", "")
                    ]
                )

        table = Table(
            table_data,
            colWidths=[
                130,
                60,
                130,
                70,
                50,
                50
            ],
            repeatRows=1
        )

        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),

                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),

                    ("FONTSIZE", (0, 0), (-1, 0), 11),
                    ("FONTSIZE", (0, 1), (-1, -1), 10),

                    ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),

                    ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 1), (-1, -1), 6),

                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
                ]
            )
        )

        elements.append(table)
        elements.append(Spacer(1, 18))

    doc.build(elements)

    buffer.seek(0)

    return buffer

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        f"{tournament_name} - Fixtures",
        styles["Title"]
    )

    elements.append(title)
    elements.append(Spacer(1, 12))

    table_data = [
        [
            "Round",
            "Player 1",
            "Result",
            "Player 2",
            "Status"
        ]
    ]

    for row in fixture_rows:

        table_data.append(
            [
                row.get("Round", ""),
                row.get("Player 1", ""),
                row.get("Result", ""),
                row.get("Player 2", ""),
                row.get("Result", ""),
                row.get("Status", "")
            ]
        )

    table = Table(
        table_data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ]
        )
    )

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)

    return buffer


icon = Image.open(
    "assets/royal_oak_logo.png"
)

st.set_page_config(
    page_title="Ye Royal Oak Darts League",
    page_icon=icon,
    layout="wide",
    initial_sidebar_state="collapsed"

)

st.markdown(
    """
    <style>

    .stDataFrame table {
        font-size: 16px;
        font-weight: 700;
    }

    .stDataFrame th {
        font-size: 17px;
        font-weight: 800;
    }

    .stDataFrame td {
        font-weight: 700;
    }

    .main {
    background: linear-gradient(135deg, #050b12 0%, #0b111a 50%, #05080d 100%);
    }

    h1, h2, h3 {
        color: #f5c542;
        font-weight: 800;
    }

    .stDataFrame th {
        font-size: 17px;
        font-weight: 800;
    }

    .stDataFrame td {
        font-weight: 700;
    }

    .royal-card {
    background: linear-gradient(145deg,#111827,#050b12);
    border:1px solid rgba(245,197,66,.45);
    border-radius:20px;
    padding:22px;
    margin-bottom:18px;
    box-shadow:0 0 22px rgba(245,197,66,.08);
    }

    .royal-card-title{
        color:#f5c542;
        font-size:16px;
        font-weight:800;
        text-transform:uppercase;
        margin-bottom:12px;
    }

    .royal-card-value{
        color:white;
        font-size:34px;
        font-weight:900;
    }

    .royal-card-subtitle{
        color:#bfc5d2;
        margin-top:6px;
        font-size:14px;
    }

    .match-card{
        text-align:center;
    }

    .match-player{
        color:white;
        font-size:26px;
        font-weight:800;
    }

    .match-score{
        color:#f5c542;
        font-size:34px;
        font-weight:900;
        margin:12px 0;
    }

    </style>
    """,
    unsafe_allow_html=True

    .league-st.table-wrapper {
        background: linear-gradient(145deg, #101827, #05080f);
        border: 1px solid rgba(245,197,66,0.45);
        border-radius: 18px;
        padding: 14px;
        box-shadow: 0 0 28px rgba(245,197,66,0.08);
        overflow-x: auto;
    }

    .league-table {
        width: 100%;
        border-collapse: collapse;
        color: white;
        font-size: 15px;
        font-weight: 700;
    }

    .league-table th {
        color: #f5c542;
        text-transform: uppercase;
        letter-spacing: 1px;
        padding: 14px 10px;
        border-bottom: 1px solid rgba(245,197,66,0.45);
        text-align: center;
    }

    .league-table td {
        padding: 13px 10px;
        text-align: center;
        border-bottom: 1px solid rgba(255,255,255,0.08);
    }

    .league-table tr:hover {
        background: rgba(245,197,66,0.08);
    }

    .league-table .player-name {
        text-align: left;
        font-size: 16px;
    }

    .league-table .points {
        color: #f5c542;
        font-size: 18px;
        font-weight: 900;
    }
)

def create_league_table_pdf(league_rows):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=30,
        bottomMargin=30
    )

    styles = getSampleStyleSheet()

    elements = []

    title = Paragraph(
        "Ye Royal Oak Darts League Table",
        styles["Title"]
    )

    elements.append(title)
    elements.append(Spacer(1, 16))

    table_data = [
        [
            "Pos",
            "Player",
            "P",
            "W",
            "D",
            "L",
            "LF",
            "LA",
            "Diff",
            "Avg",
            "Pts"
        ]
    ]

    for row in league_rows:

        table_data.append(
            [
                row.get("Pos", ""),
                row.get("Player", ""),
                row.get("Played", ""),
                row.get("Won", ""),
                row.get("Drawn", ""),
                row.get("Lost", ""),
                row.get("Legs For", ""),
                row.get("Legs Against", ""),
                row.get("Difference", ""),
                row.get("3 Dart Average", ""),
                row.get("Points", "")
            ]
        )

    table = Table(
        table_data,
        repeatRows=1
    )

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (-1, -1), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ]
        )
    )

    elements.append(table)

    doc.build(elements)

    buffer.seek(0)

    return buffer

def get_sidebar_dashboard():

    db = SessionLocal()

    players_count = db.query(Player).count()

    played_count = db.query(Fixture).filter(
        Fixture.played == 1
    ).count()

    upcoming_fixture = db.query(Fixture).filter(
        Fixture.played == 0
    ).order_by(
        Fixture.round_number,
        Fixture.id
    ).first()

    latest_result = db.query(Fixture).filter(
        Fixture.played == 1
    ).order_by(
        Fixture.id.desc()
    ).first()

    players = db.query(Player).all()

    player_lookup = {
        p.id: display_player_name(p)
        for p in players
    }

    upcoming_text = "No upcoming fixtures"

    if upcoming_fixture:

        p1 = player_lookup.get(
            upcoming_fixture.player1_id,
            "Unknown"
        )

        p2 = player_lookup.get(
            upcoming_fixture.player2_id,
            "Unknown"
        )

        upcoming_text = (
            f"R{upcoming_fixture.round_number}: "
            f"{p1} vs {p2}"
        )

    latest_result_text = "No results yet"

    if latest_result:

        p1 = player_lookup.get(
            latest_result.player1_id,
            "Unknown"
        )

        p2 = player_lookup.get(
            latest_result.player2_id,
            "Unknown"
        )

        latest_result_text = (
            f"{p1} {latest_result.player1_legs}"
            f" - "
            f"{latest_result.player2_legs} {p2}"
        )

    db.close()

    return {
        "players_count": players_count,
        "played_count": played_count,
        "upcoming": upcoming_text,
        "latest_result": latest_result_text

    }
    
# LOGIN

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    if "login_mode" not in st.session_state:
        st.session_state.login_mode = "login"

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        st.image(
            "assets/royal_oak_logo.png",
            width=250
        )

        st.title("Ye Royal Oak Darts League")

        st.caption("Welcome to the official league portal")

        btn_col1, btn_col2 = st.columns(2)

        with btn_col1:

            if st.button(
                "🔐 Login",
                use_container_width=True
            ):

                st.session_state.login_mode = "login"

        with btn_col2:

            if st.button(
                "🆕 Create Account",
                use_container_width=True
            ):

                st.session_state.login_mode = "create"

        st.divider()

        if st.session_state.login_mode == "login":

            st.subheader("Player Login")

            username = st.text_input(
                "Username",
                key="login_username"
            )

            password = st.text_input(
                "Password",
                type="password",
                key="login_password"
            )

            if st.button(
                "Enter League Portal",
                use_container_width=True
            ):

                db = SessionLocal()

                user = db.query(User).filter(
                    User.username == username,
                    User.password == password
                ).first()

                db.close()

                if user:

                    st.session_state.logged_in = True
                    st.session_state.role = user.role
                    st.session_state.username = user.username
                    st.session_state.player_id = user.player_id

                    st.rerun()

                else:

                    st.error("Invalid login")

        else:

            st.subheader("Create Player Account")

            db = SessionLocal()

            players = db.query(Player).all()
            users = db.query(User).all()

            used_player_ids = [
                user.player_id
                for user in users
                if user.player_id
            ]

            available_players = {
                player.name: player.id
                for player in players
                if player.id not in used_player_ids
            }

            if available_players:

                new_username = st.text_input(
                    "Choose Username",
                    key="create_user"
                )

                new_password = st.text_input(
                    "Choose Password",
                    type="password",
                    key="create_pass"
                )

                selected_player = st.selectbox(
                    "Select Your Player Profile",
                    list(available_players.keys()),
                    key="create_player"
                )

                if st.button(
                    "Create Account",
                    key="create_account_btn",
                    use_container_width=True
                ):

                    existing_user = db.query(User).filter(
                        User.username == new_username
                    ).first()

                    if existing_user:

                        st.error("Username already exists.")

                    elif not new_username or not new_password:

                        st.error("Please enter a username and password.")

                    else:

                        user = User(
                            username=new_username,
                            password=new_password,
                            role="viewer",
                            player_id=available_players[selected_player]
                        )

                        db.add(user)
                        db.commit()

                        st.success(
                            "Account created successfully. You can now log in."
                        )

                        st.session_state.login_mode = "login"

            else:

                st.info("All players already have accounts.")

            db.close()

    st.stop()


# LOGOUT AND TITLE

top_col1, top_col2 = st.columns([8, 1])

with top_col2:

    if st.button("Logout"):

        st.session_state.clear()
        st.rerun()

col1, col2 = st.columns([1, 6])

with col1:
    st.image(
        "assets/royal_oak_logo.png",
        width=120
    )

with col2:
    st.title(
        "Ye Royal Oak Darts League"
    )

    ticker_text = get_news_ticker_text()

st.markdown(
    f"""
    <div style="
        overflow: hidden;
        white-space: nowrap;
        background-color: #262730;
        border: 1px solid #d4af37;
        border-radius: 10px;
        padding: 10px;
        margin-bottom: 20px;
        font-weight: bold;
    ">
        <marquee behavior="scroll" direction="left" scrollamount="5">
            🎯 {ticker_text}
        </marquee>
    </div>
    """,
    unsafe_allow_html=True
)

is_admin = st.session_state.get("role") == "admin"

# TABS

if "page" not in st.session_state:
    st.session_state.page = "Home"

def get_base64_image(image_path):

    with open(image_path, "rb") as image_file:

        return base64.b64encode(
            image_file.read()
        ).decode()


with st.sidebar:

    st.image(
        "assets/royal_oak_logo.png",
        width=150
    )


    dashboard = get_sidebar_dashboard()

    st.markdown("---")

    st.markdown("## 🏠 League Dashboard")

    st.markdown(
        f"""
        <div style="
            background-color:#262730;
            border:1px solid #d4af37;
            border-radius:12px;
            padding:12px;
            margin-bottom:10px;
        ">

        <b>👥 Players:</b> {dashboard["players_count"]}<br>
        <b>🎯 Matches Played:</b> {dashboard["played_count"]}<br><br>

        <b>📅 Next Fixture</b><br>
        {dashboard["upcoming"]}<br><br>

        <b>🔥 Latest Result</b><br>
        {dashboard["latest_result"]}

        </div>
        """,
        unsafe_allow_html=True
    )

    st.markdown("---")

    st.markdown("## 🎯 Main Menu")

    if st.button("🏠 Home", use_container_width=True):
        st.session_state.page = "Home"

    if st.button("👤 My Profile", use_container_width=True):
        st.session_state.page = "My Profile"

    if st.button("📅 Fixtures", use_container_width=True):
        st.session_state.page = "Fixtures"

    if st.button("🏆 League Table", use_container_width=True):
        st.session_state.page = "League"

    if st.button("🎯 Knockout", use_container_width=True):
        st.session_state.page = "Knockout"

    if st.button("📊 Statistics", use_container_width=True):
        st.session_state.page = "Statistics"

    if st.button("📢 Announcements", use_container_width=True):
        st.session_state.page = "Announcements"

    
    if is_admin:

        st.markdown("---")

        st.markdown("## 🔐 Admin Tools")

        if st.button("➕ Players", use_container_width=True):
            st.session_state.page = "Players"

        if st.button("👥 Users", use_container_width=True):
            st.session_state.page = "Users"

        if st.button("🏆 Tournaments", use_container_width=True):
            st.session_state.page = "Tournaments"

    page = st.session_state.page

    st.markdown("---")

    st.markdown("### Follow Us")

    col1, col2 = st.columns(2)

    with col1:

        st.image(
            "assets/social/facebook.png",
            width=65
        )

        st.markdown(
            """
            <div style="text-align:center;">
                <a href="https://www.facebook.com/groups/1063585262569763/"
                    target="_blank"
                    style="font-size:13px; font-weight:bold; text-decoration:none;">
                    Open
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

    with col2:

        st.image(
            "assets/social/tiktok.png",
            width=65
        )

        st.markdown(
            """
            <div style="text-align:center;">
                <a href="https://www.tiktok.com/@yeroyaloakdarts?is_from_webapp=1&sender_device=pc"
                    target="_blank"
                    style="font-size:13px; font-weight:bold; text-decoration:none;">
                    Open
                </a>
            </div>
            """,
            unsafe_allow_html=True
        )

if page == "Home":

    st.markdown(
        """
        <h1 style='text-align:center;'>🏆 Ye Royal Oak Darts League</h1>
        <p style='text-align:center; font-size:18px; color:#bfc5d2;'>
            Official League Dashboard
        </p>
        """,
        unsafe_allow_html=True
    )

    db = SessionLocal()

    players_count = db.query(Player).count()

    fixtures_played = db.query(Fixture).filter(
        Fixture.played == 1
    ).count()

    fixtures_remaining = db.query(Fixture).filter(
        Fixture.played == 0
    ).count()

    latest_announcement = db.query(Announcement).order_by(
        Announcement.id.desc()
    ).first()

    latest_result = db.query(Fixture).filter(
        Fixture.played == 1
    ).order_by(
        Fixture.id.desc()
    ).first()

    next_fixture = db.query(Fixture).filter(
        Fixture.played == 0
    ).order_by(
        Fixture.round_number,
        Fixture.id
    ).first()

    players = db.query(Player).all()

    player_lookup = {
        p.id: display_player_name(p)
        for p in players
    }

    col1, col2, col3 = st.columns(3)

    with col1:
        dashboard_card("👥 Players", players_count, "Registered players")

    with col2:
        dashboard_card("🎯 Played", fixtures_played, "Completed matches")

    with col3:
        dashboard_card("📅 Remaining", fixtures_remaining, "Fixtures left")

    st.divider()

    col4, col5 = st.columns(2)

    with col4:

        if next_fixture:

            p1 = player_lookup.get(
                next_fixture.player1_id,
                "Unknown"
            )

            p2 = player_lookup.get(
                next_fixture.player2_id,
                "Unknown"
            )

            match_card(
                "📅 Next Fixture",
                p1,
                f"Round {next_fixture.round_number}",
                p2
            )

        else:

            dashboard_card(
                "📅 Next Fixture",
                "None",
                "No upcoming fixtures"
            )

    with col5:

        if latest_result:

            p1 = player_lookup.get(
                latest_result.player1_id,
                "Unknown"
            )

            p2 = player_lookup.get(
                latest_result.player2_id,
                "Unknown"
            )

            match_card(
                "🔥 Latest Result",
                p1,
                f"{latest_result.player1_legs} - {latest_result.player2_legs}",
                p2
            )

        else:

            dashboard_card(
                "🔥 Latest Result",
                "None",
                "No results yet"
            )

    st.divider()

    if latest_announcement:

        dashboard_card(
            "📢 Latest Announcement",
            latest_announcement.title,
            latest_announcement.message
        )

    else:

        dashboard_card(
            "📢 Latest Announcement",
            "No announcements",
            "Check back soon"
        )

    db.close()

if page == "Announcements":

    st.header("📢 Announcements")

    db = SessionLocal()

    if is_admin:

        st.subheader("Create Announcement")

        title = st.text_input(
            "Title",
            key="announcement_title"
        )

        message = st.text_area(
            "Message",
            key="announcement_message"
        )

        if st.button("Post Announcement"):

            if not title or not message:

                st.error("Please enter a title and message.")

            else:

                from datetime import datetime

                announcement = Announcement(
                    title=title,
                    message=message,
                    created_at=datetime.now().strftime("%d/%m/%Y %H:%M")
                )

                db.add(announcement)
                db.commit()

                st.success("Announcement posted.")
                st.rerun()

        st.divider()

    announcements = db.query(Announcement).order_by(
        Announcement.id.desc()
    ).all()

    if not announcements:

        st.info("No announcements yet.")

    else:

        for item in announcements:

            st.markdown(f"### 📢 {item.title}")

            st.caption(item.created_at)

            st.write(item.message)

            if is_admin:

                if st.button(
                    "🗑 Delete",
                    key=f"delete_announcement_{item.id}"
                ):

                    db.delete(item)
                    db.commit()

                    st.success("Announcement deleted.")
                    st.rerun()

            st.divider()

    db.close()

# ADMIN TABS

if page == "My Profile":

    st.markdown(
        """
        <h1 style='text-align:center;'>🎴 My Player Card</h1>
        <p style='text-align:center; color:#bfc5d2; font-size:17px;'>
            Your personal Ye Royal Oak player profile
        </p>
        """,
        unsafe_allow_html=True
    )

    player_id = st.session_state.get("player_id")

    if not player_id:

        st.info("No player is linked to this account.")

    else:

        db = SessionLocal()

        player = db.get(Player, player_id)

        if not player:

            st.error("Linked player could not be found.")

        else:

            fixtures = db.query(Fixture).filter(
                (
                    Fixture.player1_id == player_id
                )
                |
                (
                    Fixture.player2_id == player_id
                )
            ).all()

            played = 0
            wins = 0
            draws = 0
            losses = 0
            averages = []
            recent_form = []
            upcoming = []

            for fixture in fixtures:

                if fixture.played == 0:

                    upcoming.append(fixture)

                else:

                    played += 1

                    if fixture.player1_id == player_id:

                        player_legs = fixture.player1_legs
                        opponent_legs = fixture.player2_legs
                        player_avg = fixture.player1_average

                    else:

                        player_legs = fixture.player2_legs
                        opponent_legs = fixture.player1_legs
                        player_avg = fixture.player2_average

                    try:

                        averages.append(
                            float(player_avg)
                        )

                    except:

                        pass

                    if player_legs > opponent_legs:

                        wins += 1
                        recent_form.append("🟢")

                    elif player_legs < opponent_legs:

                        losses += 1
                        recent_form.append("🔴")

                    else:

                        draws += 1
                        recent_form.append("🟡")

            win_pct = 0

            if played > 0:

                win_pct = round(
                    (wins / played) * 100,
                    1
                )

            avg = 0

            if averages:

                avg = round(
                    sum(averages) / len(averages),
                    2
                )

            overall_rating = int(
                min(
                    99,
                    max(
                        40,
                        (
                            win_pct * 0.45
                            +
                            avg * 0.45
                            +
                            played * 0.5
                        )
                    )
                )
            )

            form_display = "".join(
                recent_form[-5:]
            )

            if not form_display:

                form_display = "No form yet"

            col1, col2 = st.columns(
                [1, 1.4]
            )

            with col1:

                logo_html = ""

                if player.logo_path and os.path.exists(player.logo_path):

                    st.image(
                        player.logo_path,
                        width=180
                    )

                components.html(
                    f"""
                    <div style="
                        background: linear-gradient(160deg, #2b2108, #05080f 55%, #111827);
                        border: 2px solid #f5c542;
                        border-radius: 28px;
                        padding: 24px;
                        text-align: center;
                        box-shadow: 0 0 35px rgba(245,197,66,0.18);
                        font-family: Arial, sans-serif;
                    ">
                        <div style="font-size:54px; font-weight:900; color:#f5c542;">
                            {overall_rating}
                        </div>

                        <div style="color:#bfc5d2; font-weight:800; margin-bottom:16px;">
                            OVR
                        </div>

                        <div style="font-size:28px; font-weight:900; color:white;">
                            {display_player_name(player)}
                        </div>

                        <div style="color:#f5c542; font-size:15px; font-weight:700;">
                            {player.name}
                        </div>
        
                        <hr style="border:0; border-top:1px solid rgba(245,197,66,.35); margin:18px 0;">

                        <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; color:white; font-weight:800;">
                            <div><span style="color:#f5c542;">AVG</span><br>{avg}</div>
                            <div><span style="color:#f5c542;">WIN %</span><br>{win_pct}%</div>
                            <div><span style="color:#f5c542;">WINS</span><br>{wins}</div>
                            <div><span style="color:#f5c542;">PLAYED</span><br>{played}</div>
                        </div>

                        <hr style="border:0; border-top:1px solid rgba(245,197,66,.35); margin:18px 0;">

                        <div style="color:#bfc5d2; font-size:14px; font-weight:700;">
                            Recent Form
                        </div>

                        <div style="font-size:24px; margin-top:6px;">
                            {form_display}
                        </div>
                    </div>
                    """,
                    height=520
                )


            with col2:

                st.markdown("### 📊 Player Stats")

                c1, c2, c3 = st.columns(3)

                c1.metric("Played", played)
                c2.metric("Wins", wins)
                c3.metric("Win %", f"{win_pct}%")

                c4, c5, c6 = st.columns(3)

                c4.metric("Draws", draws)
                c5.metric("Losses", losses)
                c6.metric("3 Dart Avg", avg)

                st.divider()

                st.markdown("### ⚙️ Edit My Profile")

                new_nickname = st.text_input(
                    "Nickname",
                    value=player.nickname if player.nickname else "",
                    key=f"my_profile_nickname_{player.id}"
                )

                new_logo = st.file_uploader(
                    "Upload New Logo",
                    type=["png", "jpg", "jpeg"],
                    key="my_profile_logo"
                )

                if st.button(
                    "💾 Save Profile",
                    use_container_width=True
                ):

                    db_profile = SessionLocal()

                    target_player = db_profile.get(
                        Player,
                        player.id
                    )

                    if target_player:

                        target_player.nickname = new_nickname.strip()

                        if new_logo is not None:

                            os.makedirs(
                                "assets/logos",
                                exist_ok=True
                            )

                            logo_path = os.path.join(
                                "assets/logos",
                                new_logo.name
                            )

                            with open(
                                logo_path,
                                "wb"
                            ) as f:

                                f.write(
                                    new_logo.getbuffer()
                                )

                            target_player.logo_path = logo_path

                        db_profile.commit()
                        db_profile.close()

                        if "league_standings" in st.session_state:

                            del st.session_state["league_standings"]

                        st.success("Profile updated.")

                        st.rerun()

                    else:

                        db_profile.close()

                        st.error("Player not found.")

                st.divider()

                st.markdown("### 🔒 Change Password")

                current_password = st.text_input(
                    "Current Password",
                    type="password",
                    key="current_password"
                )

                new_password = st.text_input(
                    "New Password",
                    type="password",
                    key="new_password"
                )

                confirm_password = st.text_input(
                    "Confirm New Password",
                    type="password",
                    key="confirm_password"
                )

                if st.button(
                    "Update Password",
                    key="update_password",
                    use_container_width=True
                ):

                    user = db.query(User).filter(
                        User.username == st.session_state.username
                    ).first()

                    if not user:

                        st.error("User account not found.")

                    elif user.password != current_password:

                        st.error("Current password is incorrect.")

                    elif new_password != confirm_password:

                        st.error("New passwords do not match.")

                    elif len(new_password) < 6:

                        st.error("Password must be at least 6 characters.")

                    else:

                        user.password = new_password

                        db.commit()

                        st.success("Password updated successfully.")

            st.divider()

            col3, col4 = st.columns(2)

            players = db.query(Player).all()

            player_lookup = {
                p.id: display_player_name(p)
                for p in players
            }

            with col3:

                st.markdown("### 📅 Upcoming Fixtures")

                if not upcoming:

                    dashboard_card(
                        "No Fixtures",
                        "None",
                        "No upcoming fixtures"
                    )

                else:

                    for fixture in upcoming[:5]:

                        p1 = player_lookup.get(
                            fixture.player1_id,
                            "Unknown"
                        )

                        p2 = player_lookup.get(
                            fixture.player2_id,
                            "Unknown"
                        )

                        match_card(
                            f"Round {fixture.round_number}",
                            p1,
                            "VS",
                            p2
                        )

            with col4:

                st.markdown("### 🔥 Recent Results")

                recent_results = [
                    fixture
                    for fixture in fixtures
                    if fixture.played == 1
                ]

                recent_results = recent_results[-5:]

                if not recent_results:

                    dashboard_card(
                        "No Results",
                        "None",
                        "No results yet"
                    )

                else:

                    for fixture in recent_results:

                        p1 = player_lookup.get(
                            fixture.player1_id,
                            "Unknown"
                        )

                        p2 = player_lookup.get(
                            fixture.player2_id,
                            "Unknown"
                        )

                        match_card(
                            "Result",
                            p1,
                            f"{fixture.player1_legs} - {fixture.player2_legs}",
                            p2
                        )

        db.close()

# FIXTURES TAB

if page == "Fixtures":

    st.header("📅 Fixtures & Results")

    db = SessionLocal()

    tournaments = db.query(Tournament).all()

    if not tournaments:

        st.info("Create a tournament first.")

    else:

        tournament_lookup = {
            t.name: t.id
            for t in tournaments
        }

        selected_tournament = st.selectbox(
            "Tournament",
            list(tournament_lookup.keys()),
            key="fixtures_tournament"
        )

        selected_tournament_id = tournament_lookup[selected_tournament]

        st.divider()

        if is_admin:

            if st.button("🎯 Generate Fixtures"):

                existing = db.query(Fixture).filter(
                    Fixture.tournament_id == selected_tournament_id
                ).count()

                if existing > 0:

                    st.warning("Fixtures already generated.")

                else:

                    links = db.query(TournamentPlayer).filter(
                        TournamentPlayer.tournament_id == selected_tournament_id
                    ).all()

                    player_ids = [
                        link.player_id
                        for link in links
                    ]

                    if len(player_ids) < 2:

                        st.error("This tournament needs at least two players.")

                    else:

                        generated_fixtures = generate_round_robin(player_ids)

                        for round_number, player1_id, player2_id in generated_fixtures:

                            fixture = Fixture(
                                tournament_id=selected_tournament_id,
                                round_number=round_number,
                                player1_id=player1_id,
                                player2_id=player2_id
                            )

                            db.add(fixture)

                        db.commit()

                        st.success("Fixtures Generated!")
                        st.rerun()

            st.divider()

        fixtures = db.query(Fixture).filter(
            Fixture.tournament_id == selected_tournament_id
        ).all()

        fixtures = sorted(
            fixtures,
            key=lambda x: (
                x.round_number,
                x.id
            )
        )

        players = db.query(Player).all()

        player_lookup = {
            p.id: display_player_name(p)
            for p in players
        }

        if not fixtures:

            st.info("No fixtures generated.")

        else:

            st.subheader("Fixtures")

            fixture_rows = []

            for item in fixtures:

                p1_name = player_lookup.get(
                    item.player1_id,
                    "Unknown"
                )

                p2_name = player_lookup.get(
                    item.player2_id,
                    "Unknown"
                )

                result = ""

                if item.played == 1:

                    result = (
                        f"{item.player1_legs}"
                        f" - "
                        f"{item.player2_legs}"
                    )

                fixture_rows.append({

                    "Round": item.round_number,

                    "Date Played": item.date_played,

                    "Player 1": p1_name,

                    "Result": result,

                    "Player 2": p2_name,

                    "Played?":
                    "✅"
                    if item.played == 1
                    else "❌"

                })

            fixtures_df = pd.DataFrame(
                fixture_rows
            )

            round_numbers = sorted(
                fixtures_df["Round"].unique()
            )

            for round_number in round_numbers:

                st.subheader(
                    f"Round {round_number}"
                )

                round_df = fixtures_df[
                    fixtures_df["Round"] == round_number
                ].drop(
                    columns=["Round"]
                )

                styled_round_df = (
                    round_df.style
                    .set_properties(
                        **{
                            "font-weight": "bold",
                            "font-size": "17px",
                            "text-align": "center"
                        }
                    )
                )

                st.dataframe(
                    styled_round_df,
                    hide_index=True,
                    use_container_width=True
                )

                st.markdown("---")

            csv = fixtures_df.to_csv(
                index=False
            )

            st.download_button(
                "📥 Download Fixtures CSV",
                csv,
                "fixtures.csv",
                "text/csv"
            )

            pdf_file = create_fixtures_pdf(
                fixture_rows,
                selected_tournament
            )

            st.download_button(
                "📄 Download Fixtures PDF",
                pdf_file,
                "fixtures.pdf",
                "application/pdf"
            )

            st.divider()

            current_round = None

            for fixture in fixtures:

                if fixture.round_number != current_round:

                    current_round = fixture.round_number

                    st.subheader(
                        f"Round {current_round}"
                    )

                player1 = player_lookup.get(
                    fixture.player1_id,
                    "Unknown"
                )

                player2 = player_lookup.get(
                    fixture.player2_id,
                    "Unknown"
                )

                if fixture.played == 1:

                    col1, col2, col3, col4, col5 = st.columns(
                        [3, 1, 1, 1, 3]
                    )

                    with col1:
                        st.markdown(f"### {player1}")

                    with col2:
                        st.markdown(f"### {fixture.player1_legs}")

                    with col3:
                        st.markdown("### -")

                    with col4:
                        st.markdown(f"### {fixture.player2_legs}")

                    with col5:
                        st.markdown(f"### {player2}")

                    st.caption(
                        f"📅 Played: {fixture.date_played}  |  "
                        f"🎯 Averages: {fixture.player1_average} / {fixture.player2_average}"
                    )

                else:

                    st.markdown(f"### {player1} vs {player2}")

                    st.warning("Not Played")

                    if is_admin:

                        match_date = st.date_input(
                            "Date Played",
                            value=date.today(),
                            key=f"date_{fixture.id}_fixture"
                        )

                        p1_legs = st.number_input(
                            f"{player1} Legs",
                            min_value=0,
                            max_value=20,
                            key=f"p1legs_{fixture.id}_fixture"
                        )

                        p2_legs = st.number_input(
                            f"{player2} Legs",
                            min_value=0,
                            max_value=20,
                            key=f"p2legs_{fixture.id}_fixture"
                        )

                        p1_avg = st.text_input(
                            f"{player1} Average",
                            key=f"p1avg_{fixture.id}_fixture"
                        )

                        p2_avg = st.text_input(
                            f"{player2} Average",
                            key=f"p2avg_{fixture.id}_fixture"
                        )

                        if st.button(
                            "Save Result",
                            key=f"save_{fixture.id}_fixture"
                        ):

                            fixture.player1_legs = p1_legs
                            fixture.player2_legs = p2_legs
                            fixture.player1_average = p1_avg
                            fixture.player2_average = p2_avg
                            fixture.date_played = match_date
                            fixture.played = 1

                            db.commit()

                            st.success("Result Saved!")
                            st.rerun()

                st.divider()

    db.close()


# LEAGUE TAB

if page == "League":

    st.markdown(
        """
        <h1 style='text-align:center;'>🏆 League Table</h1>
        <p style='text-align:center; color:#bfc5d2; font-size:17px;'>
            Current Ye Royal Oak standings
        </p>
        """,
        unsafe_allow_html=True
    )

    db = SessionLocal()

    players = db.query(Player).all()

    fixtures = db.query(Fixture).filter(
        Fixture.played == 1
    ).all()

    table = {}

    for player in players:

        table[player.id] = {
            "player": player,
            "played": 0,
            "won": 0,
            "drawn": 0,
            "lost": 0,
            "legs_for": 0,
            "legs_against": 0,
            "points": 0,
            "averages": []
        }

    for fixture in fixtures:

        if (
            fixture.player1_id not in table
            or fixture.player2_id not in table
        ):

            continue

        p1 = table[fixture.player1_id]
        p2 = table[fixture.player2_id]

        p1["played"] += 1
        p2["played"] += 1

        p1["legs_for"] += fixture.player1_legs
        p1["legs_against"] += fixture.player2_legs

        p2["legs_for"] += fixture.player2_legs
        p2["legs_against"] += fixture.player1_legs

        try:
            p1["averages"].append(float(fixture.player1_average))
        except:
            pass

        try:
            p2["averages"].append(float(fixture.player2_average))
        except:
            pass

        if fixture.player1_legs > fixture.player2_legs:

            p1["won"] += 1
            p1["points"] += 2
            p2["lost"] += 1

        elif fixture.player2_legs > fixture.player1_legs:

            p2["won"] += 1
            p2["points"] += 2
            p1["lost"] += 1

        else:

            p1["drawn"] += 1
            p2["drawn"] += 1
            p1["points"] += 1
            p2["points"] += 1

    rows = []

    for data in table.values():

        avg = 0

        if data["averages"]:

            avg = round(
                sum(data["averages"]) / len(data["averages"]),
                2
            )

        rows.append({
            "Player": display_player_name(data["player"]),
            "Played": data["played"],
            "Won": data["won"],
            "Drawn": data["drawn"],
            "Lost": data["lost"],
            "Legs For": data["legs_for"],
            "Legs Against": data["legs_against"],
            "Difference": data["legs_for"] - data["legs_against"],
            "3 Dart Average": avg,
            "Points": data["points"],
            "Player ID": data["player"].id
        })

    rows = sorted(
        rows,
        key=lambda x: (
            x["Points"],
            x["Difference"],
            x["3 Dart Average"]
        ),
        reverse=True
    )

    st.session_state["league_standings"] = rows

    if rows:

        leader = rows[0]

        col1, col2, col3 = st.columns(3)

        with col1:

            dashboard_card(
                "🥇 Current Leader",
                leader["Player"],
                f'{leader["Points"]} points'
            )

        with col2:

            dashboard_card(
                "🎯 Best Average",
                max(rows, key=lambda x: x["3 Dart Average"])["Player"],
                f'{max(rows, key=lambda x: x["3 Dart Average"])["3 Dart Average"]} avg'
            )

        with col3:

            dashboard_card(
                "🔥 Most Wins",
                max(rows, key=lambda x: x["Won"])["Player"],
                f'{max(rows, key=lambda x: x["Won"])["Won"]} wins'
            )

        st.divider()

        table_rows = []

        for index, row in enumerate(rows, start=1):

            table_rows.append({
                "Pos": index,
                "Player": row["Player"],
                "P": row["Played"],
                "W": row["Won"],
                "D": row["Drawn"],
                "L": row["Lost"],
                "LF": row["Legs For"],
                "LA": row["Legs Against"],
                "+/-": row["Difference"],
                "Avg": row["3 Dart Average"],
                "Pts": row["Points"],
                "Player ID": row["Player ID"]
            })

        display_df = pd.DataFrame(table_rows)

        visible_df = display_df.drop(
            columns=["Player ID"]
        )

        styled_df = (
            visible_df.style
            .set_properties(
                **{
                    "text-align": "center",
                    "font-weight": "bold",
                    "font-size": "16px"
                }
            )
        )

        table_html = """
        <div class="league-table-wrapper">
        <table class="league-table">
        <thead>
        <tr>
        <th>Pos</th>
        <th>Player</th>
        <th>P</th>
        <th>W</th>
        <th>D</th>
        <th>L</th>
        <th>LF</th>
        <th>LA</th>
        <th>+/-</th>
        <th>Avg</th>
        <th>Pts</th>
        </tr>
        </thead>
        <tbody>
        """

        for _, row in visible_df.iterrows():

            medal = ""

            if row["Pos"] == 1:
                medal = "🥇 "
            elif row["Pos"] == 2:
                medal = "🥈 "
            elif row["Pos"] == 3:
                medal = "🥉 "

            table_html += f"""
            <tr>
                <td>{row["Pos"]}</td>
                <td class="player-name">{medal}{row["Player"]}</td>
                <td>{row["P"]}</td>
                <td>{row["W"]}</td>
                <td>{row["D"]}</td>
                <td>{row["L"]}</td>
                <td>{row["LF"]}</td>
                <td>{row["LA"]}</td>
                <td>{row["+/-"]}</td>
                <td>{row["Avg"]}</td>
                <td class="points">{row["Pts"]}</td>
            </tr>
            """

        table_html += """
        </tbody>
        </table>
        </div>
        """

        st.markdown(
            table_html,
            unsafe_allow_html=True
        )
        

        st.divider()

        col4, col5 = st.columns(2)

        with col4:

            st.markdown("### 🎴 View Player Card")

            player_options = {
                row["Player"]: row["Player ID"]
                for row in rows
            }

            selected_player_name = st.selectbox(
                "Select Player",
                list(player_options.keys()),
                key="view_player_select"
            )

            if st.button(
                "View Player Profile",
                key="view_player_button",
                use_container_width=True
            ):

                st.session_state.view_player_id = player_options[
                    selected_player_name
                ]

                st.session_state.page = "View Player"

                st.rerun()

        with col5:

            st.markdown("### 📄 Export")

            league_pdf = create_league_table_pdf(
                visible_df.to_dict(
                    orient="records"
                )
            )

            st.download_button(
                "Download League Table PDF",
                league_pdf,
                "league_table.pdf",
                "application/pdf",
                use_container_width=True
            )

    else:

        dashboard_card(
            "No League Data",
            "No completed matches",
            "League table will appear once results are entered"
        )

    db.close()

# KNOCKOUT TAB

if page == "Knockout":

    st.header("🏆 Knockout Stage")

    if "league_standings" not in st.session_state:

        st.warning("Please visit the League Table first.")

    else:

        standings = st.session_state["league_standings"]

        st.subheader("Current Seeds")

        for seed, player in enumerate(standings, start=1):

            st.write(f"{seed}. {player['Player']}")

        st.divider()

        if is_admin:

            if st.button("🏆 Generate Knockout Bracket"):

                db = SessionLocal()

                existing = db.query(KnockoutMatch).count()

                if existing > 0:

                    st.warning("Knockout bracket already exists.")

                else:

                    total_players = len(standings)

                    left = 0
                    right = total_players - 1

                    while left < right:

                        player1_id = standings[left]["Player ID"]
                        player2_id = standings[right]["Player ID"]

                        match = KnockoutMatch(
                            tournament_id=1,
                            round_name="Round 1",
                            player1_id=player1_id,
                            player2_id=player2_id
                        )

                        db.add(match)

                        left += 1
                        right -= 1

                    db.commit()

                    st.success("Knockout Bracket Generated!")

                db.close()

        db = SessionLocal()

        matches = db.query(KnockoutMatch).order_by(
            KnockoutMatch.id
        ).all()

        if matches:

            st.subheader("Round 1")

            for match in matches:

                player1 = db.get(Player, match.player1_id)
                player2 = db.get(Player, match.player2_id)

                col1, col2 = st.columns([4, 1])

                with col1:

                    st.write(f"🎯 {player1.name} vs {player2.name}")

                with col2:

                    if match.winner_id:

                        winner = db.get(Player, match.winner_id)

                        st.success(winner.name)

        else:

            st.info("No knockout bracket generated yet.")

        db.close()


# STATISTICS TAB

if page == "Statistics":

    st.header("📊 Player Statistics")

    db = SessionLocal()

    players = db.query(Player).all()

    fixtures = db.query(Fixture).filter(
        Fixture.played == 1
    ).all()

    stats = {}

    for player in players:

        stats[player.id] = {
            "player": player,
            "played": 0,
            "wins": 0,
            "draws": 0,
            "losses": 0,
            "averages": []
        }

    for fixture in fixtures:

        p1 = stats[fixture.player1_id]
        p2 = stats[fixture.player2_id]

        p1["played"] += 1
        p2["played"] += 1

        try:
            p1["averages"].append(float(fixture.player1_average))
        except:
            pass

        try:
            p2["averages"].append(float(fixture.player2_average))
        except:
            pass

        if fixture.player1_legs > fixture.player2_legs:

            p1["wins"] += 1
            p2["losses"] += 1

        elif fixture.player2_legs > fixture.player1_legs:

            p2["wins"] += 1
            p1["losses"] += 1

        else:

            p1["draws"] += 1
            p2["draws"] += 1

    rows = []

    for item in stats.values():

        avg = 0

        if item["averages"]:

            avg = round(
                sum(item["averages"]) / len(item["averages"]),
                2
            )

        win_pct = 0

        if item["played"] > 0:

            win_pct = round(
                (item["wins"] / item["played"]) * 100,
                1
            )

        rows.append({
            "Player": item["player"].name,
            "Win %": win_pct,
            "3 Dart Average": avg
        })

    df = pd.DataFrame(rows)

    if not df.empty:

        df = df.sort_values(
            by=["Win %", "3 Dart Average"],
            ascending=False
        )

        styled_stats = (
            df.style.set_properties(
                **{
                "text-align": "center",
                "font-weight": "bold",
                "font-size": "15px"
                }
            )
        )

        st.dataframe(
            styled_stats,
            hide_index=True,
            use_container_width=True
        )

    else:

        st.info("No statistics available yet.")

    db.close()

if page == "View Player":

    st.header("🎯 Player Profile")

    player_id = st.session_state.get("view_player_id")

    if not player_id:

        st.info("No player selected.")

    else:

        db = SessionLocal()

        player = db.get(
            Player,
            player_id
        )

        if not player:

            st.error("Player not found.")

        else:

            col1, col2 = st.columns([1, 4])

            with col1:

                if player.logo_path and os.path.exists(player.logo_path):

                    st.image(
                        player.logo_path,
                        width=120
                    )

            with col2:

                st.subheader(player.name)

                if player.nickname:

                    st.write(f"Nickname: {player.nickname}")

            fixtures = db.query(Fixture).filter(
                (
                    Fixture.player1_id == player_id
                )
                |
                (
                    Fixture.player2_id == player_id
                )
            ).all()

            played = 0
            wins = 0
            draws = 0
            losses = 0
            averages = []

            results = []
            upcoming = []

            players = db.query(Player).all()

            player_lookup = {
                p.id: display_player_name(p)
                for p in players
            }

            for fixture in fixtures:

                opponent_id = (
                    fixture.player2_id
                    if fixture.player1_id == player_id
                    else fixture.player1_id
                )

                opponent_name = player_lookup.get(
                    opponent_id,
                    "Unknown"
                )

                if fixture.played == 1:

                    played += 1

                    if fixture.player1_id == player_id:

                        player_legs = fixture.player1_legs
                        opponent_legs = fixture.player2_legs
                        player_average = fixture.player1_average

                    else:

                        player_legs = fixture.player2_legs
                        opponent_legs = fixture.player1_legs
                        player_average = fixture.player2_average

                    try:

                        averages.append(
                            float(player_average)
                        )

                    except:

                        pass

                    if player_legs > opponent_legs:

                        wins += 1
                        result_letter = "W"

                    elif player_legs < opponent_legs:

                        losses += 1
                        result_letter = "L"

                    else:

                        draws += 1
                        result_letter = "D"

                    results.append(
                        {
                            "Opponent": opponent_name,
                            "Result": result_letter,
                            "Score": f"{player_legs} - {opponent_legs}",
                            "Average": player_average
                        }
                    )

                else:

                    upcoming.append(
                        {
                            "Opponent": opponent_name,
                            "Round": fixture.round_number
                        }
                    )

            win_pct = 0

            if played > 0:

                win_pct = round(
                    (wins / played) * 100,
                    1
                )

            avg = 0

            if averages:

                avg = round(
                    sum(averages) / len(averages),
                    2
                )

            col1, col2, col3, col4 = st.columns(4)

            col1.metric("Win %", win_pct)
            col2.metric("3 Dart Average", avg)
            col3.metric("Played", played)
            col4.metric("Wins", wins)

            col5, col6, col7 = st.columns(3)

            col5.metric("Draws", draws)
            col6.metric("Losses", losses)
            col7.metric("Remaining Fixtures", len(upcoming))

            st.divider()

            st.subheader("Recent Results")

            if results:

                st.dataframe(
                    pd.DataFrame(results),
                    hide_index=True,
                    use_container_width=True
                )

            else:

                st.info("No results yet.")

            st.divider()

            st.subheader("Upcoming Fixtures")

            if upcoming:

                st.dataframe(
                    pd.DataFrame(upcoming),
                    hide_index=True,
                    use_container_width=True
                )

            else:

                st.info("No upcoming fixtures.")

        db.close()