import asyncio
import os
import tempfile

from pytubefix import YouTube
from pytubefix.cli import on_progress

async def handle_youtube(video_url: str):
    """处理YouTube视频下载请求"""
    try:

        proxies = {
            "http": "http://127.0.0.1:10809",
            "https": "http://127.0.0.1:10809"
        }

        video = YouTube(video_url, on_progress_callback=on_progress, proxies=proxies)


        info_msg = (
            f"标题: {video.title}\n"
            f"👀: {video.views} 👍: {video.likes}\n"
            f"发布日期: {video.publish_date}\n"
            f"描述: {video.description}\n\n"
            f"------\n"
            f"作者: {video.author or '未知'} 订阅数: 1\n"
        )

        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_file:
            video_path = temp_file.name
            video_stream = video.streams.get_highest_resolution()
            if os.path.exists(video_path) and os.path.getsize(video_path) == 0:
                os.remove(video_path)
            if not os.path.exists(video_path):
                video_stream.download(
                    output_path=os.path.dirname(video_path),
                    filename=os.path.basename(video_path)
                )


            final_path = f"file:///{video_path}"
            os.unlink(video_path)

    except Exception as e:
        error_msg = f"处理失败: {str(e)}"


asyncio.run(handle_youtube("https://www.youtube.com/watch?v=ZiDBQdOpuIw"))
