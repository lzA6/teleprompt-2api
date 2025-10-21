import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import List, Optional

from loguru import logger

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        extra="ignore"
    )

    APP_NAME: str = "teleprompt-2api"
    APP_VERSION: str = "1.0.0"
    DESCRIPTION: str = "一个将 Teleprompt 提示词优化功能转换为兼容 OpenAI 格式 API 的高性能代理，支持多 Email 轮询。"

    API_MASTER_KEY: Optional[str] = None
    NGINX_PORT: int = 8088
    API_REQUEST_TIMEOUT: int = 120

    TELEPROMPT_EMAILS: List[str] = []

    DEFAULT_MODEL: str = "prompt-optimizer"
    KNOWN_MODELS: List[str] = ["prompt-optimizer"]

    @model_validator(mode='after')
    def load_credentials(self) -> 'Settings':
        """
        在设置加载后，从环境变量中动态收集所有 TELEPROMPT_EMAIL_...
        """
        i = 1
        while True:
            email = os.getenv(f"TELEPROMPT_EMAIL_{i}")
            if email:
                self.TELEPROMPT_EMAILS.append(email)
                i += 1
            else:
                break
        
        if not self.TELEPROMPT_EMAILS:
            logger.warning(
                "在 .env 文件中未找到任何 'TELEPROMPT_EMAIL_...' 凭证。"
                "服务将无法正常工作，除非至少配置一个 TELEPROMPT_EMAIL_1。"
            )
        return self

settings = Settings()
