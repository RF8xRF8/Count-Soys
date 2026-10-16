from datetime import date, datetime, timedelta, timezone

# 全系统统一使用北京时间（UTC+8）。
# 数据库的 DateTime 列存的是不带时区的本地时间，写入前一律按 UTC+8 生成：
# 前端可以直接展示这些字符串，按天聚合（今日任务、每日统计、图上时间戳）的口径
# 也和中国使用者的直觉一致，不受服务器时区（容器默认 UTC）影响。
BEIJING = timezone(timedelta(hours=8))


def beijing_now() -> datetime:
    """当前北京时间，naive，供数据库 DateTime 列使用。"""
    return datetime.now(BEIJING).replace(tzinfo=None)


def beijing_today() -> date:
    """北京时间的今天。"""
    return beijing_now().date()
