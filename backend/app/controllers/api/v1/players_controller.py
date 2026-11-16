from app.controllers.application_controller import ApplicationController
from app.models.player import Player


class PlayersController(ApplicationController):
    before_action('set_player', only=['show', 'update', 'destroy'])

    # GET /players
    def index(self):
        self.players = Player.all()

        self.render(json=self.players)

    # GET /players/1
    def show(self):
        self.render(json=self.player)

    # POST /players
    def create(self):
        self.player = Player.new(self.player_params())

        if self.player.save():
            self.render(json=self.player, status='created', location=self.api_v1_player_url(self.player))
        else:
            self.render(json=self.player.errors, status='unprocessable_entity')

    # PATCH/PUT /players/1
    def update(self):
        if self.player.update(self.player_params()):
            self.render(json=self.list)
        else:
            self.render(json=self.list.errors, status='unprocessable_entity')

    # DELETE /players/1
    def destroy(self):
        self.player.destroy()

    # private

    # Use callbacks to share common setup or constraints between actions.
    def set_player(self):
        self.player = Player.find(self.params['id'])

    # Only allow a trusted parameter "white list" through.
    def player_params(self):
        return self.params.require('player').permit('name', 'result', 'wins', 'losses', 'draws')
