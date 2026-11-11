from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8',)

    OPENAI_API_KEY: str = "place your API key"
    OPENAI_BASE_URL: str = "https://routerai.ru/api/v1"
    OPENAI_CHAT_MODEL: str = "qwen/qwen-v3.7-flash"
    DATABASE_URL: str = "postgresql+asyncpg://handproject:handproject@localhost:5432/handproject"

settings = Settings()
        