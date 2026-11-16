from lib import Rails


class RailsApi:
    class Application(Rails.Application):
        def __init__(self):
            super().__init__()

            # Settings in config/environments/* take precedence over those specified here.
            # Application configuration can go into files in config/initializers
            # -- all .py files in that directory are automatically loaded after loading
            # the framework.

            # Only registers the routes suitable for API only apps:
            # resources have no new and edit forms.
            self.config.api_only = True
