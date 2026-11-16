"""ActiveRecord-style models on top of the standard library's sqlite3 module.

Only what the application uses is implemented: columns read from the database at
runtime, attribute type casting, presence and custom validation, the
all / find / find_by_sql / new / create / save / update / destroy interface, JSON serialization, and
the schema statements behind db/schema.py and db/migrate.
"""

import json
import re
import sqlite3
import threading
from contextlib import closing, contextmanager
from datetime import datetime, timezone

from lib import active_support as ActiveSupport

ISO_DATETIME = re.compile(r'\A(\d{4})-(\d\d)-(\d\d)[ T](\d\d):(\d\d):(\d\d)(\.\d+)?Z?\Z')


class RecordNotFound(Exception):
    """Raised by find when the record does not exist. Answered with 404 Not Found."""


class UnknownAttributeError(AttributeError):
    """Raised when assigning an attribute the table has no column for."""


class ConnectionNotEstablished(Exception):
    """Raised when the database is used before establish_connection was called."""


class StatementInvalid(Exception):
    """Raised when a model's table does not exist."""


# -- attribute types -----------------------------------------------------------------


class Value:
    """A column whose values are stored and returned as they are."""

    def cast(self, value):
        return value

    def serialize(self, value):
        return value

    def deserialize(self, value):
        return self.cast(value)


class Integer(Value):
    def cast(self, value):
        if value is None:
            return None
        if value is True:
            return 1
        if value is False:
            return 0
        if isinstance(value, str):
            if ActiveSupport.blank(value):
                return None
            # The leading integer of the string; anything after it is ignored, 0 if there is none.
            match = re.match(r'[ \t\n\v\f\r]*([+-]?[0-9]+(?:_[0-9]+)*)', value)
            return int(match.group(1).replace('_', '')) if match else 0
        try:
            return int(value)  # floats are truncated toward zero
        except (TypeError, ValueError, OverflowError):
            return None


class String(Value):
    def cast(self, value):
        if value is None or isinstance(value, str):
            return value
        if value is True:
            return 't'
        if value is False:
            return 'f'
        return str(value)


