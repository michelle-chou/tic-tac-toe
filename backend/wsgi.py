# This file is used by WSGI servers and by the `flask` command to start the application.

from config import environment  # noqa: F401
from lib import Rails

application = Rails.application
