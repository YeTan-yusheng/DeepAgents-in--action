import os
from langchain_openai import ChatOpenAI
from deepagents import create_deep_agent
from dotenv import load_dotenv

load_dotenv()

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.2"),
    api_key=os.environ.get("DEEPAGENTS_API_KEY"),
    base_url=os.environ.get("DEEPAGENTS_API_BASE"),
)


def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}"


agent = create_deep_agent(
    model=model,
    tools=[get_weather],
    system_prompt="You are a helpful assistant."
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "北京今天天气怎么样？"}]}
)
print(result["messages"][-1].content)
