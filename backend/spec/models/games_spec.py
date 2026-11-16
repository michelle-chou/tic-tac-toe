from datetime import datetime, timedelta, timezone

import pytest

from spec import rails_helper  # noqa: F401
from app.models.game import Game
from spec.factories.games import GameFactory

LONG_AGO = datetime(2020, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)
INVALID_MOVES = 'must be a list of different squares, numbered 0 to 8'


# Test suite for the Game model
class DescribeGame:
    @pytest.fixture(autouse=True)
    def before(self):
        self.game = GameFactory.build()

    @property
    def subject(self):
        return self.game

    def it_should_respond_to_its_attributes(self):
        for name in ('player_x', 'player_o', 'winner', 'first_player', 'moves', 'created_at'):
            assert hasattr(self.subject, name)

    def it_should_be_valid(self):
        assert self.subject.valid()

    def it_should_be_valid_without_a_winner(self):
        # A draw: O starts and fills the board without a line for either player.
        assert GameFactory.build(winner=None, first_player='O', moves=[0, 1, 2, 4, 3, 5, 7, 6, 8]).valid()

    class DescribeTestNoPlayers:
        def it_has_no_players(self):
            game = GameFactory.build(player_x=None, player_o='  ')

            assert not game.valid()
            assert game.errors == {'player_x': ["can't be blank"], 'player_o': ["can't be blank"]}

    class DescribeTestMarks:
        def it_only_takes_a_mark_as_the_winner(self):
            for winner in ('x', 'XO', '', 'draw', 'Ann'):
                game = GameFactory.build(winner=winner)

                assert not game.valid()
                assert game.errors == {'winner': ['is not included in the list']}

        def it_needs_to_know_who_moved_first(self):
            for first_player in (None, '', 'x', 'Ann'):
                game = GameFactory.build(first_player=first_player)

                assert not game.valid()
                assert game.errors == {'first_player': ['is not included in the list']}

    class DescribeTestMoves:
        def it_takes_one_to_nine_different_squares(self):
            for moves in ([4], [8, 0], [0, 1, 2, 4, 3, 5, 7, 6, 8]):
                assert GameFactory.build(moves=moves).valid()

        def it_rejects_anything_else(self):
            moves_that_are_not_a_game = [
                None,
                [],
                '[0, 3, 1, 4, 2]',
                5,
                {'0': 0},
                [0, 3, 1, 4, 9],
                [0, 3, 1, 4, -1],
                [0, 3, 1, 4, 0],
                [0, 3, 1, 4, '2'],
                [0, 3, 1, 4, 2.0],
                [0, 3, 1, 4, None],
                [True, False],
                [0, 1, 2, 3, 4, 5, 6, 7, 8, 0],
            ]
            for moves in moves_that_are_not_a_game:
                game = GameFactory.build(moves=moves)

                assert not game.valid(), moves
                assert game.errors == {'moves': [INVALID_MOVES]}

    class DescribeTestPersistence:
        def it_reads_the_moves_back_as_a_list(self):
            game = GameFactory.create(moves=[4, 0, 8])
            rows, _ = Game.execute('SELECT "moves", typeof("moves") AS "type" FROM "games" WHERE "id" = ?', [game.id])

            assert Game.recent(1)[0].moves == [4, 0, 8]
            assert rows == [{'moves': '[4,0,8]', 'type': 'text'}]

        def it_sets_created_at(self):
            assert GameFactory.build().created_at is None
            assert isinstance(GameFactory.create().created_at, datetime)

        def it_saves_nothing_when_invalid(self):
            assert not GameFactory.build(moves=[9]).save()
            assert Game.all() == []

    class DescribeRecent:
        def it_returns_the_newest_games_first(self):
            games = [GameFactory.create(created_at=LONG_AGO + timedelta(minutes=minute)) for minute in (5, 9, 1)]

            assert [game.id for game in Game.recent(10)] == [games[1].id, games[0].id, games[2].id]

        def it_puts_the_game_saved_last_first_when_the_times_are_equal(self):
            games = [GameFactory.create(created_at=LONG_AGO) for _ in range(3)]

            assert [game.id for game in Game.recent(10)] == [game.id for game in reversed(games)]

        def it_orders_times_stored_with_and_without_a_fraction(self):
            # A whole second is stored without its fraction: it still sorts before the same second and a bit.
            later = GameFactory.create(created_at=LONG_AGO.replace(microsecond=1))
            earlier = GameFactory.create(created_at=LONG_AGO.replace(microsecond=0))

            assert [game.id for game in Game.recent(10)] == [later.id, earlier.id]

        def it_returns_no_more_games_than_asked_for(self):
            games = [GameFactory.create() for _ in range(3)]

            assert [game.id for game in Game.recent(2)] == [games[2].id, games[1].id]
            assert Game.recent(0) == []
