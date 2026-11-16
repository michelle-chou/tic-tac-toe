"""Database tasks, run from the backend directory as `flask db <task>`:

    flask db create        create the database files
    flask db schema:load   rebuild the tables from db/schema.py (existing rows are dropped)
    flask db seed          load db/seeds.py
    flask db setup         create, schema:load, then seed
    flask db migrate       run the migrations in db/migrate that have not been applied yet
"""

import os
import runpy

import click
from flask.cli import AppGroup

from lib import ActiveRecord, ActiveSupport, Rails

db = AppGroup('db', help='Create, load, migrate and seed the database.')


def each_current_configuration():
    """Connect to the current environment's database, then to the test one when in development."""
    configurations = Rails.application.database_configuration()
    environments = [Rails.env] + (['test'] if Rails.env == 'development' else [])
    try:
        for environment in environments:
            ActiveRecord.Base.establish_connection(configurations[environment])
            yield environment
    finally:
        ActiveRecord.Base.establish_connection(configurations[Rails.env])


def create_current():
    for environment in each_current_configuration():
        ActiveRecord.Base.connection().close()


def check_protected_environments():
    """Refuse to rebuild a database that is marked as the production one."""
    if os.environ.get('DISABLE_DATABASE_ENVIRONMENT_CHECK'):
        return
    if ActiveRecord.InternalMetadata.get('environment') == 'production':
        raise click.ClickException(
            "You are attempting to run a destructive action against your 'production' database.\n"
            'If you are sure you want to continue, run the same command with the environment variable:\n'
            'DISABLE_DATABASE_ENVIRONMENT_CHECK=1'
        )


def migrations():
    """The migrations in db/migrate, oldest first, as (version, class name, path)."""
    found = []
    for path in sorted((Rails.root / 'db' / 'migrate').glob('*.py')):
        version, _, name = path.stem.partition('_')
        if version.isdigit():
            found.append((version, ActiveSupport.camelize(name), path))
    return found


def load_schema_current():
    for environment in each_current_configuration():
        schema = runpy.run_path(str(Rails.root / 'db' / 'schema.py'))['schema']
        # The schema already holds what the migrations up to its version create:
        # record them as applied, so that `flask db migrate` does not run them again.
        for version, _, _ in migrations():
            if schema.version is not None and int(version) <= schema.version:
                ActiveRecord.SchemaMigration.record(version)
        ActiveRecord.InternalMetadata.set('environment', environment)


def load_seed():
    runpy.run_path(str(Rails.root / 'db' / 'seeds.py'))


@db.command('create')
def create():
    """Create the database files."""
    create_current()


@db.command('schema:load')
def schema_load():
    """Rebuild the tables from db/schema.py. Existing rows are dropped."""
    check_protected_environments()
    load_schema_current()


@db.command('seed')
def seed():
    """Load the seed data from db/seeds.py."""
    load_seed()


@db.command('setup')
def setup():
    """Create the databases, load the schema, and load the seed data."""
    create_current()
    check_protected_environments()
    load_schema_current()
    load_seed()


@db.command('migrate')
def migrate():
    """Run the migrations in db/migrate that have not been applied yet."""
    ActiveRecord.SchemaMigration.create_table()
    ActiveRecord.InternalMetadata.create_table()
    migrated = ActiveRecord.SchemaMigration.all_versions()
    for version, name, path in migrations():
        if version in migrated:
            continue
        migration = runpy.run_path(str(path))[name]
        click.echo('== %s %s: migrating' % (version, migration.__name__))
        # A migration and the record of its version are applied together or not at all.
        with ActiveRecord.Base.transaction():
            migration().migrate()
            ActiveRecord.SchemaMigration.record(version)
        click.echo('== %s %s: migrated' % (version, migration.__name__))
    ActiveRecord.InternalMetadata.set('environment', Rails.env)


Rails.application.cli.add_command(db)
