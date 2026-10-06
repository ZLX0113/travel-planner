"""聊天路由 — 支持 SSE 流式输出（需登录）"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.models.db_models import User
from app.models.schemas import ChatRequest, ChatResponse
from app.core.llm import get_llm_client

router = APIRouter(prefix="/api/chat", tags=["chat"])

SYSTEM_PROMPT = """你是一个专业的 AI 旅行规划师助手。你可以帮助用户：
1. 推荐旅行目的地和行程安排
2. 提供机票、酒店、景点等信息
3. 根据用户的预算和偏好定制旅行方案

请用友好、热情的语气回复，像一位贴心的旅行顾问。回复简洁明了，控制在 200 字以内，除非用户要求详细规划。"""


@router.post("")
async def chat(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
):
    """聊天接口 — 支持流式和非流式"""
    llm = get_llm_client()

    # 构建消息列表，确保有 system prompt
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for msg in request.messages:
        messages.append({"role": msg.role, "content": msg.content})

    if request.stream:
        return StreamingResponse(
            _stream_chat(llm, messages),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    else:
        try:
            response = await llm.get_client().chat.completions.create(
                model=llm.get_model(),
                messages=messages,
                temperature=llm.temperature,
                max_tokens=llm.max_tokens,
            )
            content = response.choices[0].message.content or ""
            return ChatResponse(content=content)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM 调用失败: {str(e)}")


async def _stream_chat(llm, messages: list[dict]):
    """SSE 流式生成器"""
    try:
        stream = await llm.get_client().chat.completions.create(
            model=llm.get_model(),
            messages=messages,
            temperature=llm.temperature,
            max_tokens=llm.max_tokens,
            stream=True,
        )

        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta.content:
                yield f"data: {json.dumps({'content': delta.content}, ensure_ascii=False)}\n\n"

        # 发送完成信号
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"