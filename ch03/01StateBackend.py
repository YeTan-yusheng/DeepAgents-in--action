"""StateBackend（默认后端）功能验证脚本

对应 ch03.md「可插拔的存储后端 / StateBackend（默认）：临时存储」
三条结论：
  1. 文件存在 LangGraph 的 Agent State 里（result["files"]），不是磁盘上
  2. 同一个对话线程内持久化（同一个 thread_id 的第二轮还记得第一轮写的文件）
  3. 换一个 thread 就没了（新 thread_id 里读同一路径 -> 文件不存在）
"""
import os

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, StateBackend
from langgraph.checkpoint.memory import MemorySaver

from utility import get_model, ask, hr

NOTE_PATH = "/notes/test.md"
NOTE_BODY = "2026年9月20日是星期天"


def state_files(out: dict) -> list[str]:
    """StateBackend 把文件写在 state 的 files 键里。"""
    return sorted((out.get("files") or {}).keys())


model = get_model()
agent = create_deep_agent(
    model=model,
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=StateBackend(),  # 默认后端，这里显式写出来
    checkpointer=MemorySaver(),  # 没有 checkpointer 就没有「同一线程持久化」
)

# 实验 1
hr("实验 1：文件到底写到哪里去了？")
out1 = ask(agent, f"请调用 write_file 工具，把「{NOTE_BODY}」写入 {NOTE_PATH}。", "t-1")
files1 = state_files(out1)
print(f"\n  result 里的顶层键: {sorted(out1.keys())}")
print(f"  state['files'] 里存了: {files1}")
print(f"  磁盘上存在 notes/test.md 吗: {os.path.exists('notes/test.md')}")
print("  => 期望: 临时文件存储里有 /notes/test.md，磁盘上没有文件")

# 实验 2
hr("实验 2：同一个 thread 内，多轮对话还认得这个文件吗？")
out2 = ask(agent, f"现在读取 {NOTE_PATH}，把内容原样告诉我。", "t-1")
hit = any(str(m.content).find(NOTE_BODY[:6]) >= 0 for m in out2["messages"])
print(f"\n  第二轮 state['files']: {state_files(out2)}")
print(f"  文件名里的关键字出现在工具返回/回答中: {hit}")
print("  => 期望: 文件还在，agent 能读出第一轮写的内容")

# 实验 3
hr("实验 3：换一个 thread_id（相当于关掉对话重开），文件还在吗？")
out3 = ask(agent, f"读取 {NOTE_PATH}，如果读不到就直接说文件不存在。", "t-2")
print(f"\n  新线程 state['files']: {state_files(out3)}")
print("  => 期望: files 为空，agent 报告文件不存在")
