from app.models.application_record import ApplicationRecord


class Player(ApplicationRecord):
    validates_presence_of('name')
