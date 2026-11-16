"""API controllers on top of Flask: request parameters, strong parameters, the JSON
params wrapper, before_action callbacks, render and the implicit 204 response."""

import importlib
import json as JSON
import re
from http import HTTPStatus
from urllib.parse import parse_qsl

import flask

from lib import active_support as ActiveSupport

JSON_MIME_TYPES = ('application/json', 'text/x-json', 'application/jsonrequest')
PERMITTED_SCALAR_TYPES = (str, int, float, bool, type(None))


class BadRequest(Exception):
    """The request body or query string could not be parsed. Answered with 400."""


class ParameterMissing(Exception):
    """A required parameter is absent or empty. Answered with 400."""

    def __init__(self, param):
        super().__init__('param is missing or the value is empty: %s' % param)
        self.param = param


class ActionNotFound(Exception):
    """A route points at an action the controller does not define. Answered with 404."""


class DoubleRenderError(Exception):
    """An action rendered more than once."""


def parse_nested_query(pairs):
    """Expand bracketed keys: player[name]=A becomes {'player': {'name': 'A'}}."""
    params = {}
    for name, value in pairs:
        _normalize_params(params, name, value)
    return params


def _normalize_params(params, name, value):
    match = re.match(r'[\[\]]*([^\[\]]+)\]*', name)
    if not match:
        return
    key, after = match.group(1), name[match.end():]
    if after == '':
        params[key] = value
    elif after == '[]':
        if not isinstance(params.setdefault(key, []), list):
            raise BadRequest('expected Array for param `%s`' % key)
        params[key].append(value)
    elif after.startswith('[]'):
        # key[][child]=value builds an array of hashes; a new hash starts when a child key repeats.
        child = re.fullmatch(r'\[\]\[([^\[\]]+)\]', after)
        child_key = child.group(1) if child else after[2:]
        if not isinstance(params.setdefault(key, []), list):
            raise BadRequest('expected Array for param `%s`' % key)
        last = params[key][-1] if params[key] else None
        if not isinstance(last, dict) or _params_hash_has_key(last, child_key):
            params[key].append({})
        _normalize_params(params[key][-1], child_key, value)
    else:
        if not isinstance(params.setdefault(key, {}), dict):
            raise BadRequest('expected Hash for param `%s`' % key)
        _normalize_params(params[key], after, value)


def _params_hash_has_key(params, key):
    if '[]' in key:
        return False
    for part in re.split(r'[\[\]]+', key):
        if part == '':
            continue
        if not isinstance(params, dict) or part not in params:
            return False
        params = params[part]
    return True


def _invalid_constant(name):
    # NaN, Infinity and -Infinity are not JSON.
    raise ValueError('unexpected token %s' % name)


class Parameters(dict):
    """Request parameters with require / permit. A missing key reads as None."""

    def __missing__(self, key):
        return None

    def require(self, key):
        value = self[key]
        if ActiveSupport.present(value) or value is False:
            return Parameters(value) if isinstance(value, dict) else value
        raise ParameterMissing(key)

    def permit(self, *filters):
        """Keep only the listed keys, and only when their value is a scalar.
        A filter written as {'moves': []} keeps the key when its value is an array of scalars."""
        permitted = Parameters()
        for filter in filters:
            if not isinstance(filter, dict):
                if filter in self and isinstance(self[filter], PERMITTED_SCALAR_TYPES):
                    permitted[filter] = self[filter]
                continue
            for key, shape in filter.items():
                if shape != []:
                    raise TypeError('permit takes names and {name: []} filters, not %r' % (filter,))
                value = self.get(key)
                if isinstance(value, list) and all(isinstance(item, PERMITTED_SCALAR_TYPES) for item in value):
                    permitted[key] = value
        return permitted


class ControllerBase(type):
    """Lets a controller declare callbacks in the class body: before_action('set_player', only=[...])."""

    @classmethod
    def __prepare__(mcs, name, bases, **kwargs):
        callbacks = [callback for base in bases for callback in getattr(base, '_before_actions', ())]

        def before_action(*names, only=None):
            callbacks.extend((name, only) for name in names)

        return {'_before_actions': callbacks, 'before_action': before_action}

    def __new__(mcs, name, bases, namespace, **kwargs):
        namespace = dict(namespace)
        namespace.pop('before_action', None)
        return super().__new__(mcs, name, bases, namespace, **kwargs)


