from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import ForeignKey
from sqlalchemy import Date

from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Player(Base):

    __tablename__ = "players"

    id = Column(
        Integer,
        primary_key=True
    )

    name = Column(
        String,
        nullable=False
    )

    nickname = Column(
        String
    )

    logo_path = Column(
        String
    )

    # Statistics

    oneeighties = Column(
        Integer,
        default=0
    )

    highest_checkout = Column(
        Integer,
        default=0
    )

    tournaments_won = Column(
        Integer,
        default=0
    )


class Tournament(Base):

    __tablename__ = "tournaments"

    id = Column(Integer, primary_key=True)

    name = Column(String, nullable=False)

    format_type = Column(String)

    legs_format = Column(String)


class TournamentPlayer(Base):

    __tablename__ = "tournament_players"

    id = Column(Integer, primary_key=True)

    tournament_id = Column(
        Integer,
        ForeignKey("tournaments.id")
    )

    player_id = Column(
        Integer,
        ForeignKey("players.id")
    )

class Fixture(Base):

    __tablename__ = "fixtures"

    id = Column(
        Integer,
        primary_key=True
    )

    tournament_id = Column(
        Integer,
        ForeignKey("tournaments.id")
    )

    player1_id = Column(
        Integer,
        ForeignKey("players.id")
    )

    player2_id = Column(
        Integer,
        ForeignKey("players.id")
    )

    date_played = Column(
        Date,
        nullable=True
    )

    player1_legs = Column(
        Integer,
        default=0
    )

    player2_legs = Column(
        Integer,
        default=0
    )

    player1_average = Column(
        String,
        default="0"
    )

    player2_average = Column(
        String,
        default="0"
    )


    played = Column(
        Integer,
        default=0
    )

class KnockoutMatch(Base):

    __tablename__ = "knockout_matches"

    id = Column(
        Integer,
        primary_key=True
    )

    tournament_id = Column(
        Integer,
        ForeignKey("tournaments.id")
    )

    round_name = Column(
        String
    )

    player1_id = Column(
        Integer,
        ForeignKey("players.id")
    )

    player2_id = Column(
        Integer,
        ForeignKey("players.id")
    )

    player1_score = Column(
        Integer,
        default=0
    )

    player2_score = Column(
        Integer,
        default=0
    )

    winner_id = Column(
        Integer,
        nullable=True
    )

    played = Column(
        Integer,
        default=0
    )

class HallOfFame(Base):

    __tablename__ = "hall_of_fame"

    id = Column(Integer, primary_key=True)

    tournament_name = Column(String)

    champion_name = Column(String)

    year = Column(String)

    oneeighties = Column(
    Integer,
    default=0
)

highest_checkout = Column(
    Integer,
    default=0
)

class User(Base):

    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True
    )

    username = Column(
        String,
        unique=True
    )

    password = Column(
        String
    )

    role = Column(
        String,
        default="viewer"
    )

    player_id = Column(
        Integer,
        ForeignKey("players.id"),
        nullable=True
    )