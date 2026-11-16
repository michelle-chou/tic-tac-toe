import sqlite3
from contextlib import closing

import pytest

from spec import rails_helper  # noqa: F401
from lib import ActiveRecord, Rails

PLAYERS = (
    'CREATE TABLE "players" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "name" varchar, '
    '"wins" integer DEFAULT 0, "losses" integer DEFAULT 0, "draws" integer DEFAULT 0, '
    '"created_at" datetime NOT NULL, "updated_at" datetime NOT NULL)'
)
GAMES = (
    'CREATE TABLE "games" ("id" integer PRIMARY KEY AUTOINCREMENT NOT NULL, "player_x" varchar, '
    '"player_o" varchar, "winner" varchar, "first_player" varchar, "moves" json, "created_at" datetime NOT NULL)'
)
VERSIONS = [('20181119085056',), ('20261116120000',)]
SEEDS = [
    (1, 'Jeff Bezos', 5, 2, 0),
    (2, 'Bill Gates', 1, 8, 3),
    (3, 'Justin Trudeau', 42, 12, 10),
    (4, 'Stephen Harper', 25, 22, 10),
    (5, 'Elon Musk', 11, 3, 9),
]


class DescribeDatabaseTasks:
    """`flask db ...`, run in development against scratch database files."""

    @pytest.fixture(autouse=True)
    def before(self, tmp_path, monkeypatch):
        (tmp_path / 'scratch').mkdir()
        self.databases = {
            environment: str(tmp_path / 'scratch' / ('%s.sqlite3' % environment))
            for environment in ('development', 'test', 'production')
        }
        configurations = {
            environment: {'adapter': 'sqlite3', 'timeout': 5000, 'database': database}
            for environment, database in self.databases.items()
        }
        monkeypatch.setattr(Rails.application, 'database_configuration', lambda: configurations)
        monkeypatch.delenv('DISABLE_DATABASE_ENVIRONMENT_CHECK', raising=False)
        self.boot(monkeypatch, 'development')
        self.runner = Rails.application.test_cli_runner()

    def boot(self, monkeypatch, environment):
        # What starting `flask` with RAILS_ENV set does: connect to that environment's database.
        monkeypatch.setenv('RAILS_ENV', environment)
        ActiveRecord.Base.establish_connection(Rails.application.database_configuration()[environment])

    def invoke(self, *args):
        return self.runner.invoke(args=['db', *args])

    def query(self, environment, sql):
        with closing(sqlite3.connect(self.databases[environment])) as connection:
            return connection.execute(sql).fetchall()

    def count(self, environment):
        return self.query(environment, 'SELECT count(*) FROM "players"')[0][0]

    def versions(self, environment):
        return self.query(environment, 'SELECT "version" FROM "schema_migrations" ORDER BY "version"')

    def it_sets_up_the_development_and_the_test_database(self):
        result = self.invoke('setup')

        assert result.exit_code == 0
        assert self.query('development', 'SELECT "id", "name", "wins", "losses", "draws" FROM "players"') == SEEDS
        assert self.count('test') == 0
        for environment in ('development', 'test'):
            assert self.query(environment, "SELECT sql FROM sqlite_master WHERE name = 'players'") == [(PLAYERS,)]
            assert self.query(environment, "SELECT sql FROM sqlite_master WHERE name = 'games'") == [(GAMES,)]
            assert self.query(environment, 'SELECT count(*) FROM "games"') == [(0,)]
            assert self.versions(environment) == VERSIONS
            assert self.query(environment, 'SELECT "key", "value" FROM "ar_internal_metadata"') == [
                ('environment', environment),
            ]

    def it_has_nothing_to_migrate_after_a_setup(self):
        self.invoke('setup')
        result = self.invoke('migrate')

        assert result.exit_code == 0
        assert result.output == ''
        assert self.count('development') == 5

    def it_appends_the_seeds_every_time_they_are_loaded(self):
        self.invoke('setup')
        result = self.invoke('seed')

        assert result.exit_code == 0
        assert self.count('development') == 10
        assert self.count('test') == 0

    def it_drops_the_existing_rows_when_the_schema_is_loaded(self):
        self.invoke('setup')
        result = self.invoke('schema:load')

        assert result.exit_code == 0
        assert self.count('development') == 0

    def it_migrates_a_new_database_once(self):
        first = self.invoke('migrate')
        second = self.invoke('migrate')

        assert first.exit_code == 0
        assert 'CreatePlayers: migrated' in first.output
        assert 'CreateGames: migrated' in first.output
        assert second.exit_code == 0
        assert second.output == ''
        assert self.query('development', "SELECT sql FROM sqlite_master WHERE name = 'players'") == [(PLAYERS,)]
        assert self.query('development', "SELECT sql FROM sqlite_master WHERE name = 'games'") == [(GAMES,)]
        assert self.versions('development') == VERSIONS
        assert self.query('test', 'SELECT name FROM sqlite_master') == []

    def it_adds_the_games_table_to_a_database_that_has_the_players(self):
        self.invoke('setup')
        with closing(sqlite3.connect(self.databases['development'])) as connection, connection:
            connection.execute('DROP TABLE "games"')
            connection.execute('DELETE FROM "schema_migrations" WHERE "version" = ?', ['20261116120000'])
        result = self.invoke('migrate')

        assert result.exit_code == 0
        assert 'CreatePlayers' not in result.output
        assert 'CreateGames: migrated' in result.output
        assert self.query('development', "SELECT sql FROM sqlite_master WHERE name = 'games'") == [(GAMES,)]
        assert self.versions('development') == VERSIONS
        assert self.count('development') == 5

    def it_applies_a_migration_completely_or_not_at_all(self, tmp_path, monkeypatch):
        migrations = tmp_path / 'db' / 'migrate'
        migrations.mkdir(parents=True)
        (migrations / '20200101000000_create_things.py').write_text(
            'from lib import ActiveRecord\n'
            '\n'
            '\n'
            'class CreateThings(ActiveRecord.Migration[5.2]):\n'
            '    def change(self):\n'
            '        with self.create_table("things") as t:\n'
            '            t.string("name")\n'
            '        with self.create_table("things") as t:\n'
            '            t.string("name")\n'
        )
        monkeypatch.setattr(Rails, 'root', tmp_path)
        result = self.invoke('migrate')

        assert result.exit_code != 0
        assert self.query('development', "SELECT name FROM sqlite_master WHERE name = 'things'") == []
        assert self.query('development', 'SELECT "version" FROM "schema_migrations"') == []

    def it_refuses_to_rebuild_a_production_database(self, monkeypatch):
        self.boot(monkeypatch, 'production')
        assert self.invoke('setup').exit_code == 0
        result = self.invoke('schema:load')

        assert result.exit_code != 0
        assert 'DISABLE_DATABASE_ENVIRONMENT_CHECK' in result.output
        assert self.count('production') == 5

        monkeypatch.setenv('DISABLE_DATABASE_ENVIRONMENT_CHECK', '1')
        assert self.invoke('schema:load').exit_code == 0
        assert self.count('production') == 0
