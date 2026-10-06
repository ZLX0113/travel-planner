# AI 旅行规划师

基于大模型 + 多智能体编排的智能旅行规划系统。输入目的地、日期、出行人数和偏好，系统自动检索实时航班、酒店、景点、餐饮数据，生成逐日行程与预算明细，并支持「省钱版 / 舒适版 / 网红打卡版」多方案对比。

> 目前仅支持**国内目的地**。景点、酒店、餐饮、路线、天气均来自高德地图 Web 服务实时查询；未接入实时航班接口的航线由大模型生成参考航班，并在界面上明确标注"参考航班，非实时数据"。

## 功能特性

| 功能 | 说明 |
|---|---|
| **单方案行程生成** | 逐日时间线（早/午/晚三餐 + 景点 + 景点间通勤 + 住宿），每天主题不同、景点不重复 |
| **多版本方案对比** | 省钱版 / 舒适版 / 网红打卡版，三套方案的景点、酒店、航班、餐标各不相同，可查看预算对比表和每日行程差异，也能点进单个版本看完整细节 |
| **在线实时数据** | 景点、餐饮、酒店、驾车/步行/公交路线、天气全部实时查询，字段随数据源返回自适应渲染，不写死 |
| **国内全量地名** | 目的地支持任意国内地名——市级、区县、乡镇、景区（如乌镇、喀纳斯、东极岛），境外一律拒绝 |
| **登录注册与记忆** | JWT 鉴权，偏好设置（旅行风格/交通/住宿/节奏）与历史行程按用户隔离存储，下次规划自动回填 |
| **地图可视化** | Leaflet + 高德瓦片，逐日绘制标记与路线；点击景点、餐厅、酒店时地图自动定位到对应地点 |
| **特殊人群关怀** | 勾选儿童 / 老人 / 孕妇 / 无障碍需求后，自动下调每日景点数、插入午休节点并给出针对性提醒 |
| **PDF 导出** | 一键把当日行程导出为 PDF |

## 技术栈

**后端**

- FastAPI 0.115 + Uvicorn
- Pydantic v2（请求/响应模型校验）
- SQLModel + SQLite（用户、偏好、历史行程；可通过 `DATABASE_URL` 切换 MySQL）
- PyJWT（HS256）+ bcrypt
- httpx（调用高德 Web 服务）
- LangGraph（多智能体工作流编排）
- OpenAI SDK（兼容 OpenAI / DeepSeek 等 OpenAI 格式的接口）

**前端**

- React 18 + TypeScript 5.5 + Vite 5.4
- Tailwind CSS 3.4
- React Router v7
- Leaflet 1.9 + react-leaflet（高德地图瓦片）
- html2pdf.js

## 系统架构

### 1. 行程生成工作流（LangGraph）

`backend/app/agents/planner_graph.py` 用 `StateGraph` 编排三个节点：

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
  planner_node ──► route_after_planner ──► search_node ─┘
 （主控 Agent）           │
                         │ 航班 + 酒店 + 景点 都已拿到
                         ▼
                  summarize_node ──► END
