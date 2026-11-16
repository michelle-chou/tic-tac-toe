import json as JSON
import re
import shutil
from datetime import datetime, timezone

import pytest

from spec import rails_helper  # noqa: F401
from app.models.player import Player
from lib import ActiveRecord, Rails
from spec.factories.players import PlayerFactory
from spec.support.request_spec_helper import RequestSpecHelper

ATTRIBUTES = ['id', 'name', 'wins', 'losses', 'draws', 'created_at', 'updated_at']
JSON_CONTENT_TYPE = 'application/json; charset=utf-8'
TIMESTAMP = re.compile(r'\A\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z\Z')
LONG_AGO = datetime(2020, 1, 2, 3, 4, 5, 678901, tzinfo=timezone.utc)


class RequestSpec(RequestSpecHelper):
    """Three saved players, and the HTTP verbs: each request stores its response in self.response."""

    @pytest.fixture(autouse=True)
    def before(self, client):
        self.client = client
        self.players = [PlayerFactory.create(created_at=LONG_AGO, updated_at=LONG_AGO) for _ in range(3)]
        self.player = self.players[0]
        self.player_id = self.player.id

    def request(self, method, path, params=None, **options):
        if params is not None:
            options.update(data=JSON.dumps(params), content_type='application/json;charset=utf-8')
        self.response = self.client.open(path, method=method, **options)
        return self.response

    def get(self, path, **options):
        return self.request('GET', path, **options)

    def post(self, path, params=None, **options):
        return self.request('POST', path, params, **options)

    def put(self, path, params=None, **options):
        return self.request('PUT', path, params, **options)

    def patch(self, path, params=None, **options):
        return self.request('PATCH', path, params, **options)

    def delete(self, path, **options):
        return self.request('DELETE', path, **options)


class DescribeGetPlayers(RequestSpec):
    def it_returns_every_player_in_id_order(self):
        self.get('/api/v1/players.json')

        assert self.response.status_code == 200
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert [player['id'] for player in self.json()] == [player.id for player in self.players]
        assert [list(player) for player in self.json()] == [ATTRIBUTES] * 3

    def it_serves_the_same_body_with_or_without_a_format_suffix(self):
        body = self.get('/api/v1/players.json').data

        assert self.get('/api/v1/players').data == body
        assert self.get('/api/v1/players.xml').data == body
        assert self.get('/api/v1/players/').data == body

    def it_returns_an_empty_array_when_there_are_no_players(self):
        for player in Player.all():
            player.destroy()

        assert self.get('/api/v1/players.json').data == b'[]'

    def it_answers_head_with_the_headers_only(self):
        self.request('HEAD', '/api/v1/players')

        assert self.response.status_code == 200
        assert self.response.data == b''


class DescribeGetPlayer(RequestSpec):
    def it_returns_the_player(self):
        self.get('/api/v1/players/%d' % self.player_id)

        assert self.response.status_code == 200
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert list(self.json()) == ATTRIBUTES
        assert self.json()['name'] == self.player.name
        assert self.json()['wins'] == self.player.wins

    def it_renders_compact_json_with_millisecond_utc_timestamps(self):
        self.get('/api/v1/players/%d.json' % self.player_id)

        assert self.json()['created_at'] == '2020-01-02T03:04:05.678Z'
        assert b', ' not in self.response.data and b'": ' not in self.response.data

    def it_answers_404_for_an_id_that_does_not_exist(self):
        for id in ('999999', 'abc', '0', '-1', '99999999999999999999', '9' * 5000):
            assert self.get('/api/v1/players/%s' % id).status_code == 404
        assert self.json() == {**self.json(), 'status': 404, 'error': 'Not Found'}

    def it_reads_the_leading_integer_of_the_id(self):
        self.get('/api/v1/players/%dabc' % self.player_id)

        assert self.response.status_code == 200
        assert self.json()['id'] == self.player_id


