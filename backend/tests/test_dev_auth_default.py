"""I-8：dev-login 旁路默认必须关闭（独立进程验证，不受本进程环境/fixture 污染）。"""
import os
import subprocess
import sys

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_dev_auth_disabled_by_default():
    """无 DEV_AUTH_ENABLED 环境变量、不读 .env 时，dev_auth_enabled 默认 False。"""
    code = (
        "from app.config import Settings; "
        "s = Settings(_env_file=None); "
        "assert s.dev_auth_enabled is False, 'dev_auth_enabled 默认应为 False'"
    )
    env = {k: v for k, v in os.environ.items() if k != "DEV_AUTH_ENABLED"}
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=BACKEND, env=env)
    assert r.returncode == 0, r.stderr


def test_dev_auth_enabled_via_env():
    env = {**{k: v for k, v in os.environ.items() if k != "DEV_AUTH_ENABLED"},
           "DEV_AUTH_ENABLED": "1"}
    code = (
        "from app.config import Settings; "
        "assert Settings(_env_file=None).dev_auth_enabled is True"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=BACKEND, env=env)
    assert r.returncode == 0, r.stderr
