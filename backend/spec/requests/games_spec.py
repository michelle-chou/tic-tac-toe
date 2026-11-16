import json as JSON
import re
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from spec import rails_helper  # noqa: F401
from app.models.game import Game
from lib import ActiveRecord, Rails
from spec.factories.games import GameFactory
from spec.support.request_spec_helper import RequestSpecHelper

ATTRIBUTES = ['id', 'player_x', 'player_o', 'winner', 'first_player', 'moves', 'created_at']
JSON_CONTENT_TYPE = 'application/json; charset=utf-8'
TIMESTAMP = re.compile(r'\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\Z')
LONG_AGO = datetime(2020, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)
INVALID_MOVES = 'must be a list of different squares, numbered 0 to 8'
# Ann starts with O and takes the top row.
GAME = {'player_x': 'Bob', 'player_o': 'Ann', 'winner': 'O', 'first_player': 'O', 'moves': [0, 3, 1, 4, 2]}
# O starts and the board fills up without a line.
DRAW = {'player_x': 'Bob', 'player_o': 'Ann', 'winner': None, 'first_player': 'O', 'moves': [0, 1, 2, 4, 3, 5, 7, 6, 8]}


class RequestSpec(RequestSpecHelper):
    """Three saved games, a minute apart, and the HTTP verbs: each request stores its response in self.response."""

    @pytest.fixture(autouse=True)
    def before(self, client):
        self.client = client
        self.games = [GameFactory.create(created_at=LONG_AGO + timedelta(minutes=minute)) for minute in range(3)]

    def request(self, method, path, params=None, **options):
        if params is not None:
            options.update(data=JSON.dumps(params), content_type='application/json;charset=utf-8')
        self.response = self.client.open(path, method=method, **options)
        return self.response

    def get(self, path, **options):
        return self.request('GET', path, **options)

    def post(self, path, params=None, **options):
        return self.request('POST', path, params, **options)

    def ids(self):
        return [game['id'] for game in self.json()]

    def create_games(self, count):
        with ActiveRecord.Base.transaction():
            return [GameFactory.create() for _ in range(count)]


class DescribeGetGames(RequestSpec):
    def it_returns_the_games_newest_first(self):
        self.get('/api/v1/games?limit=10')

        assert self.response.status_code == 200
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert self.ids() == [game.id for game in reversed(self.games)]
        assert [list(game) for game in self.json()] == [ATTRIBUTES] * 3

    def it_orders_by_the_time_a_game_was_saved(self):
        oldest = GameFactory.create(created_at=LONG_AGO - timedelta(days=1))

        assert self.get('/api/v1/games').get_json()[-1]['id'] == oldest.id

    def it_renders_the_moves_as_an_array(self):
        game = GameFactory.create(player_x='Bob', player_o='Ann', winner=None, first_player='O', moves=DRAW['moves'])
        self.get('/api/v1/games?limit=1')

        assert self.json() == [{**DRAW, 'id': game.id, 'created_at': self.json()[0]['created_at']}]
        assert b'"winner":null,"first_player":"O","moves":[0,1,2,4,3,5,7,6,8]' in self.response.data

    def it_renders_millisecond_utc_timestamps(self):
        self.get('/api/v1/games')

        assert [game['created_at'] for game in self.json()] == [
            '2020-01-02T03:06:05.678Z',
            '2020-01-02T03:05:05.678Z',
            '2020-01-02T03:04:05.678Z',
        ]

    def it_returns_as_many_games_as_the_limit(self):
        assert len(self.get('/api/v1/games?limit=2').get_json()) == 2
        assert self.ids() == [self.games[2].id, self.games[1].id]
        assert len(self.get('/api/v1/games?limit=1').get_json()) == 1
        assert len(self.get('/api/v1/games?limit=50').get_json()) == 3

    def it_returns_ten_games_without_a_limit(self):
        games = self.create_games(12)

        assert len(self.get('/api/v1/games').get_json()) == 10
        assert self.ids() == [game.id for game in reversed(games[2:])]

    def it_returns_ten_games_when_the_limit_is_not_a_positive_number(self):
        self.create_games(12)

        for limit in ('', 'abc', '0', '-1', '-100', '2.5', '1e3', 'NaN', '9' * 5000):
            assert len(self.get('/api/v1/games?limit=%s' % limit).get_json()) == 10, limit
        for query in ('limit[]=2', 'limit[a]=2'):
            assert len(self.get('/api/v1/games?%s' % query).get_json()) == 10, query

    def it_returns_a_hundred_games_at_most(self):
        self.create_games(110)

        assert len(self.get('/api/v1/games?limit=100').get_json()) == 100
        assert len(self.get('/api/v1/games?limit=101').get_json()) == 100
        assert len(self.get('/api/v1/games?limit=99999999999999999999').get_json()) == 100

    def it_serves_the_same_body_with_or_without_a_format_suffix(self):
        body = self.get('/api/v1/games?limit=10').data

        assert self.get('/api/v1/games.json?limit=10').data == body
        assert self.get('/api/v1/games/?limit=10').data == body

    def it_returns_an_empty_array_when_there_are_no_games(self):
        for game in Game.all():
            game.destroy()

        assert self.get('/api/v1/games?limit=10').data == b'[]'


