"""The application object: boots the environment, the initializers, the routes and the
database connection, and turns exceptions into the HTTP statuses the API answers with."""

import importlib
import os
import re
import traceback
from contextlib import contextmanager
from http import HTTPStatus
from pathlib import Path

import flask
import yaml
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from lib import action_controller as ActionController
from lib import action_dispatch as ActionDispatch
from lib import active_record as ActiveRecord
from lib import active_support as ActiveSupport

# The backend directory.
root = Path(__file__).resolve().parent.parent

_state = {'app_class': None, 'application': None}


def _env():
    return os.environ.get('RAILS_ENV') or 'development'


def __getattr__(name):
    # Rails.env and Rails.application are computed when they are read.
    if name == 'env':
        return _env()
    if name == 'application':
        if _state['application'] is None:
            if _state['app_class'] is None:
                raise RuntimeError('No application defined; import config.application first')
            _state['application'] = _state['app_class']()
        return _state['application']
    raise AttributeError('module %r has no attribute %r' % (__name__, name))


class NormalizePath:
    """Squeezes repeated slashes and drops trailing ones before the request is routed:
    /api//v1/players/ is served as /api/v1/players, without a redirect."""

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = re.sub(r'/{2,}', '/', '/' + environ.get('PATH_INFO', ''))
        environ['PATH_INFO'] = path.rstrip('/') or '/'
        return self.app(environ, start_response)


class Application(flask.Flask):
    # Exceptions that are answered with something other than 500 Internal Server Error.
    rescue_responses = {
        ActiveRecord.RecordNotFound: 404,
        ActionController.ActionNotFound: 404,
        ActionController.ParameterMissing: 400,
        ActionController.BadRequest: 400,
    }

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        _state['app_class'] = cls

    def __init__(self):
        # Files in public/ are served from the root of the site.
        super().__init__(type(self).__module__, root_path=str(root), static_folder=str(root / 'public'), static_url_path='')
        self.config.api_only = False
        self.config.consider_all_requests_local = False
        self.routes = ActionDispatch.RouteSet(self)
        self.url_map.strict_slashes = False
        self.url_map.converters['segment'] = ActionDispatch.Segment
        # Behind a proxy (the React dev server), URLs are built from the forwarded host and scheme.
        self.wsgi_app = NormalizePath(ProxyFix(self.wsgi_app, x_proto=1, x_host=1))
        self.register_error_handler(Exception, self.rescue)
        self._initialized = False

    @contextmanager
    def configure(self):
        yield self.config

    def database_configuration(self):
        """config/database.yml, with database paths made absolute."""
        with open(root / 'config' / 'database.yml', encoding='utf-8') as file:
            configurations = yaml.safe_load(file)
        for config in configurations.values():
            if 'database' in config:
                config['database'] = str(root / config['database'])
        return configurations

    def initialize(self):
        """Connect to the database, then load the environment, the initializers, the routes and the tasks."""
        if self._initialized:
            return self
        self._initialized = True
        ActiveRecord.Base.establish_connection(self.database_configuration()[_env()])
        importlib.import_module('config.environments.' + _env())
        for path in sorted((root / 'config' / 'initializers').glob('*.py')):
            if path.stem != '__init__':
                importlib.import_module('config.initializers.' + path.stem)
        importlib.import_module('config.routes')
        self.load_tasks()
        return self

    def load_tasks(self):
        """Load the command line tasks defined in lib/tasks."""
        for path in sorted((root / 'lib' / 'tasks').glob('*.py')):
            if path.stem != '__init__':
                importlib.import_module('lib.tasks.' + path.stem)

    def rescue(self, exception):
        """Answer an exception with a JSON error document."""
        if isinstance(exception, HTTPException):
            # The router has no 405: a known path with the wrong verb is a routing error like any other.
            status = 404 if exception.code == 405 else exception.code or 500
        else:
            status = next(
                (code for klass, code in self.rescue_responses.items() if isinstance(exception, klass)), 500
            )
        if status >= 500:
            self.logger.error('%s (%s)', type(exception).__name__, exception, exc_info=exception)
        body = {'status': status, 'error': HTTPStatus(status).phrase}
        if self.config.consider_all_requests_local:
            body['exception'] = '#<%s: %s>' % (type(exception).__name__, exception)
            body['traces'] = [line.rstrip('\n') for line in traceback.format_exception(exception)]
        return flask.Response(ActiveSupport.to_json(body), status=status, content_type='application/json; charset=utf-8')
