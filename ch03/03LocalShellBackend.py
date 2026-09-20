"""LocalShellBackend（本地命令执行后端）功能验证脚本

对应 ch03.md「可插拔的存储后端 / LocalShellBackend：本地命令执行」。

⚠️ 安全提示：这个后端会在本机真实执行 shell 命令，没有沙箱、没有进程隔离、没有资源限制。
   只在本机的学习/开发环境使用。本脚本里全部使用只读、无副作用的命令。

要验证的结论：
  1. LocalShellBackend = FilesystemBackend + 命令执行：backend 换成它之后，agent 会多出一个 execute 工具
  2. 文件操作与 FilesystemBackend 完全一致：文件落磁盘，state 里没有 files 键
  3. 安全陷阱：virtual_mode=True 只约束文件工具，不约束 shell —— shell 的工作目录是 root_dir，
     但一条 `cd ..` 就能跑出去
"""
import os
import shutil

from deepagents import create_deep_agent
from deepagents.backends import LocalShellBackend

from utility import get_model, ask, hr 

ROOT_DIR = "_shell_demo"          # shell 的工作目录 = 文件工具的真实根目录
NOTE_PATH = "/notes/shell.md"     # agent 看到的虚拟路径

def disk_files(sub: str = "notes") -> list[str]:
    """磁盘上的真实文件列表，用来证明文件工具写到了 root_dir 里。"""
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
shutil.rmtree(ROOT_DIR, ignore_errors=True)
os.makedirs(ROOT_DIR, exist_ok=True)

backend = LocalShellBackend(root_dir=ROOT_DIR, virtual_mode=True)
print(f"  id（每个实例唯一）    : {backend.id}")
print(f"  echo 'hello' 的输出   : {backend.execute('echo hello-from-shell').output.strip()!r}")
print(f"  cd 的输出（= 工作目录）: {backend.execute('cd').output.strip()!r}")
print(f"  cd .. && cd 的输出    : {backend.execute('cd .. && cd').output.strip()!r}")
print(f"  PATH 的内容           : {backend.execute('echo %PATH%').output.strip()!r}")
print(f"  python --version 的退出码: {backend.execute('python --version').exit_code}  <- 外部命令跑不起来")
print("  => 期望: 裸调可用；cwd 就是 root_dir；但 `cd ..` 能跑出去，且 PATH 近乎为空")

# 实验 1
hr("实验 1：agent 会多出一个 execute 工具吗？它能和文件工具配合吗？")
agent = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个本地开发助手，可以执行命令，也可以读写文件",
    backend=LocalShellBackend(root_dir=ROOT_DIR, virtual_mode=True),
    # 注意：依然不传 checkpointer
)
out1 = ask(
    agent,
    "请先用 execute 工具执行 `echo hello-from-execute` 拿到输出，"
    f"再用 write_file 把这个输出写入 {NOTE_PATH}。",
    "t-1",
)
print(f"\n  out1 的顶层键        : {sorted(out1.keys())}")
print(f"  out1.get('files')    : {out1.get('files')}")
print(f"  磁盘上的真实文件      : {disk_files()}")
written = os.path.join(ROOT_DIR, "notes", "shell.md")
if os.path.exists(written):
    with open(written, encoding="utf-8") as fp:
        print(f"  文件内容              : {fp.read().strip()!r}")
else:
    print("  文件没写出来")
print("  => 期望: 两个工具都被调用；state 里没有 files 键；文件落在 _shell_demo/notes/ 下")

# 实验 2
hr("实验 2：virtual_mode=True 能挡住 shell 吗？")
out2 = ask(agent, "请用 execute 工具执行命令 `cd .. && cd`，把命令输出原样告诉我。", "t-1")
escaped = any(str(m.content).find("ch03") >= 0 for m in out2["messages"])
print(f"\n  输出里出现了 root_dir 之外的上层目录吗: {escaped}")
print("  => 期望: 出现。virtual_mode 只管文件工具，agent 可以用 shell 绕过它")
