import os
from typing import Literal
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

tavily_client = TavilyClient(
    api_key=os.environ.get("TAVILY_API_KEY"),
)


def internet_search(
        query: str,
        max_results: int = 5,
        topic: Literal["general", "news", "finance"] = "general",
        include_raw_content: bool = False,
):
    """Run a web search for the given query.

       Args:
           query: The search query string.
           max_results: Maximum number of results to return.
           topic: The topic category for the search.
           include_raw_content: Whether to include raw page content.
       """
    return tavily_client.search(
        query,
        max_results=max_results,
        include_raw_content=include_raw_content,
        topic=topic,
    )


model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.2"),
    api_key=os.environ.get("DEEPAGENTS_API_KEY"),
    base_url=os.environ.get("DEEPAGENTS_API_BASE"),
)

research_instructions = """你是一位专业的研究员。
你的工作是进行深入研究，然后撰写一份完整的研究报告。

你可以使用 internet_search 工具搜索互联网获取信息。
"""

agent = create_deep_agent(
    model=model,
    tools=[internet_search],
    system_prompt=research_instructions,
    middleware=[TodoListMiddleware()],
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "什么是 LangGraph？"}]}
)

print(result["messages"][-1].content)
