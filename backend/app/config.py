from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "食材预订"
    app_base_url: str = "http://10.204.0.146:13000"
    database_url: str = "mysql+pymysql://sc:scpass@127.0.0.1:3306/shicai?charset=utf8mb4"
    session_secret: str = "dev-secret-change-me"
    session_max_age: int = 7 * 24 * 3600
    cas_base_url: str = ""  # 例 https://cas.xxx.edu.cn/cas，联调时填
    dev_auth_enabled: bool = True  # 本地开发登录旁路，上线置 false
    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin123"
    upload_dir: str = "uploads"

    class Config:
        env_file = ".env"


settings = Settings()
