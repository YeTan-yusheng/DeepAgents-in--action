"""
DeepAgents 子 Agent 示例：研究 + 分析双角色协作

本演示创建两个职责不同的子 Agent，并展示 DeepAgents 的上下文隔离机制。

上下文隔离模式（见 deepagents.middleware.subagents.SubAgent.mode）：
  - mode="isolated"  （默认）：子 Agent 只接收到主 Agent 传入的任务描述，
    看不见主 Agent 的历史对话。适合纯粹的"一次性"委派。
  - mode="fork"               ：子 Agent 继承父 Agent 的完整对话历史和状态，
    就像对话"分叉"了一样。适合需要上下文连贯的场景。
"""

import os
from datetime import date
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents.middleware import TodoListMiddleware
from tavily import TavilyClient
from deepagents import create_deep_agent

load_dotenv()


model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.1"),
    api_key=os.environ.get("DEEPAGENTS_API_KEY"),
    base_url=os.environ.get("DEEPAGENTS_API_BASE"),
)

tavily_client = TavilyClient(os.environ.get("TAVILY_API_KEY"))


def internet_search(query: str, max_results: int = 5) -> dict:
    """搜索互联网获取最新信息。"""
    return tavily_client.search(query, max_results=max_results)


def calculator(expression: str) -> dict:
    """执行简单的数学计算并返回结果。"""
    try:
        result = eval(expression, {"__builtins__": {}})
        return {"expression": expression, "result": result}
    except Exception as e:
        return {"expression": expression, "error": str(e)}

researcher_system_prompt = """你是一名专业的研究助理。你的职责是：
1. 使用 internet_search 工具搜索相关主题
2. 汇总多方来源的信息，整理出结构化的发现
3. 只返回有来源支撑的事实，避免臆测
4. 最终输出控制在 400 字以内，条理清晰

重要约束：
- 不要在最终回答中粘贴原始搜索结果 JSON
- 使用分点列出 3-5 个关键发现
- 每个发现注明信息来源"""

analyst_system_prompt = """你是一名数据分析专家。你的职责是：
1. 对提供的数据/事实进行逻辑分析
2. 使用 calculator 工具辅助量化推理（如增长率、占比等）
3. 提取 3-5 个核心洞察，用简洁语言表达
4. 最终输出控制在 300 字以内

重要约束：
- 聚焦于"所以呢？"——说明数据意味着什么
- 如果需要数值支撑，使用 calculator 而不是心算
- 避免重复原始数据，着重解读"""


subagents = [
    {
        "name": "researcher",
        "description": "对指定主题进行网络搜索并返回结构化研究摘要",
        "system_prompt": researcher_system_prompt,
        "tools": [internet_search],
    },
    {
        "name": "analyst",
        "description": "对给定的事实或数据进行分析，提取核心洞察",
        "system_prompt": analyst_system_prompt,
        "tools": [calculator],
    },
]



main_system_prompt = f"""你是一位项目协调者。面对复杂任务时，按以下策略执行：

1. 先用 write_todos 制定计划，拆解成可独立完成的子步骤
2. 将"收集信息"类任务委派给 researcher（它会自行搜索并返回摘要）
3. 将"解读分析"类任务委派给 analyst（它会提炼洞察，可做简单计算）
4. 将多份子 Agent 的输出整合成一份连贯的最终回答

关于委派的重要说明：
- 每个子 Agent 都是独立运行的，你只需要在 description 参数中写清任务，
  它们看不到你和用户的完整对话历史
- 子 Agent 返回的就是最终成果，不要再次调用同一子 Agent 做相同的事
- researcher 和 analyst 可以并行委派给它们各自独立工作

今天日期：{date.today().isoformat()}"""


agent = create_deep_agent(
    model=model,
    middleware=[TodoListMiddleware()],
    system_prompt=main_system_prompt,
    subagents=subagents,
)


result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": (
                    "请调研 Agent 开发领域的三大 Harness 框架 "
                    "（Deep Agents、Claude Agent SDK、Codex SDK），"
                    "先让 researcher 分别搜索它们的最新动态，"
                    "再让 analyst 对比它们的核心能力差异，"
                    "最后写一份简要分析报告。"
                ),
            }
        ]
    }
)

print("\n" + "=" * 60)
print("主 Agent 最终回答：")
print("=" * 60)
print(result["messages"][-1].content)