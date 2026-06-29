from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./astroao.db"
    redis_url: str = "redis://localhost:6379"
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    default_n_zernike_modes: int = 22
    default_centroid_algorithm: str = "wcog"  # cog, wcog
    default_recon_method: str = "modal"
    dm_max_stroke_microns: float = 5.0
    tikhonov_lambda: float = 0.001
    reference_wavelength_nm: float = 500.0
    ws_max_fps: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