class DateTime(Value):
    """Times are kept in UTC and stored as text: 'YYYY-MM-DD HH:MM:SS.ffffff'."""

    def cast(self, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        if isinstance(value, str):
            match = ISO_DATETIME.match(value)
            if match:
                parts = [int(part) for part in match.groups()[:6]]
                microsecond = int(((match.group(7) or '.')[1:] + '000000')[:6])
                try:
                    return datetime(*parts, microsecond, tzinfo=timezone.utc)
                except ValueError:
                    return None
        return None

    def serialize(self, value):
        if value is None:
            return None
        text = value.strftime('%Y-%m-%d %H:%M:%S')
        return text + ('.%06d' % value.microsecond if value.microsecond else '')


class Json(Value):
    """Lists and hashes, stored as JSON text and returned in the shape they were given."""

    def serialize(self, value):
        if value is None:
            return None
        return json.dumps(value, separators=(',', ':'))

    def deserialize(self, value):
        if not isinstance(value, str):
            return value
        try:
            return json.loads(value)
        except ValueError:
            return None


TYPES = {'integer': Integer(), 'varchar': String(), 'text': String(), 'datetime': DateTime(), 'json': Json()}


class Column:
    def __init__(self, name, sql_type, default):
        self.name = name
        self.type = TYPES.get(re.sub(r'\(.*\)', '', (sql_type or '').lower()).strip(), Value())
        if default is None or default.upper() == 'NULL':
            self.default = None
        else:
            self.default = self.type.cast(default.strip('\'"'))


# -- validation errors ---------------------------------------------------------------


class Errors(dict):
    """Validation errors of a record: attribute name -> list of messages."""

    MESSAGES = {'blank': "can't be blank", 'inclusion': 'is not included in the list'}

    def add(self, attribute, message):
        self.setdefault(attribute, []).append(self.MESSAGES.get(message, message))

    def as_json(self):
        return dict(self)


# -- models --------------------------------------------------------------------------


class ModelBase(type):
    """Lets a model declare its validations in the class body: validates_presence_of('name'),
    or validate('moves_are_squares') to run one of its own methods, which adds to record.errors."""

    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        validators = [validator for base in bases for validator in getattr(base, '_validators', ())]

        def validates_presence_of(*attr_names):
            def validate(record):
                for attr_name in attr_names:
                    if ActiveSupport.blank(getattr(record, attr_name)):
                        record.errors.add(attr_name, 'blank')

            validators.append(validate)

        def validate(*method_names):
            for method_name in method_names:
                validators.append(lambda record, method_name=method_name: getattr(record, method_name)())

        return {'_validators': validators, 'validates_presence_of': validates_presence_of, 'validate': validate}

    def __new__(mcs, name, bases, namespace, **kwargs):
        namespace = dict(namespace)
        namespace.pop('validates_presence_of', None)
        namespace.pop('validate', None)
        namespace.setdefault('abstract_class', False)
        return super().__new__(mcs, name, bases, namespace, **kwargs)


class Base(metaclass=ModelBase):
    abstract_class = True
    primary_key = 'id'

    _connection_config = None
    _schema_cache = {}
    _open_transaction = threading.local()

    # -- connection ------------------------------------------------------------------

    @classmethod
    def establish_connection(cls, config):
        """Use the database described by one entry of config/database.yml."""
        Base._connection_config = dict(config)
        Base._schema_cache.clear()

    @classmethod
    def connection(cls):
        """Open a connection to the configured database. The caller closes it."""
        config = Base._connection_config
        if config is None:
            raise ConnectionNotEstablished('No database configured; call establish_connection first')
        return sqlite3.connect(config['database'], timeout=config.get('timeout', 5000) / 1000)

    @classmethod
    def execute(cls, sql, binds=()):
        """Run one statement, in its own transaction unless one is open. Returns (rows as dicts, last insert id)."""
        connection = getattr(Base._open_transaction, 'connection', None)
        if connection is not None:
            return cls._run(connection, sql, binds)
        with closing(cls.connection()) as connection:
            with connection:
                return cls._run(connection, sql, binds)

    @staticmethod
    def _run(connection, sql, binds):
        cursor = connection.execute(sql, list(binds))
        names = [description[0] for description in cursor.description or ()]
        return [dict(zip(names, row)) for row in cursor.fetchall()], cursor.lastrowid

    @classmethod
    @contextmanager
    def transaction(cls):
        """Run the statements of the block on one connection: all of them are committed, or none is."""
        connection = cls.connection()
        connection.isolation_level = None  # explicit BEGIN and COMMIT, so that schema statements are covered too
        Base._open_transaction.connection = connection
        try:
            connection.execute('BEGIN')
            try:
                yield
            except BaseException:
                connection.execute('ROLLBACK')
                Base._schema_cache.clear()
                raise
            connection.execute('COMMIT')
        finally:
            Base._open_transaction.connection = None
            connection.close()

    # -- schema ----------------------------------------------------------------------

    @classmethod
    def table_name(cls):
        return ActiveSupport.pluralize(ActiveSupport.underscore(cls.__name__))

    @classmethod
    def columns(cls):
        """The table's columns, read from the database the first time they are needed."""
        table_name = cls.table_name()
        if table_name not in Base._schema_cache:
            rows, _ = cls.execute('PRAGMA table_info("%s")' % table_name)
            if not rows:
                raise StatementInvalid("Could not find table '%s'" % table_name)
            Base._schema_cache[table_name] = [Column(row['name'], row['type'], row['dflt_value']) for row in rows]
        return Base._schema_cache[table_name]

    @classmethod
    def columns_hash(cls):
        return {column.name: column for column in cls.columns()}

    @classmethod
    def attribute_names(cls):
        return [column.name for column in cls.columns()]

    # -- finders ---------------------------------------------------------------------

    @classmethod
    def all(cls):
        rows, _ = cls.execute('SELECT "%(table)s".* FROM "%(table)s"' % {'table': cls.table_name()})
        return [cls._instantiate(row) for row in rows]

    @classmethod
    def find_by_sql(cls, sql, binds=()):
        """The records returned by a SELECT on the model's table."""
        rows, _ = cls.execute(sql, binds)
        return [cls._instantiate(row) for row in rows]

    @classmethod
    def find(cls, id):
        if id is None:
            raise RecordNotFound("Couldn't find %s without an ID" % cls.__name__)
        try:
            value = cls.columns_hash()[cls.primary_key].type.cast(id)
        except ValueError:
            value = 2 ** 64  # more digits than can be converted: out of range like any other huge id
        if value is not None and not -2 ** 63 <= value < 2 ** 63:
            raise RecordNotFound("Couldn't find %s with an out of range value for '%s'" % (cls.__name__, cls.primary_key))
        rows, _ = cls.execute(
            'SELECT "%(table)s".* FROM "%(table)s" WHERE "%(table)s"."%(key)s" = ? LIMIT ?'
            % {'table': cls.table_name(), 'key': cls.primary_key},
            [value, 1],
        )
        if not rows:
            raise RecordNotFound("Couldn't find %s with '%s'=%s" % (cls.__name__, cls.primary_key, id))
        return cls._instantiate(rows[0])

    @classmethod
    def _instantiate(cls, row):
        """Build a record from a database row."""
        columns = cls.columns_hash()
        if not row.keys() <= columns.keys():
            # The table has changed since its columns were read: read them again.
            Base._schema_cache.pop(cls.table_name(), None)
            columns = cls.columns_hash()
        attributes = {name: columns[name].type.deserialize(value) for name, value in row.items()}
        record = cls.__new__(cls)
        record.__dict__.update(_attributes=attributes, _original=dict(attributes), _new_record=False, errors=Errors())
        return record

    # -- building --------------------------------------------------------------------

    def __init__(self, attributes=None, **kwargs):
        defaults = {column.name: column.default for column in type(self).columns()}
        self.__dict__.update(_attributes=defaults, _original={}, _new_record=True, errors=Errors())
        self.assign_attributes({**(attributes or {}), **kwargs})

    @classmethod
    def new(cls, attributes=None, **kwargs):
        return cls(attributes, **kwargs)

    @classmethod
    def create(cls, attributes=None, **kwargs):
        record = cls(attributes, **kwargs)
        record.save()
        return record

    # -- attributes ------------------------------------------------------------------

    def __getattr__(self, name):
        attributes = self.__dict__.get('_attributes', {})
        if name in attributes:
            return attributes[name]
        raise AttributeError("undefined attribute '%s' for %s" % (name, type(self).__name__))

    def __setattr__(self, name, value):
        attributes = self.__dict__.get('_attributes', {})
        if name in attributes:
            attributes[name] = type(self).columns_hash()[name].type.cast(value)
        else:
            object.__setattr__(self, name, value)

    def assign_attributes(self, new_attributes):
        for name, value in dict(new_attributes).items():
            if name not in self._attributes:
                raise UnknownAttributeError("unknown attribute '%s' for %s." % (name, type(self).__name__))
            setattr(self, name, value)

    def as_json(self):
        return dict(self._attributes)

    def __repr__(self):
        pairs = ', '.join('%s: %r' % pair for pair in self._attributes.items())
        return '#<%s %s>' % (type(self).__name__, pairs)

    # -- validation ------------------------------------------------------------------

    def valid(self):
        self.errors.clear()
        for validate in type(self)._validators:
            validate(self)
        return not self.errors

    # -- persistence -----------------------------------------------------------------

    def new_record(self):
        return self._new_record

    def save(self):
        """Insert or update the row. Returns False, writing nothing, when the record is invalid."""
        if not self.valid():
            return False
        if self._new_record:
            self._create_record()
        else:
            self._update_record()
        return True

    def update(self, attributes=None, **kwargs):
        self.assign_attributes({**(attributes or {}), **kwargs})
        return self.save()

    def destroy(self):
        if not self._new_record:
            type(self).execute(
                'DELETE FROM "%(table)s" WHERE "%(table)s"."%(key)s" = ?'
                % {'table': type(self).table_name(), 'key': self.primary_key},
                [self._original[self.primary_key]],
            )
        return self

    def _create_record(self):
        current_time = datetime.now(timezone.utc)
        for name in ('created_at', 'updated_at'):
            if name in self._attributes and self._attributes[name] is None:
                self._attributes[name] = current_time
        # The primary key is left to the database unless it was given explicitly.
        names = [name for name, value in self._attributes.items() if name != self.primary_key or value is not None]
        _, last_insert_id = type(self).execute(
            'INSERT INTO "%s" (%s) VALUES (%s)'
            % (type(self).table_name(), ', '.join('"%s"' % name for name in names), ', '.join('?' for _ in names)),
            self._serialize(names),
        )
        if self._attributes[self.primary_key] is None:
            self._attributes[self.primary_key] = last_insert_id
        self.__dict__.update(_new_record=False, _original=dict(self._attributes))

    def _update_record(self):
        # Only the attributes that changed are written; updated_at moves only when something did.
        names = [name for name, value in self._attributes.items() if value != self._original.get(name)]
        if names:
            if 'updated_at' in self._attributes and 'updated_at' not in names:
                self._attributes['updated_at'] = datetime.now(timezone.utc)
                names.append('updated_at')
            type(self).execute(
                'UPDATE "%(table)s" SET %(assignments)s WHERE "%(table)s"."%(key)s" = ?'
                % {
                    'table': type(self).table_name(),
                    'assignments': ', '.join('"%s" = ?' % name for name in names),
                    'key': self.primary_key,
                },
                self._serialize(names) + [self._original[self.primary_key]],
            )
        self.__dict__['_original'] = dict(self._attributes)

    def _serialize(self, names):
        columns = type(self).columns_hash()
        return [columns[name].type.serialize(self._attributes[name]) for name in names]


# -- schema statements ---------------------------------------------------------------


def _quote(value):
    if isinstance(value, bool):
        return '1' if value else '0'
    if isinstance(value, (int, float)):
        return str(value)
    return "'%s'" % str(value).replace("'", "''")


class TableDefinition:
    """The `t` of a create_table block. The table is created when the block ends."""

    def __init__(self, name):
        self.name = name
        self.columns = ['"id" integer PRIMARY KEY AUTOINCREMENT NOT NULL']

    def column(self, name, sql_type, **options):
        sql = '"%s" %s' % (name, sql_type)
        if options.get('default') is not None:
            sql += ' DEFAULT %s' % _quote(options['default'])
        if options.get('null') is False:
            sql += ' NOT NULL'
        self.columns.append(sql)

    def string(self, name, **options):
        self.column(name, 'varchar', **options)

    def integer(self, name, **options):
        self.column(name, 'integer', **options)

    def datetime(self, name, **options):
        self.column(name, 'datetime', **options)

    def json(self, name, **options):
        self.column(name, 'json', **options)

    def timestamps(self, **options):
        options.setdefault('null', False)
        self.datetime('created_at', **options)
        self.datetime('updated_at', **options)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            Base.execute('CREATE TABLE "%s" (%s)' % (self.name, ', '.join(self.columns)))
            Base._schema_cache.clear()


class SchemaStatements:
    def create_table(self, table_name, force=None):
        """Used as `with create_table("players") as t:`. With force, an existing table is dropped first."""
        if force:
            self.drop_table(table_name, if_exists=True)
        return TableDefinition(table_name)

    def drop_table(self, table_name, if_exists=False):
        Base.execute('DROP TABLE %s"%s"' % ('IF EXISTS ' if if_exists else '', table_name))
        Base._schema_cache.clear()


class SchemaMigration:
    """The schema_migrations table: one row per migration version that has been applied."""

    @staticmethod
    def create_table():
        Base.execute('CREATE TABLE IF NOT EXISTS "schema_migrations" ("version" varchar NOT NULL PRIMARY KEY)')

    @staticmethod
    def all_versions():
        rows, _ = Base.execute('SELECT "version" FROM "schema_migrations"')
        return {row['version'] for row in rows}

    @staticmethod
    def record(version):
        Base.execute('INSERT OR IGNORE INTO "schema_migrations" ("version") VALUES (?)', [str(version)])


class InternalMetadata:
    """The ar_internal_metadata table: remembers which environment the database belongs to."""

    @staticmethod
    def create_table():
        Base.execute(
            'CREATE TABLE IF NOT EXISTS "ar_internal_metadata" ("key" varchar NOT NULL PRIMARY KEY, '
            '"value" varchar, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL)'
        )

    @staticmethod
    def get(key):
        try:
            rows, _ = Base.execute('SELECT "value" FROM "ar_internal_metadata" WHERE "key" = ?', [key])
        except sqlite3.OperationalError:  # a new database does not have the table yet
            return None
        return rows[0]['value'] if rows else None

    @staticmethod
    def set(key, value):
        current_time = DateTime().serialize(datetime.now(timezone.utc))
        rows, _ = Base.execute('SELECT "value" FROM "ar_internal_metadata" WHERE "key" = ?', [key])
        if not rows:
            Base.execute(
                'INSERT INTO "ar_internal_metadata" ("key", "value", "created_at", "updated_at") VALUES (?, ?, ?, ?)',
                [key, value, current_time, current_time],
            )
        elif rows[0]['value'] != value:
            Base.execute(
                'UPDATE "ar_internal_metadata" SET "value" = ?, "updated_at" = ? WHERE "key" = ?',
                [value, current_time, key],
            )


class Schema(SchemaStatements):
    """db/schema.py: `with ActiveRecord.Schema.define(version=...) as schema:`"""

    def __init__(self, version=None):
        self.version = version

    @classmethod
    def define(cls, version=None):
        return cls(version)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            SchemaMigration.create_table()
            InternalMetadata.create_table()
            if self.version is not None:
                SchemaMigration.record(self.version)


class Migration(SchemaStatements):
    """Base class of the migrations in db/migrate. Subclasses implement change()."""

    def __class_getitem__(cls, version):
        # Migration[5.2] names the schema format the migration was written for.
        return cls

    def change(self):
        raise NotImplementedError

    def migrate(self):
        self.change()
