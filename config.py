from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, HttpUrl

class YouTubeConfig(BaseModel):
    """YouTube下载插件具体配置"""

    timeout: int = Field(
        default=300,
        description="下载超时时间(秒)"
    )

    proxy: Optional[str] = Field(
        default=None,
        description="HTTP代理地址"
    )

    banned_qqs: List[str] = Field(
        default_factory=list,
        description="黑名单QQ列表"
    )

    @field_validator("timeout")
    @classmethod
    def check_timeout(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("timeout must be greater than 0")
        return v

    @field_validator("proxy")
    @classmethod
    def check_proxy(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        try:
            url = HttpUrl(v)
            if url.scheme not in ("http", "https"):
                raise ValueError("proxy must be http or https")
            return str(url)
        except Exception:
            raise ValueError("invalid proxy url format")

    @field_validator("banned_qqs")
    @classmethod
    def check_banned_qqs(cls, v: List[str]) -> List[str]:
        for qq in v:
            if not qq.isdigit():
                raise ValueError(f"invalid QQ number format: {qq}")
        return v

class Config(BaseModel):
    """插件主配置"""

    youtube: YouTubeConfig = Field(
        default_factory=YouTubeConfig,
        description="YouTube下载配置"
    )
