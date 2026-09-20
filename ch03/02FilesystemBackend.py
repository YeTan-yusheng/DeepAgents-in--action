"""FilesystemBackend（本地磁盘后端）功能验证脚本

对应 ch03.md「可插拔的存储后端 / FilesystemBackend：本地磁盘存储」。
要验证的结论：
  1. 后端本身就能脱离 agent 使用，不需要 LLM、不需要 LangGraph 运行时
  2. 文件落在磁盘上，state 里连 files 这个键都不存在
  3. 不需要 checkpointer，也能跨轮 / 跨线程 / 跨 agent 实例读回文件
  4. 虚拟路径解析到哪个真实目录，由 root_dir 决定；换 root_dir = 换了一个文件系统
"""
import os

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, StateBackend

from utility import get_model, ask, hr

ROOT_DIR = "."                    # 磁盘上的真实根目录（相对 ch03）
NOTE_PATH = "/notes/test.md"      # agent 看到的虚拟路径
NOTE_BODY = "2026年9月20日是星期天"

def disk_files(sub: str = "notes") -> list[str]:
    """磁盘上的真实文件列表。FilesystemBackend 的「文件系统」就是这个，用 os.walk 自己就能查。"""
    base = os.path.join(ROOT_DIR, sub)
    return sorted(
        os.path.relpath(os.path.join(root, name), ROOT_DIR).replace("\\", "/")
        for root, _, names in os.walk(base)
        for name in names
    )


def seen_in_trace(out: dict, needle: str) -> bool:
    """工具返回或模型回答里是否出现过某段内容。"""
    return any(needle in str(m.content) for m in out["messages"])


# 实验 0
hr("实验 0：后端能脱离 agent 单独用吗？（不经 LLM，秒级、确定性）")
backend = FilesystemBackend(root_dir=ROOT_DIR, virtual_mode=True)
backend.write(NOTE_PATH, NOTE_BODY)                 # 相当于「人」直接往磁盘写文件
print(f"  read() 读回  : {backend.read(NOTE_PATH).file_data['content']!r}")
print(f"  ls('/notes') : {[e['path'] for e in backend.ls('/notes').entries]}")
print("  => 期望: FilesystemBackend 直接可用")

# 实验 1
hr("实验 1：agent 能读到「人」写在磁盘上的文件吗？")
agent = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=FilesystemBackend(root_dir=ROOT_DIR, virtual_mode=True),
    # 注意：这里故意不传 checkpointer
)

out1 = ask(agent, f"读取 {NOTE_PATH}，把内容原样告诉我。", "t-1")
print(f"\n  读到了「人」写的内容吗: {seen_in_trace(out1, NOTE_BODY)}")
print("  => 期望: 读得到。这个文件从没进过 state，agent 只是读了磁盘")

# 实验 2
hr("实验 2：agent 写回磁盘后，state 里有文件吗？")
out2 = ask(agent, f"请调用 write_file，把「实验二更新：{NOTE_BODY}」写入 {NOTE_PATH}。", "t-1")
print(f"\n  out2 的顶层键        : {sorted(out2.keys())}")
print(f"  out2.get('files')    : {out2.get('files')}")
print(f"  磁盘上的真实文件      : {disk_files()}")
print("  => 期望: 只有 messages，没有 files 键；磁盘上有 notes/test.md")

# 实验 3
hr("实验 3：新 agent 实例 + 新 thread_id + 不传 checkpointer，还读得到吗？")
agent2 = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=FilesystemBackend(root_dir=ROOT_DIR, virtual_mode=True),
)
out3 = ask(agent2, f"读取 {NOTE_PATH}，如果读不到就说文件不存在。", "brand-new-thread")
print(f"\n  新实例新线程读到了吗: {seen_in_trace(out3, NOTE_BODY)}")
print("  => 期望: 读得到。这就是磁盘后端和 StateBackend 的分水岭")