class DescribePostPlayers(RequestSpec):
    def it_creates_a_player(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1', 'wins': 1, 'losses': 0, 'draws': 0}})

        assert self.response.status_code == 201
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert self.response.headers['Location'] == 'http://localhost/api/v1/players/%d' % self.json()['id']
        assert list(self.json()) == ATTRIBUTES
        assert [self.json()[name] for name in ('name', 'wins', 'losses', 'draws')] == ['Tester1', 1, 0, 0]
        assert TIMESTAMP.match(self.json()['created_at'])
        assert self.json()['created_at'] == self.json()['updated_at']
        assert len(Player.all()) == 4

    def it_defaults_the_counters_to_zero(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}})

        assert [self.json()[name] for name in ('wins', 'losses', 'draws')] == [0, 0, 0]

    def it_accepts_the_attributes_without_the_player_root(self):
        self.post('/api/v1/players', {'name': 'Flat', 'wins': 2, 'result': 'win', 'foo': 1})

        assert self.response.status_code == 201
        assert [self.json()[name] for name in ('name', 'wins')] == ['Flat', 2]

    def it_ignores_attributes_that_are_not_permitted(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1', 'id': 999, 'created_at': '2000-01-01', 'foo': 1}})

        assert self.response.status_code == 201
        assert self.json()['id'] == self.players[-1].id + 1
        assert not self.json()['created_at'].startswith('2000')

    def it_casts_the_attributes(self):
        self.post('/api/v1/players', {'player': {'name': False, 'wins': '7', 'losses': 'abc', 'draws': 5.9}})

        assert [self.json()[name] for name in ('name', 'wins', 'losses', 'draws')] == ['f', 7, 0, 5]

    def it_stores_an_explicit_null_counter(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1', 'wins': None, 'losses': True}})

        assert [self.json()[name] for name in ('wins', 'losses', 'draws')] == [None, 1, 0]

    def it_accepts_duplicate_names_and_negative_counters(self):
        first = self.post('/api/v1/players', {'player': {'name': 'Twin', 'wins': -5}})
        second = self.post('/api/v1/players', {'player': {'name': 'Twin', 'wins': -5}})

        assert [first.status_code, second.status_code] == [201, 201]
        assert first.get_json()['id'] != second.get_json()['id']
        assert second.get_json()['wins'] == -5

    def it_accepts_form_encoded_parameters(self):
        self.post('/api/v1/players', data={'player[name]': 'Form', 'player[wins]': '3'})

        assert self.response.status_code == 201
        assert [self.json()[name] for name in ('name', 'wins')] == ['Form', 3]

    def it_escapes_html_characters_in_the_body(self):
        self.post('/api/v1/players', {'player': {'name': 'Tom & <Jerry>'}})

        assert b'"Tom \\u0026 \\u003cJerry\\u003e"' in self.response.data
        assert self.json()['name'] == 'Tom & <Jerry>'

    def it_answers_422_when_the_name_is_blank(self):
        for player in ({'wins': 1}, {'name': ''}, {'name': '   '}, {'name': None, 'wins': 1}, {'foo': 1}):
            self.post('/api/v1/players', {'player': player})

            assert self.response.status_code == 422
            assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
            assert self.response.data == b'{"name":["can\'t be blank"]}'
        assert len(Player.all()) == 3

    def it_answers_400_when_the_player_is_missing(self):
        for params in ({}, {'foo': 1}, {'result': 'win'}, {'player': {}}, {'player': None}, {'player': ''}):
            assert self.post('/api/v1/players', params).status_code == 400
        assert self.post('/api/v1/players').status_code == 400
        assert self.post('/api/v1/players', data={'name': 'Flat form'}).status_code == 400
        assert self.json() == {**self.json(), 'status': 400, 'error': 'Bad Request'}
        assert len(Player.all()) == 3

    def it_answers_400_when_the_body_is_not_valid_json(self):
        bodies = [
            '{bad',
            '{"player":{"name":"Tester1","wins":NaN}}',
            '{"player":{"name":Infinity}}',
            '{"player":{"name":"Tester1","wins":-Infinity}}',
            '[' * 100000,
        ]
        for body in bodies:
            self.post('/api/v1/players', data=body, content_type='application/json')

            assert self.response.status_code == 400
        assert len(Player.all()) == 3

    def it_reads_a_body_without_a_content_type_as_a_form(self):
        self.post('/api/v1/players', data='player[name]=NoType&player[wins]=4')

        assert self.response.status_code == 201
        assert [self.json()[name] for name in ('name', 'wins')] == ['NoType', 4]

    def it_answers_500_when_the_player_is_an_array_of_hashes(self):
        self.post('/api/v1/players?player[][name]=Tester1')

        assert self.response.status_code == 500
        assert len(Player.all()) == 3

    def it_answers_500_for_a_permitted_attribute_that_is_not_a_column(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1', 'result': 'win'}})

        assert self.response.status_code == 500
        assert len(Player.all()) == 3

    def it_answers_500_when_the_player_is_not_an_object(self):
        for player in ('abc', 5, True, [1]):
            assert self.post('/api/v1/players', {'player': player}).status_code == 500


class DescribePutPlayer(RequestSpec):
    def it_updates_the_player_and_renders_null(self):
        self.put('/api/v1/players/%d' % self.player_id, {'player': {'wins': 100, 'losses': 200, 'draws': 300}})

        assert self.response.status_code == 200
        assert self.response.headers['Content-Type'] == JSON_CONTENT_TYPE
        assert self.response.data == b'null'
        player = Player.find(self.player_id)
        assert [player.name, player.wins, player.losses, player.draws] == [self.player.name, 100, 200, 300]
        assert player.created_at == LONG_AGO
        assert player.updated_at > LONG_AGO

    def it_updates_with_patch_as_well(self):
        self.patch('/api/v1/players/%d.json' % self.player_id, {'player': {'name': 'Renamed'}})

        assert self.response.data == b'null'
        assert Player.find(self.player_id).name == 'Renamed'

    def it_accepts_the_attributes_without_the_player_root(self):
        self.put('/api/v1/players/%d' % self.player_id, {'wins': 321})

        assert self.response.data == b'null'
        assert Player.find(self.player_id).wins == 321

    def it_leaves_updated_at_alone_when_nothing_changes(self):
        self.put('/api/v1/players/%d' % self.player_id, {'player': {'wins': str(self.player.wins)}})

        assert self.response.status_code == 200
        assert Player.find(self.player_id).updated_at == LONG_AGO

    def it_leaves_the_other_players_alone(self):
        self.put('/api/v1/players/%d' % self.player_id, {'player': {'wins': 100}})

        assert Player.find(self.players[1].id).wins == self.players[1].wins

    def it_answers_500_when_the_name_is_blank(self):
        self.put('/api/v1/players/%d' % self.player_id, {'player': {'name': ''}})

        assert self.response.status_code == 500
        assert Player.find(self.player_id).name == self.player.name
        assert Player.find(self.player_id).updated_at == LONG_AGO

    def it_answers_404_for_an_id_that_does_not_exist(self):
        assert self.put('/api/v1/players/999999', {'player': {'wins': 1}}).status_code == 404
        assert self.put('/api/v1/players/999999').status_code == 404

    def it_answers_400_when_the_player_is_missing(self):
        assert self.put('/api/v1/players/%d' % self.player_id, {}).status_code == 400
        assert self.put('/api/v1/players/%d' % self.player_id).status_code == 400

    def it_answers_400_for_invalid_json_before_looking_up_the_player(self):
        self.put('/api/v1/players/999999', data='{bad', content_type='application/json')

        assert self.response.status_code == 400

    def it_takes_the_id_from_the_path(self):
        self.put('/api/v1/players/%d?id=%d' % (self.player_id, self.players[1].id), {'id': 999999, 'player': {'wins': 77}})

        assert Player.find(self.player_id).wins == 77


class DescribePutPlayers(RequestSpec):
    """PUT on the collection path is routed to the top-level PlayersController."""

    def it_answers_404_without_an_id(self):
        self.put('/api/v1/players', {'player': {'wins': 100}})

        assert self.response.status_code == 404
        assert Player.find(self.player_id).wins == self.player.wins

    def it_updates_and_renders_the_player_when_given_an_id(self):
        self.put('/api/v1/players?id=%d' % self.player_id, {'player': {'wins': 100}})

        assert self.response.status_code == 200
        assert list(self.json()) == ATTRIBUTES
        assert [self.json()['id'], self.json()['wins']] == [self.player_id, 100]

    def it_takes_the_id_from_the_body_too(self):
        self.put('/api/v1/players.json', {'id': self.player_id, 'wins': 55})

        assert [self.response.status_code, self.json()['wins']] == [200, 55]

    def it_answers_422_when_the_name_is_blank(self):
        self.put('/api/v1/players?id=%d' % self.player_id, {'player': {'name': ''}})

        assert self.response.status_code == 422
        assert self.json() == {'name': ["can't be blank"]}

    def it_answers_500_for_a_permitted_attribute_that_is_not_a_column(self):
        self.put('/api/v1/players?id=%d' % self.player_id, {'player': {'slug': 'x'}})

        assert self.response.status_code == 500


class DescribeDeletePlayer(RequestSpec):
    def it_deletes_the_player(self):
        self.delete('/api/v1/players/%d' % self.player_id)

        assert self.response.status_code == 204
        assert self.response.data == b''
        assert 'Content-Type' not in self.response.headers
        assert [player.id for player in Player.all()] == [player.id for player in self.players[1:]]

    def it_answers_404_once_the_player_is_gone(self):
        self.delete('/api/v1/players/%d' % self.player_id)

        assert self.get('/api/v1/players/%d' % self.player_id).status_code == 404
        assert self.delete('/api/v1/players/%d' % self.player_id).status_code == 404

    def it_never_reuses_an_id(self):
        last_id = self.players[-1].id
        self.delete('/api/v1/players/%d' % last_id)
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}})

        assert self.json()['id'] == last_id + 1


