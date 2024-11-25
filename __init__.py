import asyncio
import os
import re
import tempfile

from pytubefix import YouTube
from pytubefix.cli import on_progress

import aiohttp
from nonebot import get_plugin_config, on_regex, on_command
from nonebot.plugin import PluginMetadata
from nonebot.adapters import Event, Bot
from nonebot.adapters.onebot import V11MessageSegment as MessageSegment
from nonebot.adapters.onebot import V11Message as Message
from nonebot.permission import SUPERUSER
from nonebot.params import CommandArg, RegexStr
from loguru import logger

from .config import Config

__plugin_meta__ = PluginMetadata(
    name="YouTube下载",
    description="{插件介绍}",
    usage="""
自动检测YouTube链接并下载
管理命令(仅超级用户，需要加上命令前缀):
ytdl代理[地址] - 设置代理
ytdl超时[秒数] - 设置超时
ytdl拉黑[QQ号] - 拉黑用户
ytdl取消拉黑 [QQ号] - 取消拉黑
    """.strip(),

    type="application",

    homepage="{项目主页}",
    # 发布必填。

    config=Config,
    # 插件配置项类，如无需配置可不填写。

    supported_adapters={"~onebot.v11"},
    # 支持的适配器集合，其中 `~` 在此处代表前缀 `nonebot.adapters.`，其余适配器亦按此格式填写。
    # 若插件可以保证兼容所有适配器（即仅使用基本适配器功能）可不填写，否则应该列出插件支持的适配器。
)
plugin_config = get_plugin_config(Config).youtube

# 命令匹配器

parse_youtube_matcher = on_regex(
    r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([\w-]+)",
    priority=5
)

command_prefix = "ytdl"
set_proxy_matcher = on_command(command_prefix + "代理", permission=SUPERUSER, priority=1)
set_timeout_matcher = on_command(command_prefix + "超时", permission=SUPERUSER, priority=1)
ban_user_matcher = on_command(command_prefix + "拉黑", permission=SUPERUSER, priority=1)
unban_user_matcher = on_command(command_prefix + "取消拉黑", permission=SUPERUSER, priority=1)

@set_proxy_matcher.handle()
async def handle_set_proxy(proxy: Message = CommandArg()):
    """设置代理"""
    try:
        if proxy := proxy.extract_plain_text().strip():
            msg = f"代理已设置为: {proxy}"
        else:
            msg = "已清除代理设置"
        plugin_config.proxy = proxy
        await set_proxy_matcher.finish(msg)
    except ValueError as e:
        await set_proxy_matcher.finish(f"设置代理失败: {str(e)}")

@set_timeout_matcher.handle()
async def handle_set_timeout(timeout: Message = CommandArg()):
    """设置超时时间"""
    try:
        if timeout_str := timeout.extract_plain_text().strip():
            timeout_val = int(timeout_str)
            plugin_config.timeout = timeout_val
            msg = f"超时时间已设置为: {timeout_val}秒"
        else:
            plugin_config.timeout = 300  # 恢复默认值
            msg = "已恢复默认超时时间(300秒)"
        await set_timeout_matcher.finish(msg)
    except ValueError as e:
        await set_timeout_matcher.finish(f"设置超时失败: {str(e)}")

@ban_user_matcher.handle()
async def handle_ban_user(user: Message = CommandArg()):
    """拉黑用户"""
    try:
        qq = user.extract_plain_text().strip()
        if qq:
            if qq not in plugin_config.banned_qqs:
                plugin_config.banned_qqs.append(qq)
                msg = f"已添加到拉黑名单: {qq}\n"
            else:
                msg = f"用户 {qq} 已在黑名单中\n"
        else:
            msg = ""

        if plugin_config.banned_qqs:
            msg += f"当前拉黑名单：{', '.join(plugin_config.banned_qqs)}"
        else:
            msg += "当前拉黑名单为空"

        await ban_user_matcher.finish(msg)
    except ValueError as e:
        await ban_user_matcher.finish(f"拉黑用户失败: {str(e)}")


@unban_user_matcher.handle()
async def handle_unban_user(user: Message = CommandArg()):
    """取消拉黑用户"""
    try:
        if qq := user.extract_plain_text().strip():
            if qq in plugin_config.banned_qqs:
                plugin_config.banned_qqs.remove(qq)
                msg = f"已取消拉黑用户: {qq}"
            else:
                msg = f"用户 {qq} 不在黑名单中"
        else:
            msg = "请提供要取消拉黑的QQ号"
        await unban_user_matcher.finish(msg)
    except ValueError as e:
        await unban_user_matcher.finish(f"取消拉黑失败: {str(e)}")

