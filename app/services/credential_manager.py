import threading
from typing import Optional
from loguru import logger

from app.core.config import settings

class CredentialManager:
    """
    一个线程安全的凭证管理器，用于轮询 Teleprompt 的 email 列表。
    """
    def __init__(self):
        self.credentials = settings.TELEPROMPT_EMAILS
        if not self.credentials:
            raise ValueError("凭证列表为空。请在 .env 文件中配置至少一个 'TELEPROMPT_EMAIL_1'。")
        self.lock = threading.Lock()
        self.current_index = 0
        logger.info(f"凭证管理器已初始化，共加载 {len(self.credentials)} 个凭证。")

    def get_credential(self) -> str:
        """
        线程安全地获取下一个凭证。
        """
        with self.lock:
            credential = self.credentials[self.current_index]
            logger.info(f"使用凭证索引: {self.current_index}")
            self.current_index = (self.current_index + 1) % len(self.credentials)
            return credential
