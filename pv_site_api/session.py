""" Get access to the database"""

from pvsite_datamodel.connection import DatabaseConnection


def create_session_dependency(db_url: str, *, is_fake: bool):
    """Return a fastAPI dependency function."""

    def get_session():
        if is_fake:
            yield None
        else:
            connection = DatabaseConnection(url=db_url)

            with connection.get_session() as s:
                yield s

    return get_session
