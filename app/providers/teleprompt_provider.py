import json
import time
import uuid
import asyncio
from typing import Dict, Any, AsyncGenerator

import cloudscraper
from fastapi.responses import StreamingResponse, JSONResponse
from loguru import logger

from app.core.config import settings
from app.providers.base_provider import BaseProvider
from app.services.credential_manager import CredentialManager
from app.utils.sse_utils import create_sse_data, create_chat_completion_chunk, DONE_CHUNK

class TelepromptProvider(BaseProvider):
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.credential_manager = CredentialManager()
        self.api_url = "https://teleprompt-v2-backend-production.up.railway.app/api/v1/prompt/optimize_auth"

    async def chat_completion(self, request_data: Dict[str, Any]) -> StreamingResponse:
        
        async def stream_generator() -> AsyncGenerator[bytes, None]:
            request_id = f"chatcmpl-{uuid.uuid4()}"
            model = request_data.get("model", settings.DEFAULT_MODEL)
            
            try:
                # 1. 从消息列表中获取最后一个用户输入
                messages = request_data.get("messages", [])
                last_user_message = next((m['content'] for m in reversed(messages) if m.get('role') == 'user'), None)
                if not last_user_message:
                    raise ValueError("在请求的 'messages' 列表中未找到用户消息。")

                # 2. 从凭证池获取一个 email
                email = self.credential_manager.get_credential()

                # 3. 准备请求头和载荷
                headers = self._prepare_headers(email)
                payload = self._prepare_payload(last_user_message)
                
                logger.info(f"向上游发送请求, Email: ...{email[-10:]}")
                
                # 4. 发送请求 (cloudscraper 是同步库, FastAPI 会在线程池中运行它)
                response = self.scraper.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=settings.API_REQUEST_TIMEOUT
                )
                response.raise_for_status()
                response_data = response.json()
                
                logger.info(f"收到上游响应: {response_data}")

                if not response_data.get("success") or "data" not in response_data:
                    raise ValueError(f"上游 API 返回失败或格式不正确: {response_data}")

                # 5. 提取优化后的文本
                optimized_prompt = response_data["data"]

                # 6. 使用伪流式生成器返回结果
                chunk = create_chat_completion_chunk(request_id, model, optimized_prompt)
                yield create_sse_data(chunk)
                await asyncio.sleep(0.01) # 短暂停顿以模拟流式效果

                # 7. 发送结束标志
                final_chunk = create_chat_completion_chunk(request_id, model, "", "stop")
                yield create_sse_data(final_chunk)
                yield DONE_CHUNK
                logger.success("伪流式响应成功完成。")

            except Exception as e:
                logger.error(f"处理流时发生错误: {e}", exc_info=True)
                error_message = f"内部服务器错误: {str(e)}"
                error_chunk = create_chat_completion_chunk(request_id, model, error_message, "stop")
                yield create_sse_data(error_chunk)
                yield DONE_CHUNK

        return StreamingResponse(stream_generator(), media_type="text/event-stream")

    def _prepare_headers(self, email: str) -> Dict[str, str]:
        return {
            "accept": "*/*",
            "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
            "content-type": "application/json",
            "email": email,
            "origin": "chrome-extension://alfpjlcndmeoainjfgbbnphcidpnmoae",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
        }

    def _prepare_payload(self, text: str) -> Dict[str, Any]:
        return {"text": text}

    async def get_models(self) -> JSONResponse:
        model_data = {
            "object": "list",
            "data": [
                {"id": name, "object": "model", "created": int(time.time()), "owned_by": "lzA6"}
                for name in settings.KNOWN_MODELS
            ]
        }
        return JSONResponse(content=model_data)

# BaseProvider 的抽象基类
class BaseProvider:
    async def chat_completion(self, request_data: Dict[str, Any]) -> StreamingResponse:
        raise NotImplementedError
    async def get_models(self) -> JSONResponse:
        raise NotImplementedError
