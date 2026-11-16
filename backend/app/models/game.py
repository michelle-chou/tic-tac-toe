from app.models.application_record import ApplicationRecord

MARKS = ('X', 'O')


class Game(ApplicationRecord):
    """A finished game. `moves` lists the squares (0 to 8) in the order they were taken, the two
    players taking turns from `first_player` on; `winner` is the winning mark, None for a draw."""

    validates_presence_of('player_x', 'player_o')
    validate('marks_are_known', 'moves_are_squares')

    @classmethod
    def recent(cls, limit):
        """The games that were saved last, newest first."""
        return cls.find_by_sql(
            'SELECT "games".* FROM "games" ORDER BY "games"."created_at" DESC, "games"."id" DESC LIMIT ?',
            [limit],
        )

    def marks_are_known(self):
        if self.winner is not None and self.winner not in MARKS:
            self.errors.add('winner', 'inclusion')
        if self.first_player not in MARKS:
            self.errors.add('first_player', 'inclusion')

    def moves_are_squares(self):
        moves = self.moves
        if (
            not isinstance(moves, list)
            or not 0 < len(moves) <= 9
            # True and False are integers too: only accept plain ones.
            or not all(type(move) is int and 0 <= move <= 8 for move in moves)
            or len(set(moves)) != len(moves)
        ):
            self.errors.add('moves', 'must be a list of different squares, numbered 0 to 8')
