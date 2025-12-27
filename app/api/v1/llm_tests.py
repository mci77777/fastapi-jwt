"""LLM 测试相关路由。"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, conint

from app.auth import AuthenticatedUser, get_current_user

from .llm_common import create_response, get_jwt_test_service, get_service

router = APIRouter(prefix="/llm", tags=["llm"])


class PromptTestRequest(BaseModel):
    """Prompt 测试请求体。"""

    prompt_id: int = Field(..., description="Prompt ID")
    endpoint_id: int = Field(..., description="接口 ID")
    message: str = Field(..., min_length=1, description="测试消息内容")
    model: str | None = Field(None, description="可选模型名称")
    skip_prompt: bool = False


class JwtDialogRequest(BaseModel):
    """JWT 对话模拟请求。"""

    prompt_id: int
    endpoint_id: int
    message: str
    model: str | None = None
    username: str | None = None
    skip_prompt: bool = False


class JwtLoadTestRequest(BaseModel):
    """JWT 并发压测请求。"""

    prompt_id: int
    endpoint_id: int
    message: str
    batch_size: conint(ge=1, le=1000) = 1  # type: ignore[valid-type]
    concurrency: conint(ge=1, le=1000) = 1  # type: ignore[valid-type]
    model: str | None = None
    username: str | None = None
    stop_on_error: bool = False
    skip_prompt: bool = False


class CreateMailUserRequest(BaseModel):
    mail_api_key: Optional[str] = None
    username_prefix: str = "test"


@router.post("/prompts/test")
async def test_prompt(
    payload: PromptTestRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_service(request)
    try:
        result = await service.test_prompt(
            prompt_id=payload.prompt_id,
            endpoint_id=payload.endpoint_id,
            message=payload.message,
            model=payload.model,
            skip_prompt=payload.skip_prompt,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg=str(exc)),
        )
    return create_response(data=result, msg="测试成功")


@router.post("/tests/create-mail-user")
async def create_mail_user(
    payload: CreateMailUserRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> dict[str, Any]:
    """通过 Mail API 创建测试用户流程（仅用于调试）。
    
    1. 生成临时邮箱
    2. (模拟) 如果有真实的注册接口，应该调用它。
       目前由于没有真实的注册接口暴露给前端，且 base.py 只有 admin 登录，
       我们这里模拟这个过程：获取邮箱 -> 生成此邮箱对应的 Token。
       这允许该用户以该邮箱身份进行 JWT 测试。
    """
    try:
        from app.services.mail_auth_service import MailAuthService
        from app.api.v1.base import create_test_jwt_token
        
        from app.settings.config import get_settings
        
        # 获取 API Key (优先 Payload, 其次 Settings/Env)
        api_key = payload.mail_api_key
        # Fallback to settings
        if not api_key:
            settings = get_settings()
            api_key = settings.mail_api_key
            
        if not api_key:
             raise HTTPException(status_code=400, detail="Missing Mail API Key")

        # MOCK MODE: 支持使用 mock key 进行端到端 UI 测试，无需真实 API
        if api_key == "test-key-mock":
            # Use global import time
            ts = int(time.time())
            username = payload.username_prefix if payload.username_prefix != "test" else f"mock-user-{ts}"
            
            return create_response(data={
                "email": f"{username}@example.com",
                "username": username,
                "access_token": create_test_jwt_token(username),
                "note": "MOCK MODE: No real email generated."
            })

        ms = MailAuthService(api_key=api_key)
        
        # 1. 验证并获取域名
        config = await ms.get_config()
        domains = config.get("domains")
        if not domains:
             raise HTTPException(status_code=502, detail="Mail API no domains available")
             
        # 2. 生成邮箱
        email_data = await ms.generate_email(domain=domains[0], name=payload.username_prefix)
        # 3. 模拟注册/登录成功 -> 生成 Token
        email_address = email_data["address"]
        username = email_address.split("@")[0]
        token = create_test_jwt_token(username)
        
        return create_response(data={
            "email": email_address,
            "username": username,
            "access_token": token,
            "note": "Token generated locally for this temp email."
        })
    except httpx.HTTPStatusError as e:
        # 上游返回非 2xx 响应
        error_detail = f"Mail API Error: {e.response.status_code} {e.response.text}"
        raise HTTPException(status_code=502, detail=error_detail)
    except Exception as exc:
        import traceback
        with open("debug_error.log", "a", encoding="utf-8") as f:
             f.write(f"\n[{time.ctime()}] ERROR in create_mail_user:\n")
             f.write(str(exc) + "\n")
             traceback.print_exc(file=f)
        raise HTTPException(status_code=500, detail=f"Internal Error: {str(exc)}")


@router.post("/tests/dialog")
async def simulate_jwt_dialog(
    payload: JwtDialogRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    try:
        result = await service.simulate_dialog(payload.model_dump())
        return create_response(data=result)
    except RuntimeError as exc:
        # AI 服务调用失败（如 API 超时、模型不存在等）
        return create_response(code=500, msg=str(exc), data={"error": str(exc)})
    except ValueError as exc:
        # 配置错误（如 prompt/endpoint 不存在）
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg=str(exc)),
        )
    except Exception as exc:
        # 未知错误 - 记录并返回
        import logging
        logging.exception("simulate_jwt_dialog error")
        return create_response(code=500, msg=f"内部错误: {exc}", data={"error": str(exc)})


@router.post("/tests/load")
async def run_jwt_load_test(
    payload: JwtLoadTestRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    result = await service.run_load_test(payload.model_dump())
    return create_response(data=result, msg="压测完成")


@router.get("/tests/runs/{run_id}")
async def get_jwt_run(
    run_id: str,
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),  # noqa: B008
) -> dict[str, Any]:
    service = get_jwt_test_service(request)
    result = await service.get_run(run_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_response(code=404, msg="Run 不存在"),
        )
    return create_response(data=result)


__all__ = [
    "router",
    "PromptTestRequest",
    "JwtDialogRequest",
    "JwtLoadTestRequest",
    "CreateMailUserRequest",
]
