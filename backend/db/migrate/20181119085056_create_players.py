from lib import ActiveRecord


class CreatePlayers(ActiveRecord.Migration[5.2]):
    def change(self):
        with self.create_table("players") as t:
            t.string("name")
            t.integer("wins", default=0)
            t.integer("losses", default=0)
            t.integer("draws", default=0)

            t.timestamps()
