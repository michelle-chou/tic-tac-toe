import os
import shutil

import pytest

os.environ.setdefault('RAILS_ENV', 'test')
from config import environment  # noqa: E402,F401
from lib import ActiveRecord, Rails  # noqa: E402

# Prevent database truncation if the environment is production
if Rails.env == 'production':
    raise SystemExit('The Rails environment is running in production mode!')

# Add additional imports below this line. The application is not loaded until this point!

# Supporting files with custom helpers live in spec/support/.
from spec.support.request_spec_helper import RequestSpecHelper  # noqa: E402,F401


@pytest.fixture(autouse=True)
def use_transactional_fixtures(tmp_path):
    """Run each example against its own copy of the test database, so that nothing
    an example writes is visible to the next one or ends up in db/test.sqlite3."""
    configuration = Rails.application.database_configuration()[Rails.env]
    database = tmp_path / 'test.sqlite3'
    shutil.copyfile(configuration['database'], database)
    ActiveRecord.Base.establish_connection({**configuration, 'database': str(database)})
    yield
    ActiveRecord.Base.establish_connection(configuration)


@pytest.fixture
def client():
    return Rails.application.test_client()
