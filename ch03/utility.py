from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# 加载模型
def get_model():
    return ChatOpenAI(
        model=os.environ.get("MODEL_NAME", "glm-5.2"),
        api_key=os.environ.get("DEEPAGENTS_API_KEY"),
        base_url=os.environ.get("DEEPAGENTS_API_BASE"),
    )

# 跑一轮对话，并在控制台打印这一轮的工具调用轨迹。
def ask(agent, text: str, thread_id: str) -> dict:
    out = agent.invoke(
        {"messages": [{"role": "user", "content": text}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    for msg in out["messages"]:
        kind = type(msg).__name__
        for call in getattr(msg, "tool_calls", None) or []:
            print(f"  >> {kind} 调用工具 {call['name']}  参数={call['args']}")
        if kind == "ToolMessage":
            print(f"  << 工具返回 {msg.name}: {str(msg.content)[:70]!r}")
        elif kind == "AIMessage" and msg.content:
            print(f"  -- 模型回答: {str(msg.content)[:100]!r}")
    return out

# 打印分隔线
def hr(title: str) -> None:
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)