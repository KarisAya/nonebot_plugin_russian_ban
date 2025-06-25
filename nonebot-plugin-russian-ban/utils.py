zh_number = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def to_int(N) -> int | None:
    try:
        result = int(N)
    except ValueError:
        result = zh_number.get(N)
    return result


def format_timedelta(seconds: int | float) -> str:
    days = seconds // 86400
    seconds -= days * 86400
    hours = seconds // 3600
    seconds -= hours * 3600
    minutes = seconds // 60
    seconds -= minutes * 60
    result = []
    if days > 0:
        result.append(f"{days} 天")
    if hours > 0:
        result.append(f"{hours} 小时")
    if minutes > 0:
        result.append(f"{minutes} 分钟")
    if seconds > 0:
        result.append(f"{seconds} 秒")
    return "".join(result)