class DescribeRouting(RequestSpec):
    def it_answers_404_for_anything_that_is_not_routed(self):
        requests = [
            ('DELETE', '/api/v1/players'),
            ('PATCH', '/api/v1/players'),
            ('POST', '/api/v1/players/%d' % self.player_id),
            ('GET', '/api/v1/players/new'),
            ('GET', '/api/v1/players/%d/edit' % self.player_id),
            ('GET', '/api/v1/players.json.bak'),
            ('GET', '/API/v1/players'),
            ('GET', '/'),
            ('GET', '/players'),
        ]
        for method, path in requests:
            assert self.request(method, path).status_code == 404, '%s %s' % (method, path)

    def it_names_the_member_route(self):
        with Rails.application.test_request_context('/', base_url='http://example.com:3001'):
            helpers = Rails.application.routes.url_helpers

            assert helpers['api_v1_player_url'](self.player) == 'http://example.com:3001/api/v1/players/%d' % self.player_id
            assert helpers['api_v1_players_path']() == '/api/v1/players'

    def it_serves_paths_with_repeated_slashes(self):
        assert self.get('/api//v1/players').status_code == 200
        assert self.get('/api/v1/players//%d//' % self.player_id).get_json()['id'] == self.player_id
        assert self.put('/api/v1//players//%d' % self.player_id, {'player': {'wins': 100}}).data == b'null'
        assert Player.find(self.player_id).wins == 100

    def it_builds_the_location_from_the_forwarded_host(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}}, headers={'X-Forwarded-Host': 'localhost:3000'})

        assert self.response.headers['Location'].startswith('http://localhost:3000/api/v1/players/')

    def it_uses_https_in_the_location_behind_a_tls_proxy(self):
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}}, headers={'X-Forwarded-Proto': 'https'})

        assert self.response.headers['Location'].startswith('https://localhost/api/v1/players/')

    def it_takes_nothing_else_from_the_forwarded_headers(self):
        headers = {'X-Forwarded-Host': 'example.com', 'X-Forwarded-Port': '8080', 'X-Forwarded-Proto': 'javascript'}
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}}, headers=headers)

        assert self.response.headers['Location'].startswith('http://example.com/api/v1/players/')


