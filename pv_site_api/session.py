""" Get access to the database"""

import os

from pvsite_datamodel.connection import DatabaseConnection


def get_session():
    """Get database settion"""
    if int(os.environ.get("FAKE", 0)):
        yield None
    else:
        connection = DatabaseConnection(url=os.getenv("DB_URL", "not_set"))

        with connection.get_session() as s:
            yield s
