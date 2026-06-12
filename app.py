import streamlit as st
import pandas as pd
import os

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
    KnockoutMatch
)


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

def create_fixtures_pdf(fixture_rows, tournament_name):

    buffer = BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4
    )

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
    layout="wide"
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

    </style>
    """,
    unsafe_allow_html=True
)


# LOGIN

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:

    col1, col2, col3 = st.columns([1, 2, 1])

    with col2:

        st.image(
            "assets/royal_oak_logo.png",
            width=250
        )

        st.title("Ye Royal Oak Darts League")

        st.subheader("Player Login")

        username = st.text_input("Username")

        password = st.text_input(
            "Password",
            type="password"
        )

        if st.button(
            "Login",
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

        st.divider()

        with st.expander("🆕 Create Account"):

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

                        st.success("Account created successfully. You can now log in.")

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

is_admin = st.session_state.get("role") == "admin"


# TABS

if is_admin:

    profile_tab, players_tab, users_tab, tournaments_tab, fixtures_tab, league_tab, knockout_tab, stats_tab = st.tabs(
        [
            "Profile",
            "Players",
            "Users",
            "Tournaments",
            "Fixtures",
            "League",
            "Knockout",
            "Statistics"
        ]
    )

else:

    profile_tab, fixtures_tab, league_tab, knockout_tab, stats_tab = st.tabs(
        [
            "My Profile",
            "Fixtures",
            "League",
            "Knockout",
            "Statistics"
        ]
    )


# ADMIN TABS

with profile_tab:

    st.header("🎯 My Player Profile")

    player_id = st.session_state.get("player_id")

    if not player_id:

        st.info("No player is linked to this account.")

    else:

        db = SessionLocal()

        player = db.get(Player, player_id)

        if not player:

            st.error("Linked player could not be found.")

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

            upcoming = []

            for fixture in fixtures:

                if fixture.played == 0:

                    upcoming.append(fixture)

                else:

                    played += 1

                    if fixture.player1_id == player_id:

                        player_legs = fixture.player1_legs
                        opponent_legs = fixture.player2_legs

                        try:
                            averages.append(float(fixture.player1_average))
                        except:
                            pass

                    else:

                        player_legs = fixture.player2_legs
                        opponent_legs = fixture.player1_legs

                        try:
                            averages.append(float(fixture.player2_average))
                        except:
                            pass

                    if player_legs > opponent_legs:

                        wins += 1

                    elif player_legs < opponent_legs:

                        losses += 1

                    else:

                        draws += 1

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

            st.subheader("Upcoming Fixtures")

            if not upcoming:

                st.info("No upcoming fixtures.")

            else:

                players = db.query(Player).all()

                player_lookup = {
                    p.id: p.name
                    for p in players
                }

                for fixture in upcoming:

                    p1 = player_lookup.get(
                        fixture.player1_id,
                        "Unknown"
                    )

                    p2 = player_lookup.get(
                        fixture.player2_id,
                        "Unknown"
                    )

                    st.write(f"🎯 {p1} vs {p2}")

            st.divider()

            st.subheader("Recent Results")

            recent_results = [
                fixture
                for fixture in fixtures
                if fixture.played == 1
            ]

            recent_results = recent_results[-5:]

            if not recent_results:

                st.info("No results yet.")

            else:

                players = db.query(Player).all()

                player_lookup = {
                    p.id: p.name
                    for p in players
                }

                for fixture in recent_results:

                    p1 = player_lookup.get(
                        fixture.player1_id,
                        "Unknown"
                    )

                    p2 = player_lookup.get(
                        fixture.player2_id,
                        "Unknown"
                    )

                    st.write(
                        f"{p1} {fixture.player1_legs} - "
                        f"{fixture.player2_legs} {p2}"
                    )

        db.close()

if is_admin:

    with players_tab:

        st.header("Add Player")

        name = st.text_input("Player Name")

        nickname = st.text_input("Nickname")

        logo = st.file_uploader(
            "Player Logo",
            type=["png", "jpg", "jpeg"]
        )

        if st.button("Add Player"):

            if name and logo:

                os.makedirs("assets/logos", exist_ok=True)

                logo_path = f"assets/logos/{logo.name}"

                with open(logo_path, "wb") as f:
                    f.write(logo.getbuffer())

                db = SessionLocal()

                player = Player(
                    name=name,
                    nickname=nickname,
                    logo_path=logo_path
                )

                db.add(player)
                db.commit()
                db.close()

                st.success("Player Added!")
                st.rerun()

            else:

                st.error("Please enter a name and upload a logo.")

        st.divider()

        st.subheader("Current Players")

        db = SessionLocal()
        players = db.query(Player).all()
        db.close()

        for player in players:

            col1, col2, col3 = st.columns([1, 4, 1])

            with col1:

                if player.logo_path and os.path.exists(player.logo_path):
                    st.image(player.logo_path, width=75)

            with col2:

                st.write(f"### {player.name}")
                st.write(player.nickname)

            with col3:

                if st.button("Delete", key=f"del_{player.id}"):

                    db = SessionLocal()

                    target = db.get(Player, player.id)

                    if target:
                        db.delete(target)
                        db.commit()

                    db.close()

                    st.rerun()

            st.divider()


    with users_tab:

        st.header("👤 User Accounts")

        db = SessionLocal()

        players = db.query(Player).all()

        player_lookup = {
            p.name: p.id
            for p in players
        }

        username = st.text_input(
            "Username",
            key="new_user"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="new_pass"
        )

        role = st.selectbox(
            "Role",
            [
                "viewer",
                "admin"
            ],
            key="new_role"
        )

        player_names = list(player_lookup.keys())

        selected_player = st.selectbox(
            "Linked Player",
            player_names if player_names else ["No players available"],
            key="linked_player"
        )

        if st.button("Create User"):

            if not username or not password:

                st.error("Please enter a username and password.")

            elif not player_names:

                st.error("Please add players before creating user accounts.")

            else:

                existing_user = db.query(User).filter(
                    User.username == username
                ).first()

                if existing_user:

                    st.error("That username already exists.")

                else:

                    user = User(
                        username=username,
                        password=password,
                        role=role,
                        player_id=player_lookup[selected_player]
                    )

                    db.add(user)
                    db.commit()

                    st.success("User Created")
                    st.rerun()

        st.divider()

        st.subheader("Current Users")

        users = db.query(User).all()

        for user in users:

            linked_player = db.get(Player, user.player_id) if user.player_id else None
            player_name = linked_player.name if linked_player else "No linked player"

            st.write(
                f"{user.username} ({user.role}) - {player_name}"
            )

        db.close()


    with tournaments_tab:

        st.header("🏆 Create Tournament")

        tournament_name = st.text_input(
            "Tournament Name",
            key="tournament_name"
        )

        format_type = st.selectbox(
            "Format",
            [
                "League + Knockout",
                "League Only",
                "Knockout Only"
            ],
            key="tournament_format"
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
            key="legs_format"
        )

        db = SessionLocal()

        all_players = db.query(Player).all()

        player_options = {
            p.name: p.id
            for p in all_players
        }

        selected_players = st.multiselect(
            "Select Players",
            list(player_options.keys()),
            key="tournament_players"
        )

        if st.button("Create Tournament"):

            if not tournament_name:

                st.error("Please enter a tournament name.")

            elif len(selected_players) < 2:

                st.error("Please select at least two players.")

            else:

                tournament = Tournament(
                    name=tournament_name,
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

                st.success("Tournament Created!")
                st.rerun()

        st.divider()

        st.subheader("Existing Tournaments")

        tournaments = db.query(Tournament).all()

        for tournament in tournaments:

            st.write(f"🏆 {tournament.name}")
            st.write(f"Format: {tournament.format_type}")
            st.write(f"Match Format: {tournament.legs_format}")

            st.divider()

        db.close()


# FIXTURES TAB

with fixtures_tab:

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

            
            "played?":
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

with league_tab:

    st.header("🏆 League Table")

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

        p1 = table[fixture.player1_id]
        p2 = table[fixture.player2_id]

        p1["played"] += 1
        p2["played"] += 1

        p1["legs_for"] += fixture.player1_legs
        p1["legs_against"] += fixture.player2_legs

        p2["legs_for"] += fixture.player2_legs
        p2["legs_against"] += fixture.player1_legs

        try:
            p1["averages"].append(
                float(fixture.player1_average)
            )
        except:
            pass

        try:
            p2["averages"].append(
                float(fixture.player2_average)
            )
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

        if len(data["averages"]) > 0:

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
            x["Difference"]
        ),
        reverse=True
    )

    st.session_state["league_standings"] = rows

    if rows:

        df = pd.DataFrame(rows)

        display_df = df.copy()

        if "Player ID" in display_df.columns:
            display_df = display_df.drop(columns=["Player ID"])

        display_df.insert(
            0,
            "Pos",
            range(1, len(display_df) + 1)
        )

        styled_df = (
        display_df.style.set_properties(
             **{
            "text-align": "center",
            "font-weight": "bold",
            "font-size": "15px"
        }
    )
)

        st.dataframe(
            styled_df,
            hide_index=True,
            use_container_width=True
        )

        csv = display_df.to_csv(index=False)

        st.download_button(
            "📥 Download League Table CSV",
            csv,
            "league_table.csv",
            "text/csv"
        )

    else:

        st.info("No completed matches yet.")

    db.close()


# KNOCKOUT TAB

with knockout_tab:

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

with stats_tab:

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

        styled_fixtures = (
    fixtures_df.style
    .set_properties(
        **{
            "font-weight": "bold",
            "font-size": "15px",
            "text-align": "center"
        }
    )
)

        st.dataframe(
            styled_fixtures,
            hide_index=True,
            use_container_width=True
)

    else:

        st.info("No statistics available yet.")

    db.close()
