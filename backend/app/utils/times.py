"""业务时间统一入口。

全系统业务时区固定为 Asia/Shanghai：取货批次按 16 点截单、订单时间戳、
锁定到期等都用它。返回**无 tzinfo 的墙钟时间**（数据库列是 DATETIME，
MySQL/SQLite 存的都是墙钟字符串），容器或宿主机时区怎么配都不影响业务。
"""
from datetime import datetime
from zoneinfo import ZoneInfo

CST = ZoneInfo("Asia/Shanghai")


def now_cst() -> datetime:
    """当前业务时间（上海墙钟，naive）。"""
    return datetime.now(CST).replace(tzinfo=None)
