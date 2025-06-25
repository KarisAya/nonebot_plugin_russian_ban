import re
import time
import random
from nonebot.plugin import PluginMetadata
from nonebot import on_startswith, on_command
from nonebot.log import logger
from nonebot.permission import SUPERUSER
from nonebot.params import ArgPlainText
from nonebot.typing import T_State
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, GROUP_ADMIN, GROUP_OWNER
from .utils import to_int, format_timedelta


# 插件元数据
__plugin_meta__ = PluginMetadata(
    name="轮盘禁言小游戏",
    description="",
    usage="自由轮盘，开枪，拨动滚轮",
    homepage="https://github.com/KarisAya/nonebot_plugin_russian_ban",
    type="application",
    supported_adapters={"~onebot.v11"},
)


any_permission = SUPERUSER | GROUP_ADMIN | GROUP_OWNER

ban = on_startswith("禁言", permission=any_permission, priority=20)

pattern = re.compile(r"^禁言(\d+|[一二三四五六七八九十]|)(.*)")


@ban.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    cmd_match = pattern.match(event.get_plaintext().strip())
    if cmd_match is None:
        await ban.finish()
    t, unit = cmd_match.groups()
    t = (to_int(t) or 5) if t else 5
    match unit:
        case "秒" | "s":
            t = t * 1
        case "分钟" | "min":
            t = t * 60
        case "小时" | "h":
            t = t * 3600
        case "天" | "d":
            t = t * 86400
        case "月" | "个月" | "M":
            t = t * 2592000
        case _:
            t = t * 60

    for messege in event.message:
        if messege.type == "at":
            await bot.set_group_ban(group_id=event.group_id, user_id=messege.data["qq"], duration=t)
    await ban.finish()


type BanInfo = dict[int, tuple[str, float]]

amnesty = on_startswith(("解封", "解禁", "解除禁言"), permission=any_permission, priority=20)


@amnesty.handle()
async def _(bot: Bot, event: GroupMessageEvent, state: T_State):
    at_list: list[int] = [messege.data["qq"] for messege in event.message if messege.type == "at"]
    if at_list:
        group_id = event.group_id
        for at_uid in at_list:
            await bot.set_group_ban(group_id=group_id, user_id=at_uid, duration=0)
        await amnesty.finish()
    else:
        now = time.time()
        ban_info: BanInfo = {
            member["user_id"]: (member["card"] or member["nickname"], shut_up_timestamp - now)
            for member in await bot.get_group_member_list(group_id=event.group_id)
            if (shut_up_timestamp := member["shut_up_timestamp"]) > now
        }
        if not ban_info:
            await amnesty.finish("当前没有成员被禁言。")
        msg = []
        for uid, (nickname, interval) in ban_info.items():
            msg.append(f"{nickname} {uid}\n    -- {format_timedelta(int(interval))}\n")
        state["ban_info"] = ban_info
        await amnesty.send("以下成员正在被禁言：\n" + "\n".join(msg))


@amnesty.got("user_ids", prompt="请输入要解除禁言的成员，如输入多个群成员用空格隔开。")
async def _(bot: Bot, event: GroupMessageEvent, state: T_State, user_ids: str = ArgPlainText()):
    uids = user_ids.strip().split()
    ban_info: BanInfo = state["ban_info"]
    for uid in uids:
        if not uid.isdigit():
            continue
        uid = int(uid)
        if uid in ban_info:
            await bot.set_group_ban(group_id=event.group_id, user_id=int(uid), duration=0)
    await amnesty.finish()


class BanGameState:
    def __init__(self, switch: bool = False):
        self.switch: bool = switch
        self.star = 0
        self.st = 0


states: dict[int, BanGameState] = {}


switch_on = on_command("开启自由轮盘", aliases={"开启轮盘禁言"}, permission=any_permission, priority=5)


@switch_on.handle()
async def _(event: GroupMessageEvent):
    global states
    if event.group_id in states:
        states[event.group_id].switch = True
    else:
        states[event.group_id] = BanGameState(True)
    await switch_on.finish("自由轮盘已开启！")


switch_off = on_command("关闭自由轮盘", aliases={"关闭轮盘禁言"}, permission=any_permission, priority=5)


