from lib import Rails

with Rails.application.configure() as config:
    # Settings specified here will take precedence over those in config/application.py.

    # The test environment is used exclusively to run your application's
    # test suite. You never need to work with it otherwise. Remember that
    # your test database is "scratch space" for the test suite.

    # Show full error reports.
    config.consider_all_requests_local = True
