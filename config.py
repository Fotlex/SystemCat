from pydantic_settings import BaseSettings


class Config(BaseSettings):
    BOT_ADMIN_TOKEN: str
    BOT_WORKER_TOKEN: str
    
    CHAT1_ID: int
    CHAT2_ID: int
    CHAT3_ID: int
    CHAT4_ID: int
    CHAT5_ID: int
    CHAT6_ID: int
    CHAT7_ID: int

    DEBUG: bool
    TIMEZONE: str

    DJANGO_ALLOWED_HOSTS: list[str]
    CSRF_TRUSTED_ORIGINS: list[str]
    
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    DB_HOST: str
    DB_PORT: str

    REDIS_HOST: str
    REDIS_PORT: str

    class Config:
        env_file = ".env"


config = Config()