```

- `planner_node`：主控 Agent。把目的地、天数、预算、偏好以及已检索到的数据拼成上下文交给大模型，由它决定下一步该调哪些工具
- `search_node`：统一搜索节点，检索航班、酒店、景点
- `route_after_planner`：条件路由。航班 / 酒店 / 景点**三类数据齐了就进入汇总**，缺任意一类就回到 `search_node` 继续检索
- `summarize_node`：构建逐日行程、计算预算明细、生成文字总结

### 2. 可插拔数据源

`backend/app/tools/data_source.py` 定义了抽象基类 `TravelDataSource` 和注册表：

- `AmapDataSource`：高德在线数据源（景点/餐饮/酒店 POI、路线、天气）
- `LocalJsonDataSource`：`backend/app/data/*.json` 离线种子数据
- `auto` 策略：配了高德 Key 就走在线，否则自动回退离线，任何外部接口不可用都不会中断主流程

新增数据源只需实现接口并注册，上层业务代码不用改。

### 3. 国内地名解析

`backend/app/core/cities.py` 采用两级校验：

1. 本地白名单（含别名），离线可用，同时作为前端输入联想的数据源
2. 白名单未命中时走高德行政区划 / 输入提示接口在线校验，**只接受市、区县、乡镇、景区级结果**

境外地名通过黑名单 + 行政区划接口双重拦截。解析结果会额外给出 adcode 作为检索键——高德的 POI / 天气接口对乡镇级地名（如"乌镇"）会退化成默认城市，必须用 adcode 才能正确定位。

### 4. 设计原则

**必须精确的数据交给确定性代码，自由文本才交给 LLM。** 航班价格、门票、酒店房价、路线时长这类数字全部来自接口或确定性计算，大模型只负责意图理解、行程编排和文案总结，以降低幻觉对结果的影响。

## 目录结构

```
.
├── backend/
│   ├── app/
│   │   ├── agents/          # LangGraph 工作流（planner_graph / state）
│   │   ├── core/            # 配置、数据库、鉴权、地名解析
│   │   ├── data/            # 离线种子数据（景点/酒店/航班 JSON）
│   │   ├── models/          # SQLModel 表模型 + Pydantic 请求响应模型
│   │   ├── routers/         # auth / user / trip / chat / search 接口
│   │   ├── tools/           # 数据源、行程构建、预算计算、高德客户端
│   │   └── main.py          # FastAPI 入口
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── api/             # 带 token 的请求封装
│       ├── components/      # 表单、时间线、地图、卡片等
│       ├── constants/       # 城市、偏好、预算档位
│       ├── context/         # 登录态
│       ├── pages/           # 首页/规划/行程/对比/历史/登录
│       └── utils/
├── api/index.py             # Vercel Serverless 入口
├── start.bat                # Windows 一键启动前后端
└── vercel.json
```

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+

### 1. 配置后端环境变量

```bash
cd backend
cp .env.example .env
```

编辑 `backend/.env`：

```ini
# OpenAI 兼容接口（也可填 DeepSeek 等）
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

# 高德地图 Web 服务 Key（选「Web 服务」类型）
# 申请：https://console.amap.com/dev/key/app
AMAP_KEY=

# 数据源：auto / amap / local_json
DATA_SOURCE=auto
# 航班来源：auto（在线优先，无数据时用大模型生成参考航班）/ llm / local
FLIGHT_SOURCE=auto
```

> `AMAP_KEY` 不填也能跑，程序会自动回退到 `backend/app/data/` 里的离线种子数据，只是数据不实时。

### 2. 启动后端

```bash
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- 接口文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

首次启动会自动建表（SQLite，默认落在 `backend/data/app.db`）。

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173 ，注册账号后即可使用（规划相关接口需要登录）。

### 一键启动（Windows）

项目根目录双击 `start.bat`，会同时拉起前后端并打开浏览器。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/register` `/api/auth/login` | 注册 / 登录，返回 JWT |
| GET | `/api/auth/me` | 当前用户信息 |
| GET/PUT | `/api/user/preferences` | 读取 / 保存偏好记忆 |
| GET/POST | `/api/user/trips` | 历史行程列表 / 保存 |
| GET/DELETE | `/api/user/trips/{id}` | 历史行程详情 / 删除 |
| POST | `/api/trip/plan` | 生成单份行程（SSE 流式返回进度） |
| POST | `/api/trip/versions` | 生成三套对比方案 |
| POST | `/api/trip/modify` | 按指令局部调整已有行程 |
| GET | `/api/cities` | 支持的城市分组 |
| GET | `/api/cities/suggest` | 目的地输入联想 |
| GET | `/api/search?q=` | 按关键词查目的地概览 / 景点 / 酒店 |
| POST | `/api/chat` | 对话式规划 |

## 已知限制

- 仅支持国内目的地，境外城市会被明确拒绝
- 高德 POI 只覆盖中国大陆，且个人 Key 有 QPS 限制，短时间大量请求可能被限流
- 实时航班与酒店房价接口在国内需企业资质，当前航班为**参考数据**，酒店价格为**参考估价**，界面上均有标注
- 门票、开放时间等字段在高德侧缺失时显示"实时票价待查"，不臆造数值

## 部署

仓库内含 `vercel.json` 与 `api/index.py`，前端静态资源 + 后端 Serverless 函数可一并部署到 Vercel；后端环境变量需在平台侧配置。详细步骤见 `DEPLOY.md`。
