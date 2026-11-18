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

DEFAULT_SESSION_SECRET = "dev-secret-change-me"
DEFAULT_INITIAL_ADMIN_PASSWORD = "admin123"


def validate_security_settings(s: "Settings") -> None:
    """启动期校验：空密钥任何环境都拒；默认密钥不得进入生产姿态（dev 登录已关）。"""
    problems: list[str] = []
    if not s.session_secret:
        problems.append("SESSION_SECRET 不能为空")
    if not s.initial_admin_password:
        problems.append("INITIAL_ADMIN_PASSWORD 不能为空")
    if not s.dev_auth_enabled:  # 生产姿态：默认值即拒
        if s.session_secret == DEFAULT_SESSION_SECRET:
            problems.append("生产环境 SESSION_SECRET 不能用开发默认值，请换成随机长串")
        if s.initial_admin_password == DEFAULT_INITIAL_ADMIN_PASSWORD:
            problems.append("生产环境 INITIAL_ADMIN_PASSWORD 不能用默认 admin123")
    if problems:
        raise RuntimeError("启动安全校验失败：" + "；".join(problems))
