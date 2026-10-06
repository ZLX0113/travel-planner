"""Planner Agent — LangGraph 工作流"""

import json
from typing import Literal
from langgraph.graph import StateGraph, END
from app.agents.state import PlannerState, FlightInfo, HotelInfo, AttractionInfo, DayPlan
from app.tools.search_tools import search_flights, search_hotels, search_attractions
from app.core.llm import get_llm_client
from app.tools.budget_calculator import calculate_budget
from app.tools.itinerary_builder import build_itinerary, itinerary_to_markdown


# ============ 工具定义（供 LLM Function Calling） ============

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_flights",
            "description": "搜索航班信息，返回可选航班列表（含航司、时间、价格）",
            "parameters": {
                "type": "object",
                "properties": {
                    "departure": {"type": "string", "description": "出发城市，如 北京、上海"},
                    "destination": {"type": "string", "description": "目的地城市，如 东京、大阪"},
                    "budget": {"type": "number", "description": "往返机票预算上限（元），可选"}
                },
                "required": ["departure", "destination"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_hotels",
            "description": "搜索目的地酒店，返回酒店列表（含名称、评分、价格、地址）",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                    "budget_per_night": {"type": "number", "description": "每晚预算上限（元），可选"},
                    "min_rating": {"type": "number", "description": "最低评分，默认3.5"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_attractions",
            "description": "搜索目的地景点和活动，返回景点列表（含类别、建议时长、门票价格）",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "城市名"},
                    "preferences": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "偏好筛选，可选值：文化、美食、购物、自然、娱乐"
                    }
                },
                "required": ["city"]
            }
        }
    }
]

# 工具函数映射
TOOL_MAP = {
    "search_flights": search_flights,
    "search_hotels": search_hotels,
    "search_attractions": search_attractions,
}


# ============ Agent 节点 ============

PLANNER_SYSTEM_PROMPT = """你是一个专业的旅行规划 Agent。你的任务是根据用户需求，调用工具获取真实数据，然后生成详细的旅行行程。

## 工作流程
1. 分析用户需求，提取：目的地、天数、预算、偏好、出发城市
2. 调用 search_flights 获取航班信息
3. 调用 search_hotels 获取酒店信息
4. 调用 search_attractions 获取景点信息
5. 汇总所有数据，生成每日行程计划

## 行程生成规则
- 每天安排 2-3 个景点，避免过于紧凑
- 考虑景点地理位置，相近的排在同一天
- 景点类别多样化（文化/美食/购物/自然/娱乐）
- 每天安排早中晚三餐建议
- 标注每天的住宿酒店

## 输出格式
当所有数据收集完毕后，用 JSON 格式输出最终行程：
```json
{
  "itinerary": [
    {
      "day": 1,
      "date": "Day 1",
      "activities": [{"name": "景点名", "time": "建议时段", "duration": "时长", "notes": "贴士"}],
      "meals": [{"type": "早餐", "suggestion": "推荐"}],
      "hotel": "酒店名",
      "notes": "当天注意事项"
    }
  ],
  "total_budget": {
    "flights": 0,
    "hotels": 0,
    "attractions": 0,
    "meals": 0,
    "total": 0
  },
  "summary": "行程总结（100字以内）"
}
```

请逐步执行，每步告诉用户你在做什么。"""


async def planner_node(state: PlannerState) -> PlannerState:
    """主控 Planner Agent — 分析需求、调用工具、生成行程"""
    llm = get_llm_client()
    client = llm.get_client()
    
    messages = [{"role": "system", "content": PLANNER_SYSTEM_PROMPT}]
    
    # 添加用户消息
    if state.get("messages"):
        messages.extend(state["messages"])
    
    # 提取用户需求信息
    user_context = "当前已知信息：\n"
    if state.get("destination"):
        user_context += f"- 目的地: {state['destination']}\n"
    if state.get("days"):
        user_context += f"- 天数: {state['days']}天\n"
    if state.get("budget"):
        user_context += f"- 预算: {state['budget']}元\n"
    if state.get("preferences"):
        user_context += f"- 偏好: {', '.join(state['preferences'])}\n"
    if state.get("departure_city"):
        user_context += f"- 出发城市: {state['departure_city']}\n"
    
    # 检查是否已有搜索结果
    has_data = False
    if state.get("flights"):
        user_context += "\n已获取航班数据：\n" + json.dumps(state["flights"], ensure_ascii=False, indent=2)
        has_data = True
    if state.get("hotels"):
        user_context += "\n已获取酒店数据：\n" + json.dumps(state["hotels"], ensure_ascii=False, indent=2)
        has_data = True
    if state.get("attractions"):
        user_context += "\n已获取景点数据：\n" + json.dumps(state["attractions"], ensure_ascii=False, indent=2)
        has_data = True
    
    if has_data:
        user_context += "\n请基于以上数据，生成完整的 JSON 格式行程。"
    else:
        user_context += "\n请开始调用工具搜索数据。先搜航班、再搜酒店、最后搜景点。"
    
    messages.append({"role": "user", "content": user_context})
    
    # 调用 LLM（带工具）
    response = await client.chat.completions.create(
        model=llm.get_model(),
        messages=messages,
        tools=TOOLS,
        tool_choice="auto" if not has_data else "none",
        temperature=0.7,
        max_tokens=4096,
    )
    
    msg = response.choices[0].message
    
    # 处理工具调用
    if msg.tool_calls:
        tool_results = []
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            func_args = json.loads(tool_call.function.arguments)
            
            if func_name in TOOL_MAP:
                result = TOOL_MAP[func_name](**func_args)
                tool_results.append({
                    "tool": func_name,
                    "args": func_args,
                    "result": result
                })
                
                # 更新状态
                if func_name == "search_flights":
                    state["flights"] = result
                elif func_name == "search_hotels":
                    state["hotels"] = result
                elif func_name == "search_attractions":
                    state["attractions"] = result
        
        # 将工具结果添加到消息中
        tool_call_messages = []
        for i, tc in enumerate(msg.tool_calls):
            tool_call_messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": json.dumps(tool_results[i]["result"], ensure_ascii=False)
            })
        
        messages.append({"role": "assistant", "content": None, "tool_calls": [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments}
            }
            for tc in msg.tool_calls
        ]})
        messages.extend(tool_call_messages)
        
        # 递归调用 LLM 继续处理
        follow_up = await client.chat.completions.create(
            model=llm.get_model(),
            messages=messages,
            temperature=0.7,
            max_tokens=4096,
        )
        state["messages"] = [{"role": "assistant", "content": follow_up.choices[0].message.content or ""}]
    else:
        state["messages"] = [{"role": "assistant", "content": msg.content or ""}]
    
    return state


