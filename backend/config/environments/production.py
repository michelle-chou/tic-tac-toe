from lib import Rails

with Rails.application.configure() as config:
    # Settings specified here will take precedence over those in config/application.py.

    # Full error reports are disabled.
    config.consider_all_requests_local = False
