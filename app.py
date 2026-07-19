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
from textwrap import dedent

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
    
/* =====================================================
   PREMIUM LEAGUE TABLE
   ===================================================== */

.premium-table-wrapper {
    background: linear-gradient(145deg, #111827, #05080f);
    border: 1px solid rgba(245, 197, 66, 0.5);
    border-radius: 20px;
    padding: 12px;
    margin-top: 15px;
    margin-bottom: 25px;
    box-shadow:
        0 14px 35px rgba(0, 0, 0, 0.35),
        0 0 25px rgba(245, 197, 66, 0.06);
    overflow-x: auto;
}

.premium-league-table {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0 7px;
    color: white;
    min-width: 950px;
}

.premium-league-table thead th {
    color: #f5c542;
    padding: 12px 10px;
    font-size: 13px;
    font-weight: 900;
    letter-spacing: 1px;
    text-transform: uppercase;
    text-align: center;
    border-bottom: 1px solid rgba(245, 197, 66, 0.35);
}

.premium-league-table thead th.player-heading {
    text-align: left;
}

.premium-league-table tbody tr {
    background: linear-gradient(
        90deg,
        rgba(23, 31, 44, 0.96),
        rgba(10, 15, 24, 0.96)
    );
    transition:
        transform 0.18s ease,
        background 0.18s ease,
        box-shadow 0.18s ease;
}

.premium-league-table tbody tr:hover {
    transform: translateY(-2px);
    background: linear-gradient(
        90deg,
        rgba(49, 43, 23, 0.96),
        rgba(15, 20, 29, 0.96)
    );
    box-shadow: 0 7px 22px rgba(0, 0, 0, 0.3);
}

.premium-league-table tbody td {
    padding: 14px 10px;
    text-align: center;
    font-size: 15px;
    font-weight: 750;
    border-top: 1px solid rgba(255, 255, 255, 0.04);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}

.premium-league-table tbody td:first-child {
    border-radius: 13px 0 0 13px;
}

.premium-league-table tbody td:last-child {
    border-radius: 0 13px 13px 0;
}

.position-cell {
    width: 55px;
    font-size: 19px !important;
    color: #d8dde7;
}

.player-cell {
    text-align: left !important;
    min-width: 210px;
}

.player-profile {
    display: flex;
    align-items: center;
    gap: 12px;
}

.player-table-logo {
    width: 46px;
    height: 46px;
    min-width: 46px;
    border-radius: 50%;
    object-fit: cover;
    background: #080d15;
    border: 2px solid rgba(245, 197, 66, 0.65);
    box-shadow: 0 0 12px rgba(245, 197, 66, 0.12);
}

.player-placeholder-logo {
    width: 46px;
    height: 46px;
    min-width: 46px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #080d15;
    border: 2px solid rgba(245, 197, 66, 0.5);
    font-size: 22px;
}

.player-primary-name {
    color: white;
    font-size: 16px;
    font-weight: 900;
    line-height: 1.15;
}

.player-real-name {
    color: #929bab;
    font-size: 12px;
    font-weight: 650;
    margin-top: 4px;
}

.form-cell {
    min-width: 145px;
    white-space: nowrap;
}

.form-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 25px;
    height: 25px;
    margin: 0 2px;
    border-radius: 7px;
    color: white;
    font-size: 11px;
    font-weight: 900;
}

.form-win {
    background: #118848;
    box-shadow: 0 0 7px rgba(17, 136, 72, 0.4);
}

.form-draw {
    background: #b18416;
}

.form-loss {
    background: #b52d38;
}

.form-empty {
    background: #313846;
    color: #9da5b3;
}

.average-cell {
    color: #e5e9f0;
    font-weight: 850 !important;
}

.difference-positive {
    color: #38d981;
}

.difference-negative {
    color: #ff6670;
}

.difference-neutral {
    color: #bfc5d2;
}

.points-cell {
    color: #f5c542;
    font-size: 20px !important;
    font-weight: 950 !important;
}

.leader-row {
    background: linear-gradient(
        90deg,
        rgba(80, 62, 14, 0.9),
        rgba(20, 22, 25, 0.98)
    ) !important;
}

