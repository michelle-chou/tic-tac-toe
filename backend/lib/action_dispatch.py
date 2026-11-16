"""Routing: the match / namespace / resources vocabulary of config/routes.py,
registered as Flask URL rules."""

import importlib
import re
from contextlib import contextmanager

import flask
from werkzeug.routing import BaseConverter

from lib import active_support as ActiveSupport


class Segment(BaseConverter):
    """A dynamic path segment (:id, :format): everything up to the next '.', '/' or '?'."""

    regex = r'[^./?]+'
    part_isolating = True


def _to_param(value):
    return str(getattr(value, 'id', value))


class RouteSet:
    def __init__(self, application):
        self.application = application
        self.named_routes = {}
        self.url_helpers = {}
        self._endpoints = {}

    @contextmanager
    def draw(self):
        yield Mapper(self)

    def add_route(self, path, controller, action, via, name=None):
        endpoint = '%s#%s' % (controller, action)
        if endpoint not in self._endpoints:
            self._endpoints[endpoint] = self._controller_class(controller).action(action)
        # Every route also matches with an optional format suffix: /players and /players.json
        for rule in (path, path + '.<segment:format>'):
            self.application.add_url_rule(
                rule,
                endpoint=endpoint,
                view_func=self._endpoints[endpoint],
                methods=[verb.upper() for verb in via],
            )
        if name and name not in self.named_routes:
            self._name_route(name, path)

    def _controller_class(self, controller):
        """'api/v1/players' -> app.controllers.api.v1.players_controller.PlayersController"""
        module = importlib.import_module('app.controllers.%s_controller' % controller.replace('/', '.'))
        return getattr(module, ActiveSupport.camelize(controller.split('/')[-1]) + 'Controller')

    def _name_route(self, name, path):
        """Define the <name>_path and <name>_url helpers of a named route."""

        def path_helper(*args):
            values = iter(args)
            return re.sub(r'<segment:\w+>', lambda _: _to_param(next(values)), path)

        def url_helper(*args):
            # The scheme is http or https, whatever a forwarded header claims.
            protocol = 'https://' if flask.request.scheme == 'https' else 'http://'
            return protocol + flask.request.host + path_helper(*args)

        self.named_routes[name] = path
        self.url_helpers[name + '_path'] = path_helper
        self.url_helpers[name + '_url'] = url_helper


class Mapper:
    def __init__(self, route_set):
        self.set = route_set
        self.scope = []

    def match(self, path, to=None, via=None):
        """match({'/path': 'controller#action'}, via='put')"""
        if isinstance(path, dict):
            (path, to), = path.items()
        controller, action = to.split('#')
        self._add(path, controller, action, [via] if isinstance(via, str) else via)

    @contextmanager
    def namespace(self, name):
        """Routes inside the block get the path, controller and helper-name prefix of the namespace."""
        self.scope.append(name)
        try:
            yield self
        finally:
            self.scope.pop()

    def resources(self, name):
        """The REST routes of a resource. An API-only application has no new and edit forms."""
        singular = ActiveSupport.singularize(name)
        collection = '/' + name
        member = collection + '/<segment:id>'
        self._add(collection, name, 'index', ['get'], as_=name)
        self._add(collection, name, 'create', ['post'])
        if not self.set.application.config.api_only:
            self._add(collection + '/new', name, 'new', ['get'], as_='new_' + singular)
            self._add(member + '/edit', name, 'edit', ['get'], as_='edit_' + singular)
        self._add(member, name, 'show', ['get'], as_=singular)
        self._add(member, name, 'update', ['patch'])
        self._add(member, name, 'update', ['put'])
        self._add(member, name, 'destroy', ['delete'])

    def _add(self, path, controller, action, via, as_=None):
        prefix = ''.join('/' + part for part in self.scope)
        name = '_'.join(self.scope + [as_]) if as_ else None
        self.set.add_route(prefix + path, '/'.join(self.scope + [controller]), action, via, name)