class DescribeCors(RequestSpec):
    def it_allows_any_origin(self):
        self.get('/api/v1/players', headers={'Origin': 'http://localhost:3000'})

        assert self.response.headers['Access-Control-Allow-Origin'] == '*'
        exposed = self.response.headers['Access-Control-Expose-Headers'].split(', ')
        assert sorted(exposed) == ['access-token', 'client', 'expiry', 'token-type', 'uid']

    def it_answers_preflight_requests(self):
        headers = {
            'Origin': 'http://localhost:3000',
            'Access-Control-Request-Method': 'PUT',
            'Access-Control-Request-Headers': 'content-type',
        }
        self.request('OPTIONS', '/api/v1/players/%d' % self.player_id, headers=headers)

        assert self.response.status_code == 200
        assert self.response.headers['Access-Control-Allow-Origin'] == '*'
        allowed = self.response.headers['Access-Control-Allow-Methods'].split(', ')
        assert sorted(allowed) == ['DELETE', 'GET', 'HEAD', 'OPTIONS', 'PATCH', 'POST', 'PUT']
        assert self.response.headers['Access-Control-Allow-Headers'] == 'content-type'
        assert self.response.headers['Access-Control-Max-Age'] == '0'


class DescribeDevelopmentDatabase(RequestSpec):
    """The database file committed in db/development.sqlite3 is served as it is."""

    @pytest.fixture(autouse=True)
    def before(self, client, tmp_path):
        self.client = client
        configuration = Rails.application.database_configuration()['development']
        database = tmp_path / 'development.sqlite3'
        shutil.copyfile(configuration['database'], database)
        ActiveRecord.Base.establish_connection({**configuration, 'database': str(database)})

    def it_reads_the_existing_players(self):
        self.get('/api/v1/players.json')

        # Whatever the file holds right now: the scores change with every game that is played.
        assert self.response.status_code == 200
        assert [list(player) for player in self.json()] == [ATTRIBUTES] * len(self.json())
        assert [player['id'] for player in self.json()] == sorted(player['id'] for player in self.json())
        for player in self.json():
            assert TIMESTAMP.match(player['created_at']) and TIMESTAMP.match(player['updated_at'])

    def it_continues_the_existing_id_sequence(self):
        last_id = max([player['id'] for player in self.get('/api/v1/players.json').get_json()], default=0)
        self.post('/api/v1/players', {'player': {'name': 'Tester1'}})

        assert self.json()['id'] > last_id