class API(metaclass=ControllerBase):
    _wrapper_options = {'format': []}

    @classmethod
    def wrap_parameters(cls, format=()):
        """Wrap the attributes of a JSON body under the model's name: {"name": ...} -> {"player": {"name": ...}}."""
        cls._wrapper_options = {'format': list(format)}

    @classmethod
    def controller_path(cls):
        """app.controllers.api.v1.players_controller -> 'api/v1/players'"""
        path = cls.__module__.split('controllers.', 1)[-1]
        return re.sub(r'_controller\Z', '', path).replace('.', '/')

    @classmethod
    def action(cls, name):
        """An endpoint that runs one action of this controller for the current request."""

        def endpoint(**path_parameters):
            return cls().process(name, path_parameters)

        return endpoint

    def __getattr__(self, name):
        # Reached only for names that are not set. Route helpers such as api_v1_player_url can be
        # called from any action, and an instance variable that was never assigned reads as None.
        if name.startswith('_'):
            raise AttributeError(name)
        return flask.current_app.routes.url_helpers.get(name)

    # -- request processing ----------------------------------------------------------

    def process(self, action, path_parameters):
        if not callable(getattr(type(self), action, None)):
            raise ActionNotFound("The action '%s' could not be found for %s" % (action, type(self).__name__))
        self.action_name = action
        self.request = flask.request
        self.response = None
        self.params = self._parameters(path_parameters)
        for callback, only in self._before_actions:
            if self.response is None and (only is None or action in only):
                getattr(self, callback)()
        if self.response is None:
            getattr(self, action)()
        if self.response is None:
            # An action that renders nothing answers 204 No Content.
            self.head('no_content')
        return self.response

    def _parameters(self, path_parameters):
        """Body, query string and path parameters merged; later sources win."""
        request_parameters = self._request_parameters()
        parameters = dict(request_parameters)
        parameters.update(parse_nested_query(flask.request.args.items(multi=True)))
        parameters.update(path_parameters, controller=type(self).controller_path(), action=self.action_name)
        model = self._wrapper_model() if self._wrapper_enabled() else None
        if model is not None:
            key = ActiveSupport.underscore(model.__name__)
            if key not in parameters:
                names = model.attribute_names()
                parameters[key] = {name: value for name, value in request_parameters.items() if name in names}
        return Parameters(parameters)

    def _request_parameters(self):
        """The parameters carried by the request body: JSON or a form."""
        if flask.request.mimetype in JSON_MIME_TYPES:
            data = flask.request.get_data()
            if not data:
                return {}
            try:
                body = JSON.loads(data, parse_constant=_invalid_constant)
            except (ValueError, RecursionError) as error:
                raise BadRequest('Error occurred while parsing request parameters') from error
            return body if isinstance(body, dict) else {'_json': body}
        if flask.request.method == 'POST' and not flask.request.content_type:
            # A POST body that comes without a Content-Type is read as a form.
            pairs = parse_qsl(flask.request.get_data(as_text=True), keep_blank_values=True)
            return parse_nested_query(pairs)
        return parse_nested_query(flask.request.form.items(multi=True))

    def _wrapper_enabled(self):
        return (
            bool(flask.request.content_type)
            and 'json' in self._wrapper_options['format']
            and flask.request.mimetype in JSON_MIME_TYPES
        )

    @classmethod
    def _wrapper_model(cls):
        """The model a controller is named after: PlayersController -> Player. None if there is none."""
        name = ActiveSupport.singularize(cls.__name__.removesuffix('Controller'))
        try:
            module = importlib.import_module('app.models.' + ActiveSupport.underscore(name))
        except ImportError:
            return None
        return getattr(module, name, None)

    # -- rendering -------------------------------------------------------------------

    def render(self, *, json, status='ok', location=None):
        if self.response is not None:
            raise DoubleRenderError('Render was called multiple times in this action')
        response = flask.Response(
            ActiveSupport.to_json(json),
            status=_status_code(status),
            content_type='application/json; charset=utf-8',
        )
        if location is not None:
            response.headers['Location'] = location if isinstance(location, str) else self.url_for(location)
        self.response = response

    def head(self, status):
        response = flask.Response(status=_status_code(status))
        del response.headers['Content-Type']
        self.response = response

    def url_for(self, record):
        """The URL of a record, through the route helper named after its model: player_url."""
        name = ActiveSupport.underscore(type(record).__name__) + '_url'
        helper = flask.current_app.routes.url_helpers.get(name)
        if helper is None:
            raise AttributeError("undefined method '%s' for %s" % (name, type(self).__name__))
        return helper(record)


def _status_code(status):
    """'created' -> 201"""
    return status if isinstance(status, int) else HTTPStatus[status.upper()].value
