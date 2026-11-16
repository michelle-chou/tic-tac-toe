from lib import ActiveRecord


class ApplicationRecord(ActiveRecord.Base):
    abstract_class = True
