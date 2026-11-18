import re

import httpx


class CASClient:  # 接口约定：get_user(ticket, service_url) -> (empid, name|None)
    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        raise NotImplementedError


class HttpCASClient(CASClient):
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        r = httpx.post(
            f"{self.base_url}/serviceValidate",
            params={"ticket": ticket, "service": service_url}, timeout=10,
        )
        m = re.search(
            r"<cas:user>(.*?)</cas:user>", r.text, re.S,
        )
        if not m:
            raise RuntimeError("CAS ticket 校验失败")
        empid = m.group(1).strip()
        nm = re.search(
            r'<cas:attribute name="(?:displayName|cn|name|employeeName)"[^>]*>(.*?)</cas:attribute>',
            r.text, re.S,
        )
        name = nm.group(1).strip() if nm else None
        return empid, name


class FakeCASClient(CASClient):
    """开发/测试用：预先注入 {ticket: (empid, name)}，命中即通过。"""

    def __init__(self, users: dict[str, tuple[str, str | None]]):
        self.users = users

    def get_user(self, ticket: str, service_url: str) -> tuple[str, str | None]:
        if ticket not in self.users:
            raise RuntimeError("CAS ticket 校验失败")
        return self.users[ticket]
