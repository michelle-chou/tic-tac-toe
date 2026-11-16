"""Framework layer of the backend.

The application code under app/, config/ and db/ is written against these modules:

    ActiveSupport     blank/present, inflections and JSON encoding
    ActiveRecord      models, validations and schema statements on top of sqlite3
    ActionDispatch    routing (match / namespace / resources) on top of Flask URL rules
    ActionController  controllers: params, before_action and render
    Rails             the application object, its environment and its boot sequence
"""

from lib import active_support as ActiveSupport  # noqa: F401
from lib import active_record as ActiveRecord  # noqa: F401
from lib import action_dispatch as ActionDispatch  # noqa: F401
from lib import action_controller as ActionController  # noqa: F401
from lib import rails as Rails  # noqa: F401
