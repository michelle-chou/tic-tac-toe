from flask_cors import CORS

from lib import Rails

CORS(
    Rails.application,
    resources={
        r'/*': {
            'origins': '*',
            'allow_headers': '*',
            'methods': ['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS', 'HEAD'],
            'expose_headers': ['access-token', 'expiry', 'token-type', 'uid', 'client'],
            # Given as a string: flask-cors leaves the header out for a numeric 0.
            'max_age': '0',
            'send_wildcard': True,
            # Only requests that carry an Origin header get the CORS headers.
            'always_send': False,
        },
    },
)
