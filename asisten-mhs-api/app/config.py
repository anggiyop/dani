from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "asisten_mhs"
    DB_USER: str = "root"
    DB_PASS: str = "root"  # ganti dengan password MySQL kamu
    JWT_SECRET: str = "supersecret"
    JWT_ALG: str = "HS256"

    class Config:
        env_file = ".env"

settings = Settings()