@switch_off.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    global states
    if event.group_id in states:
        states[event.group_id].switch = False
    else:
        states[event.group_id] = BanGameState(False)
    await switch_off.finish("自由轮盘已关闭！")


async def game_start_rule(event: GroupMessageEvent):
    return event.group_id in states and states[event.group_id].switch


game_start = on_command("自由轮盘", aliases={"轮盘禁言"}, permission=any_permission | game_start_rule, priority=5)
game_start_tips = [
    "这个游戏非常简单，只需要几种道具：一把左轮，一颗子弹，以及愿意跟你一起玩的人。",
    "拿起这把左轮，对着自己的脑袋扣动扳机。如果安然无恙，继续游戏。",
    "对着自己，扣动扳机。如果你是六分之一的“幸运儿”，那么恭喜你，游戏结束。",
    "等等......好像有点不对劲？不过好在“幸运儿”永远没有机会开口说话并诉说游戏的邪恶了",
    "这个游戏非常公平，因为左轮最大的优点就是——不会卡壳",
    "小提示：每次开枪之前可以重新拨动滚轮哦",
]


@game_start.handle()
async def _(event: GroupMessageEvent):
    global states
    if event.group_id in states:
        state = states[event.group_id]
    else:
        state = states[event.group_id] = BanGameState()
    state.star = random.randint(1, 6)
    if state.st == 0:
        msg = "游戏开始！\n" + random.choice(game_start_tips)
    else:
        msg = "重新装弹！"
    state.st = 1
    await game_start.finish(msg)


async def game_ready_rule(event: GroupMessageEvent):
    return event.group_id in states and states[event.group_id].star > 0


game_roll = on_command("重新装弹", aliases={"拨动滚轮"}, permission=game_ready_rule, priority=4, block=True)
game_roll_tips = [
    "随着金属轮清脆的转动声，子弹重新排列。",
    "——依旧没有人知道子弹的位置。",
    "也许...没有人知道子弹的位置。",
    "拿起这把左轮，对着自己的脑袋扣动扳机。如果安然无恙，继续游戏。",
    "小提示：开枪之前，你还可以继续拨动滚轮哦",
    "",
]


@game_roll.handle()
async def _(event: GroupMessageEvent):
    global states
    state = states[event.group_id]
    state.star = random.randint(1, 6)
    msg = random.choice(game_roll_tips)
    if not msg:
        msg = f"偷偷告诉你，{'如果你开枪的话，下回合将游戏结束。' if state.star  == 1 else '下一发是空的。'}"

    await game_roll.finish("重新装弹！\n" + msg)


game_shot = on_command("开枪", permission=game_ready_rule, priority=4, block=True)
game_shot_tips = [
    "——传来一声清脆的金属碰撞声。\n没有人知道子弹的位置。可是不论它转到了哪里，总是要响的。",
    "恭喜你，安然无恙......但是下一次还会这么幸运吗？",
    "显然你不是这六分之一的“幸运儿”。但是好消息是，游戏还在继续。",
    "咔的一声，撞针敲击到空仓上。——你还安全地活着。",
    "你的运气不错。祝你好运。",
]


@game_shot.handle()
async def _(bot: Bot, event: GroupMessageEvent):
    global states
    state = states[event.group_id]
    if state.star == 1:
        del states[event.group_id]
        try:
            await bot.set_group_ban(group_id=event.group_id, user_id=event.user_id, duration=random.randint(2, 6) * 60)
        except Exception as e:
            logger.exception(f"Failed to ban user {event.user_id} in group {event.group_id}: {e}")
            pass
        await game_shot.finish("中弹！游戏结束。", at_sender=True)
    else:
        state.star -= 1
        match random.randint(1, 10):
            case 1:
                msg = f"提示：接下来第{state.star}发是子弹的位置。"
            case 2:
                msg = f"提示：{'下回合将游戏结束' if state.star == 1 else '下一发是空的'}。"
            case 3:
                msg = f"提示：如果没有拨动滚轮，接下来的两次开枪内{"将" if state.star <=2  else '不'}会有人中弹。"
            case 4:
                msg = f"提示：{'你应该重新拨动滚轮' if state.star == 1 else '每次开枪之前可以重新拨动滚轮哦'}。"
            case _:
                msg = random.choice(game_shot_tips)
        await game_shot.finish("继续！\n" + msg)