@media (max-width: 800px) {
    .premium-table-wrapper {
        padding: 7px;
        border-radius: 14px;
    }

    .premium-league-table tbody td {
        padding: 11px 8px;
    }
}

    </style>
    """,
    unsafe_allow_html=True

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

    if "public_page" not in st.session_state:
        st.session_state.public_page = "Login"

    if "login_mode" not in st.session_state:
        st.session_state.login_mode = "login"

    # ---------------------------------------------------------
    # LOAD PUBLIC DASHBOARD INFORMATION
    # ---------------------------------------------------------

    public_db = SessionLocal()

    public_players = public_db.query(Player).all()

    public_player_lookup = {
        player.id: display_player_name(player)
        for player in public_players
    }

    public_next_fixture = public_db.query(Fixture).filter(
        Fixture.played == 0
    ).order_by(
        Fixture.round_number,
        Fixture.id
    ).first()

    public_latest_result = public_db.query(Fixture).filter(
        Fixture.played == 1
    ).order_by(
        Fixture.id.desc()
    ).first()

    public_latest_announcement = public_db.query(
        Announcement
    ).order_by(
        Announcement.id.desc()
    ).first()

    public_players_count = len(public_players)

    public_matches_played = public_db.query(Fixture).filter(
        Fixture.played == 1
    ).count()

    public_db.close()

    # ---------------------------------------------------------
    # LANDING PAGE HEADER
    # ---------------------------------------------------------

    st.markdown(
        """
        <div style="text-align:center;">
        """,
        unsafe_allow_html=True,
    )

    logo_left, logo_centre, logo_right = st.columns([2, 1, 2])

    with logo_centre:
        st.image(
            "assets/royal_oak_logo.png",
            use_container_width=True
        )

    st.markdown(
        """
        <h1 style="text-align:center; margin-bottom:0;">
            Ye Royal Oak Darts League
        </h1>

        <p style="
            text-align:center;
            color:#bfc5d2;
            font-size:18px;
            margin-top:8px;
        ">
            Official League Portal
        </p>
        """,
        unsafe_allow_html=True,
    )

    # ---------------------------------------------------------
    # PUBLIC NAVIGATION
    # ---------------------------------------------------------

    nav_col1, nav_col2, nav_col3 = st.columns(3)

    with nav_col1:

        if st.button(
            "🔐 Login",
            key="landing_login_page",
            use_container_width=True
        ):

            st.session_state.public_page = "Login"
            st.rerun()

    with nav_col2:

        if st.button(
            "🏆 League Table",
            key="landing_league_page",
            use_container_width=True
        ):

            st.session_state.public_page = "League Table"
            st.rerun()

    with nav_col3:

        if st.button(
            "📱 Social Media",
            key="landing_socials_page",
            use_container_width=True
        ):

            st.session_state.public_page = "Socials"
            st.rerun()

    st.divider()

    # ---------------------------------------------------------
    # PUBLIC DASHBOARD CARDS
    # ---------------------------------------------------------

    stat_col1, stat_col2 = st.columns(2)

    with stat_col1:

        dashboard_card(
            "👥 Registered Players",
            public_players_count,
            "Current league members"
        )

    with stat_col2:

        dashboard_card(
            "🎯 Matches Played",
            public_matches_played,
            "Completed league matches"
        )

    fixture_col, result_col = st.columns(2)

    with fixture_col:

        if public_next_fixture:

            next_p1 = public_player_lookup.get(
                public_next_fixture.player1_id,
                "Unknown"
            )

            next_p2 = public_player_lookup.get(
                public_next_fixture.player2_id,
                "Unknown"
            )

            match_card(
                "📅 Next Fixture",
                next_p1,
                f"Round {public_next_fixture.round_number}",
                next_p2
            )

        else:

            dashboard_card(
                "📅 Next Fixture",
                "None",
                "No upcoming fixtures"
            )

    with result_col:

        if public_latest_result:

            result_p1 = public_player_lookup.get(
                public_latest_result.player1_id,
                "Unknown"
            )

            result_p2 = public_player_lookup.get(
                public_latest_result.player2_id,
                "Unknown"
            )

            match_card(
                "🔥 Latest Result",
                result_p1,
                (
                    f"{public_latest_result.player1_legs}"
                    f" - "
                    f"{public_latest_result.player2_legs}"
                ),
                result_p2
            )

        else:

            dashboard_card(
                "🔥 Latest Result",
                "None",
                "No completed results yet"
            )

    if public_latest_announcement:

        dashboard_card(
            "📢 Latest Announcement",
            public_latest_announcement.title,
            public_latest_announcement.message
        )

    st.divider()

    # ---------------------------------------------------------
    # LOGIN / CREATE ACCOUNT PAGE
    # ---------------------------------------------------------

    if st.session_state.public_page == "Login":

        form_left, form_centre, form_right = st.columns(
            [1, 1.5, 1]
        )

        with form_centre:

            login_col, create_col = st.columns(2)

            with login_col:

                if st.button(
                    "🔐 Player Login",
                    key="landing_login_mode",
                    use_container_width=True
                ):

                    st.session_state.login_mode = "login"
                    st.rerun()

            with create_col:

                if st.button(
                    "🆕 Create Account",
                    key="landing_create_mode",
                    use_container_width=True
                ):

                    st.session_state.login_mode = "create"
                    st.rerun()

            st.divider()

            if st.session_state.login_mode == "login":

                st.markdown("### 🔐 Player Login")

                username = st.text_input(
                    "Username",
                    key="landing_login_username"
                )

                password = st.text_input(
                    "Password",
                    type="password",
                    key="landing_login_password"
                )

                if st.button(
                    "Enter League Portal",
                    key="landing_enter_portal",
                    use_container_width=True
                ):

                    login_db = SessionLocal()

                    user = login_db.query(User).filter(
                        User.username == username,
                        User.password == password
                    ).first()

                    if user:

                        st.session_state.logged_in = True
                        st.session_state.role = user.role
                        st.session_state.username = user.username
                        st.session_state.player_id = user.player_id
                        st.session_state.page = "Home"

                        login_db.close()

                        st.rerun()

                    else:

                        login_db.close()

                        st.error(
                            "Incorrect username or password."
                        )

            else:

                st.markdown("### 🆕 Create Player Account")

                create_db = SessionLocal()

                account_players = create_db.query(Player).all()
                existing_users = create_db.query(User).all()

                used_player_ids = {
                    user.player_id
                    for user in existing_users
                    if user.player_id is not None
                }

                available_players = {
                    player.name: player.id
                    for player in account_players
                    if player.id not in used_player_ids
                }

                if not available_players:

                    st.info(
                        "All player profiles already have accounts."
                    )

                else:

                    new_username = st.text_input(
                        "Choose Username",
                        key="landing_create_username"
                    )

                    new_password = st.text_input(
                        "Choose Password",
                        type="password",
                        key="landing_create_password"
                    )

                    confirm_password = st.text_input(
                        "Confirm Password",
                        type="password",
                        key="landing_confirm_password"
                    )

                    selected_player = st.selectbox(
                        "Select Your Player Profile",
                        list(available_players.keys()),
                        key="landing_select_player"
                    )

                    if st.button(
                        "Create My Account",
                        key="landing_create_account",
                        use_container_width=True
                    ):

                        existing_username = create_db.query(
                            User
                        ).filter(
                            User.username == new_username.strip()
                        ).first()

                        if not new_username.strip():

                            st.error(
                                "Please choose a username."
                            )

                        elif not new_password:

                            st.error(
                                "Please choose a password."
                            )

                        elif len(new_password) < 6:

                            st.error(
                                "Password must contain at least 6 characters."
                            )

                        elif new_password != confirm_password:

                            st.error(
                                "The passwords do not match."
                            )

                        elif existing_username:

                            st.error(
                                "That username is already in use."
                            )

                        else:

                            new_user = User(
                                username=new_username.strip(),
                                password=new_password,
                                role="viewer",
                                player_id=available_players[
                                    selected_player
                                ]
                            )

                            create_db.add(new_user)
                            create_db.commit()

                            st.success(
                                "Account created successfully. "
                                "You can now log in."
                            )

                            st.session_state.login_mode = "login"

                            create_db.close()

                            st.rerun()

                create_db.close()

    # ---------------------------------------------------------
    # PUBLIC LEAGUE TABLE
    # ---------------------------------------------------------

    elif st.session_state.public_page == "League Table":

        st.markdown(
            """
            <h2 style="text-align:center;">
                🏆 Current League Table
            </h2>
            """,
            unsafe_allow_html=True
        )

        league_db = SessionLocal()

        league_players = league_db.query(Player).all()

        completed_fixtures = league_db.query(Fixture).filter(
            Fixture.played == 1
        ).all()

        public_table = {}

        for player in league_players:

            public_table[player.id] = {
                "player": player,
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "legs_for": 0,
                "legs_against": 0,
                "points": 0
            }

        for fixture in completed_fixtures:

            if (
                fixture.player1_id not in public_table
                or fixture.player2_id not in public_table
            ):

                continue

            p1 = public_table[fixture.player1_id]
            p2 = public_table[fixture.player2_id]

            p1["played"] += 1
            p2["played"] += 1

            p1["legs_for"] += fixture.player1_legs
            p1["legs_against"] += fixture.player2_legs

            p2["legs_for"] += fixture.player2_legs
            p2["legs_against"] += fixture.player1_legs

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

        public_rows = []

        for table_data in public_table.values():

            public_rows.append(
                {
                    "Player": display_player_name(
                        table_data["player"]
                    ),
                    "P": table_data["played"],
                    "W": table_data["won"],
                    "D": table_data["drawn"],
                    "L": table_data["lost"],
                    "LF": table_data["legs_for"],
                    "LA": table_data["legs_against"],
                    "+/-": (
                        table_data["legs_for"]
                        -
                        table_data["legs_against"]
                    ),
                    "Pts": table_data["points"]
                }
            )

        public_rows = sorted(
            public_rows,
            key=lambda row: (
                row["Pts"],
                row["+/-"],
                row["W"]
            ),
            reverse=True
        )

        if public_rows:

            public_league_df = pd.DataFrame(
                public_rows
            )

            public_league_df.insert(
                0,
                "Pos",
                range(
                    1,
                    len(public_league_df) + 1
                )
            )

            public_league_df["Pos"] = (
                public_league_df["Pos"].astype(str)
            )

            if len(public_league_df) > 0:
                public_league_df.loc[0, "Pos"] = "🥇"

            if len(public_league_df) > 1:
                public_league_df.loc[1, "Pos"] = "🥈"

            if len(public_league_df) > 2:
                public_league_df.loc[2, "Pos"] = "🥉"

            st.dataframe(
                public_league_df,
                hide_index=True,
                use_container_width=True
            )

        else:

            st.info(
                "The league table will appear after results are entered."
            )

        league_db.close()

    # ---------------------------------------------------------
    # SOCIAL MEDIA PAGE
    # ---------------------------------------------------------

    elif st.session_state.public_page == "Socials":

        socials_left, socials_centre, socials_right = st.columns(
            [1, 1.5, 1]
        )

        with socials_centre:

            st.markdown(
                """
                <h2 style="text-align:center;">
                    📱 Follow The League
                </h2>

                <p style="
                    text-align:center;
                    color:#bfc5d2;
                ">
                    Keep up with league news, videos and results.
                </p>
                """,
                unsafe_allow_html=True
            )

            st.link_button(
                "📘 Facebook Community",
                "https://www.facebook.com/groups/1063585262569763/",
                use_container_width=True
            )

            st.link_button(
                "🎵 TikTok Videos",
                "https://www.tiktok.com/@yeroyaloakdarts?is_from_webapp=1&sender_device=pc",
                use_container_width=True
            )

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

# =========================================================
# ADMIN: PLAYERS
# =========================================================

if page == "Players":

    if not is_admin:
        st.error("Administrator access is required.")

    else:
        st.header("➕ Player Management")

        db = SessionLocal()

        st.subheader("Add New Player")

        name = st.text_input(
            "Player Name",
            key="admin_add_player_name"
        )

        nickname = st.text_input(
            "Nickname",
            key="admin_add_player_nickname"
        )

        logo = st.file_uploader(
            "Player Logo",
            type=["png", "jpg", "jpeg"],
            key="admin_add_player_logo"
        )

        if st.button(
            "➕ Add Player",
            key="admin_add_player_button",
            use_container_width=True
        ):

            if not name.strip():
                st.error("Please enter the player's name.")

            elif logo is None:
                st.error("Please upload a player logo.")

            else:
                os.makedirs(
                    "assets/logos",
                    exist_ok=True
                )

                safe_filename = (
                    f"player_{logo.name}"
                )

                logo_path = os.path.join(
                    "assets/logos",
                    safe_filename
                )

                with open(logo_path, "wb") as file:
                    file.write(logo.getbuffer())

                new_player = Player(
                    name=name.strip(),
                    nickname=nickname.strip(),
                    logo_path=logo_path
                )

                db.add(new_player)
                db.commit()

                if "league_standings" in st.session_state:
                    del st.session_state["league_standings"]

                db.close()

                st.success("Player added successfully.")
                st.rerun()

        st.divider()
        st.subheader("Current Players")

        players = db.query(Player).order_by(
            Player.name
        ).all()

        if not players:
            st.info("No players have been added yet.")

        for player in players:

            player_title = display_player_name(player)

            with st.expander(
                f"🎯 {player_title} — Player ID {player.id}"
            ):

                info_col, edit_col = st.columns(
                    [1, 3]
                )

                with info_col:

                    if (
                        player.logo_path
                        and os.path.exists(player.logo_path)
                    ):
                        st.image(
                            player.logo_path,
                            width=130
                        )
                    else:
                        st.info("No logo")

                with edit_col:

                    with st.form(
                        key=f"admin_player_form_{player.id}"
                    ):

                        updated_name = st.text_input(
                            "Player Name",
                            value=player.name or "",
                            key=f"admin_player_name_{player.id}"
                        )

                        updated_nickname = st.text_input(
                            "Nickname",
                            value=player.nickname or "",
                            key=f"admin_player_nickname_{player.id}"
                        )

                        updated_logo = st.file_uploader(
                            "Upload Replacement Logo",
                            type=["png", "jpg", "jpeg"],
                            key=f"admin_player_logo_{player.id}"
                        )

                        save_player = st.form_submit_button(
                            "💾 Save Changes",
                            use_container_width=True
                        )

                    if save_player:

                        edit_db = SessionLocal()

                        target_player = edit_db.get(
                            Player,
                            player.id
                        )

                        if not target_player:
                            edit_db.close()
                            st.error("Player could not be found.")

                        elif not updated_name.strip():
                            edit_db.close()
                            st.error("Player name cannot be empty.")

                        else:
                            target_player.name = (
                                updated_name.strip()
                            )

                            target_player.nickname = (
                                updated_nickname.strip()
                            )

                            if updated_logo is not None:

                                os.makedirs(
                                    "assets/logos",
                                    exist_ok=True
                                )

                                replacement_path = os.path.join(
                                    "assets/logos",
                                    f"player_{player.id}_{updated_logo.name}"
                                )

                                with open(
                                    replacement_path,
                                    "wb"
                                ) as file:
                                    file.write(
                                        updated_logo.getbuffer()
                                    )

                                target_player.logo_path = (
                                    replacement_path
                                )

                            edit_db.commit()
                            edit_db.close()

                            if "league_standings" in st.session_state:
                                del st.session_state[
                                    "league_standings"
                                ]

                            st.success(
                                f"{updated_name.strip()} updated."
                            )

                            st.rerun()

                st.divider()

                if st.button(
                    "🗑 Delete Player",
                    key=f"admin_delete_player_{player.id}",
                    use_container_width=True
                ):

                    delete_db = SessionLocal()

                    linked_users = delete_db.query(User).filter(
                        User.player_id == player.id
                    ).all()

                    linked_fixtures = delete_db.query(Fixture).filter(
                        (
                            Fixture.player1_id == player.id
                        )
                        |
                        (
                            Fixture.player2_id == player.id
                        )
                    ).count()

                    if linked_users:
                        st.error(
                            "This player is linked to a user account. "
                            "Remove or reassign that account first."
                        )

                    elif linked_fixtures > 0:
                        st.error(
                            "This player has fixtures and cannot be "
                            "deleted safely."
                        )

                    else:
                        target_player = delete_db.get(
                            Player,
                            player.id
                        )

                        if target_player:
                            delete_db.delete(target_player)
                            delete_db.commit()

                        if "league_standings" in st.session_state:
                            del st.session_state[
                                "league_standings"
                            ]

                        delete_db.close()

                        st.success("Player deleted.")
                        st.rerun()

                    delete_db.close()

        db.close()

# =========================================================
# ADMIN: USERS
# =========================================================

if page == "Users":

    if not is_admin:
        st.error("Administrator access is required.")

    else:
        st.header("👥 User Account Management")

        db = SessionLocal()

        players = db.query(Player).order_by(
            Player.name
        ).all()

        player_options = {
            display_player_name(player): player.id
            for player in players
        }

        st.subheader("Create User")

        new_username = st.text_input(
            "Username",
            key="admin_new_username"
        )

        new_password = st.text_input(
            "Password",
            type="password",
            key="admin_new_password"
        )

        new_role = st.selectbox(
            "Account Role",
            ["viewer", "admin"],
            key="admin_new_role"
        )

        linked_player_options = {
            "No linked player": None,
            **player_options
        }

        selected_player_name = st.selectbox(
            "Linked Player",
            list(linked_player_options.keys()),
            key="admin_new_linked_player"
        )

        if st.button(
            "➕ Create User",
            key="admin_create_user_button",
            use_container_width=True
        ):

            username_clean = new_username.strip()

            existing_user = db.query(User).filter(
                User.username == username_clean
            ).first()

            selected_player_id = linked_player_options[
                selected_player_name
            ]

            player_already_linked = None

            if selected_player_id is not None:
                player_already_linked = db.query(User).filter(
                    User.player_id == selected_player_id
                ).first()

            if not username_clean:
                st.error("Please enter a username.")

            elif not new_password:
                st.error("Please enter a password.")

            elif len(new_password) < 6:
                st.error(
                    "Password must contain at least six characters."
                )

            elif existing_user:
                st.error("That username already exists.")

            elif player_already_linked:
                st.error(
                    "That player is already linked to another account."
                )

            else:
                new_user = User(
                    username=username_clean,
                    password=new_password,
                    role=new_role,
                    player_id=selected_player_id
                )

                db.add(new_user)
                db.commit()
                db.close()

                st.success("User account created.")
                st.rerun()

        st.divider()
        st.subheader("Current Users")

        users = db.query(User).order_by(
            User.username
        ).all()

        if not users:
            st.info("No user accounts were found.")

        for user in users:

            linked_player = None

            if user.player_id is not None:
                linked_player = db.get(
                    Player,
                    user.player_id
                )

            linked_name = (
                display_player_name(linked_player)
                if linked_player
                else "No linked player"
            )

            with st.expander(
                f"👤 {user.username} — {user.role}"
            ):

                st.write(f"**Linked player:** {linked_name}")

                editable_player_options = {
                    "No linked player": None,
                    **player_options
                }

                current_player_name = "No linked player"

                for option_name, option_id in (
                    editable_player_options.items()
                ):
                    if option_id == user.player_id:
                        current_player_name = option_name
                        break

                option_names = list(
                    editable_player_options.keys()
                )

                current_player_index = option_names.index(
                    current_player_name
                )

                edited_role = st.selectbox(
                    "Role",
                    ["viewer", "admin"],
                    index=(
                        1
                        if str(user.role).lower() == "admin"
                        else 0
                    ),
                    key=f"admin_edit_role_{user.id}"
                )

                edited_player_name = st.selectbox(
                    "Linked Player",
                    option_names,
                    index=current_player_index,
                    key=f"admin_edit_player_{user.id}"
                )

                new_user_password = st.text_input(
                    "New Password",
                    type="password",
                    help=(
                        "Leave blank to keep the existing password."
                    ),
                    key=f"admin_edit_password_{user.id}"
                )

                action_col1, action_col2 = st.columns(2)

                with action_col1:

                    if st.button(
                        "💾 Save User",
                        key=f"admin_save_user_{user.id}",
                        use_container_width=True
                    ):

                        edit_db = SessionLocal()

                        target_user = edit_db.get(
                            User,
                            user.id
                        )

                        selected_player_id = (
                            editable_player_options[
                                edited_player_name
                            ]
                        )

                        conflicting_user = None

                        if selected_player_id is not None:
                            conflicting_user = (
                                edit_db.query(User).filter(
                                    User.player_id
                                    == selected_player_id,
                                    User.id != user.id
                                ).first()
                            )

                        if not target_user:
                            st.error(
                                "The user account could not be found."
                            )

                        elif conflicting_user:
                            st.error(
                                "That player is already linked to "
                                "another account."
                            )

                        elif (
                            new_user_password
                            and len(new_user_password) < 6
                        ):
                            st.error(
                                "The new password must contain at "
                                "least six characters."
                            )

                        else:
                            target_user.role = edited_role
                            target_user.player_id = (
                                selected_player_id
                            )

                            if new_user_password:
                                target_user.password = (
                                    new_user_password
                                )

                            edit_db.commit()

                            if (
                                user.username
                                == st.session_state.get("username")
                            ):
                                st.session_state.role = edited_role
                                st.session_state.player_id = (
                                    selected_player_id
                                )

                            st.success("User updated.")
                            st.rerun()

                        edit_db.close()

                with action_col2:

                    if st.button(
                        "🗑 Delete User",
                        key=f"admin_delete_user_{user.id}",
                        use_container_width=True
                    ):

                        if (
                            user.username
                            == st.session_state.get("username")
                        ):
                            st.error(
                                "You cannot delete the account "
                                "you are currently using."
                            )

                        else:
                            delete_db = SessionLocal()

                            target_user = delete_db.get(
                                User,
                                user.id
                            )

                            if target_user:
                                delete_db.delete(target_user)
                                delete_db.commit()

                            delete_db.close()

                            st.success("User account deleted.")
                            st.rerun()

        db.close()

# =========================================================
# ADMIN: TOURNAMENTS
# =========================================================

if page == "Tournaments":

    if not is_admin:
        st.error("Administrator access is required.")

    else:
        st.header("🏆 Tournament Management")

        db = SessionLocal()

        all_players = db.query(Player).order_by(
            Player.name
        ).all()

        player_options = {
            display_player_name(player): player.id
            for player in all_players
        }

        # -----------------------------------------------------
        # CREATE TOURNAMENT
        # -----------------------------------------------------

        st.subheader("Create Tournament")

        tournament_name = st.text_input(
            "Tournament Name",
            key="admin_tournament_name"
        )

        format_type = st.selectbox(
            "Tournament Format",
            [
                "League + Knockout",
                "League Only",
                "Knockout Only"
            ],
            key="admin_tournament_format"
        )

        legs_format = st.selectbox(
            "Match Format",
            [
                "Best of 3",
                "Best of 5",
                "Best of 6",
                "Best of 7",
                "Best of 9",
                "Best of 11"
            ],
            key="admin_tournament_legs"
        )

        selected_players = st.multiselect(
            "Select Players",
            list(player_options.keys()),
            key="admin_tournament_players"
        )

        if st.button(
            "🏆 Create Tournament",
            key="admin_create_tournament",
            use_container_width=True
        ):

            clean_name = tournament_name.strip()

            existing_tournament = db.query(Tournament).filter(
                Tournament.name == clean_name
            ).first()

            if not clean_name:
                st.error("Please enter a tournament name.")

            elif existing_tournament:
                st.error(
                    "A tournament with that name already exists."
                )

            elif len(selected_players) < 2:
                st.error(
                    "Please select at least two players."
                )

            else:
                tournament = Tournament(
                    name=clean_name,
                    format_type=format_type,
                    legs_format=legs_format
                )

                db.add(tournament)
                db.commit()
                db.refresh(tournament)

                for player_name in selected_players:

                    link = TournamentPlayer(
                        tournament_id=tournament.id,
                        player_id=player_options[player_name]
                    )

                    db.add(link)

                db.commit()
                db.close()

                st.success("Tournament created successfully.")
                st.rerun()

        st.divider()

        # -----------------------------------------------------
        # EXISTING TOURNAMENTS
        # -----------------------------------------------------

        st.subheader("Existing Tournaments")

        tournaments = db.query(Tournament).order_by(
            Tournament.id.desc()
        ).all()

        if not tournaments:
            st.info("No tournaments have been created yet.")

        for tournament in tournaments:

            tournament_links = db.query(
                TournamentPlayer
            ).filter(
                TournamentPlayer.tournament_id == tournament.id
            ).all()

            tournament_player_ids = [
                link.player_id
                for link in tournament_links
            ]

            tournament_players = [
                player
                for player in all_players
                if player.id in tournament_player_ids
            ]

            player_names = [
                display_player_name(player)
                for player in tournament_players
            ]

            fixtures_count = db.query(Fixture).filter(
                Fixture.tournament_id == tournament.id
            ).count()

            played_count = db.query(Fixture).filter(
                Fixture.tournament_id == tournament.id,
                Fixture.played == 1
            ).count()

            with st.expander(
                f"🏆 {tournament.name}",
                expanded=False
            ):

                info_col1, info_col2, info_col3 = st.columns(3)

                with info_col1:
                    st.metric(
                        "Players",
                        len(tournament_player_ids)
                    )

                with info_col2:
                    st.metric(
                        "Fixtures",
                        fixtures_count
                    )

                with info_col3:
                    st.metric(
                        "Played",
                        played_count
                    )

                st.write(
                    f"**Format:** {tournament.format_type}"
                )

                st.write(
                    f"**Match format:** {tournament.legs_format}"
                )

                if player_names:
                    st.write(
                        "**Players:** "
                        + ", ".join(player_names)
                    )
                else:
                    st.warning(
                        "No players are linked to this tournament."
                    )

                st.divider()

                action_col1, action_col2 = st.columns(2)

                # ---------------------------------------------
                # GENERATE FIXTURES
                # ---------------------------------------------

                with action_col1:

                    if st.button(
                        "🎯 Generate Fixtures",
                        key=f"admin_generate_fixtures_{tournament.id}",
                        use_container_width=True
                    ):

                        if fixtures_count > 0:
                            st.warning(
                                "Fixtures have already been generated "
                                "for this tournament."
                            )

                        elif len(tournament_player_ids) < 2:
                            st.error(
                                "At least two players are required."
                            )

                        elif tournament.format_type == "Knockout Only":
                            st.info(
                                "Knockout-only tournament selected. "
                                "League fixtures were not generated."
                            )

                        else:
                            generated_fixtures = generate_round_robin(
                                tournament_player_ids
                            )

                            fixture_db = SessionLocal()

                            for (
                                round_number,
                                player1_id,
                                player2_id
                            ) in generated_fixtures:

                                fixture = Fixture(
                                    tournament_id=tournament.id,
                                    round_number=round_number,
                                    player1_id=player1_id,
                                    player2_id=player2_id,
                                    played=0
                                )

                                fixture_db.add(fixture)

                            fixture_db.commit()
                            fixture_db.close()

                            st.success(
                                "Fixtures generated successfully."
                            )

                            st.rerun()

                # ---------------------------------------------
                # DELETE TOURNAMENT
                # ---------------------------------------------

                with action_col2:

                    confirm_delete = st.checkbox(
                        "Confirm deletion",
                        key=f"confirm_tournament_delete_{tournament.id}"
                    )

                    if st.button(
                        "🗑 Delete Tournament",
                        key=f"admin_delete_tournament_{tournament.id}",
                        use_container_width=True
                    ):

                        if not confirm_delete:
                            st.warning(
                                "Tick Confirm deletion first."
                            )

                        else:
                            delete_db = SessionLocal()

                            delete_db.query(Fixture).filter(
                                Fixture.tournament_id
                                == tournament.id
                            ).delete(
                                synchronize_session=False
                            )

                            delete_db.query(KnockoutMatch).filter(
                                KnockoutMatch.tournament_id
                                == tournament.id
                            ).delete(
                                synchronize_session=False
                            )

                            delete_db.query(TournamentPlayer).filter(
                                TournamentPlayer.tournament_id
                                == tournament.id
                            ).delete(
                                synchronize_session=False
                            )

                            target_tournament = delete_db.get(
                                Tournament,
                                tournament.id
                            )

                            if target_tournament:
                                delete_db.delete(
                                    target_tournament
                                )

                            delete_db.commit()
                            delete_db.close()

                            if "league_standings" in st.session_state:
                                del st.session_state[
                                    "league_standings"
                                ]

                            st.success(
                                "Tournament deleted successfully."
                            )

                            st.rerun()

        db.close()

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

                # =====================================================
        # STYLED LEAGUE TABLE
        # =====================================================

        visible_rows = []

        for position, row in enumerate(rows, start=1):

            if position == 1:
                position_display = "🥇"

            elif position == 2:
                position_display = "🥈"

            elif position == 3:
                position_display = "🥉"

            else:
                position_display = str(position)

            difference = row["Difference"]

            if difference > 0:
                difference_display = f"+{difference}"
            else:
                difference_display = str(difference)

            visible_rows.append(
                {
                    "Pos": position_display,
                    "Player": row["Player"],
                    "P": row["Played"],
                    "W": row["Won"],
                    "D": row["Drawn"],
                    "L": row["Lost"],
                    "LF": row["Legs For"],
                    "LA": row["Legs Against"],
                    "+/-": difference_display,
                    "Average": row["3 Dart Average"],
                    "Points": row["Points"]
                }
            )

        visible_df = pd.DataFrame(
            visible_rows
        )

        styled_league_table = (
            visible_df.style
            .hide(axis="index")
            .format(
                {
                    "Average": "{:.2f}"
                }
            )
            .set_properties(
                subset=["Player"],
                **{
                    "text-align": "left",
                    "font-weight": "bold"
                }
            )
            .set_properties(
                subset=["Points"],
                **{
                    "font-weight": "bold",
                    "font-size": "18px"
                }
            )
            .set_properties(
                subset=["Pos"],
                **{
                    "font-size": "18px",
                    "font-weight": "bold"
                }
            )
        )

        st.dataframe(
            styled_league_table,
            hide_index=True,
            use_container_width=True,
            height=(
                min(
                    70 + len(visible_df) * 42,
                    760
                )
            ),
            column_config={
                "Pos": st.column_config.TextColumn(
                    "Pos",
                    width="small"
                ),
                "Player": st.column_config.TextColumn(
                    "Player",
                    width="large"
                ),
                "P": st.column_config.NumberColumn(
                    "P",
                    width="small"
                ),
                "W": st.column_config.NumberColumn(
                    "W",
                    width="small"
                ),
                "D": st.column_config.NumberColumn(
                    "D",
                    width="small"
                ),
                "L": st.column_config.NumberColumn(
                    "L",
                    width="small"
                ),
                "LF": st.column_config.NumberColumn(
                    "LF",
                    width="small"
                ),
                "LA": st.column_config.NumberColumn(
                    "LA",
                    width="small"
                ),
                "+/-": st.column_config.TextColumn(
                    "+/-",
                    width="small"
                ),
                "Average": st.column_config.NumberColumn(
                    "AVG",
                    format="%.2f",
                    width="small"
                ),
                "Points": st.column_config.NumberColumn(
                    "PTS",
                    width="small"
                )
            }
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

            pdf_rows = []

        for position, row in enumerate(rows, start=1):

            pdf_rows.append(
                {
                "Pos": position,
                "Player": row["Player"],
                "Played": row["Played"],
                "Won": row["Won"],
                "Drawn": row["Drawn"],
                "Lost": row["Lost"],
                "Legs For": row["Legs For"],
                "Legs Against": row["Legs Against"],
                "Difference": row["Difference"],
                "3 Dart Average": row["3 Dart Average"],
                "Points": row["Points"]
            }
        )

            league_pdf = create_league_table_pdf(
                pdf_rows
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

    st.markdown(
        """
        <h1 style='text-align:center;'>🎴 Player Card</h1>
        <p style='text-align:center; color:#bfc5d2; font-size:17px;'>
            View player profile and performance
        </p>
        """,
        unsafe_allow_html=True
    )

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
                        recent_form.append("🟢")

                    elif player_legs < opponent_legs:

                        losses += 1
                        result_letter = "L"
                        recent_form.append("🔴")

                    else:

                        draws += 1
                        result_letter = "D"
                        recent_form.append("🟡")

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

                st.subheader("🔥 Recent Results")

                if results:

                    st.dataframe(
                        pd.DataFrame(results),
                        hide_index=True,
                        use_container_width=True
                    )

                else:

                    st.info("No results yet.")

                st.divider()

                st.subheader("📅 Upcoming Fixtures")

                if upcoming:

                    st.dataframe(
                        pd.DataFrame(upcoming),
                        hide_index=True,
                        use_container_width=True
                    )

                else:

                    st.info("No upcoming fixtures.")

        db.close()