# Load the application.
from config.application import RailsApi  # noqa: F401
from lib import Rails

# Initialize the application.
Rails.application.initialize()
