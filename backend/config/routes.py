from lib import Rails

with Rails.application.routes.draw() as routes:
    routes.match({'/api/v1/players': 'players#update'}, via='put')
    with routes.namespace('api'):
        with routes.namespace('v1'):
            routes.match({'/players': 'players#create'}, via='post')

            routes.resources('players')

            routes.match({'/games': 'games#index'}, via='get')
            routes.match({'/games': 'games#create'}, via='post')
