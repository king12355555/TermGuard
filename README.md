# TermGuard 术语卫士 —— 游戏本地化术语一致性智能质检助手

> 面向 ECI 创思立信「AI 产品助理」岗位的实战项目。
> 把译员痛点（术语上下文不一致、特定语境校验难）变成可落地的自动化 QA 工具。

## 一、解决什么问题

本地化 QA 中最耗人力的场景：

| 译员/QA 痛点 | 本工具做法 |
|---|---|
| 术语译法不统一（同词不同译法、跨文件打架） | 术语库驱动的一致性扫描 + 跨行不一致提示 |
| 术语有"语境"（Level→等级 vs Level 3→第 3 章） | 上下文限定词条，长词条优先匹配 |
| 占位符/数字被改丢（{player}、[E]、伤害数值） | 规则层精确比对，零成本高确定 |
| 漏译、空译文、截断 | 规则层 + 大模型复核双层兜底 |
| 特定语境校验难（语域、误译、信息遗漏） | 可选接入 DeepSeek 等 LLM 做语义复核 |

## 二、架构与分层思想

```
前端 Vue3 (dist 由 FastAPI 托管, 单端口 8010)
   │  POST /api/check
后端 FastAPI
   ├─ 规则层 checkers/rules.py    快 · 确定性强（占位符/数字/术语/漏译/一致性）
   └─ LLM 层 checkers/llm_check.py 慢 · 抓语义（语境/语域/误译，无 Key 自动降级）
数据：内置游戏本地化 Demo（26 句 / 埋 14 处典型错误 / 术语库 12 条）
```

分层设计体现岗位要求的**实用主义**：确定性问题用规则（免费、可解释、快），语义问题才交给大模型——"用最合适的工具解决当前问题"。

## 三、Demo 内置的典型错误（面试讲解用）

26 句游戏文案中埋入 14 处问题，覆盖 7 类：
术语误译（HP→健康点、Cooldown→CD）、术语跨行不一致（Cloud Sync、Quest）、
上下文限定词条用错（Level 3→等级3 应为第3章）、专有名词被意译（GvG、Legionnaire's Blade）、
占位符丢失（{player}、[E]）、数字改写（50→5000、10%→100%）、空译文/未翻译/长句截断。

自测脚本：`tests/selftest.py` —— 输出"漏报/误报"校验，当前 **零漏报、零误报**。

## 四、技术栈

- 后端：Python · FastAPI · Pydantic · openai SDK（DeepSeek 兼容接口）
- 前端：Vue3 · Vite · ECharts（暗色游戏本地化 UI）
- 规则引擎：正则精确匹配（占位符/数字）+ 术语词条区间去重匹配 + 跨行一致性
- 大模型：DeepSeek API，JSON 结构化输出，10 句/批，温度 0.1

## 五、快速启动

```bash
# 1. 首次：创建虚拟环境并安装后端依赖
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 2. 前端构建（代码已改动时才需要）
cd ../frontend
npm install
npm run build

# 3. 启动（服务 http://127.0.0.1:8010，同时托管前端）
cd ../backend
.venv\Scripts\python main.py
```

**或者直接双击 `start.bat`**（自动打开浏览器）。

开发模式：后端跑 `python main.py`，前端 `npm run dev`（5173 端口，/api 已代理到 8010）。

## 六、可选：启用 AI 语境复核

界面左侧「③ AI 语境复核」开启后填写：
- API Key：DeepSeek 官网获取 `sk-...`（仅存本地浏览器，不落盘）
- Base URL：`https://api.deepseek.com`（默认）
- 模型：`deepseek-chat`（默认）

不配置 Key 时自动降级为纯规则检查，Demo 演示不受影响（规则层已覆盖全部内置错误）。

## 七、项目结构

```
TermGuard/
├─ backend/
│  ├─ main.py            # FastAPI 入口 + 前端托管
│  ├─ sample_data.py     # 内置游戏本地化示例（含坑）
│  └─ checkers/
│     ├─ rules.py        # 规则检查引擎（术语/占位符/数字/漏译/一致性）
│     └─ llm_check.py    # LLM 语境复核（可选）
├─ frontend/
│  └─ src/
│     ├─ App.vue
│     └─ components/     # DataPanel / ReportPanel / GlossaryDrawer
├─ tests/selftest.py     # 引擎自测（漏报/误报校验）
├─ start.bat             # 一键启动
└─ README.md
```