class DescribePostGames(RequestSpec):
    def it_creates_a_game(self):
        self.post('/api/v1/games', {'game': GAME})

        assert self.response.status_code == 201
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert list(self.json()) == ATTRIBUTES
        assert self.json() == {**GAME, 'id': self.games[-1].id + 1, 'created_at': self.json()['created_at']}
        assert TIMESTAMP.match(self.json()['created_at'])
        assert len(Game.all()) == 4

    def it_lists_the_new_game_first(self):
        created = self.post('/api/v1/games', {'game': GAME}).get_json()

        assert self.get('/api/v1/games?limit=10').get_json()[0] == created
        assert len(self.json()) == 4

    def it_creates_a_drawn_game(self):
        self.post('/api/v1/games', {'game': DRAW})

        assert self.response.status_code == 201
        assert [self.json()['winner'], self.json()['moves']] == [None, DRAW['moves']]

    def it_reads_a_game_without_a_winner_as_a_draw(self):
        self.post('/api/v1/games', {'game': {name: value for name, value in DRAW.items() if name != 'winner'}})

        assert self.response.status_code == 201
        assert self.json()['winner'] is None

    def it_accepts_the_attributes_without_the_game_root(self):
        self.post('/api/v1/games', {**GAME, 'foo': 1})

        assert self.response.status_code == 201
        assert self.json()['moves'] == GAME['moves']

    def it_ignores_attributes_that_are_not_permitted(self):
        self.post('/api/v1/games', {'game': {**GAME, 'id': 999, 'created_at': '2000-01-01', 'foo': 1}})

        assert self.response.status_code == 201
        assert self.json()['id'] == self.games[-1].id + 1
        assert not self.json()['created_at'].startswith('2000')

    def it_escapes_html_characters_in_the_body(self):
        self.post('/api/v1/games', {'game': {**GAME, 'player_x': 'Tom & <Jerry>'}})

        assert b'"Tom \\u0026 \\u003cJerry\\u003e"' in self.response.data
        assert self.json()['player_x'] == 'Tom & <Jerry>'

    def it_answers_422_when_a_player_is_blank(self):
        self.post('/api/v1/games', {'game': {**GAME, 'player_x': '', 'player_o': None}})

        assert self.response.status_code == 422
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert self.json() == {'player_x': ["can't be blank"], 'player_o': ["can't be blank"]}
        assert len(Game.all()) == 3

    def it_answers_422_when_a_mark_is_unknown(self):
        self.post('/api/v1/games', {'game': {**GAME, 'winner': 'Ann', 'first_player': 'o'}})

        assert self.response.status_code == 422
        assert self.json() == {
            'winner': ['is not included in the list'],
            'first_player': ['is not included in the list'],
        }
        assert self.post('/api/v1/games', {'game': {**GAME, 'first_player': None}}).status_code == 422
        assert len(Game.all()) == 3

    def it_answers_422_when_the_moves_are_not_squares(self):
        moves_that_are_not_a_game = [
            None,
            [],
            '[0,3,1,4,2]',
            5,
            {'0': 0},
            [[0, 3, 1, 4, 2]],
            [{'square': 0}],
            [0, 3, 1, 4, 9],
            [0, 3, 1, 4, -1],
            [0, 3, 1, 4, 0],
            [0, 3, 1, 4, '2'],
            [0, 3, 1, 4, 2.5],
            [0, 3, 1, 4, None],
            [True, False],
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 0],
        ]
        for moves in moves_that_are_not_a_game:
            self.post('/api/v1/games', {'game': {**GAME, 'moves': moves}})

            assert self.response.status_code == 422, moves
            assert self.json() == {'moves': [INVALID_MOVES]}
        self.post('/api/v1/games', {'game': {name: value for name, value in GAME.items() if name != 'moves'}})

        assert self.response.status_code == 422
        assert len(Game.all()) == 3

    def it_answers_422_for_moves_sent_as_form_fields(self):
        # Form fields are text: the squares have to be sent as JSON numbers.
        self.post('/api/v1/games', data='game[player_x]=Bob&game[player_o]=Ann&game[first_player]=X&game[moves][]=4')

        assert self.response.status_code == 422
        assert self.json() == {'moves': [INVALID_MOVES]}

    def it_answers_400_when_the_game_is_missing(self):
        for params in ({}, {'foo': 1}, {'game': {}}, {'game': None}, {'game': ''}):
            assert self.post('/api/v1/games', params).status_code == 400
        assert self.post('/api/v1/games').status_code == 400
        assert self.json() == {**self.json(), 'status': 400, 'error': 'Bad Request'}
        assert len(Game.all()) == 3

    def it_answers_400_when_the_body_is_not_valid_json(self):
        self.post('/api/v1/games', data='{"game":{"moves":[0,', content_type='application/json')

        assert self.response.status_code == 400
        assert len(Game.all()) == 3


