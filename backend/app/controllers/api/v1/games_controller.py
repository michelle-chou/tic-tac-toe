from app.controllers.application_controller import ApplicationController
from app.models.game import Game

DEFAULT_LIMIT = 10
MAX_LIMIT = 100


class GamesController(ApplicationController):
    # GET /games?limit=10
    def index(self):
        self.games = Game.recent(self.limit())

        self.render(json=self.games)

    # POST /games
    def create(self):
        self.game = Game.new(self.game_params())

        if self.game.save():
            self.render(json=self.game, status='created')
        else:
            self.render(json=self.game.errors, status='unprocessable_entity')

    # private

    # How many games to list: the limit parameter, at most MAX_LIMIT.
    # DEFAULT_LIMIT when it is missing or not a positive number.
    def limit(self):
        try:
            limit = int(self.params['limit'])
        except (TypeError, ValueError, OverflowError):
            return DEFAULT_LIMIT
        return min(limit, MAX_LIMIT) if limit > 0 else DEFAULT_LIMIT

    # Only allow a trusted parameter "white list" through.
    def game_params(self):
        return self.params.require('game').permit('player_x', 'player_o', 'winner', 'first_player', {'moves': []})
