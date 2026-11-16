# pytest loads this file by itself; it makes the fixtures of rails_helper available to every spec.
from spec.rails_helper import client, use_transactional_fixtures  # noqa: F401
