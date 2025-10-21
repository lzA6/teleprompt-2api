import sys
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.responses import JSONResponse, StreamingResponse
from loguru import logger

from app.core.config import settings
from app.providers.teleprompt_provider import TelepromptProvider

# --- 配置 Loguru ---
logger.remove()
logger.add(
    sys.stdout,
    level="INFO",
    format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}:{function}:{line}</cyan> - <level>{message}</level>",
    colorize=True
)

provider = TelepromptProvider()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"应用启动中... {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"加载了 {len(settings.TELEPROMPT_EMAILS)} 个 Teleprompt 凭证。")
    logger.info("服务已进入 'Intelligent Credential Pool' 模式。")
    logger.info(f"服务将在 http://localhost:{settings.NGINX_PORT} 上可用")
    yield
    logger.info("应用关闭。")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=settings.DESCRIPTION,
    lifespan=lifespan
)

async def verify_api_key(authorization: Optional[str] = Header(None)):
    if settings.API_MASTER_KEY and settings.API_MASTER_KEY != "1":
        if not authorization or "bearer" not in authorization.lower():
            raise HTTPException(status_code=401, detail="需要 Bearer Token 认证。")
        token = authorization.split(" ")[-1]
        if token != settings.API_MASTER_KEY:
            raise HTTPException(status_code=403, detail="无效的 API Key。")

@app.post("/v1/chat/completions", dependencies=[Depends(verify_api_key)])
async def chat_completions(request: Request):
    try:
        request_data = await request.json()
        return await provider.chat_completion(request_data)
    except Exception as e:
        logger.error(f"处理聊天请求时发生顶层错误: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"内部服务器错误: {str(e)}")

# --- [修正] 移除此处的密钥验证依赖 ---
@app.get("/v1/models", response_class=JSONResponse)
async def list_models():
    """
    提供模型列表端点，无需认证即可访问，以提高与第三方客户端的兼容性。
    """
    return await provider.get_models()

@app.get("/", summary="根路径", include_in_schema=False)
def root():
    return {"message": f"欢迎来到 {settings.APP_NAME} v{settings.APP_VERSION}. 服务运行正常。"}

