import factory

from app.models.game import Game


class GameFactory(factory.Factory):
    """A game X starts and wins on the top row."""

    class Meta:
        model = Game

    player_x = factory.Faker('first_name')
    player_o = factory.Faker('first_name')
    winner = 'X'
    first_player = 'X'
    moves = factory.LazyFunction(lambda: [0, 3, 1, 4, 2])

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # GameFactory.create() saves the game; GameFactory.build() only instantiates it.
        return model_class.create(*args, **kwargs)