async def get_video_id(msg: str) -> str:
    """提取YouTube视频ID"""
    pattern = r"(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/|user\/[^#]+\/u\/\d\/|v=))([a-zA-Z0-9_-]{11})"
    if match := re.search(pattern, msg):
        return match.group(1)
    raise ValueError("无效的YouTube视频ID")

@parse_youtube_matcher.handle()
async def handle_youtube(event: Event, bot: Bot, video_url: str = RegexStr()):
    """处理YouTube视频下载请求"""
    user_id = str(event.get_user_id())

    if user_id == bot.self_id:
        return

    if user_id in plugin_config.banned_qqs:
        logger.info(f"用户 {user_id} 已被拉黑,忽略请求")
        return

    try:
        await parse_youtube_matcher.send("正在解析YouTube视频，请稍等")

        proxies = {
            "http": plugin_config.proxy,
            "https": plugin_config.proxy
        } if plugin_config.proxy else None

        video = YouTube(video_url, on_progress_callback=on_progress, proxies=proxies)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(video.thumbnail_url, proxy=plugin_config.proxy if plugin_config.proxy else None) as response:
                    thumbnail_data = await response.read()

            await parse_youtube_matcher.send(MessageSegment.image(file=thumbnail_data))
        except Exception as e:
            logger.error(f"获取视频缩略图失败: {e}")
            await parse_youtube_matcher.send("获取视频缩略图失败，继续尝试下载")

        sub_count_raw = video.vid_details['contents']['twoColumnWatchNextResults']['results']['results']['contents'][1]['videoSecondaryInfoRenderer']['owner']['videoOwnerRenderer']['subscriberCountText']['simpleText']

        info_msg = (
            f"标题: {video.title}\n"
            f"👀: {video.views} 👍: {video.likes if video.likes else '未知'}\n"
            f"发布日期: {video.publish_date}\n"
            f"描述: {video.description}\n\n"
            f"------\n"
            f"作者: {video.author or '未知'}\n订阅数: {normalize_count(sub_count_raw)}\n"
        )
        await parse_youtube_matcher.send(info_msg)

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            video_path = temp_file.name
            video_stream = video.streams.get_highest_resolution()
            video_stream.download(
                output_path=os.path.dirname(video_path),
                filename=os.path.basename(video_path)
            )

            logger.debug("视频已下载")

            final_path = f"file:///{video_path}"
            await parse_youtube_matcher.send(MessageSegment.video(final_path))
            try:
                await asyncio.sleep(plugin_config.timeout)
                os.unlink(video_path)
                logger.info(f"[ytdl] 视频文件 {video.video_id} 已被清理")
            except Exception as e:
                logger.warning(f"[ytdl] 清理视频文件 {video.video_id} 失败: {e}")


    except Exception as e:
        error_msg = f"处理失败: {str(e)}"
        if "fetch failed" in str(e):
            error_msg += f"\n当前代理: {plugin_config.proxy}\n使用 #ytdl代理[HTTP代理] 来指定代理"
        await parse_youtube_matcher.send(error_msg)
        logger.error(f"YT视频下载错误: {e}")

def normalize_count(count_str):
    """
    将带单位的数字字符串转换为普通数字

    参数:
        count_str (str): 输入的字符串，如 "3.74M subscribers"

    返回:
        int: 转换后的数字
    """
    # 首先移除非必要的文字（如 'subscribers'）
    count_str = count_str.split()[0].strip()

    # 定义单位映射
    multipliers = {
        'K': 1000,
        'M': 1000000,
        'B': 1000000000,
        'k': 1000,
        'm': 1000000,
        'b': 1000000000
    }

    try:
        # 检查最后一个字符是否是单位
        if count_str[-1].upper() in multipliers:
            # 获取数字部分
            number = float(count_str[:-1])
            # 获取单位
            unit = count_str[-1].upper()
            # 计算实际数值
            return int(number * multipliers[unit])
        else:
            # 如果没有单位，直接转换为整数
            return int(float(count_str))
    except (ValueError, IndexError):
        raise ValueError(f"Invalid count string: {count_str}")