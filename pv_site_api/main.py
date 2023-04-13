from .app import create_app
from .config import Config
from .session import create_session_dependency

config = Config()

get_session = create_session_dependency(
    db_url=config.DB_URL,
    is_fake=config.FAKE,
)

app = create_app(config=config, get_session=get_session)