def route_after_planner(state: PlannerState) -> Literal["search_node", "summarize_node", END]:
    """路由决策：是否需要继续搜索或生成摘要"""
    if state.get("flights") and state.get("hotels") and state.get("attractions"):
        return "summarize_node"
    if not state.get("flights") or not state.get("hotels") or not state.get("attractions"):
        return "search_node"
    return END


async def search_node(state: PlannerState) -> PlannerState:
    """统一搜索节点 — 并行搜索航班、酒店、景点"""
    destination = state.get("destination", "东京")
    departure = state.get("departure_city", "北京")
    budget = state.get("budget")
    preferences = state.get("preferences")
    days = state.get("days", 5)
    
    # 搜索航班
    if not state.get("flights"):
        flight_budget = budget * 0.5 if budget else None
        state["flights"] = search_flights(departure, destination, flight_budget)
    
    # 搜索酒店
    if not state.get("hotels"):
        hotel_budget = budget * 0.3 / (days or 1) if budget else None
        state["hotels"] = search_hotels(destination, hotel_budget)
    
    # 搜索景点
    if not state.get("attractions"):
        state["attractions"] = search_attractions(destination, preferences)
    
    return state


async def summarize_node(state: PlannerState) -> PlannerState:
    """汇总节点 — 结构化行程 + 预算计算 + LLM 润色"""
    llm = get_llm_client()
    client = llm.get_client()
    
    flights = state.get("flights", [])
    hotels = state.get("hotels", [])
    attractions = state.get("attractions", [])
    destination = state.get("destination", "")
    days = state.get("days", 5)
    travelers = state.get("travelers", 1)
    
    # 1. 构建结构化行程
    itinerary = build_itinerary(
        flights=flights,
        hotels=hotels,
        attractions=attractions,
        days=days,
        destination=destination,
        start_date=state.get("start_date"),
        special_needs=state.get("special_needs"),
    )
    state["itinerary"] = itinerary
    
    # 2. 计算预算
    budget = calculate_budget(
        flights=flights,
        hotels=hotels,
        attractions=attractions,
        days=days,
        travelers=travelers,
    )
    state["total_budget_estimate"] = budget.total
    state["budget_breakdown"] = budget.to_dict()
    
    # 3. 生成 Markdown 行程文本
    flight_info = flights[0] if flights else None
    hotel_info = hotels[0] if hotels else None
    md_itinerary = itinerary_to_markdown(itinerary, destination, flight_info, hotel_info)
    md_budget = budget.to_markdown_table()
    
    # 4. LLM 生成行程总结
    context = f"""以下是根据搜索数据生成的旅行行程，请为这份行程写一个 100 字以内的旅行总结。

## 行程概览
- 目的地: {destination}
- 天数: {days} 天
- 景点数: {len(attractions)} 个
- 预算总计: ¥{budget.total:,.0f}

## 行程亮点
{chr(10).join([f"- Day {plan['day']}: {', '.join([a['name'] for a in plan['activities'][:2]])}" for plan in itinerary])}

请用热情、友好的语气写一段旅行总结，突出行程亮点。"""
    
    try:
        response = await client.chat.completions.create(
            model=llm.get_model(),
            messages=[
                {"role": "system", "content": "你是一个专业的旅行规划师，请为用户写一段简洁的行程总结。"},
                {"role": "user", "content": context}
            ],
            temperature=0.7,
            max_tokens=300,
        )
        summary = response.choices[0].message.content or ""
    except Exception:
        summary = f"为您规划了 {destination} {days} 天旅行，精选 {len(attractions)} 个景点，总预算约 ¥{budget.total:,.0f}。"
    
    # 5. 组装最终输出
    final_output = f"{summary}\n\n{md_budget}\n\n{md_itinerary}"
    state["messages"] = [{"role": "assistant", "content": final_output}]
    
    return state


# ============ 构建 Graph ============

def create_planner_graph() -> StateGraph:
    """创建旅行规划 Agent 工作流"""
    workflow = StateGraph(PlannerState)
    
    # 添加节点
    workflow.add_node("planner_node", planner_node)
    workflow.add_node("search_node", search_node)
    workflow.add_node("summarize_node", summarize_node)
    
    # 设置入口
    workflow.set_entry_point("planner_node")
    
    # 添加边
    workflow.add_conditional_edges(
        "planner_node",
        route_after_planner,
        {
            "search_node": "search_node",
            "summarize_node": "summarize_node",
            END: END,
        }
    )
    
    # 搜索完成后回到 planner 继续
    workflow.add_edge("search_node", "planner_node")
    
    # 摘要完成后结束
    workflow.add_edge("summarize_node", END)
    
    return workflow.compile()


# 全局 graph 实例
planner_graph = create_planner_graph()