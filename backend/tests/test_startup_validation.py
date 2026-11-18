"""启动期安全配置校验（C-1）：空密钥/默认密钥不得静默进入生产姿态。"""
import pytest

from app.config import Settings, validate_security_settings


def make(**kw) -> Settings:
    base = dict(_env_file=None, session_secret="x" * 32,
                initial_admin_password="good-pass", dev_auth_enabled=True)
    base.update(kw)
    return Settings(**base)


def test_empty_session_secret_rejected():
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_security_settings(make(session_secret=""))


def test_empty_initial_admin_password_rejected():
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        validate_security_settings(make(initial_admin_password=""))


def test_default_secret_rejected_in_production():
    with pytest.raises(RuntimeError, match="SESSION_SECRET"):
        validate_security_settings(make(dev_auth_enabled=False,
                                        session_secret="dev-secret-change-me"))


def test_default_initial_password_rejected_in_production():
    with pytest.raises(RuntimeError, match="INITIAL_ADMIN_PASSWORD"):
        validate_security_settings(make(dev_auth_enabled=False,
                                        initial_admin_password="admin123"))


def test_dev_defaults_allowed_in_dev_mode():
    """本地开发姿态允许默认值（测试/联调环境依赖）。"""
    validate_security_settings(make(session_secret="dev-secret-change-me",
                                    initial_admin_password="admin123"))


def test_production_strong_values_allowed():
    validate_security_settings(make(dev_auth_enabled=False))
