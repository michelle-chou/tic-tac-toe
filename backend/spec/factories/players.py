import factory

from app.models.player import Player


class PlayerFactory(factory.Factory):
    class Meta:
        model = Player

    name = factory.Faker('first_name')
    wins = factory.Faker('random_number', digits=2)
    losses = factory.Faker('random_number', digits=2)
    draws = factory.Faker('random_number', digits=2)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # PlayerFactory.create() saves the player; PlayerFactory.build() only instantiates it.
        return model_class.create(*args, **kwargs)
