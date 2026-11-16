from lib import ActiveRecord


class CreateGames(ActiveRecord.Migration[5.2]):
    def change(self):
        with self.create_table("games") as t:
            t.string("player_x")
            t.string("player_o")
            t.string("winner")
            t.string("first_player")
            t.json("moves")
            t.datetime("created_at", null=False)
