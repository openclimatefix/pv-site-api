import os

from dotenv import load_dotenv


class Config:
    """This encapsulates the environment variables we use to configure the app.

    We make sure to load the dotenv environment.
    We also take care of parsing the types when required.
    """

    def __init__(self, env_path: str = ".env"):
        load_dotenv(env_path)

        self.SENTRY_DSN = os.getenv("SENTRY_DSN")
        self.ENVIRONMENT = os.getenv("ENVIRONMENT", "local")
        self.CORS_ORIGINS = os.getenv("ORIGINS", "*").split(",")
        self.DB_URL = os.environ["DB_URL"]

    # The FAKE setting is special because we can't set it once and for all in the tests, it changes
    # with every test. This is why we make it dynamic.
    @property
    def FAKE(self):
        return bool(int(os.environ.get("FAKE", 0)))
