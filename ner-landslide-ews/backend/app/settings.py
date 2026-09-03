from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    postgres_url: str
    redis_url: str = "redis://redis:6379/0"
    jwt_secret: str
    jwt_alg: str = "HS256"
    model_dir: str = "/data/models"
    high_risk_threshold: float = 0.70
    medium_risk_threshold: float = 0.40
    alert_cooldown_minutes: int = 360
    msg91_auth_key: str = ""
    msg91_sender: str = "NEREWS"
    fcm_server_key: str = ""

    class Config: env_file = ".env"

settings = Settings()