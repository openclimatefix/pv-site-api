from .app import create_app
from .auth import Auth
from .config import Config
from .session import create_session_dependency

config = Config()

get_session = create_session_dependency(
    db_url=config.DB_URL,
    is_fake=config.FAKE,
)

auth = Auth(
    domain=config.AUTH0_DOMAIN,
    api_audience=config.AUTH0_API_AUDIENCE,
    algorithm=config.AUTH0_ALGORITHM,
)

app = create_app(
    config=config,
    get_session=get_session,
    auth=auth,
)
