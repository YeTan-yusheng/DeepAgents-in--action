import os
from sys import path

from dotenv import load_dotenv
from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI
from deepagents.backends.filesystem import FilesystemBackend
load_dotenv()


backend = FilesystemBackend(root_dir="./",virtual_mode=True)

model = ChatOpenAI(
    model=os.environ.get("MODEL_NAME", "glm-5.1"),
    api_key=os.environ.get("DEEPAGENTS_API_KEY"),
    base_url=os.environ.get("DEEPAGENTS_API_BASE"),
)


agent = create_deep_agent(
    model=model,
    backend=backend,
    skills=["/hello-skill/"],
)

result = agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": "测试运行hello-skill",
            }
        ]
    }
)

print(result["messages"][-1].content)