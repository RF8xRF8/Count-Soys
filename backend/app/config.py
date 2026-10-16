from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PhotoCount"
    database_url: str = "sqlite:///./data/app.db"
    jwt_secret: str = "change-this-development-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120
    refresh_token_expire_days: int = 14
    storage_dir: str = "./data"
    max_upload_mb: int = 10
    frontend_origin: str = "http://localhost:5173"
    # 处理时长边上限。必须与前端 frontend/src/utils/image.js 的 MAX_SIDE 保持一致。
    # 实测（scripts/eval_accuracy.py）：examples/ 样本长边均为 1920，设为 1600 会因下采样
    # 让 MAE 从 1.29 退化到 1.64，1920 及以上结果相同（都是不缩放）。取 2200 是为了让常见
    # 的 1080x1920 竖拍图完全不缩放，并给 iPhone 原图（4032 长边）留余量。
    default_max_side: int = 2200
    default_min_area: int = 100
    default_fg_ratio: float = 0.5

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir)


settings = Settings()
