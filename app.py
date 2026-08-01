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
from datetime import date, datetime, timedelta

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

FACEBOOK_URL = (
    "https://www.facebook.com/groups/1063585262569763/"
)

TIKTOK_URL = (
    "https://www.tiktok.com/@yeroyaloakdarts"
)

YOUTUBE_URL = (
    "https://www.youtube.com/@YeRoyalOakDarts"
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
    

# =========================================================
# KNOCKOUT HELPER FUNCTIONS
# =========================================================

def calculate_knockout_seeds(db, tournament_id):

    tournament_links = db.query(
        TournamentPlayer
    ).filter(
        TournamentPlayer.tournament_id == tournament_id
    ).all()

    player_ids = [
        link.player_id
        for link in tournament_links
    ]

    players = db.query(Player).filter(
        Player.id.in_(player_ids)
    ).all()

    fixtures = db.query(Fixture).filter(
        Fixture.tournament_id == tournament_id,
        Fixture.played == 1
    ).all()

    standings = {}

    for player in players:

        standings[player.id] = {
            "player_id": player.id,
            "points": 0,
            "wins": 0,
            "difference": 0,
            "averages": []
        }

    for fixture in fixtures:

        if (
            fixture.player1_id not in standings
            or fixture.player2_id not in standings
        ):
            continue

        player1 = standings[
            fixture.player1_id
        ]

        player2 = standings[
            fixture.player2_id
        ]

        player1_legs = int(
            fixture.player1_legs or 0
        )

        player2_legs = int(
            fixture.player2_legs or 0
        )

        player1["difference"] += (
            player1_legs - player2_legs
        )

        player2["difference"] += (
            player2_legs - player1_legs
        )

        try:

            player1_average = float(
                fixture.player1_average or 0
            )

            if 0 < player1_average <= 200:

                player1["averages"].append(
                    player1_average
                )

        except (TypeError, ValueError):

            pass

        try:

            player2_average = float(
                fixture.player2_average or 0
            )

            if 0 < player2_average <= 200:

                player2["averages"].append(
                    player2_average
                )

        except (TypeError, ValueError):

            pass

        if player1_legs > player2_legs:

            player1["wins"] += 1
            player1["points"] += 2

        elif player2_legs > player1_legs:

            player2["wins"] += 1
            player2["points"] += 2

        else:

            player1["points"] += 1
            player2["points"] += 1

    seed_rows = []

    for player_id, data in standings.items():

        average = 0.0

        if data["averages"]:

            average = (
                sum(data["averages"])
                / len(data["averages"])
            )

        seed_rows.append(
            {
                "player_id": player_id,
                "points": data["points"],
                "wins": data["wins"],
                "difference": data["difference"],
                "average": average
            }
        )

    seed_rows = sorted(
        seed_rows,
        key=lambda row: (
            row["points"],
            row["difference"],
            row["wins"],
            row["average"],
            -row["player_id"]
        ),
        reverse=True
    )

    return [
        row["player_id"]
        for row in seed_rows
    ]


def create_knockout_match(
    db,
    tournament_id,
    round_name,
    player1_id,
    player2_id
):

    is_bye = (
        player1_id is not None
        and player2_id is None
    )

    match = KnockoutMatch(
        tournament_id=tournament_id,
        round_name=round_name,
        player1_id=player1_id,
        player2_id=player2_id,
        player1_score=0,
        player2_score=0,
        winner_id=(
            player1_id
            if is_bye
            else None
        ),
        played=(
            1
            if is_bye
            else 0
        )
    )

    db.add(match)


def create_preliminary_round(
    db,
    tournament_id,
    round_name,
    player_ids,
    seed_order
):

    ordered_players = sorted(
        player_ids,
        key=lambda player_id: (
            seed_order.get(
                player_id,
                9999
            )
        )
    )

    player_count = len(
        ordered_players
    )

    if player_count <= 4:
        return

    # If there are between five and eight players,
    # only enough matches are created to reduce the
    # field to exactly four qualifiers.

    if player_count <= 8:

        number_of_matches = (
            player_count - 4
        )

        bye_count = (
            player_count
            - number_of_matches * 2
        )

        bye_players = ordered_players[
            :bye_count
        ]

        match_players = ordered_players[
            bye_count:
        ]

        for player_id in bye_players:

            create_knockout_match(
                db=db,
                tournament_id=tournament_id,
                round_name=round_name,
                player1_id=player_id,
                player2_id=None
            )

        while len(match_players) >= 2:

            highest_remaining = (
                match_players.pop(0)
            )

            lowest_remaining = (
                match_players.pop(-1)
            )

            create_knockout_match(
                db=db,
                tournament_id=tournament_id,
                round_name=round_name,
                player1_id=highest_remaining,
                player2_id=lowest_remaining
            )

    else:

        match_players = (
            ordered_players.copy()
        )

        if len(match_players) % 2 != 0:

            bye_player = (
                match_players.pop(0)
            )

            create_knockout_match(
                db=db,
                tournament_id=tournament_id,
                round_name=round_name,
                player1_id=bye_player,
                player2_id=None
            )

        while len(match_players) >= 2:

            highest_remaining = (
                match_players.pop(0)
            )

            lowest_remaining = (
                match_players.pop(-1)
            )

            create_knockout_match(
                db=db,
                tournament_id=tournament_id,
                round_name=round_name,
                player1_id=highest_remaining,
                player2_id=lowest_remaining
            )


def get_knockout_round_matches(
    db,
    tournament_id,
    round_name
):

    return db.query(
        KnockoutMatch
    ).filter(
        KnockoutMatch.tournament_id
        == tournament_id,
        KnockoutMatch.round_name
        == round_name
    ).order_by(
        KnockoutMatch.id
    ).all()


def knockout_round_complete(matches):

    if not matches:
        return False

    return all(
        match.played == 1
        and match.winner_id is not None
        for match in matches
    )


def get_round_winners(matches):

    return [
        match.winner_id
        for match in matches
        if match.winner_id is not None
    ]

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

def get_winning_legs(legs_format):

    if not legs_format:
        return None

    try:

        best_of_number = int(
            str(legs_format)
            .lower()
            .replace("best of", "")
            .strip()
        )

    except (TypeError, ValueError):

        return None

    return (best_of_number // 2) + 1


def validate_match_score(
    player1_score,
    player2_score,
    legs_format
):

    try:

        player1_score = int(player1_score)
        player2_score = int(player2_score)

    except (TypeError, ValueError):

        return False, "Both scores must be whole numbers."

    if player1_score < 0 or player2_score < 0:

        return False, "Scores cannot be negative."

    if player1_score == player2_score:

        return False, "A darts match cannot finish as a draw."

    winning_legs = get_winning_legs(
        legs_format
    )

    if winning_legs is None:

        return (
            False,
            "The tournament match format could not be recognised."
        )

    highest_score = max(
        player1_score,
        player2_score
    )

    lowest_score = min(
        player1_score,
        player2_score
    )

    if highest_score != winning_legs:

        return (
            False,
            (
                f"A {legs_format} match must be won "
                f"with exactly {winning_legs} legs."
            )
        )

    if lowest_score >= winning_legs:

        return (
            False,
            "The losing player must finish below the winning score."
        )

    return True, ""

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

        # ---------------------------------------------------------
    # NEXT LEAGUE NIGHT
    # Thursday at 8:00 PM
    # ---------------------------------------------------------

    now = datetime.now()

    target_weekday = 3
    days_until_thursday = (
        target_weekday - now.weekday()
    ) % 7

    next_league_night = (
        now
        + timedelta(days=days_until_thursday)
    ).replace(
        hour=20,
        minute=0,
        second=0,
        microsecond=0
    )

    if next_league_night <= now:

        next_league_night += timedelta(
            days=7
        )

    time_until_league = (
        next_league_night - now
    )

    countdown_days = (
        time_until_league.days
    )

    countdown_hours = (
        time_until_league.seconds // 3600
    )

    countdown_minutes = (
        (
            time_until_league.seconds
            % 3600
        )
        // 60
    )

    league_night_date = (
        next_league_night.strftime(
            "%A %d %B"
        )
    )

    league_countdown = (
        f"{countdown_days}d "
        f"{countdown_hours}h "
        f"{countdown_minutes}m"
    )

        # ---------------------------------------------------------
    # CURRENT LEAGUE LEADER
    # Uses the newest league-compatible tournament
    # ---------------------------------------------------------

    public_leader_name = "No standings yet"
    public_leader_points = 0

    public_league_tournament = (
        public_db.query(Tournament)
        .filter(
            Tournament.format_type.in_(
                [
                    "League + Knockout",
                    "League Only"
                ]
            )
        )
        .order_by(
            Tournament.id.desc()
        )
        .first()
    )

    if public_league_tournament:

        public_tournament_links = (
            public_db.query(
                TournamentPlayer
            )
            .filter(
                TournamentPlayer.tournament_id
                == public_league_tournament.id
            )
            .all()
        )

        public_tournament_player_ids = {
            link.player_id
            for link
            in public_tournament_links
        }

        public_league_fixtures = (
            public_db.query(Fixture)
            .filter(
                Fixture.tournament_id
                == public_league_tournament.id,
                Fixture.played == 1
            )
            .all()
        )

        public_standings = {
            player_id: {
                "points": 0,
                "wins": 0,
                "difference": 0
            }
            for player_id
            in public_tournament_player_ids
        }

        for fixture in public_league_fixtures:

            if (
                fixture.player1_id
                not in public_standings
                or fixture.player2_id
                not in public_standings
            ):

                continue

            player1_legs = int(
                fixture.player1_legs or 0
            )

            player2_legs = int(
                fixture.player2_legs or 0
            )

            player1_data = public_standings[
                fixture.player1_id
            ]

            player2_data = public_standings[
                fixture.player2_id
            ]

            player1_data["difference"] += (
                player1_legs
                - player2_legs
            )

            player2_data["difference"] += (
                player2_legs
                - player1_legs
            )

            if player1_legs > player2_legs:

                player1_data["wins"] += 1
                player1_data["points"] += 2

            elif player2_legs > player1_legs:

                player2_data["wins"] += 1
                player2_data["points"] += 2

            else:

                player1_data["points"] += 1
                player2_data["points"] += 1

        if public_standings:

            leader_id, leader_data = max(
                public_standings.items(),
                key=lambda item: (
                    item[1]["points"],
                    item[1]["difference"],
                    item[1]["wins"]
                )
            )

            public_leader_name = (
                public_player_lookup.get(
                    leader_id,
                    "Unknown"
                )
            )

            public_leader_points = (
                leader_data["points"]
            )

    public_db.close()

    # ---------------------------------------------------------
    # PREMIUM PUBLIC LANDING PAGE
    # ---------------------------------------------------------

    st.markdown(
    dedent(
        """
        <style>

        .landing-hero {
            background:
                radial-gradient(
                    circle at top,
                    rgba(245,197,66,0.18),
                    transparent 42%
                ),
                linear-gradient(
                    145deg,
                    #172033,
                    #05080f 70%
                );
            border:
                1px solid
                rgba(245,197,66,0.55);
            border-radius: 28px;
            padding: 28px 22px;
            margin-bottom: 22px;
            text-align: center;
        }

        /* Keep the rest of your landing CSS here */

        </style>
        """
    ).strip(),
    unsafe_allow_html=True
)

    # ---------------------------------------------------------
    # HERO
    # ---------------------------------------------------------

    hero_left, hero_logo, hero_right = (
        st.columns([2, 1, 2])
    )

    with hero_logo:

        st.image(
            "assets/royal_oak_logo.png",
            use_container_width=True
        )

    st.markdown(
        dedent(
            """
            <div class="landing-hero">

                <div class="landing-eyebrow">
                    Official League Portal
                </div>

                <div class="landing-title">
                    Ye Royal Oak<br>
                    Darts League
                </div>

                <div class="landing-subtitle">
                    Fixtures · Results · Standings ·
                    Awards · Player Profiles
            </div>

            </div>
            """
        ).strip(),
        unsafe_allow_html=True
)

    # ---------------------------------------------------------
    # PRIMARY NAVIGATION
    # ---------------------------------------------------------

    nav_col1, nav_col2, nav_col3 = (
        st.columns(3)
    )

    with nav_col1:

        if st.button(
            "🔐 Login / Create Account",
            key="premium_landing_login",
            use_container_width=True
        ):

            st.session_state.public_page = (
                "Login"
            )

            st.rerun()

    with nav_col2:

        if st.button(
            "🏆 View League Table",
            key="premium_landing_league",
            use_container_width=True
        ):

            st.session_state.public_page = (
                "League Table"
            )

            st.rerun()

    with nav_col3:

        if st.button(
            "📱 Follow the League",
            key="premium_landing_socials",
            use_container_width=True
        ):

            st.session_state.public_page = (
                "Socials"
            )

            st.rerun()

    st.divider()

    # ---------------------------------------------------------
    # FEATURE CARDS
    # ---------------------------------------------------------

    feature_col1, feature_col2, feature_col3 = (
        st.columns(3)
    )

    with feature_col1:

        st.markdown(
            dedent(
                f"""
                <div class="landing-panel">

                    <div class="landing-panel-title">
                        📅 Next League Night
                    </div>

                    <div class="landing-panel-value">
                        {league_night_date}
                    </div>

                    <div class="landing-panel-detail">
                        First match at 8:00 PM
                    </div>

                    <div style="
                        color:#f5c542;
                        font-size:20px;
                        font-weight:900;
                        margin-top:14px;
                    ">
                        {league_countdown}
                    </div>

                </div>
                """
            ).strip(),
            unsafe_allow_html=True
        )

    with feature_col2:

        st.markdown(
            dedent(
                f"""
                <div class="landing-panel">

                    <div class="landing-panel-title">
                        👑 Current League Leader
                    </div>

                    <div class="landing-panel-value">
                        {public_leader_name}
                    </div>

                    <div class="landing-panel-detail">
                        {public_leader_points} league points
                    </div>

                    <div style="
                        font-size:34px;
                        margin-top:13px;
                    ">
                        🥇
                    </div>

                </div>
                """
            ).strip(),
            unsafe_allow_html=True
        )

    with feature_col3:

        if public_next_fixture:

            next_player1 = public_player_lookup.get(
                public_next_fixture.player1_id,
                "Unknown"
            )

            next_player2 = public_player_lookup.get(
                public_next_fixture.player2_id,
                "Unknown"
            )

            st.markdown(
                dedent(
                    f"""
                    <div class="landing-panel">

                        <div class="landing-panel-title">
                            🎯 Next Fixture
                        </div>

                        <div class="landing-panel-value">
                            {next_player1}
                        </div>

                        <div class="landing-vs">
                            VS
                        </div>

                        <div style="
                            color:white;
                            font-size:24px;
                            font-weight:900;
                        ">
                            {next_player2}
                        </div>

                        <div class="landing-panel-detail">
                            Round {public_next_fixture.round_number}
                        </div>

                    </div>
                    """
                ).strip(),
                unsafe_allow_html=True
            )

    # ---------------------------------------------------------
    # LEAGUE ACTIVITY
    # ---------------------------------------------------------

    activity_col1, activity_col2 = (
        st.columns(2)
    )

    with activity_col1:

        dashboard_card(
            "👥 Registered Players",
            public_players_count,
            "Current league members"
        )

    with activity_col2:

        dashboard_card(
            "🎯 Matches Completed",
            public_matches_played,
            "League results recorded"
        )

    if public_latest_result:

        latest_player1 = (
            public_player_lookup.get(
                public_latest_result.player1_id,
                "Unknown"
            )
        )

        latest_player2 = (
            public_player_lookup.get(
                public_latest_result.player2_id,
                "Unknown"
            )
        )

        match_card(
            "🔥 Latest Result",
            latest_player1,
            (
                f"{public_latest_result.player1_legs}"
                f" - "
                f"{public_latest_result.player2_legs}"
            ),
            latest_player2
        )

    # ---------------------------------------------------------
    # ANNOUNCEMENT
    # ---------------------------------------------------------

    if public_latest_announcement:

        st.markdown(
            f"""
            <div class="landing-announcement">

                <div style="
                    color:#f5c542;
                    font-size:14px;
                    font-weight:900;
                    text-transform:uppercase;
                    letter-spacing:1px;
                ">
                    📢 Latest Announcement
                </div>

                <div style="
                    color:white;
                    font-size:24px;
                    font-weight:900;
                    margin-top:9px;
                ">
                    {public_latest_announcement.title}
                </div>

                <div style="
                    color:#c6ccd6;
                    font-size:16px;
                    margin-top:8px;
                ">
                    {public_latest_announcement.message}
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

    # ---------------------------------------------------------
    # SOCIAL MEDIA PREVIEW
    # ---------------------------------------------------------

    st.markdown(
        """
        <h2 style="text-align:center;">
            📱 Follow the League
        </h2>

        <p style="
            text-align:center;
            color:#aeb6c5;
        ">
            Highlights, results, announcements
            and behind-the-scenes content
        </p>
        """,
        unsafe_allow_html=True
    )

    social_col1, social_col2, social_col3 = (
        st.columns(3)
    )

    with social_col1:

        st.markdown(
            """
            <div class="landing-social-card">

                <div class="landing-social-icon">
                    📘
                </div>

                <div class="landing-social-name">
                    Facebook
                </div>

                <div class="landing-social-description">
                    Community news, fixtures
                    and league discussion
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        st.link_button(
            "Visit Facebook",
            FACEBOOK_URL,
            use_container_width=True
        )

    with social_col2:

        st.markdown(
            """
            <div class="landing-social-card">

                <div class="landing-social-icon">
                    ▶️
                </div>

                <div class="landing-social-name">
                    YouTube
                </div>

                <div class="landing-social-description">
                    Match highlights, finals
                    and player features
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        if (
            YOUTUBE_URL
            != "PASTE_YOUR_YOUTUBE_CHANNEL_LINK_HERE"
        ):

            st.link_button(
                "Watch on YouTube",
                YOUTUBE_URL,
                use_container_width=True
            )

        else:

            st.button(
                "YouTube Coming Soon",
                key="youtube_coming_soon",
                disabled=True,
                use_container_width=True
            )

    with social_col3:

        st.markdown(
            """
            <div class="landing-social-card">

                <div class="landing-social-icon">
                    🎵
                </div>

                <div class="landing-social-name">
                    TikTok
                </div>

                <div class="landing-social-description">
                    180s, checkouts and
                    league-night moments
                </div>

            </div>
            """,
            unsafe_allow_html=True
        )

        st.link_button(
            "Follow on TikTok",
            TIKTOK_URL,
            use_container_width=True
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

    elif st.session_state.public_page == "Socials":

        st.markdown(
            """
            <h1 style="text-align:center;">
                📱 Follow Ye Royal Oak Darts
            </h1>

            <p style="
                text-align:center;
                color:#bfc5d2;
                font-size:17px;
            ">
                League news, results, highlights
                and behind-the-scenes content
            </p>
            """,
            unsafe_allow_html=True
        )

        social_col1, social_col2, social_col3 = (
            st.columns(3)
        )

        with social_col1:

            with st.container(border=True):

                st.markdown("# 📘")
                st.subheader("Facebook")

                st.write(
                    "Fixtures, announcements, photos "
                    "and league discussion."
                )

                st.link_button(
                    "Visit Facebook",
                    FACEBOOK_URL,
                    use_container_width=True
                )

        with social_col2:

            with st.container(border=True):

                st.markdown("# ▶️")
                st.subheader("YouTube")

                st.write(
                    "Match highlights, tournament "
                    "finals and player interviews."
                )

                if (
                    YOUTUBE_URL
                    != "https://www.youtube.com/@YeRoyalOakDarts"
                ):

                    st.link_button(
                        "Watch on YouTube",
                        YOUTUBE_URL,
                        use_container_width=True
                    )

                else:

                    st.info(
                        "YouTube channel coming soon."
                    )

        with social_col3:

            with st.container(border=True):

                st.markdown("# 🎵")
                st.subheader("TikTok")

                st.write(
                    "180s, big checkouts, funny "
                    "moments and short highlights."
                )

                st.link_button(
                    "Follow on TikTok",
                    TIKTOK_URL,
                    use_container_width=True
                )

        st.divider()

        venue_col1, venue_col2 = (
            st.columns(2)
        )

        with venue_col1:

            with st.container(border=True):

                st.subheader("📍 Venue")

                st.write(
                    """
**Ye Royal Oak**

The Shambles
Chesterfield
Derbyshire
"""
                )

        with venue_col2:

            with st.container(border=True):

                st.subheader("🎯 League Night")

                st.write(
                    f"""
**Every Thursday**

First match: **7.45 PM**

Next night: **{league_night_date}**
"""
                )

        if st.button(
            "⬅ Back to Login",
            key="socials_back_to_login",
            use_container_width=True
        ):

            st.session_state.public_page = (
                "Login"
            )

            st.rerun()    

    # ---------------------------------------------------------
    # SOCIAL MEDIA PAGE
    # ---------------------------------------------------------

    elif st.session_state.public_page == "Socials":

        st.markdown(
            """
            <h2 style='text-align:center;'>
                📱 Follow Ye Royal Oak Darts
            </h2>

            <p style='text-align:center; color:#bfc5d2;'>
                Keep up to date with fixtures, highlights, league news and events.
            </p>
            """,
            unsafe_allow_html=True
        )

        st.divider()

        fb_col1, fb_col2 = st.columns([1,4])

        with fb_col1:
            st.markdown("# 📘")

        with fb_col2:

            st.subheader("Facebook Community")

            st.write(
                "League announcements, fixtures, results, photos and player discussion."
            )

            st.link_button(
                "Visit Facebook",
                "https://www.facebook.com/groups/1063585262569763/",
                use_container_width=True
            )

        st.divider()

        yt_col1, yt_col2 = st.columns([1,4])

        with yt_col1:
            st.markdown("# ▶️")

        with yt_col2:

            st.subheader("YouTube")

            st.write(
                "Watch match highlights, tournament finals, player interviews and league content."
            )

            st.link_button(
                "Watch on YouTube",
                "https://www.youtube.com/@YeRoyalOakDarts",
                use_container_width=True
            )

        st.divider()

        tt_col1, tt_col2 = st.columns([1,4])

        with tt_col1:
            st.markdown("# 🎵")

        with tt_col2:

            st.subheader("TikTok")

            st.write(
                "180s, big checkouts, funny moments and behind-the-scenes clips."
            )

            st.link_button(
                "Follow on TikTok",
                "https://www.tiktok.com/@yeroyaloakdarts?is_from_webapp=1&sender_device=pc",
                use_container_width=True
            )

        st.divider()

        st.markdown(
            """
            <h3 style='text-align:center; color:#f5c542;'>
                🎯 League Night
            </h3>
            """,
            unsafe_allow_html=True
        )

        info1, info2 = st.columns(2)

        with info1:

            st.info(
                """
    **Venue**

    Ye Royal Oak

    The Shambles

    Chesterfield

    Derbyshire
    """
            )

        with info2:

            st.success(
                """
    **League Nights**

    Every Thursday

    Start Time: 7:30 PM

    First Match: 7.45 PM
    """
        )

        st.divider()

        st.markdown(
            """
            <div style="
                text-align:center;
                color:#999;
                font-size:14px;
                padding-top:10px;
            ">
            © Ye Royal Oak Darts League
            </div>
            """,
            unsafe_allow_html=True
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

    if st.button(
        "📊 Statistics",
        key="sidebar_statistics",
        use_container_width=True
    ):
        st.session_state.page = "Statistics"

    if st.button(
        "🏅 Awards",
        key="sidebar_awards",
        use_container_width=True
    ):
        st.session_state.page = "Awards"

    if st.button(
        "📢 Announcements",
        key="sidebar_announcements",
        use_container_width=True
    ):
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

# =========================================================
# AWARDS PAGE
# =========================================================

if page == "Awards":

    st.title("🏅 League Awards")

    st.caption(
        "Outstanding performances from each round "
        "and across the current tournament."
    )

    awards_db = SessionLocal()

    tournaments = awards_db.query(
        Tournament
    ).order_by(
        Tournament.id.desc()
    ).all()

    if not tournaments:

        st.info(
            "Create a tournament before viewing awards."
        )

        awards_db.close()

    else:

        tournament_options = {
            tournament.name: tournament.id
            for tournament in tournaments
        }

        selected_tournament_name = st.selectbox(
            "Tournament",
            list(tournament_options.keys()),
            key="awards_tournament"
        )

        selected_tournament_id = tournament_options[
            selected_tournament_name
        ]

        players = awards_db.query(
            Player
        ).all()

        completed_fixtures = awards_db.query(
            Fixture
        ).filter(
            Fixture.tournament_id
            == selected_tournament_id,
            Fixture.played == 1
        ).order_by(
            Fixture.round_number,
            Fixture.id
        ).all()

        player_lookup = {
            player.id: player
            for player in players
        }

        if not completed_fixtures:

            st.info(
                "Awards will appear after results have "
                "been entered for this tournament."
            )

            awards_db.close()

        else:

            available_rounds = sorted(
                {
                    fixture.round_number
                    for fixture in completed_fixtures
                    if fixture.round_number is not None
                }
            )

            if not available_rounds:

                st.warning(
                    "The completed fixtures do not have "
                    "round numbers."
                )

                awards_db.close()

            else:

                selected_round = st.selectbox(
                    "Round",
                    available_rounds,
                    index=len(available_rounds) - 1,
                    key="awards_round"
                )

                round_fixtures = [
                    fixture
                    for fixture in completed_fixtures
                    if fixture.round_number
                    == selected_round
                ]

                # ---------------------------------------------
                # HELPER FUNCTIONS
                # ---------------------------------------------

                def safe_float(value):

                    try:
                        return float(value or 0)

                    except (TypeError, ValueError):
                        return 0.0


                def safe_int(value):

                    try:
                        return int(value or 0)

                    except (TypeError, ValueError):
                        return 0


                def player_name(player_id):

                    player = player_lookup.get(
                        player_id
                    )

                    if not player:
                        return "Unknown"

                    return display_player_name(
                        player
                    )


                def show_award(
                    icon,
                    title,
                    winner,
                    detail,
                    extra=None
                ):

                    with st.container(
                        border=True
                    ):

                        st.markdown(
                            f"### {icon} {title}"
                        )

                        st.markdown(
                            f"## {winner}"
                        )

                        st.write(detail)

                        if extra:
                            st.caption(extra)


                # ---------------------------------------------
                # BUILD ROUND PERFORMANCES
                # ---------------------------------------------

                round_performances = []

                for fixture in round_fixtures:

                    player1 = player_lookup.get(
                        fixture.player1_id
                    )

                    player2 = player_lookup.get(
                        fixture.player2_id
                    )

                    if not player1 or not player2:
                        continue

                    p1_legs = safe_int(
                        fixture.player1_legs
                    )

                    p2_legs = safe_int(
                        fixture.player2_legs
                    )

                    p1_average = safe_float(
                        fixture.player1_average
                    )

                    p2_average = safe_float(
                        fixture.player2_average
                    )

                    p1_180s = safe_int(
                        getattr(
                            fixture,
                            "player1_180s",
                            0
                        )
                    )

                    p2_180s = safe_int(
                        getattr(
                            fixture,
                            "player2_180s",
                            0
                        )
                    )

                    p1_checkout = safe_int(
                        getattr(
                            fixture,
                            "player1_high_checkout",
                            0
                        )
                    )

                    p2_checkout = safe_int(
                        getattr(
                            fixture,
                            "player2_high_checkout",
                            0
                        )
                    )

                    round_performances.append(
                        {
                            "player_id": player1.id,
                            "player": player1,
                            "opponent": player2,
                            "average": p1_average,
                            "legs_for": p1_legs,
                            "legs_against": p2_legs,
                            "won": p1_legs > p2_legs,
                            "margin": max(
                                0,
                                p1_legs - p2_legs
                            ),
                            "180s": p1_180s,
                            "checkout": p1_checkout
                        }
                    )

                    round_performances.append(
                        {
                            "player_id": player2.id,
                            "player": player2,
                            "opponent": player1,
                            "average": p2_average,
                            "legs_for": p2_legs,
                            "legs_against": p1_legs,
                            "won": p2_legs > p1_legs,
                            "margin": max(
                                0,
                                p2_legs - p1_legs
                            ),
                            "180s": p2_180s,
                            "checkout": p2_checkout
                        }
                    )

                if not round_performances:

                    st.info(
                        "No valid performances were found "
                        "for this round."
                    )

                else:

                    # -----------------------------------------
                    # CALCULATE ROUND AWARDS
                    # -----------------------------------------

                    for performance in round_performances:

                        performance[
                            "performance_score"
                        ] = (
                            performance["average"]
                            + performance["margin"] * 3
                            + performance["180s"] * 4
                            + (
                                performance["checkout"]
                                / 20
                            )
                            + (
                                10
                                if performance["won"]
                                else 0
                            )
                        )

                    winners = [
                        performance
                        for performance
                        in round_performances
                        if performance["won"]
                    ]

                    player_of_round = max(
                        round_performances,
                        key=lambda item: (
                            item["performance_score"],
                            item["average"]
                        )
                    )

                    highest_average = max(
                        round_performances,
                        key=lambda item: item[
                            "average"
                        ]
                    )

                    most_180s = max(
                        round_performances,
                        key=lambda item: (
                            item["180s"],
                            item["average"]
                        )
                    )

                    highest_checkout = max(
                        round_performances,
                        key=lambda item: (
                            item["checkout"],
                            item["average"]
                        )
                    )

                    biggest_victory = None

                    if winners:

                        biggest_victory = max(
                            winners,
                            key=lambda item: (
                                item["margin"],
                                item["average"]
                            )
                        )

                    st.subheader(
                        f"🏆 Round {selected_round} Awards"
                    )

                    featured_left, featured_centre, featured_right = (
                        st.columns([1, 1.6, 1])
                    )

                    with featured_centre:

                        show_award(
                            "👑",
                            "Player of the Round",
                            display_player_name(
                                player_of_round["player"]
                            ),
                            (
                                f'{player_of_round["legs_for"]}'
                                f'–'
                                f'{player_of_round["legs_against"]}'
                                f' against '
                                f'{display_player_name(player_of_round["opponent"])}'
                            ),
                            (
                                f'{player_of_round["average"]:.2f} AVG'
                                f' · {player_of_round["180s"]} 180s'
                                f' · {player_of_round["checkout"]} checkout'
                            )
                        )

                    st.divider()

                    award_col1, award_col2 = (
                        st.columns(2)
                    )

                    with award_col1:

                        show_award(
                            "🎯",
                            "Highest Average",
                            display_player_name(
                                highest_average["player"]
                            ),
                            (
                                f'{highest_average["average"]:.2f}'
                                " three-dart average"
                            ),
                            (
                                "Against "
                                + display_player_name(
                                    highest_average[
                                        "opponent"
                                    ]
                                )
                            )
                        )

                    with award_col2:

                        if biggest_victory:

                            show_award(
                                "💥",
                                "Biggest Victory",
                                display_player_name(
                                    biggest_victory[
                                        "player"
                                    ]
                                ),
                                (
                                    f'{biggest_victory["legs_for"]}'
                                    f'–'
                                    f'{biggest_victory["legs_against"]}'
                                ),
                                (
                                    "Against "
                                    + display_player_name(
                                        biggest_victory[
                                            "opponent"
                                        ]
                                    )
                                )
                            )

                        else:

                            show_award(
                                "💥",
                                "Biggest Victory",
                                "No winner",
                                (
                                    "No winning result was "
                                    "found in this round."
                                )
                            )

                    award_col3, award_col4 = (
                        st.columns(2)
                    )

                    with award_col3:

                        show_award(
                            "💯",
                            "Most 180s",
                            display_player_name(
                                most_180s["player"]
                            ),
                            (
                                f'{most_180s["180s"]}'
                                " maximums"
                            ),
                            (
                                "Against "
                                + display_player_name(
                                    most_180s["opponent"]
                                )
                            )
                        )

                    with award_col4:

                        show_award(
                            "🏹",
                            "Highest Checkout",
                            display_player_name(
                                highest_checkout[
                                    "player"
                                ]
                            ),
                            (
                                f'{highest_checkout["checkout"]}'
                                " checkout"
                            ),
                            (
                                "Against "
                                + display_player_name(
                                    highest_checkout[
                                        "opponent"
                                    ]
                                )
                            )
                        )

                    # -----------------------------------------
                    # SEASON STATISTICS
                    # -----------------------------------------

                    st.divider()

                    st.subheader(
                        "🌟 Tournament Leaders"
                    )

                    season_stats = {}

                    for player in players:

                        season_stats[player.id] = {
                            "player": player,
                            "played": 0,
                            "wins": 0,
                            "averages": [],
                            "180s": 0,
                            "highest_checkout": 0,
                            "legs_for": 0,
                            "legs_against": 0
                        }

                    for fixture in completed_fixtures:

                        if (
                            fixture.player1_id
                            not in season_stats
                            or fixture.player2_id
                            not in season_stats
                        ):
                            continue

                        p1_stats = season_stats[
                            fixture.player1_id
                        ]

                        p2_stats = season_stats[
                            fixture.player2_id
                        ]

                        p1_legs = safe_int(
                            fixture.player1_legs
                        )

                        p2_legs = safe_int(
                            fixture.player2_legs
                        )

                        p1_stats["played"] += 1
                        p2_stats["played"] += 1

                        p1_stats["legs_for"] += p1_legs
                        p1_stats[
                            "legs_against"
                        ] += p2_legs

                        p2_stats["legs_for"] += p2_legs
                        p2_stats[
                            "legs_against"
                        ] += p1_legs

                        p1_average = safe_float(
                            fixture.player1_average
                        )

                        p2_average = safe_float(
                            fixture.player2_average
                        )

                        if p1_average > 0:
                            p1_stats[
                                "averages"
                            ].append(
                                p1_average
                            )

                        if p2_average > 0:
                            p2_stats[
                                "averages"
                            ].append(
                                p2_average
                            )

                        p1_stats["180s"] += safe_int(
                            getattr(
                                fixture,
                                "player1_180s",
                                0
                            )
                        )

                        p2_stats["180s"] += safe_int(
                            getattr(
                                fixture,
                                "player2_180s",
                                0
                            )
                        )

                        p1_stats[
                            "highest_checkout"
                        ] = max(
                            p1_stats[
                                "highest_checkout"
                            ],
                            safe_int(
                                getattr(
                                    fixture,
                                    "player1_high_checkout",
                                    0
                                )
                            )
                        )

                        p2_stats[
                            "highest_checkout"
                        ] = max(
                            p2_stats[
                                "highest_checkout"
                            ],
                            safe_int(
                                getattr(
                                    fixture,
                                    "player2_high_checkout",
                                    0
                                )
                            )
                        )

                        if p1_legs > p2_legs:
                            p1_stats["wins"] += 1

                        elif p2_legs > p1_legs:
                            p2_stats["wins"] += 1

                    season_rows = []

                    for stats in season_stats.values():

                        if stats["played"] == 0:
                            continue

                        average = 0.0

                        if stats["averages"]:

                            average = (
                                sum(stats["averages"])
                                / len(stats["averages"])
                            )

                        win_percentage = (
                            stats["wins"]
                            / stats["played"]
                            * 100
                        )

                        season_rows.append(
                            {
                                **stats,
                                "average": average,
                                "win_percentage": (
                                    win_percentage
                                ),
                                "leg_difference": (
                                    stats["legs_for"]
                                    - stats[
                                        "legs_against"
                                    ]
                                )
                            }
                        )

                    if season_rows:

                        most_wins = max(
                            season_rows,
                            key=lambda item: (
                                item["wins"],
                                item["average"]
                            )
                        )

                        best_average = max(
                            season_rows,
                            key=lambda item: (
                                item["average"],
                                item["wins"]
                            )
                        )

                        season_most_180s = max(
                            season_rows,
                            key=lambda item: (
                                item["180s"],
                                item["average"]
                            )
                        )

                        season_checkout = max(
                            season_rows,
                            key=lambda item: (
                                item[
                                    "highest_checkout"
                                ],
                                item["average"]
                            )
                        )

                        season_col1, season_col2 = (
                            st.columns(2)
                        )

                        with season_col1:

                            show_award(
                                "👑",
                                "Most Wins",
                                display_player_name(
                                    most_wins["player"]
                                ),
                                (
                                    f'{most_wins["wins"]}'
                                    f' wins from '
                                    f'{most_wins["played"]}'
                                    " matches"
                                ),
                                (
                                    f'{most_wins["win_percentage"]:.1f}%'
                                    " win rate"
                                )
                            )

                        with season_col2:

                            show_award(
                                "📈",
                                "Best Average",
                                display_player_name(
                                    best_average["player"]
                                ),
                                (
                                    f'{best_average["average"]:.2f}'
                                    " tournament average"
                                )
                            )

                        season_col3, season_col4 = (
                            st.columns(2)
                        )

                        with season_col3:

                            show_award(
                                "💯",
                                "Most 180s",
                                display_player_name(
                                    season_most_180s[
                                        "player"
                                    ]
                                ),
                                (
                                    f'{season_most_180s["180s"]}'
                                    " total maximums"
                                )
                            )

                        with season_col4:

                            show_award(
                                "🏹",
                                "Highest Checkout",
                                display_player_name(
                                    season_checkout[
                                        "player"
                                    ]
                                ),
                                (
                                    f'{season_checkout["highest_checkout"]}'
                                    " checkout"
                                )
                            )

                    else:

                        st.info(
                            "No tournament statistics "
                            "are available yet."
                        )

                awards_db.close()    

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

# =========================================================
# FIXTURES & RESULTS
# =========================================================

if page == "Fixtures":

    st.markdown(
        """
        <h1 style="text-align:center;">
            📅 Fixtures & Results
        </h1>

        <p style="
            text-align:center;
            color:#bfc5d2;
            font-size:17px;
        ">
            View upcoming matches and enter league results
        </p>
        """,
        unsafe_allow_html=True
    )

    db = SessionLocal()

    tournaments = db.query(
        Tournament
    ).order_by(
        Tournament.id.desc()
    ).all()

    if not tournaments:

        st.info(
            "No tournaments have been created yet."
        )

        db.close()

    else:

        tournament_lookup = {
            tournament.name: tournament.id
            for tournament in tournaments
        }

        selected_tournament = st.selectbox(
            "Tournament",
            list(tournament_lookup.keys()),
            key="fixtures_tournament_v2"
        )

        selected_tournament_id = tournament_lookup[
            selected_tournament
        ]

        selected_tournament_object = db.get(
            Tournament,
            selected_tournament_id
        )

        winning_legs = get_winning_legs(
            selected_tournament_object.legs_format
    )

    if winning_legs:

        st.info(
            f"🎯 Match format: "
            f"{selected_tournament_object.legs_format}. "
            f"The first player to {winning_legs} legs wins."
        )

        if not selected_tournament_object:

            st.error(
                "The selected tournament could not be found."
            )

            db.close()
            st.stop()

        fixtures = db.query(Fixture).filter(
            Fixture.tournament_id
            == selected_tournament_id
        ).order_by(
            Fixture.round_number,
            Fixture.id
        ).all()

        players = db.query(Player).all()

        player_lookup = {
            player.id: display_player_name(player)
            for player in players
        }

        # -----------------------------------------------------
        # FIXTURE SUMMARY
        # -----------------------------------------------------

        total_fixtures = len(fixtures)

        played_fixtures = len(
            [
                fixture
                for fixture in fixtures
                if fixture.played == 1
            ]
        )

        remaining_fixtures = (
            total_fixtures - played_fixtures
        )

        summary_col1, summary_col2, summary_col3 = (
            st.columns(3)
        )

        with summary_col1:

            dashboard_card(
                "📋 Total Fixtures",
                total_fixtures,
                selected_tournament
            )

        with summary_col2:

            dashboard_card(
                "✅ Completed",
                played_fixtures,
                "Results entered"
            )

        with summary_col3:

            dashboard_card(
                "⏳ Remaining",
                remaining_fixtures,
                "Matches still to play"
            )

        # -----------------------------------------------------
        # ADMIN: GENERATE FIXTURES
        # -----------------------------------------------------

        if is_admin:

            with st.expander(
                "⚙️ Fixture Administration",
                expanded=False
            ):

                st.write(
                    "Generate the round-robin fixtures for "
                    "this tournament."
                )

                if st.button(
                    "🎯 Generate Fixtures",
                    key=(
                        f"generate_fixtures_"
                        f"{selected_tournament_id}"
                    ),
                    use_container_width=True
                ):

                    existing_count = db.query(
                        Fixture
                    ).filter(
                        Fixture.tournament_id
                        == selected_tournament_id
                    ).count()

                    if existing_count > 0:

                        st.warning(
                            "Fixtures have already been "
                            "generated for this tournament."
                        )

                    else:

                        tournament_links = db.query(
                            TournamentPlayer
                        ).filter(
                            TournamentPlayer.tournament_id
                            == selected_tournament_id
                        ).all()

                        player_ids = [
                            link.player_id
                            for link in tournament_links
                        ]

                        if len(player_ids) < 2:

                            st.error(
                                "At least two players are "
                                "required."
                            )

                        else:

                            generated_fixtures = (
                                generate_round_robin(
                                    player_ids
                                )
                            )

                            for (
                                round_number,
                                player1_id,
                                player2_id
                            ) in generated_fixtures:

                                new_fixture = Fixture(
                                    tournament_id=(
                                        selected_tournament_id
                                    ),
                                    round_number=round_number,
                                    player1_id=player1_id,
                                    player2_id=player2_id,
                                    played=0
                                )

                                db.add(new_fixture)

                            db.commit()

                            st.success(
                                "Fixtures generated successfully."
                            )

                            st.rerun()

        st.divider()

        if not fixtures:

            st.info(
                "No fixtures have been generated for "
                "this tournament."
            )

        else:

            # -------------------------------------------------
            # DISPLAY FILTER
            # -------------------------------------------------

            view_mode = st.radio(
                "Display",
                [
                    "Upcoming",
                    "Results",
                    "All Fixtures"
                ],
                horizontal=True,
                key="fixture_view_mode"
            )

            if view_mode == "Upcoming":

                displayed_fixtures = [
                    fixture
                    for fixture in fixtures
                    if fixture.played != 1
                ]

            elif view_mode == "Results":

                displayed_fixtures = [
                    fixture
                    for fixture in fixtures
                    if fixture.played == 1
                ]

            else:

                displayed_fixtures = fixtures

            if not displayed_fixtures:

                if view_mode == "Upcoming":

                    st.success(
                        "All fixtures have been completed."
                    )

                elif view_mode == "Results":

                    st.info(
                        "No results have been entered yet."
                    )

                else:

                    st.info("No fixtures are available.")

            else:

                round_numbers = sorted(
                    {
                        fixture.round_number
                        for fixture in displayed_fixtures
                    }
                )

                # ---------------------------------------------
                # DISPLAY EACH ROUND
                # ---------------------------------------------

                for round_number in round_numbers:

                    round_fixtures = [
                        fixture
                        for fixture in displayed_fixtures
                        if fixture.round_number
                        == round_number
                    ]

                    round_played = len(
                        [
                            fixture
                            for fixture in round_fixtures
                            if fixture.played == 1
                        ]
                    )

                    round_total = len(round_fixtures)

                    with st.expander(
                        (
                            f"🎯 Round {round_number} "
                            f"— {round_played}/{round_total} "
                            f"completed"
                        ),
                        expanded=(
                            round_number
                            == round_numbers[0]
                        )
                    ):

                        for fixture in round_fixtures:

                            player1_name = (
                                player_lookup.get(
                                    fixture.player1_id,
                                    "Unknown"
                                )
                            )

                            player2_name = (
                                player_lookup.get(
                                    fixture.player2_id,
                                    "Unknown"
                                )
                            )

                            # =================================
                            # COMPLETED FIXTURE
                            # =================================

                            if fixture.played == 1:

                                result_col1, result_col2, result_col3 = (
                                    st.columns(
                                        [2.5, 1.2, 2.5]
                                    )
                                )

                                with result_col1:

                                    st.markdown(
                                        f"""
                                        <div style="
                                            text-align:right;
                                            font-size:21px;
                                            font-weight:900;
                                            padding-top:8px;
                                        ">
                                            {player1_name}
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                                with result_col2:

                                    st.markdown(
                                        f"""
                                        <div style="
                                            text-align:center;
                                            color:#f5c542;
                                            font-size:28px;
                                            font-weight:950;
                                        ">
                                            {fixture.player1_legs}
                                            -
                                            {fixture.player2_legs}
                                        </div>

                                        <div style="
                                            text-align:center;
                                            color:#45df8b;
                                            font-size:12px;
                                            font-weight:800;
                                        ">
                                            COMPLETED
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                                with result_col3:

                                    st.markdown(
                                        f"""
                                        <div style="
                                            text-align:left;
                                            font-size:21px;
                                            font-weight:900;
                                            padding-top:8px;
                                        ">
                                            {player2_name}
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                                stat_col1, stat_col2, stat_col3 = (
                                    st.columns(3)
                                )

                                with stat_col1:

                                    st.caption(
                                        (
                                            "📅 Date: "
                                            f"{fixture.date_played or '—'}"
                                        )
                                    )

                                with stat_col2:

                                    st.caption(
                                        (
                                            "🎯 Averages: "
                                            f"{fixture.player1_average or 0}"
                                            " / "
                                            f"{fixture.player2_average or 0}"
                                        )
                                    )

                                with stat_col3:

                                    st.caption(
                                        (
                                            "💯 180s: "
                                            f"{getattr(fixture, 'player1_180s', 0) or 0}"
                                            " / "
                                            f"{getattr(fixture, 'player2_180s', 0) or 0}"
                                        )
                                    )

                                checkout_col1, checkout_col2 = (
                                    st.columns(2)
                                )

                                with checkout_col1:

                                    st.caption(
                                        (
                                            f"🏹 {player1_name} "
                                            "highest checkout: "
                                            f"{getattr(fixture, 'player1_high_checkout', 0) or 0}"
                                        )
                                    )

                                with checkout_col2:

                                    st.caption(
                                        (
                                            f"🏹 {player2_name} "
                                            "highest checkout: "
                                            f"{getattr(fixture, 'player2_high_checkout', 0) or 0}"
                                        )
                                    )

                                # Admin can correct an existing result.
                                if is_admin:

                                    with st.expander(
                                        "✏️ Edit Result",
                                        expanded=False
                                    ):

                                        with st.form(
                                            key=(
                                                f"edit_result_form_"
                                                f"{fixture.id}"
                                            )
                                        ):

                                            edit_date = st.date_input(
                                                "Date Played",
                                                value=(
                                                    fixture.date_played
                                                    if fixture.date_played
                                                    else date.today()
                                                ),
                                                key=(
                                                    f"edit_date_"
                                                    f"{fixture.id}"
                                                )
                                            )

                                            edit_score_col1, edit_score_col2 = (
                                                st.columns(2)
                                            )

                                            with edit_score_col1:

                                                edit_p1_legs = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "Legs"
                                                        ),
                                                        min_value=0,
                                                        max_value=20,
                                                        value=(
                                                            fixture.player1_legs
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p1_legs_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with edit_score_col2:

                                                edit_p2_legs = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "Legs"
                                                        ),
                                                        min_value=0,
                                                        max_value=20,
                                                        value=(
                                                            fixture.player2_legs
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p2_legs_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            edit_avg_col1, edit_avg_col2 = (
                                                st.columns(2)
                                            )

                                            with edit_avg_col1:

                                                edit_p1_avg = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "3-Dart Average"
                                                        ),
                                                        min_value=0.0,
                                                        max_value=1000.0,
                                                        value=float(
                                                            fixture.player1_average
                                                            or 0
                                                        ),
                                                        step=0.01,
                                                        format="%.2f",
                                                        key=(
                                                            f"edit_p1_avg_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with edit_avg_col2:

                                                edit_p2_avg = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "3-Dart Average"
                                                        ),
                                                        min_value=0.0,
                                                        max_value=1000.0,
                                                        value=float(
                                                            fixture.player2_average
                                                            or 0
                                                        ),
                                                        step=0.01,
                                                        format="%.2f",
                                                        key=(
                                                            f"edit_p2_avg_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            edit_180_col1, edit_180_col2 = (
                                                st.columns(2)
                                            )

                                            with edit_180_col1:

                                                edit_p1_180s = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "180s"
                                                        ),
                                                        min_value=0,
                                                        max_value=50,
                                                        value=int(
                                                            getattr(
                                                                fixture,
                                                                "player1_180s",
                                                                0
                                                            )
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p1_180s_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with edit_180_col2:

                                                edit_p2_180s = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "180s"
                                                        ),
                                                        min_value=0,
                                                        max_value=50,
                                                        value=int(
                                                            getattr(
                                                                fixture,
                                                                "player2_180s",
                                                                0
                                                            )
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p2_180s_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            edit_checkout_col1, edit_checkout_col2 = (
                                                st.columns(2)
                                            )

                                            with edit_checkout_col1:

                                                edit_p1_checkout = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "Highest Checkout"
                                                        ),
                                                        min_value=0,
                                                        max_value=170,
                                                        value=int(
                                                            getattr(
                                                                fixture,
                                                                "player1_high_checkout",
                                                                0
                                                            )
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p1_checkout_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with edit_checkout_col2:

                                                edit_p2_checkout = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "Highest Checkout"
                                                        ),
                                                        min_value=0,
                                                        max_value=170,
                                                        value=int(
                                                            getattr(
                                                                fixture,
                                                                "player2_high_checkout",
                                                                0
                                                            )
                                                            or 0
                                                        ),
                                                        key=(
                                                            f"edit_p2_checkout_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            update_result = (
                                                st.form_submit_button(
                                                    "💾 Update Result",
                                                    use_container_width=True
                                                )
                                            )

                                        if update_result:

                                            score_is_valid, score_error = validate_match_score(
                                                edit_p1_legs,
                                                edit_p2_legs,
                                                selected_tournament_object.legs_format
                                            )

                                            if not score_is_valid:

                                                st.error(
                                                    score_error
                                                )

                                            elif edit_p1_avg > 200:

                                                st.error(
                                                    f"{player1_name}'s average cannot exceed 200."
                                                )

                                            elif edit_p2_avg > 200:

                                                st.error(
                                                    f"{player2_name}'s average cannot exceed 200."
                                                )

                                            elif edit_p1_checkout > 170:

                                                st.error(
                                                    f"{player1_name}'s highest checkout cannot exceed 170."
                                                )

                                            elif edit_p2_checkout > 170:

                                                st.error(
                                                    f"{player2_name}'s highest checkout cannot exceed 170."
                                                )

                                            else:

                                                edit_db = SessionLocal()

                                                target_fixture = edit_db.get(
                                                    Fixture,
                                                    fixture.id
                                                )

                                                if not target_fixture:

                                                    edit_db.close()

                                                    st.error(
                                                        "Fixture could not be found."
                                                    )


                                                else:

                                                    target_fixture.player1_legs = (
                                                        edit_p1_legs
                                                    )

                                                    target_fixture.player2_legs = (
                                                        edit_p2_legs
                                                    )

                                                    target_fixture.player1_average = (
                                                        edit_p1_avg
                                                    )

                                                    target_fixture.player2_average = (
                                                        edit_p2_avg
                                                    )

                                                    target_fixture.player1_180s = (
                                                        edit_p1_180s
                                                    )

                                                    target_fixture.player2_180s = (
                                                        edit_p2_180s
                                                    )

                                                    target_fixture.player1_high_checkout = (
                                                        edit_p1_checkout
                                                    )

                                                    target_fixture.player2_high_checkout = (
                                                        edit_p2_checkout
                                                    )

                                                    target_fixture.date_played = (
                                                        edit_date
                                                    )

                                                    target_fixture.played = 1

                                                    edit_db.commit()
                                                    edit_db.close()

                                                    if "league_standings" in st.session_state:
                                                        del st.session_state["league_standings"]

                                                    st.success("Result updated.")

                                                    st.rerun()

                            # =================================
                            # UPCOMING FIXTURE
                            # =================================

                            else:

                                fixture_title = (
                                    f"⏳ {player1_name} "
                                    f"vs {player2_name}"
                                )

                                with st.expander(
                                    fixture_title,
                                    expanded=False
                                ):

                                    st.markdown(
                                        f"""
                                        <div style="
                                            text-align:center;
                                            font-size:25px;
                                            font-weight:900;
                                            margin-bottom:12px;
                                        ">
                                            {player1_name}
                                            <span style="
                                                color:#f5c542;
                                                padding:0 14px;
                                            ">
                                                VS
                                            </span>
                                            {player2_name}
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                                    if not is_admin:

                                        st.info(
                                            "This fixture has not "
                                            "been played yet."
                                        )

                                    else:

                                        with st.form(
                                            key=(
                                                f"result_form_"
                                                f"{fixture.id}"
                                            )
                                        ):

                                            match_date = st.date_input(
                                                "Date Played",
                                                value=date.today(),
                                                key=(
                                                    f"result_date_"
                                                    f"{fixture.id}"
                                                )
                                            )

                                            score_col1, score_col2 = (
                                                st.columns(2)
                                            )

                                            with score_col1:

                                                player1_legs = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "Legs"
                                                        ),
                                                        min_value=0,
                                                        max_value=20,
                                                        value=0,
                                                        key=(
                                                            f"result_p1_legs_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with score_col2:

                                                player2_legs = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "Legs"
                                                        ),
                                                        min_value=0,
                                                        max_value=20,
                                                        value=0,
                                                        key=(
                                                            f"result_p2_legs_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            average_col1, average_col2 = (
                                                st.columns(2)
                                            )

                                            with average_col1:

                                                player1_average = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "3-Dart Average"
                                                        ),
                                                        min_value=0.0,
                                                        max_value=200.0,
                                                        value=0.0,
                                                        step=0.01,
                                                        format="%.2f",
                                                        key=(
                                                            f"result_p1_avg_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with average_col2:

                                                player2_average = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "3-Dart Average"
                                                        ),
                                                        min_value=0.0,
                                                        max_value=200.0,
                                                        value=0.0,
                                                        step=0.01,
                                                        format="%.2f",
                                                        key=(
                                                            f"result_p2_avg_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            one_eighty_col1, one_eighty_col2 = (
                                                st.columns(2)
                                            )

                                            with one_eighty_col1:

                                                player1_180s = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "180s"
                                                        ),
                                                        min_value=0,
                                                        max_value=50,
                                                        value=0,
                                                        key=(
                                                            f"result_p1_180s_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with one_eighty_col2:

                                                player2_180s = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "180s"
                                                        ),
                                                        min_value=0,
                                                        max_value=50,
                                                        value=0,
                                                        key=(
                                                            f"result_p2_180s_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            checkout_col1, checkout_col2 = (
                                                st.columns(2)
                                            )

                                            with checkout_col1:

                                                player1_checkout = (
                                                    st.number_input(
                                                        (
                                                            f"{player1_name} "
                                                            "Highest Checkout"
                                                        ),
                                                        min_value=0,
                                                        max_value=170,
                                                        value=0,
                                                        key=(
                                                            f"result_p1_checkout_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            with checkout_col2:

                                                player2_checkout = (
                                                    st.number_input(
                                                        (
                                                            f"{player2_name} "
                                                            "Highest Checkout"
                                                        ),
                                                        min_value=0,
                                                        max_value=170,
                                                        value=0,
                                                        key=(
                                                            f"result_p2_checkout_"
                                                            f"{fixture.id}"
                                                        )
                                                    )
                                                )

                                            save_result = (
                                                st.form_submit_button(
                                                    "💾 Save Result",
                                                    use_container_width=True
                                                )
                                            )


                                        if save_result:

                                            score_is_valid, score_error = validate_match_score(
                                                player1_legs,
                                                player2_legs,
                                                selected_tournament_object.legs_format
                                            )

                                            if not score_is_valid:

                                                st.error(score_error)

                                            elif player1_average > 200:

                                                st.error(
                                                    f"{player1_name}'s average cannot exceed 200."
                                                )

                                            elif player2_average > 200:

                                                st.error(
                                                    f"{player2_name}'s average cannot exceed 200."
                                                )

                                            elif player1_checkout > 170:

                                                st.error(
                                                    f"{player1_name}'s highest checkout cannot exceed 170."
                                                )

                                            elif player2_checkout > 170:

                                                st.error(
                                                    f"{player2_name}'s highest checkout cannot exceed 170."
                                                )

                                            else:

                                                save_db = SessionLocal()

                                                target_fixture = save_db.get(
                                                    Fixture,
                                                    fixture.id
                                                )

                                                if not target_fixture:

                                                    save_db.close()

                                                    st.error(
                                                        "Fixture could not be found."
                                                    )

                                                else:

                                                    target_fixture.player1_legs = player1_legs
                                                    target_fixture.player2_legs = player2_legs

                                                    target_fixture.player1_average = player1_average
                                                    target_fixture.player2_average = player2_average

                                                    target_fixture.player1_180s = player1_180s
                                                    target_fixture.player2_180s = player2_180s

                                                    target_fixture.player1_high_checkout = (
                                                        player1_checkout
                                                    )

                                                    target_fixture.player2_high_checkout = (
                                                        player2_checkout
                                                    )

                                                    target_fixture.date_played = match_date
                                                    target_fixture.played = 1

                                                    save_db.commit()
                                                    save_db.close()

                                                    if "league_standings" in st.session_state:
                                                        del st.session_state["league_standings"]

                                                    st.success("Result saved.")
                                                    st.rerun()

        db.close()


# LEAGUE TAB

# =========================================================
# LEAGUE TABLE — PHASE C
# =========================================================

if page == "League":

    st.markdown(
        """
        <h1 style="text-align:center;">
            🏆 League Standings
        </h1>

        <p style="
            text-align:center;
            color:#bfc5d2;
            font-size:17px;
        ">
            Current Ye Royal Oak league positions
        </p>
        """,
        unsafe_allow_html=True
    )

    league_db = SessionLocal()

    tournaments = league_db.query(
        Tournament
    ).order_by(
        Tournament.id.desc()
    ).all()

    if not tournaments:

        st.info(
            "Create a tournament before viewing "
            "the league standings."
        )

        league_db.close()

    else:

        tournament_options = {
            tournament.name: tournament.id
            for tournament in tournaments
            if tournament.format_type
            != "Knockout Only"
        }

        if not tournament_options:

            st.info(
                "No league-based tournaments were found."
            )

            league_db.close()

        else:

            selected_tournament_name = st.selectbox(
                "Tournament",
                list(tournament_options.keys()),
                key="league_tournament_selector"
            )

            selected_tournament_id = tournament_options[
                selected_tournament_name
            ]

            tournament_links = league_db.query(
                TournamentPlayer
            ).filter(
                TournamentPlayer.tournament_id
                == selected_tournament_id
            ).all()

            tournament_player_ids = {
                link.player_id
                for link in tournament_links
            }

            players = league_db.query(
                Player
            ).filter(
                Player.id.in_(
                    tournament_player_ids
                )
            ).all()

            fixtures = league_db.query(
                Fixture
            ).filter(
                Fixture.tournament_id
                == selected_tournament_id,
                Fixture.played == 1
            ).order_by(
                Fixture.round_number,
                Fixture.id
            ).all()

            player_objects = {
                player.id: player
                for player in players
            }

            standings = {}

            for player in players:

                standings[player.id] = {
                    "player": player,
                    "played": 0,
                    "won": 0,
                    "drawn": 0,
                    "lost": 0,
                    "legs_for": 0,
                    "legs_against": 0,
                    "points": 0,
                    "averages": [],
                    "form": []
                }

            for fixture in fixtures:

                if (
                    fixture.player1_id
                    not in standings
                    or fixture.player2_id
                    not in standings
                ):
                    continue

                player1 = standings[
                    fixture.player1_id
                ]

                player2 = standings[
                    fixture.player2_id
                ]

                player1["played"] += 1
                player2["played"] += 1

                player1["legs_for"] += (
                    fixture.player1_legs or 0
                )

                player1["legs_against"] += (
                    fixture.player2_legs or 0
                )

                player2["legs_for"] += (
                    fixture.player2_legs or 0
                )

                player2["legs_against"] += (
                    fixture.player1_legs or 0
                )

                try:

                    player1_average = float(
                        fixture.player1_average
                    )

                    if 0 < player1_average <= 200:

                        player1["averages"].append(
                            player1_average
                        )

                except (TypeError, ValueError):

                    pass

                try:

                    player2_average = float(
                        fixture.player2_average
                    )

                    if 0 < player2_average <= 200:

                        player2["averages"].append(
                            player2_average
                        )

                except (TypeError, ValueError):

                    pass

                player1_legs = (
                    fixture.player1_legs or 0
                )

                player2_legs = (
                    fixture.player2_legs or 0
                )

                if player1_legs > player2_legs:

                    player1["won"] += 1
                    player1["points"] += 2
                    player1["form"].append("W")

                    player2["lost"] += 1
                    player2["form"].append("L")

                elif player2_legs > player1_legs:

                    player2["won"] += 1
                    player2["points"] += 2
                    player2["form"].append("W")

                    player1["lost"] += 1
                    player1["form"].append("L")

                else:

                    player1["drawn"] += 1
                    player2["drawn"] += 1

                    player1["points"] += 1
                    player2["points"] += 1

                    player1["form"].append("D")
                    player2["form"].append("D")

            rows = []

            for player_id, data in standings.items():

                average = 0.0

                if data["averages"]:

                    average = round(
                        sum(data["averages"])
                        / len(data["averages"]),
                        2
                    )

                leg_difference = (
                    data["legs_for"]
                    - data["legs_against"]
                )

                rows.append(
                    {
                        "Player": display_player_name(
                            data["player"]
                        ),
                        "Real Name": (
                            data["player"].name
                        ),
                        "Played": data["played"],
                        "Won": data["won"],
                        "Drawn": data["drawn"],
                        "Lost": data["lost"],
                        "Legs For": (
                            data["legs_for"]
                        ),
                        "Legs Against": (
                            data["legs_against"]
                        ),
                        "Difference": (
                            leg_difference
                        ),
                        "3 Dart Average": average,
                        "Points": data["points"],
                        "Form": data["form"][-5:],
                        "Player ID": player_id
                    }
                )

            rows = sorted(
                rows,
                key=lambda row: (
                    row["Points"],
                    row["Difference"],
                    row["Won"],
                    row["3 Dart Average"]
                ),
                reverse=True
            )

            st.session_state[
                "league_standings"
            ] = rows

            st.session_state[
                "league_tournament_id"
            ] = selected_tournament_id

            if not rows:

                dashboard_card(
                    "No League Data",
                    "No players found",
                    (
                        "Add players to this tournament "
                        "to create the table."
                    )
                )

            else:

                completed_matches = len(
                    fixtures
                )

                total_players = len(
                    rows
                )

                leader = rows[0]

                best_average = max(
                    rows,
                    key=lambda row: row[
                        "3 Dart Average"
                    ]
                )

                most_wins = max(
                    rows,
                    key=lambda row: (
                        row["Won"],
                        row["3 Dart Average"]
                    )
                )

                summary_col1, summary_col2, summary_col3 = (
                    st.columns(3)
                )

                with summary_col1:

                    dashboard_card(
                        "👑 League Leader",
                        leader["Player"],
                        (
                            f'{leader["Points"]} points '
                            f'from {leader["Played"]} matches'
                        )
                    )

                with summary_col2:

                    dashboard_card(
                        "🎯 Best Average",
                        best_average["Player"],
                        (
                            f'{best_average["3 Dart Average"]:.2f}'
                            " three-dart average"
                        )
                    )

                with summary_col3:

                    dashboard_card(
                        "🔥 Most Wins",
                        most_wins["Player"],
                        (
                            f'{most_wins["Won"]} wins '
                            f'from {most_wins["Played"]} matches'
                        )
                    )

                overview_col1, overview_col2 = (
                    st.columns(2)
                )

                with overview_col1:

                    st.metric(
                        "League Players",
                        total_players
                    )

                with overview_col2:

                    st.metric(
                        "Matches Completed",
                        completed_matches
                    )

                st.divider()

                st.markdown(
                    "## 📊 Current Standings"
                )

                st.caption(
                    "P = Played · W = Won · "
                    "D = Drawn · L = Lost · "
                    "LF = Legs For · LA = Legs Against"
                )

                # ---------------------------------------------
                # PLAYER STANDING CARDS
                # ---------------------------------------------

                for position, row in enumerate(
                    rows,
                    start=1
                ):

                    player = player_objects.get(
                        row["Player ID"]
                    )

                    if position == 1:
                        position_display = "🥇"
                        position_title = (
                            "League Leader"
                        )

                    elif position == 2:
                        position_display = "🥈"
                        position_title = (
                            "Second Place"
                        )

                    elif position == 3:
                        position_display = "🥉"
                        position_title = (
                            "Third Place"
                        )

                    else:
                        position_display = str(
                            position
                        )

                        position_title = (
                            f"Position {position}"
                        )

                    form_display = []

                    for form_result in row["Form"]:

                        if form_result == "W":
                            form_display.append("🟢 W")

                        elif form_result == "D":
                            form_display.append("🟡 D")

                        else:
                            form_display.append("🔴 L")

                    while len(form_display) < 5:

                        form_display.insert(
                            0,
                            "⚫ —"
                        )

                    difference = row[
                        "Difference"
                    ]

                    if difference > 0:

                        difference_display = (
                            f"+{difference}"
                        )

                        difference_delta = (
                            "positive"
                        )

                    elif difference < 0:

                        difference_display = str(
                            difference
                        )

                        difference_delta = (
                            "negative"
                        )

                    else:

                        difference_display = "0"
                        difference_delta = "off"

                    with st.container(
                        border=True
                    ):

                        main_col1, main_col2, main_col3 = (
                            st.columns(
                                [0.7, 3.4, 1.2]
                            )
                        )

                        with main_col1:

                            st.markdown(
                                f"""
                                <div style="
                                    text-align:center;
                                    font-size:34px;
                                    font-weight:950;
                                    color:#f5c542;
                                    padding-top:8px;
                                ">
                                    {position_display}
                                </div>

                                <div style="
                                    text-align:center;
                                    color:#9ca3af;
                                    font-size:11px;
                                    font-weight:800;
                                ">
                                    {position_title}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        with main_col2:

                            identity_col1, identity_col2 = (
                                st.columns(
                                    [0.8, 3.2]
                                )
                            )

                            with identity_col1:

                                if (
                                    player
                                    and player.logo_path
                                    and os.path.exists(
                                        player.logo_path
                                    )
                                ):

                                    st.image(
                                        player.logo_path,
                                        width=72
                                    )

                                else:

                                    st.markdown(
                                        """
                                        <div style="
                                            width:65px;
                                            height:65px;
                                            border-radius:50%;
                                            display:flex;
                                            align-items:center;
                                            justify-content:center;
                                            background:#111827;
                                            border:2px solid #f5c542;
                                            font-size:28px;
                                        ">
                                            🎯
                                        </div>
                                        """,
                                        unsafe_allow_html=True
                                    )

                            with identity_col2:

                                st.markdown(
                                    f"### {row['Player']}"
                                )

                                if (
                                    row["Player"]
                                    != row["Real Name"]
                                ):

                                    st.caption(
                                        row["Real Name"]
                                    )

                                st.caption(
                                    "Recent form: "
                                    + "  ".join(
                                        form_display
                                    )
                                )

                        with main_col3:

                            st.metric(
                                "Points",
                                row["Points"]
                            )

                        stat_col1, stat_col2, stat_col3, stat_col4 = (
                            st.columns(4)
                        )

                        with stat_col1:

                            st.metric(
                                "Record",
                                (
                                    f'{row["Won"]}-'
                                    f'{row["Drawn"]}-'
                                    f'{row["Lost"]}'
                                ),
                                help="Wins-Draws-Losses"
                            )

                        with stat_col2:

                            st.metric(
                                "Played",
                                row["Played"]
                            )

                        with stat_col3:

                            difference = row["Difference"]

                            if difference > 0:
                                difference_display = f"+{difference}"
                                difference_caption = "Positive leg difference"
                                difference_colour = "normal"

                            elif difference < 0:
                                difference_display = str(difference)
                                difference_caption = "Negative leg difference"
                                difference_colour = "inverse"

                            else:
                                difference_display = "0"
                                difference_caption = "Level"
                                difference_colour = "off"

                            st.metric(
                                label="Leg Difference",
                                value=difference_display,
                                delta=difference_caption,
                                delta_color=difference_colour
                            )

                        with stat_col4:

                            st.metric(
                                "3-Dart Average",
                                (
                                    f'{row["3 Dart Average"]:.2f}'
                                )
                            )

                        detail_col1, detail_col2, detail_col3 = (
                            st.columns(3)
                        )

                        with detail_col1:

                            st.caption(
                                (
                                    f'🎯 Legs For: '
                                    f'{row["Legs For"]}'
                                )
                            )

                        with detail_col2:

                            st.caption(
                                (
                                    f'🛡 Legs Against: '
                                    f'{row["Legs Against"]}'
                                )
                            )

                        with detail_col3:

                            if st.button(
                                "🎴 View Player Card",
                                key=(
                                    f"league_view_player_"
                                    f'{row["Player ID"]}'
                                ),
                                use_container_width=True
                            ):

                                st.session_state[
                                    "view_player_id"
                                ] = row[
                                    "Player ID"
                                ]

                                st.session_state.page = (
                                    "View Player"
                                )

                                st.rerun()

                # ---------------------------------------------
                # EXPORT
                # ---------------------------------------------

                st.divider()

                export_col1, export_col2 = (
                    st.columns([2, 1])
                )

                with export_col1:

                    st.info(
                        "The PDF contains the full standings "
                        "in a printable table format."
                    )

                with export_col2:

                    pdf_rows = []

                    for position, row in enumerate(
                        rows,
                        start=1
                    ):

                        pdf_rows.append(
                            {
                                "Pos": position,
                                "Player": row[
                                    "Player"
                                ],
                                "Played": row[
                                    "Played"
                                ],
                                "Won": row["Won"],
                                "Drawn": row[
                                    "Drawn"
                                ],
                                "Lost": row["Lost"],
                                "Legs For": row[
                                    "Legs For"
                                ],
                                "Legs Against": row[
                                    "Legs Against"
                                ],
                                "Difference": row[
                                    "Difference"
                                ],
                                "3 Dart Average": row[
                                    "3 Dart Average"
                                ],
                                "Points": row[
                                    "Points"
                                ]
                            }
                        )

                    league_pdf = (
                        create_league_table_pdf(
                            pdf_rows
                        )
                    )

                    st.download_button(
                        label=(
                            "📄 Download League Table"
                        ),
                        data=league_pdf,
                        file_name=(
                            f"{selected_tournament_name}"
                            "_league_table.pdf"
                        ),
                        mime="application/pdf",
                        key=(
                            "download_league_pdf_"
                            f"{selected_tournament_id}"
                        ),
                        use_container_width=True
                    )

            league_db.close()

# =========================================================
# KNOCKOUT STAGE — SEEDED BRACKET
# =========================================================

if page == "Knockout":

    st.markdown(
        """
        <h1 style="text-align:center;">
            🎯 Knockout Championship
        </h1>

        <p style="
            text-align:center;
            color:#bfc5d2;
            font-size:17px;
        ">
            All players qualify. The top four league seeds
            enter directly at the quarter-final stage.
        </p>
        """,
        unsafe_allow_html=True
    )

    knockout_db = SessionLocal()

    # -----------------------------------------------------
    # ADMIN: CREATE STANDALONE KNOCKOUT TOURNAMENT
    # -----------------------------------------------------

    if is_admin:

        with st.expander(
            "➕ Create Standalone Knockout Tournament",
            expanded=False
        ):

            all_players = knockout_db.query(
                Player
            ).order_by(
                Player.name
            ).all()

            knockout_player_options = {
                display_player_name(player): player.id
                for player in all_players
            }

            new_knockout_name = st.text_input(
                "Tournament Name",
                key="new_knockout_tournament_name"
            )

            new_knockout_format = st.selectbox(
                "Match Format",
                [
                    "Best of 3",
                    "Best of 5",
                    "Best of 7",
                    "Best of 9",
                    "Best of 11"
                ],
                key="new_knockout_match_format"
            )

            selected_knockout_players = st.multiselect(
                "Select Players",
                list(knockout_player_options.keys()),
                key="new_knockout_players"
            )

            if st.button(
                "🏆 Create Knockout Tournament",
                key="create_standalone_knockout",
                use_container_width=True
            ):

                clean_name = new_knockout_name.strip()

                existing_tournament = knockout_db.query(
                    Tournament
                ).filter(
                    Tournament.name == clean_name
                ).first()

                if not clean_name:

                    st.error(
                        "Please enter a tournament name."
                    )

                elif existing_tournament:

                    st.error(
                        "A tournament with that name already exists."
                    )

                elif len(selected_knockout_players) < 2:

                    st.error(
                        "Please select at least two players."
                    )

                else:

                    new_tournament = Tournament(
                        name=clean_name,
                        format_type="Knockout Only",
                        legs_format=new_knockout_format
                    )

                    knockout_db.add(
                        new_tournament
                    )

                    knockout_db.commit()

                    knockout_db.refresh(
                        new_tournament
                    )

                    for player_name in selected_knockout_players:

                        knockout_link = TournamentPlayer(
                            tournament_id=new_tournament.id,
                            player_id=knockout_player_options[
                                player_name
                            ]
                        )

                        knockout_db.add(
                            knockout_link
                        )

                    knockout_db.commit()

                    st.success(
                        "Standalone knockout tournament created."
                    )

                    st.rerun()

        st.divider()

    tournaments = knockout_db.query(
        Tournament
    ).order_by(
        Tournament.id.desc()
    ).all()

    knockout_tournaments = [
        tournament
        for tournament in tournaments
        if tournament.format_type
        in [
            "League + Knockout",
            "Knockout Only"
        ]
    ]

    if not knockout_tournaments:

        st.info(
            "No knockout-compatible tournaments "
            "have been created."
        )

        knockout_db.close()

    else:

        tournament_options = {
            tournament.name: tournament.id
            for tournament in knockout_tournaments
        }

        selected_tournament_name = st.selectbox(
            "Tournament",
            list(tournament_options.keys()),
            key="knockout_tournament_selector"
        )

        selected_tournament_id = (
            tournament_options[
                selected_tournament_name
            ]
        )

        players = knockout_db.query(
            Player
        ).all()

        player_objects = {
            player.id: player
            for player in players
        }

        player_lookup = {
            player.id: display_player_name(
                player
            )
            for player in players
        }

        selected_tournament = knockout_db.get(
            Tournament,
            selected_tournament_id
        )

        if (
            selected_tournament
            and selected_tournament.format_type == "Knockout Only"
        ):

            knockout_links = knockout_db.query(
                TournamentPlayer
            ).filter(
                TournamentPlayer.tournament_id
                == selected_tournament_id
            ).order_by(
                TournamentPlayer.id
            ).all()

            seeded_player_ids = [
                link.player_id
                for link in knockout_links
            ]

        else:

            seeded_player_ids = calculate_knockout_seeds(
                knockout_db,
                selected_tournament_id
            )

        seed_order = {
            player_id: seed_number
            for seed_number, player_id in enumerate(
                seeded_player_ids,
                start=1
            )
        }

        existing_matches = knockout_db.query(
            KnockoutMatch
        ).filter(
            KnockoutMatch.tournament_id
            == selected_tournament_id
        ).order_by(
            KnockoutMatch.id
        ).all()

        # -----------------------------------------------------
        # TOURNAMENT SUMMARY
        # -----------------------------------------------------

        summary_col1, summary_col2, summary_col3 = (
            st.columns(3)
        )

        with summary_col1:

            dashboard_card(
                "👥 Knockout Players",
                len(seeded_player_ids),
                selected_tournament_name
            )

        with summary_col2:

            completed_knockout_matches = len(
                [
                    match
                    for match in existing_matches
                    if match.played == 1
                    and match.player2_id is not None
                ]
            )

            dashboard_card(
                "✅ Matches Completed",
                completed_knockout_matches,
                "Knockout results entered"
            )

        with summary_col3:

            top_seed_name = "—"

            if seeded_player_ids:

                top_seed_name = (
                    player_lookup.get(
                        seeded_player_ids[0],
                        "Unknown"
                    )
                )

            dashboard_card(
                "🥇 Number One Seed",
                top_seed_name,
                "League seed"
            )

        # -----------------------------------------------------
        # SEEDING PREVIEW
        # -----------------------------------------------------

        with st.expander(
            "📋 View Knockout Seeds",
            expanded=False
        ):

            if not seeded_player_ids:

                st.info(
                    "No players are linked to this tournament."
                )

            else:

                for seed_number, player_id in enumerate(
                    seeded_player_ids,
                    start=1
                ):

                    seed_name = player_lookup.get(
                        player_id,
                        "Unknown"
                    )

                    if seed_number <= 4:

                        st.write(
                            f"**Seed {seed_number}:** "
                            f"{seed_name} "
                            "— Quarter-final bye"
                        )

                    else:

                        st.write(
                            f"**Seed {seed_number}:** "
                            f"{seed_name} "
                            "— Preliminary rounds"
                        )

        # -----------------------------------------------------
        # INITIALISE KNOCKOUT
        # -----------------------------------------------------

        if not existing_matches:

            if not is_admin:

                st.info(
                    "The knockout bracket has not "
                    "been created yet."
                )

            else:

                st.warning(
                    "Create the knockout only after the "
                    "league standings are ready. The current "
                    "league positions will be used as seeds."
                )

                confirm_start = st.checkbox(
                    "I confirm that the knockout seeds are correct",
                    key=(
                        "confirm_start_knockout_"
                        f"{selected_tournament_id}"
                    )
                )

                if st.button(
                    "🏆 Create Knockout Bracket",
                    key=(
                        "create_knockout_bracket_"
                        f"{selected_tournament_id}"
                    ),
                    use_container_width=True
                ):

                    if not confirm_start:

                        st.warning(
                            "Confirm the knockout seeds first."
                        )

                    elif len(seeded_player_ids) < 2:

                        st.error(
                            "At least eight players are required "
                            "for this seeded knockout format."
                        )

                    else:

                        top_four = (
                            seeded_player_ids[:4]
                        )

                        preliminary_players = (
                            seeded_player_ids[4:]
                        )

                        if len(
                            preliminary_players
                        ) == 4:

                            qualifier_ids = (
                                preliminary_players
                            )

                            quarter_final_pairs = [
                                (
                                    top_four[0],
                                    qualifier_ids[3]
                                ),
                                (
                                    top_four[3],
                                    qualifier_ids[0]
                                ),
                                (
                                    top_four[1],
                                    qualifier_ids[2]
                                ),
                                (
                                    top_four[2],
                                    qualifier_ids[1]
                                )
                            ]

                            for player1_id, player2_id in (
                                quarter_final_pairs
                            ):

                                create_knockout_match(
                                    db=knockout_db,
                                    tournament_id=(
                                        selected_tournament_id
                                    ),
                                    round_name="Quarter Final",
                                    player1_id=player1_id,
                                    player2_id=player2_id
                                )

                        else:

                            create_preliminary_round(
                                db=knockout_db,
                                tournament_id=(
                                    selected_tournament_id
                                ),
                                round_name="Preliminary 1",
                                player_ids=(
                                    preliminary_players
                                ),
                                seed_order=seed_order
                            )

                        knockout_db.commit()

                        st.success(
                            "Knockout bracket created."
                        )

                        st.rerun()

        else:

            # -------------------------------------------------
            # AUTOMATIC ROUND PROGRESSION
            # -------------------------------------------------

            preliminary_round_names = sorted(
                {
                    match.round_name
                    for match in existing_matches
                    if match.round_name.startswith(
                        "Preliminary"
                    )
                },
                key=lambda name: int(
                    name.split()[-1]
                )
            )

            latest_preliminary_name = None

            if preliminary_round_names:

                latest_preliminary_name = (
                    preliminary_round_names[-1]
                )

            quarter_final_matches = (
                get_knockout_round_matches(
                    knockout_db,
                    selected_tournament_id,
                    "Quarter Final"
                )
            )

            semi_final_matches = (
                get_knockout_round_matches(
                    knockout_db,
                    selected_tournament_id,
                    "Semi Final"
                )
            )

            final_matches = (
                get_knockout_round_matches(
                    knockout_db,
                    selected_tournament_id,
                    "Final"
                )
            )

            if (
                latest_preliminary_name
                and not quarter_final_matches
            ):

                latest_preliminary_matches = (
                    get_knockout_round_matches(
                        knockout_db,
                        selected_tournament_id,
                        latest_preliminary_name
                    )
                )

                if knockout_round_complete(
                    latest_preliminary_matches
                ):

                    preliminary_winners = (
                        get_round_winners(
                            latest_preliminary_matches
                        )
                    )

                    if len(preliminary_winners) > 4:

                        next_round_number = (
                            int(
                                latest_preliminary_name
                                .split()[-1]
                            )
                            + 1
                        )

                        next_round_name = (
                            f"Preliminary "
                            f"{next_round_number}"
                        )

                        create_preliminary_round(
                            db=knockout_db,
                            tournament_id=(
                                selected_tournament_id
                            ),
                            round_name=next_round_name,
                            player_ids=(
                                preliminary_winners
                            ),
                            seed_order=seed_order
                        )

                        knockout_db.commit()

                        st.success(
                            f"{next_round_name} created."
                        )

                        st.rerun()

                    elif len(preliminary_winners) == 4:

                        top_four = (
                            seeded_player_ids[:4]
                        )

                        qualifiers = sorted(
                            preliminary_winners,
                            key=lambda player_id: (
                                seed_order.get(
                                    player_id,
                                    9999
                                )
                            )
                        )

                        quarter_final_pairs = [
                            (
                                top_four[0],
                                qualifiers[-1]
                            ),
                            (
                                top_four[3],
                                qualifiers[0]
                            ),
                            (
                                top_four[1],
                                qualifiers[-2]
                            ),
                            (
                                top_four[2],
                                qualifiers[1]
                            )
                        ]

                        for player1_id, player2_id in (
                            quarter_final_pairs
                        ):

                            create_knockout_match(
                                db=knockout_db,
                                tournament_id=(
                                    selected_tournament_id
                                ),
                                round_name=(
                                    "Quarter Final"
                                ),
                                player1_id=player1_id,
                                player2_id=player2_id
                            )

                        knockout_db.commit()

                        st.success(
                            "Quarter-finals created."
                        )

                        st.rerun()

            if (
                quarter_final_matches
                and knockout_round_complete(
                    quarter_final_matches
                )
                and not semi_final_matches
            ):

                quarter_final_winners = (
                    get_round_winners(
                        quarter_final_matches
                    )
                )

                semi_final_pairs = [
                    (
                        quarter_final_winners[0],
                        quarter_final_winners[1]
                    ),
                    (
                        quarter_final_winners[2],
                        quarter_final_winners[3]
                    )
                ]

                for player1_id, player2_id in (
                    semi_final_pairs
                ):

                    create_knockout_match(
                        db=knockout_db,
                        tournament_id=(
                            selected_tournament_id
                        ),
                        round_name="Semi Final",
                        player1_id=player1_id,
                        player2_id=player2_id
                    )

                knockout_db.commit()

                st.success(
                    "Semi-finals created."
                )

                st.rerun()

            if (
                semi_final_matches
                and knockout_round_complete(
                    semi_final_matches
                )
                and not final_matches
            ):

                semi_final_winners = (
                    get_round_winners(
                        semi_final_matches
                    )
                )

                create_knockout_match(
                    db=knockout_db,
                    tournament_id=(
                        selected_tournament_id
                    ),
                    round_name="Final",
                    player1_id=(
                        semi_final_winners[0]
                    ),
                    player2_id=(
                        semi_final_winners[1]
                    )
                )

                knockout_db.commit()

                st.success(
                    "The final has been created."
                )

                st.rerun()

            # -------------------------------------------------
            # DISPLAY BRACKET
            # -------------------------------------------------

            display_rounds = []

            for match in knockout_db.query(
                KnockoutMatch
            ).filter(
                KnockoutMatch.tournament_id
                == selected_tournament_id
            ).order_by(
                KnockoutMatch.id
            ).all():

                if match.round_name not in display_rounds:

                    display_rounds.append(
                        match.round_name
                    )

            for round_name in display_rounds:

                round_matches = (
                    get_knockout_round_matches(
                        knockout_db,
                        selected_tournament_id,
                        round_name
                    )
                )

                st.divider()

                st.markdown(
                    f"## 🎯 {round_name}"
                )

                for match_number, match in enumerate(
                    round_matches,
                    start=1
                ):

                    player1_name = (
                        player_lookup.get(
                            match.player1_id,
                            "Unknown"
                        )
                    )

                    player2_name = (
                        player_lookup.get(
                            match.player2_id,
                            "BYE"
                        )
                        if match.player2_id
                        else "BYE"
                    )

                    with st.container(
                        border=True
                    ):

                        match_col1, match_col2, match_col3 = (
                            st.columns(
                                [2.5, 1.2, 2.5]
                            )
                        )

                        with match_col1:

                            st.markdown(
                                f"""
                                <div style="
                                    text-align:right;
                                    font-size:21px;
                                    font-weight:900;
                                    padding-top:8px;
                                ">
                                    {player1_name}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        with match_col2:

                            if (
                                match.player2_id is None
                                and match.winner_id
                            ):

                                score_display = "BYE"

                            elif match.played == 1:

                                score_display = (
                                    f"{match.player1_score}"
                                    f" - "
                                    f"{match.player2_score}"
                                )

                            else:

                                score_display = "VS"

                            st.markdown(
                                f"""
                                <div style="
                                    text-align:center;
                                    color:#f5c542;
                                    font-size:27px;
                                    font-weight:950;
                                ">
                                    {score_display}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        with match_col3:

                            st.markdown(
                                f"""
                                <div style="
                                    text-align:left;
                                    font-size:21px;
                                    font-weight:900;
                                    padding-top:8px;
                                ">
                                    {player2_name}
                                </div>
                                """,
                                unsafe_allow_html=True
                            )

                        if (
                            match.played == 1
                            and match.winner_id
                        ):

                            winner_name = (
                                player_lookup.get(
                                    match.winner_id,
                                    "Unknown"
                                )
                            )

                            st.success(
                                f"Winner: {winner_name}"
                            )

                        elif is_admin:

                            with st.form(
                                key=(
                                    f"knockout_result_form_"
                                    f"{match.id}"
                                )
                            ):

                                score_col1, score_col2 = (
                                    st.columns(2)
                                )

                                with score_col1:

                                    player1_score = (
                                        st.number_input(
                                            (
                                                f"{player1_name} "
                                                "Score"
                                            ),
                                            min_value=0,
                                            max_value=20,
                                            value=0,
                                            key=(
                                                f"ko_p1_score_"
                                                f"{match.id}"
                                            )
                                        )
                                    )

                                with score_col2:

                                    player2_score = (
                                        st.number_input(
                                            (
                                                f"{player2_name} "
                                                "Score"
                                            ),
                                            min_value=0,
                                            max_value=20,
                                            value=0,
                                            key=(
                                                f"ko_p2_score_"
                                                f"{match.id}"
                                            )
                                        )
                                    )

                                save_knockout_result = (
                                    st.form_submit_button(
                                        "💾 Save Knockout Result",
                                        use_container_width=True
                                    )
                                )

                            if save_knockout_result:

                                if (
                                    player1_score
                                    == player2_score
                                ):

                                    st.error(
                                        "A knockout match cannot "
                                        "finish as a draw."
                                    )

                                else:

                                    result_db = (
                                        SessionLocal()
                                    )

                                    target_match = (
                                        result_db.get(
                                            KnockoutMatch,
                                            match.id
                                        )
                                    )

                                    if not target_match:

                                        st.error(
                                            "Knockout match "
                                            "could not be found."
                                        )

                                    else:

                                        target_match.player1_score = (
                                            player1_score
                                        )

                                        target_match.player2_score = (
                                            player2_score
                                        )

                                        target_match.winner_id = (
                                            target_match.player1_id
                                            if player1_score
                                            > player2_score
                                            else target_match.player2_id
                                        )

                                        target_match.played = 1

                                        result_db.commit()

                                        st.success(
                                            "Knockout result saved."
                                        )

                                        result_db.close()

                                        st.rerun()

                                    result_db.close()

            # -------------------------------------------------
            # CHAMPION
            # -------------------------------------------------

            final_matches = (
                get_knockout_round_matches(
                    knockout_db,
                    selected_tournament_id,
                    "Final"
                )
            )

            if (
                final_matches
                and knockout_round_complete(
                    final_matches
                )
            ):

                champion_id = (
                    final_matches[0].winner_id
                )

                champion = player_objects.get(
                    champion_id
                )

                st.divider()

                champion_left, champion_centre, champion_right = (
                    st.columns([1, 1.5, 1])
                )

                with champion_centre:

                    with st.container(
                        border=True
                    ):

                        st.markdown(
                            """
                            <h1 style="
                                text-align:center;
                                color:#f5c542;
                            ">
                                🏆 CHAMPION 🏆
                            </h1>
                            """,
                            unsafe_allow_html=True
                        )

                        if (
                            champion
                            and champion.logo_path
                            and os.path.exists(
                                champion.logo_path
                            )
                        ):

                            st.image(
                                champion.logo_path,
                                width=180
                            )

                        st.markdown(
                            f"""
                            <h2 style="
                                text-align:center;
                            ">
                                {
                                    player_lookup.get(
                                        champion_id,
                                        "Unknown"
                                    )
                                }
                            </h2>
                            """,
                            unsafe_allow_html=True
                        )

            # -------------------------------------------------
            # ADMIN RESET
            # -------------------------------------------------

            if is_admin:

                st.divider()

                with st.expander(
                    "⚠️ Reset Knockout Bracket",
                    expanded=False
                ):

                    st.warning(
                        "This deletes every knockout match "
                        "and result for the selected tournament."
                    )

                    confirm_reset = st.checkbox(
                        "I understand that all knockout results will be deleted",
                        key=(
                            "confirm_reset_knockout_"
                            f"{selected_tournament_id}"
                        )
                    )

                    if st.button(
                        "🗑 Reset Knockout",
                        key=(
                            "reset_knockout_"
                            f"{selected_tournament_id}"
                        ),
                        use_container_width=True
                    ):

                        if not confirm_reset:

                            st.warning(
                                "Confirm the reset first."
                            )

                        else:

                            knockout_db.query(
                                KnockoutMatch
                            ).filter(
                                KnockoutMatch.tournament_id
                                == selected_tournament_id
                            ).delete(
                                synchronize_session=False
                            )

                            knockout_db.commit()

                            st.success(
                                "Knockout bracket reset."
                            )

                            st.rerun()

        knockout_db.close()

# =========================================================
# STATISTICS PAGE — UPGRADE
# =========================================================

if page == "Statistics":

    st.markdown(
        """
        <h1 style="text-align:center;">
            📊 League Statistics
        </h1>

        <p style="
            text-align:center;
            color:#bfc5d2;
            font-size:17px;
        ">
            Player performance, scoring records and current form
        </p>
        """,
        unsafe_allow_html=True
    )

    stats_db = SessionLocal()

    tournaments = stats_db.query(
        Tournament
    ).order_by(
        Tournament.id.desc()
    ).all()

    if not tournaments:

        st.info(
            "Create a tournament before viewing statistics."
        )

        stats_db.close()

    else:

        tournament_options = {
            tournament.name: tournament.id
            for tournament in tournaments
        }

        selected_tournament_name = st.selectbox(
            "Tournament",
            list(tournament_options.keys()),
            key="statistics_tournament_selector"
        )

        selected_tournament_id = tournament_options[
            selected_tournament_name
        ]

        tournament_links = stats_db.query(
            TournamentPlayer
        ).filter(
            TournamentPlayer.tournament_id
            == selected_tournament_id
        ).all()

        tournament_player_ids = {
            link.player_id
            for link in tournament_links
        }

        players = stats_db.query(
            Player
        ).filter(
            Player.id.in_(
                tournament_player_ids
            )
        ).all()

        fixtures = stats_db.query(
            Fixture
        ).filter(
            Fixture.tournament_id
            == selected_tournament_id,
            Fixture.played == 1
        ).order_by(
            Fixture.round_number,
            Fixture.id
        ).all()

        player_lookup = {
            player.id: player
            for player in players
        }

        def safe_int(value):

            try:
                return int(value or 0)

            except (TypeError, ValueError):
                return 0


        def safe_average(value):

            try:
                average_value = float(value or 0)

            except (TypeError, ValueError):
                return None

            if 0 < average_value <= 200:
                return average_value

            return None


        statistics = {}

        for player in players:

            statistics[player.id] = {
                "player": player,
                "played": 0,
                "wins": 0,
                "draws": 0,
                "losses": 0,
                "legs_for": 0,
                "legs_against": 0,
                "averages": [],
                "180s": 0,
                "highest_checkout": 0,
                "form": []
            }

        for fixture in fixtures:

            if (
                fixture.player1_id not in statistics
                or fixture.player2_id not in statistics
            ):
                continue

            player1_stats = statistics[
                fixture.player1_id
            ]

            player2_stats = statistics[
                fixture.player2_id
            ]

            player1_legs = safe_int(
                fixture.player1_legs
            )

            player2_legs = safe_int(
                fixture.player2_legs
            )

            player1_stats["played"] += 1
            player2_stats["played"] += 1

            player1_stats["legs_for"] += (
                player1_legs
            )

            player1_stats["legs_against"] += (
                player2_legs
            )

            player2_stats["legs_for"] += (
                player2_legs
            )

            player2_stats["legs_against"] += (
                player1_legs
            )

            player1_average = safe_average(
                fixture.player1_average
            )

            player2_average = safe_average(
                fixture.player2_average
            )

            if player1_average is not None:

                player1_stats["averages"].append(
                    player1_average
                )

            if player2_average is not None:

                player2_stats["averages"].append(
                    player2_average
                )

            player1_stats["180s"] += safe_int(
                getattr(
                    fixture,
                    "player1_180s",
                    0
                )
            )

            player2_stats["180s"] += safe_int(
                getattr(
                    fixture,
                    "player2_180s",
                    0
                )
            )

            player1_stats[
                "highest_checkout"
            ] = max(
                player1_stats[
                    "highest_checkout"
                ],
                safe_int(
                    getattr(
                        fixture,
                        "player1_high_checkout",
                        0
                    )
                )
            )

            player2_stats[
                "highest_checkout"
            ] = max(
                player2_stats[
                    "highest_checkout"
                ],
                safe_int(
                    getattr(
                        fixture,
                        "player2_high_checkout",
                        0
                    )
                )
            )

            if player1_legs > player2_legs:

                player1_stats["wins"] += 1
                player2_stats["losses"] += 1

                player1_stats["form"].append(
                    "W"
                )

                player2_stats["form"].append(
                    "L"
                )

            elif player2_legs > player1_legs:

                player2_stats["wins"] += 1
                player1_stats["losses"] += 1

                player2_stats["form"].append(
                    "W"
                )

                player1_stats["form"].append(
                    "L"
                )

            else:

                player1_stats["draws"] += 1
                player2_stats["draws"] += 1

                player1_stats["form"].append(
                    "D"
                )

                player2_stats["form"].append(
                    "D"
                )

        statistic_rows = []

        for player_id, data in statistics.items():

            average = 0.0

            if data["averages"]:

                average = round(
                    sum(data["averages"])
                    / len(data["averages"]),
                    2
                )

            win_percentage = 0.0

            if data["played"] > 0:

                win_percentage = round(
                    (
                        data["wins"]
                        / data["played"]
                    )
                    * 100,
                    1
                )

            one_eighties_per_match = 0.0

            if data["played"] > 0:

                one_eighties_per_match = round(
                    data["180s"]
                    / data["played"],
                    2
                )

            leg_difference = (
                data["legs_for"]
                - data["legs_against"]
            )

            longest_winning_streak = 0
            current_winning_streak = 0
            running_winning_streak = 0

            for result in data["form"]:

                if result == "W":

                    running_winning_streak += 1

                    longest_winning_streak = max(
                        longest_winning_streak,
                        running_winning_streak
                    )

                else:

                    running_winning_streak = 0

            for result in reversed(
                data["form"]
            ):

                if result == "W":

                    current_winning_streak += 1

                else:

                    break

            statistic_rows.append(
                {
                    "Player ID": player_id,
                    "Player": display_player_name(
                        data["player"]
                    ),
                    "Real Name": (
                        data["player"].name
                    ),
                    "Played": data["played"],
                    "Wins": data["wins"],
                    "Draws": data["draws"],
                    "Losses": data["losses"],
                    "Win Percentage": (
                        win_percentage
                    ),
                    "Average": average,
                    "180s": data["180s"],
                    "180s Per Match": (
                        one_eighties_per_match
                    ),
                    "Highest Checkout": (
                        data["highest_checkout"]
                    ),
                    "Legs For": (
                        data["legs_for"]
                    ),
                    "Legs Against": (
                        data["legs_against"]
                    ),
                    "Leg Difference": (
                        leg_difference
                    ),
                    "Form": data["form"][-5:],
                    "Current Streak": (
                        current_winning_streak
                    ),
                    "Longest Streak": (
                        longest_winning_streak
                    )
                }
            )

        statistic_rows = sorted(
            statistic_rows,
            key=lambda row: (
                row["Win Percentage"],
                row["Wins"],
                row["Average"]
            ),
            reverse=True
        )

        if not statistic_rows:

            st.info(
                "No players are linked to this tournament."
            )

        elif not fixtures:

            st.info(
                "Statistics will appear after results "
                "have been entered."
            )

        else:

            # -------------------------------------------------
            # LEAGUE LEADERS
            # -------------------------------------------------

            most_wins = max(
                statistic_rows,
                key=lambda row: (
                    row["Wins"],
                    row["Win Percentage"],
                    row["Average"]
                )
            )

            best_average = max(
                statistic_rows,
                key=lambda row: (
                    row["Average"],
                    row["Wins"]
                )
            )

            most_180s = max(
                statistic_rows,
                key=lambda row: (
                    row["180s"],
                    row["Average"]
                )
            )

            highest_checkout = max(
                statistic_rows,
                key=lambda row: (
                    row["Highest Checkout"],
                    row["Average"]
                )
            )

            leader_col1, leader_col2 = (
                st.columns(2)
            )

            with leader_col1:

                dashboard_card(
                    "👑 Most Wins",
                    most_wins["Player"],
                    (
                        f'{most_wins["Wins"]} wins '
                        f'from {most_wins["Played"]} matches'
                    )
                )

            with leader_col2:

                dashboard_card(
                    "🎯 Best Average",
                    best_average["Player"],
                    (
                        f'{best_average["Average"]:.2f}'
                        " three-dart average"
                    )
                )

            leader_col3, leader_col4 = (
                st.columns(2)
            )

            with leader_col3:

                dashboard_card(
                    "💯 Most 180s",
                    most_180s["Player"],
                    (
                        f'{most_180s["180s"]}'
                        " maximums"
                    )
                )

            with leader_col4:

                dashboard_card(
                    "🏹 Highest Checkout",
                    highest_checkout["Player"],
                    (
                        f'{highest_checkout["Highest Checkout"]}'
                        " checkout"
                    )
                )

            st.divider()

            # -------------------------------------------------
            # SORTING
            # -------------------------------------------------

            sort_options = {
                "Win Percentage": (
                    "Win Percentage"
                ),
                "Three-Dart Average": (
                    "Average"
                ),
                "Most Wins": "Wins",
                "Most 180s": "180s",
                "Highest Checkout": (
                    "Highest Checkout"
                ),
                "Leg Difference": (
                    "Leg Difference"
                ),
                "Longest Winning Streak": (
                    "Longest Streak"
                )
            }

            sort_selection = st.selectbox(
                "Rank players by",
                list(sort_options.keys()),
                key="statistics_sort_option"
            )

            sort_column = sort_options[
                sort_selection
            ]

            displayed_rows = sorted(
                statistic_rows,
                key=lambda row: (
                    row[sort_column],
                    row["Average"],
                    row["Wins"]
                ),
                reverse=True
            )

            st.markdown(
                f"## 📈 {sort_selection}"
            )

            # -------------------------------------------------
            # PLAYER STATISTIC CARDS
            # -------------------------------------------------

            for position, row in enumerate(
                displayed_rows,
                start=1
            ):

                player = player_lookup.get(
                    row["Player ID"]
                )

                if position == 1:
                    position_display = "🥇"

                elif position == 2:
                    position_display = "🥈"

                elif position == 3:
                    position_display = "🥉"

                else:
                    position_display = str(
                        position
                    )

                form_display = []

                for result in row["Form"]:

                    if result == "W":

                        form_display.append(
                            "🟢 W"
                        )

                    elif result == "D":

                        form_display.append(
                            "🟡 D"
                        )

                    else:

                        form_display.append(
                            "🔴 L"
                        )

                while len(form_display) < 5:

                    form_display.insert(
                        0,
                        "⚫ —"
                    )

                with st.container(
                    border=True
                ):

                    header_col1, header_col2, header_col3 = (
                        st.columns(
                            [0.7, 3.4, 1.2]
                        )
                    )

                    with header_col1:

                        st.markdown(
                            f"""
                            <div style="
                                text-align:center;
                                font-size:34px;
                                font-weight:950;
                                color:#f5c542;
                                padding-top:8px;
                            ">
                                {position_display}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )

                    with header_col2:

                        identity_col1, identity_col2 = (
                            st.columns(
                                [0.8, 3.2]
                            )
                        )

                        with identity_col1:

                            if (
                                player
                                and player.logo_path
                                and os.path.exists(
                                    player.logo_path
                                )
                            ):

                                st.image(
                                    player.logo_path,
                                    width=70
                                )

                            else:

                                st.markdown(
                                    """
                                    <div style="
                                        width:64px;
                                        height:64px;
                                        border-radius:50%;
                                        display:flex;
                                        align-items:center;
                                        justify-content:center;
                                        background:#111827;
                                        border:2px solid #f5c542;
                                        font-size:27px;
                                    ">
                                        🎯
                                    </div>
                                    """,
                                    unsafe_allow_html=True
                                )

                        with identity_col2:

                            st.markdown(
                                f"### {row['Player']}"
                            )

                            if (
                                row["Player"]
                                != row["Real Name"]
                            ):

                                st.caption(
                                    row["Real Name"]
                                )

                            st.caption(
                                "Recent form: "
                                + "  ".join(
                                    form_display
                                )
                            )

                    with header_col3:

                        if sort_column == "Average":

                            main_value = (
                                f'{row["Average"]:.2f}'
                            )

                            main_label = "AVG"

                        elif sort_column == (
                            "Win Percentage"
                        ):

                            main_value = (
                                f'{row["Win Percentage"]:.1f}%'
                            )

                            main_label = "WIN RATE"

                        elif sort_column == "180s":

                            main_value = row["180s"]
                            main_label = "180s"

                        elif sort_column == (
                            "Highest Checkout"
                        ):

                            main_value = row[
                                "Highest Checkout"
                            ]

                            main_label = "CHECKOUT"

                        elif sort_column == (
                            "Leg Difference"
                        ):

                            main_value = row[
                                "Leg Difference"
                            ]

                            main_label = "LEG DIFF"

                        elif sort_column == (
                            "Longest Streak"
                        ):

                            main_value = row[
                                "Longest Streak"
                            ]

                            main_label = "BEST STREAK"

                        else:

                            main_value = row["Wins"]
                            main_label = "WINS"

                        st.metric(
                            main_label,
                            main_value
                        )

                    result_col1, result_col2, result_col3, result_col4 = (
                        st.columns(4)
                    )

                    with result_col1:

                        st.metric(
                            "Record",
                            (
                                f'{row["Wins"]}-'
                                f'{row["Draws"]}-'
                                f'{row["Losses"]}'
                            ),
                            help="Wins-Draws-Losses"
                        )

                    with result_col2:

                        st.metric(
                            "Win Percentage",
                            (
                                f'{row["Win Percentage"]:.1f}%'
                            )
                        )

                    with result_col3:

                        st.metric(
                            "3-Dart Average",
                            (
                                f'{row["Average"]:.2f}'
                            )
                        )

                    with result_col4:

                        st.metric(
                            "Highest Checkout",
                            row["Highest Checkout"]
                        )

                    scoring_col1, scoring_col2, scoring_col3, scoring_col4 = (
                        st.columns(4)
                    )

                    with scoring_col1:

                        st.metric(
                            "Total 180s",
                            row["180s"]
                        )

                    with scoring_col2:

                        st.metric(
                            "180s Per Match",
                            (
                                f'{row["180s Per Match"]:.2f}'
                            )
                        )

                    with scoring_col3:

                        st.metric(
                            "Leg Difference",
                            row["Leg Difference"]
                        )

                    with scoring_col4:

                        st.metric(
                            "Current Win Streak",
                            row["Current Streak"]
                        )

                    detail_col1, detail_col2, detail_col3 = (
                        st.columns(3)
                    )

                    with detail_col1:

                        st.caption(
                            f'🎯 Legs For: {row["Legs For"]}'
                        )

                    with detail_col2:

                        st.caption(
                            (
                                f'🛡 Legs Against: '
                                f'{row["Legs Against"]}'
                            )
                        )

                    with detail_col3:

                        st.caption(
                            (
                                f'🔥 Longest winning streak: '
                                f'{row["Longest Streak"]}'
                            )
                        )

                    if st.button(
                        "🎴 View Player Card",
                        key=(
                            f"statistics_view_player_"
                            f'{row["Player ID"]}'
                        ),
                        use_container_width=True
                    ):

                        st.session_state[
                            "view_player_id"
                        ] = row[
                            "Player ID"
                        ]

                        st.session_state.page = (
                            "View Player"
                        )

                        st.rerun()

        stats_db.close()

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