# Be sure to restart your server when you modify this file.

# This file contains settings for the params wrapper of the controllers.

from lib import ActionController

# Enable parameter wrapping for JSON. You can disable this by setting format to an empty list.
ActionController.API.wrap_parameters(format=['json'])
