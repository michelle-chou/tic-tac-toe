import pytest

from spec import rails_helper  # noqa: F401
from spec.factories.players import PlayerFactory


# Test suite for the Item model
class DescribePlayer:
    @pytest.fixture(autouse=True)
    def before(self):
        self.player = PlayerFactory.build()

    @property
    def subject(self):
        return self.player

    def it_should_respond_to_name(self):
        assert hasattr(self.subject, 'name')

    def it_should_respond_to_wins(self):
        assert hasattr(self.subject, 'wins')

    def it_should_respond_to_losses(self):
        assert hasattr(self.subject, 'losses')

    def it_should_respond_to_draws(self):
        assert hasattr(self.subject, 'draws')

    def it_should_be_valid(self):
        assert self.subject.valid()

    class DescribeTestNoName:
        def it_has_no_name(self):
            assert not PlayerFactory.build(name=None).valid()
