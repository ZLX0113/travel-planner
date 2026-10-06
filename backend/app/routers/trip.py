"""旅行规划路由 — 支持流式 Agent 输出（需登录）"""

import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from app.core.security import get_current_user
from app.core.cities import ensure_domestic_city, normalize_departure
from app.models.db_models import User
from app.tools.itinerary_builder import modify_itinerary, generate_versions
from app.models.schemas import TripPlanRequest, ModifyRequest, VersionPlanRequest
from app.agents.planner_graph import planner_graph
from app.agents.state import PlannerState

router = APIRouter(prefix="/api/trip", tags=["trip"])


@router.post("/plan")
async def plan_trip(
    request: TripPlanRequest,
    current_user: User = Depends(get_current_user),
):
    """生成旅行规划
    
    通过 Agent 工作流搜索航班、酒店、景点，生成结构化行程。
    支持 SSE 流式输出每一步的进度。仅支持国内目的地。
    """
    destination = ensure_domestic_city(request.destination)
    departure = normalize_departure(request.departure)

    initial_state: PlannerState = {
        "messages": [
            {"role": "user", "content": f"请帮我规划一次{destination}的{request.days}天旅行。预算{request.budget or '不限'}元。偏好：{', '.join(request.preferences) if request.preferences else '综合'}。出发城市：{departure}。"}
        ],
        "destination": destination,
        "days": request.days,
        "budget": request.budget,
        "preferences": request.preferences,
        "departure_city": departure,
        "travelers": request.travelers or 1,
        "special_needs": request.special_needs or [],
        "start_date": request.start_date,
        "flights": None,
        "hotels": None,
        "attractions": None,
        "itinerary": None,
        "total_budget_estimate": None,
        "next_step": None,
        "error": None,
    }
    
    return StreamingResponse(
        _stream_plan(initial_state),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _stream_plan(state: PlannerState):
    """流式执行 Agent 工作流并推送进度"""
    try:
        yield f"data: {json.dumps({'status': 'start', 'message': '开始规划旅行...'}, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({'status': 'searching', 'message': '正在搜索航班、酒店和景点信息...'}, ensure_ascii=False)}\n\n"
        
        from app.agents.planner_graph import search_node, summarize_node
        
        # 搜索
        state = await search_node(state)
        yield f"data: {json.dumps({'status': 'searched', 'message': f'找到 {len(state.get("flights", []))} 个航班、{len(state.get("hotels", []))} 家酒店、{len(state.get("attractions", []))} 个景点'}, ensure_ascii=False)}\n\n"
        
        # 生成行程
        yield f"data: {json.dumps({'status': 'generating', 'message': '正在生成行程方案...'}, ensure_ascii=False)}\n\n"
        
        state = await summarize_node(state)
        
        # 发送结构化行程数据
        if state.get("itinerary"):
            yield f"data: {json.dumps({'status': 'itinerary', 'data': state['itinerary']}, ensure_ascii=False, default=str)}\n\n"
        
        # 发送预算数据
        if state.get("budget_breakdown"):
            yield f"data: {json.dumps({'status': 'budget', 'breakdown': state['budget_breakdown'], 'total': state['total_budget_estimate']}, ensure_ascii=False)}\n\n"
        
        # 发送最终文本
        content = state["messages"][-1]["content"] if state.get("messages") else "行程生成失败"
        yield f"data: {json.dumps({'status': 'done', 'content': content}, ensure_ascii=False)}\n\n"
        
        yield f"data: {json.dumps({'done': True})}\n\n"
        
    except Exception as e:
        yield f"data: {json.dumps({'status': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"


@router.post("/modify")
async def modify_trip(
    request: ModifyRequest,
    current_user: User = Depends(get_current_user),
):
    """修改已有行程 — 根据用户指令局部调整"""
    try:
        modified, message = modify_itinerary(
            itinerary=request.itinerary,
            attractions=request.attractions,
            modify_request=request.modify_request,
        )
        return {"status": "ok", "itinerary": modified, "message": message}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/versions")
async def plan_versions(
    request: VersionPlanRequest,
    current_user: User = Depends(get_current_user),
):
    """生成多版本方案对比（省钱版/舒适版/网红版），仅支持国内目的地"""
    from app.agents.planner_graph import search_node

    destination = ensure_domestic_city(request.destination)
    departure = normalize_departure(request.departure)

    try:
        state: PlannerState = {
            "messages": [],
            "destination": destination,
            "days": request.days,
            "budget": request.budget,
            "preferences": request.preferences,
            "departure_city": departure,
            "travelers": request.travelers or 1,
            "special_needs": request.special_needs or [],
            "start_date": request.start_date,
            "flights": None,
            "hotels": None,
            "attractions": None,
            "itinerary": None,
            "total_budget_estimate": None,
            "next_step": None,
            "error": None,
        }

        state = await search_node(state)

        versions = generate_versions(
            flights=state.get("flights", []),
            hotels=state.get("hotels", []),
            attractions=state.get("attractions", []),
            days=request.days,
            destination=destination,
            budget=request.budget,
            travelers=request.travelers or 1,
            start_date=request.start_date,
            special_needs=request.special_needs or [],
        )

        return {"status": "ok", "versions": versions}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))