class DescribeRouting(RequestSpec):
    def it_answers_404_for_anything_that_is_not_routed(self):
        game_id = self.games[0].id
        requests = [
            ('GET', '/api/v1/games/%d' % game_id),
            ('PUT', '/api/v1/games/%d' % game_id),
            ('PATCH', '/api/v1/games/%d' % game_id),
            ('DELETE', '/api/v1/games/%d' % game_id),
            ('PUT', '/api/v1/games'),
            ('DELETE', '/api/v1/games'),
            ('GET', '/games'),
        ]
        for method, path in requests:
            assert self.request(method, path).status_code == 404, '%s %s' % (method, path)
        assert len(Game.all()) == 3

    def it_answers_head_with_the_headers_only(self):
        self.request('HEAD', '/api/v1/games')

        assert self.response.status_code == 200
        assert self.response.data == b''

    def it_leaves_the_players_routes_alone(self):
        assert self.get('/api/v1/players').status_code == 200
        assert self.post('/api/v1/players', {'player': {'name': 'Tester1'}}).status_code == 201


class DescribeDevelopmentDatabase(RequestSpec):
    """The database file committed in db/development.sqlite3 has the games table."""

    @pytest.fixture(autouse=True)
    def before(self, client, tmp_path):
        self.client = client
        configuration = Rails.application.database_configuration()['development']
        database = tmp_path / 'development.sqlite3'
        shutil.copyfile(configuration['database'], database)
        ActiveRecord.Base.establish_connection({**configuration, 'database': str(database)})

    def it_lists_and_saves_games(self):
        # Whatever the file holds right now: a game is added every time one is finished.
        listed = self.get('/api/v1/games?limit=100').get_json()
        created = self.post('/api/v1/games', {'game': GAME}).get_json()

        assert self.response.status_code == 201
        assert [list(game) for game in listed] == [ATTRIBUTES] * len(listed)
        assert self.get('/api/v1/games?limit=100').get_json()[0] == created
