import logging
import re

import httpx

logger = logging.getLogger(__name__)

# 常见"姓名"属性名：中外校园 CAS 都有，具体释放哪个以联调日志为准
_NAME_KEYS = ("displayName", "cn", "employeeName", "realName", "userName", "xm", "name")


def _extract_name(xml: str) -> str | None:
    """兼容三种属性写法（引号单双都认）：
    属性式   <cas:attribute name='xm'>李四</cas:attribute>
    自闭合式 <cas:attribute name="realName" value="王五"/>
    元素式   <cas:cn>张三</cas:cn>（Apereo CAS 3.0 默认）
    """
    for key in _NAME_KEYS:
        patterns = (
            rf'<cas:attribute name=["\']{key}["\'][^>]*>(.*?)</cas:attribute>',
            rf'<cas:attribute name=["\']{key}["\'][^>]*?value=["\'](.*?)["\']',
            rf"<cas:{key}>(.*?)</cas:{key}>",
        )
        for p in patterns:
            m = re.search(p, xml, re.S | re.I)  # 学校实测属性名为大写 Name，忽略大小写
            if m and m.group(1).strip():
                return m.group(1).strip()
    return None


class CASClient:  # 接口约定：get_user(ticket, service_url) -> (empid, name|None)
    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        raise NotImplementedError


class HttpCASClient(CASClient):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        params = {"ticket": ticket, "service": service_url}
        # 优先 CAS 3.0 端点：属性块基本只在它这里按服务配置释放。
        # 学校 tpass 的 p3 只认 GET（POST 返回 405，实测 2026-11-18）；
        # 响应不是 CAS XML（如 404 页）时回退 2.0 端点，登录不中断
        r = httpx.get(f"{self.base_url}/p3/serviceValidate", params=params, timeout=10)
        if "cas:serviceResponse" not in r.text:
            r = httpx.post(f"{self.base_url}/serviceValidate", params=params, timeout=10)
        m = re.search(r"<cas:user>(.*?)</cas:user>", r.text, re.S)
        # 摘要日志只记结果；原始 XML 含工号/姓名等个人信息，降级到 DEBUG 按需开启
        logger.info("CAS validate: user=%s name_released=%s",
                    m.group(1).strip() if m else None, bool(_extract_name(r.text)))
        logger.debug("CAS validate 原始响应: %s", r.text)
        if not m:
            raise RuntimeError("CAS ticket 校验失败")
        return m.group(1).strip(), _extract_name(r.text)


class FakeCASClient(CASClient):
    """开发/测试用：预先注入 {ticket: (empid, name)}，命中即通过。"""

    def __init__(self, users: dict[str, tuple[str, str | None]]):
        self.users = users

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        if ticket not in self.users:
            raise RuntimeError("CAS ticket 校验失败")
        return self.users[ticket]