class DescribeStoredTimestamps(RequestSpec):
    """Times are stored as UTC text, 'YYYY-MM-DD HH:MM:SS' with an optional six-digit fraction."""

    def it_renders_rows_stored_with_and_without_a_fraction(self):
        ActiveRecord.Base.execute(
            'INSERT INTO "players" ("name", "wins", "losses", "draws", "created_at", "updated_at") '
            'VALUES (?, ?, ?, ?, ?, ?)',
            ['Stored', 5, 2, 0, '2021-12-28 18:47:06.265999', '2021-12-28 18:47:13'],
        )
        self.get('/api/v1/players.json')

        assert self.json()[-1]['name'] == 'Stored'
        assert self.json()[-1]['created_at'] == '2021-12-28T18:47:06.265Z'
        assert self.json()[-1]['updated_at'] == '2021-12-28T18:47:13.000Z'

    def it_writes_the_same_format(self):
        self.put('/api/v1/players/%d' % self.player_id, {'player': {'wins': 100}})
        rows, _ = ActiveRecord.Base.execute(
            'SELECT "created_at", "updated_at", typeof("updated_at") AS "type" FROM "players" WHERE "id" = ?',
            [self.player_id],
        )

        assert rows[0]['created_at'] == '2020-01-02 03:04:05.678901'
        assert re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(\.\d{6})?', rows[0]['updated_at'])
        assert rows[0]['type'] == 'text'
