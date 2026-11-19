"""HttpCASClient 解析层单测：姓名属性三种写法 + p3 端点回退 + 诊断日志。"""
import logging

import pytest

from app.auth.cas import HttpCASClient, _extract_name

# Apereo CAS 3.0 默认元素式属性
ELEMENT_XML = """<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>012005006</cas:user>
    <cas:attributes>
      <cas:cn>张三</cas:cn>
      <cas:displayName>张三</cas:displayName>
    </cas:attributes>
  </cas:authenticationSuccess>
</cas:serviceResponse>"""

# 属性式（学校 tpass 服务器实测用单引号）
ATTR_XML = """<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>012005006</cas:user>
    <cas:attribute name='xm'>李四</cas:attribute>
  </cas:authenticationSuccess>
</cas:serviceResponse>"""

# 自闭合 value 属性式
SELF_CLOSING_XML = """<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>012005006</cas:user>
    <cas:attribute name="realName" value="王五"/>
  </cas:authenticationSuccess>
</cas:serviceResponse>"""

NO_ATTR_XML = """<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>012005006</cas:user>
  </cas:authenticationSuccess>
</cas:serviceResponse>"""

# 学校 tpass 实测格式（2026-11-19 信息中心释放后）：元素式、属性名大写 Name
CPPU_XML = """<cas:serviceResponse xmlns:cas='http://www.yale.edu/tp/cas'>
  <cas:authenticationSuccess>
    <cas:user>012005006</cas:user>
    <cas:attributes>
      <cas:LoginName>012005006</cas:LoginName>
      <cas:longTermAuthenticationRequestTokenUsed>false</cas:longTermAuthenticationRequestTokenUsed>
      <cas:isFromNewLogin>true</cas:isFromNewLogin>
      <cas:authenticationDate>2026-11-19T09:07:38.148+08:00</cas:authenticationDate>
      <cas:Name>刘然</cas:Name>
    </cas:attributes>
  </cas:authenticationSuccess>
</cas:serviceResponse>"""


class _Resp:
    def __init__(self, text: str):
        self.text = text


def test_name_element_style():
    assert _extract_name(ELEMENT_XML) == "张三"


def test_name_attribute_style_single_quotes():
    assert _extract_name(ATTR_XML) == "李四"


def test_name_self_closing_value_style():
    assert _extract_name(SELF_CLOSING_XML) == "王五"


def test_name_absent_returns_none():
    assert _extract_name(NO_ATTR_XML) is None


def test_name_capitalized_key_cppu_format():
    """学校真实格式：大写 Name、LoginName 同屏——必须取到刘然而不是工号。"""
    assert _extract_name(CPPU_XML) == "刘然"


def test_get_user_prefers_p3_then_falls_back(monkeypatch):
    """p3 端点返回非 CAS XML（如 404 页）时回退 serviceValidate，登录不中断。"""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(("GET", url))
        return _Resp("<html>404 Not Found</html>")

    def fake_post(url, params=None, timeout=None):
        calls.append(("POST", url))
        return _Resp(ELEMENT_XML)

    monkeypatch.setattr("app.auth.cas.httpx.get", fake_get)
    monkeypatch.setattr("app.auth.cas.httpx.post", fake_post)
    empid, name = HttpCASClient("https://sso.example.edu/tpass").get_user("t", "s")
    assert empid == "012005006" and name == "张三"
    assert calls == [
        ("GET", "https://sso.example.edu/tpass/p3/serviceValidate"),
        ("POST", "https://sso.example.edu/tpass/serviceValidate"),
    ]


def test_get_user_single_p3_call_when_healthy(monkeypatch):
    """p3 正常时只打一次，不额外请求老端点。"""
    calls = []

    def fake_get(url, params=None, timeout=None):
        calls.append(url)
        return _Resp(ELEMENT_XML)

    monkeypatch.setattr("app.auth.cas.httpx.get", fake_get)
    monkeypatch.setattr(
        "app.auth.cas.httpx.post",
        lambda url, params=None, timeout=None: pytest.fail("不应回退到 2.0 端点"),
    )
    empid, name = HttpCASClient("https://sso.example.edu/tpass").get_user("t", "s")
    assert (empid, name) == ("012005006", "张三")
    assert len(calls) == 1


def test_get_user_invalid_ticket_raises(monkeypatch):
    monkeypatch.setattr(
        "app.auth.cas.httpx.get",
        lambda url, params=None, timeout=None: _Resp(
            "<cas:serviceResponse><cas:authenticationFailure code='INVALID_TICKET'/>"
            "</cas:serviceResponse>"),
    )
    with pytest.raises(RuntimeError):
        HttpCASClient("https://sso.example.edu/tpass").get_user("bad", "s")


def test_get_user_logs_raw_response(monkeypatch, caplog):
    """诊断日志必须落原始响应——联调时据此确认学校 CAS 释放的属性名。"""
    monkeypatch.setattr(
        "app.auth.cas.httpx.get",
        lambda url, params=None, timeout=None: _Resp(ATTR_XML),
    )
    with caplog.at_level(logging.INFO, logger="app.auth.cas"):
        HttpCASClient("https://sso.example.edu/tpass").get_user("t", "s")
    assert any("李四" in r.message for r in caplog.records)
