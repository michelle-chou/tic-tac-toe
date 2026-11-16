# This file describes the current state of the database. `flask db setup` and
# `flask db schema:load` build the database from it.
#
# Note that this schema.py definition is the authoritative source for your
# database schema. If you need to create the application database on another
# system, you should be using `flask db schema:load`, not running all the migrations
# from scratch. The latter is a flawed and unsustainable approach (the more migrations
# you'll amass, the slower it'll run and the greater likelihood for issues).
#
# It's strongly recommended that you check this file into your version control system.

from lib import ActiveRecord

with ActiveRecord.Schema.define(version=2026_11_16_120000) as schema:

    with schema.create_table("games", force="cascade") as t:
        t.string("player_x")
        t.string("player_o")
        t.string("winner")
        t.string("first_player")
        t.json("moves")
        t.datetime("created_at", null=False)

    with schema.create_table("players", force="cascade") as t:
        t.string("name")
        t.integer("wins", default=0)
        t.integer("losses", default=0)
        t.integer("draws", default=0)
        t.datetime("created_at", null=False)
        t.datetime("updated_at", null=False)
