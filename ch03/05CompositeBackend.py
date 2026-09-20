"""CompositeBackend（按路径前缀路由的混合后端）功能验证脚本

对应 ch03.md「可插拔的存储后端 / 5.CompositeBackend：混合路由」。

要验证的结论：
  1. 同一个 write() 接口按路径前缀分派：/memories/ 之外落 default（StateBackend，临时），
     /memories/ 之下落 StoreBackend（持久）—— 一个 agent，两套存储
  2. 路由前缀是「虚拟挂载点」：存的时候前缀被剥掉，后端只看到后缀；
     read/ls/glob/grep 再把前缀拼回来，所以外面看起来像一棵完整的树
  3. ls("/") 只多出一个挂载点目录，不会把路由里的文件摊到根上
  4. 两个边界：/memoriesx/ 不会被 /memories/ 吃掉；两个路由指向同一个后端会撞车

⚠️ 与 01~04 的区别：本脚本里有两条路径同时存在，每个 print 都要能回答
   「这个文件落在哪一边」——state / 磁盘 / store 三处对照。

⚠️ 关于 execute：它是唯一不按路径路由的操作（永远走 default 后端），
   所以想用混合路由 + 命令执行，default 必须是沙箱后端。本脚本不演示它（见 03）。

⚠️ 关于 FilesystemBackend 的 grep：deepagents 0.7.14 里它 shell 出 ripgrep 时没给
   subprocess.Popen 指定 encoding，管道按本机 locale 解码；在中文 Windows（cp936）上
   搜含中文的文件会直接 UnicodeDecodeError。实验 3 因此改用全内存的 composite。
"""
import os
import shutil

from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, FilesystemBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore

from utility import get_model, ask, hr

ROOT_DIR = "_composite_demo"        # 裸调演示里 default 后端落盘的地方
NAMESPACE = ("local-user",)         # 共享 store 的命名空间（本地兜底值，见 04）
SCRATCH_NS = ("scratch",)           # 内存版 composite 里 default 那份的命名空间
PLAN_PATH = "/workspace/plan.md"    # 不匹配任何路由 -> default（StateBackend，临时）
PREF_PATH = "/memories/prefs.txt"   # 匹配 /memories/ -> 路由到 StoreBackend（持久）
TEMP_PATH = "/notes/temp.md"        # 裸调演示里的非路由路径 -> 磁盘
MEMO_PATH = "/memories/note.md"     # 裸调演示里的路由路径 -> store
PLAN_BODY = "计划：把 ch03 的六个后端都跑一遍"
PREF_BODY = "偏好：笔记一律写中文"
NOTE_BODY = "2026年9月20日是星期天"

store = InMemoryStore()             # agent 和裸调演示共用这一个 store

def user_namespace(user_id: str):
    """04 里的 namespace 工厂：线上按用户隔离，本地兜底成固定 user_id。"""
    return lambda rt: (rt.server_info.user.identity,) if rt.server_info else (user_id,)

def ls_paths(result) -> list[str]:
    """把 LsResult 压成一串路径，省得每次写 e['path']。"""
    return [e["path"] for e in result.entries]

def state_files(out: dict) -> list[str]:
    """StateBackend 把路由到它的文件写在 state 的 files 键里。"""
    return sorted((out.get("files") or {}).keys())

def store_keys(namespace: tuple[str, ...] = NAMESPACE) -> list[str]:
    """store 里真实躺着哪些 key —— 注意这里看到的是剥掉路由前缀之后的路径。"""
    return sorted(item.key for item in store.search(namespace))

def disk_files(sub: str = "") -> list[str]:
    """_composite_demo 下真实的磁盘文件。"""
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

try:
    CompositeBackend(default=StateBackend(), routes={}).ls("/")
except RuntimeError as exc:
    print(f"  A) 拿 StateBackend 当 default，图外裸调: RuntimeError({str(exc)[:42]}...)")

bare = CompositeBackend(
    default=FilesystemBackend(root_dir=ROOT_DIR, virtual_mode=True),   # 裸调演示换成磁盘后端
    routes={"/memories/": StoreBackend(namespace=lambda rt: NAMESPACE, store=store)},
)
print(f"  B) write({TEMP_PATH!r})  -> 返回 {bare.write(TEMP_PATH, NOTE_BODY).path!r}")
print(f"     write({MEMO_PATH!r}) -> 返回 {bare.write(MEMO_PATH, NOTE_BODY).path!r}")
print(f"     磁盘上的文件        : {disk_files()}")
print(f"     store 里的 key      : {store_keys()}")
print(f"     ls('/')             : {ls_paths(bare.ls('/'))}")
print(f"     ls('/memories/')    : {ls_paths(bare.ls('/memories/'))}")
print(f"     read(MEMO_PATH)     : {bare.read(MEMO_PATH).file_data['content']!r}")
print("  => 期望: 一个 write() 接口、两个落点；store 里的 key 是 '/note.md'（前缀被剥掉了）；")
print("     ls('/') 只多出一个挂载点 /memories/，路由里的文件不会摊到根上")
print("     （A 说明 StateBackend 离不开图，所以裸调演示要把 default 换成磁盘后端）")

# 实验 1
hr("实验 1：按文档写法搭一个（default=StateBackend + /memories/ 路由），两条路径会分家吗？")
agent = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=CompositeBackend(
        default=StateBackend(),                                                      # 默认：临时存储
        routes={"/memories/": StoreBackend(namespace=user_namespace("local-user"))},  # 不给 store，靠 get_store()
    ),
    store=store,
    # 注意：依然不传 checkpointer
)
out1 = ask(
    agent,
    f"依次调用两次 write_file 工具：先把「{PLAN_BODY}」写入 {PLAN_PATH}，"
    f"再把「{PREF_BODY}」写入 {PREF_PATH}。",
    "t-1",
)
print(f"\n  同一轮里写了两条路径后 state['files']: {state_files(out1)}")
print(f"  store 里的 key                       : {store_keys()}")
print(f"  _composite_demo 里的磁盘文件          : {disk_files()}")
print("  => 期望: state 里只有 /workspace/plan.md；/memories/prefs.txt 根本没进 state，")
print("     而是以 '/prefs.txt' 的名字进了 store；磁盘上两边都没有")
print("     （两条路径必须写在同一次 invoke 里，否则没有 checkpointer，state 每次都从空开始）")

# 实验 2
hr("实验 2：换一个 thread_id，两条路径上的文件各剩几条命？")
out2 = ask(agent, f"分别读取 {PREF_PATH} 和 {PLAN_PATH}，逐个把结果告诉我。", "brand-new-thread")
print(f"\n  读到 {PREF_PATH} 的内容吗 : {seen_in_trace(out2, PREF_BODY[:6])}")
print(f"  读到 {PLAN_PATH} 的内容吗  : {seen_in_trace(out2, PLAN_BODY[:6])}")
print(f"  新线程 state['files']             : {state_files(out2)}   <- 键还在，但是空的")
print("  => 期望: 路由到 store 的读得到，落 state 的没了 —— 这就是混合路由的意义：")
print("     临时文件随线程消失，长期记忆跨会话留存")
print("     （注意 files 键本身不会消失：它由 default 那个 StateBackend 带进 state schema，")
print("      跟 04 里清一色 StoreBackend 时「连 files 键都没有」正好成对照）")

# 实验 3
hr("实验 3：glob / grep 是怎么跨后端聚合的？（纯后端调用，不花 LLM）")
# ⚠️ 这里故意换成「两份都是 store」的 composite。原因是一个库级坑：
#    FilesystemBackend.grep 会 shell 出 ripgrep，而 deepagents 0.7.14 里那条
#    subprocess.Popen(..., text=True) 没写 encoding，管道就按本机 locale 代码页解码
#    （中文 Windows = cp936），ripgrep 吐的却是 UTF-8 —— 只要匹配到的行里有中文，
#    就 UnicodeDecodeError: 'gbk' codec can't decode byte ...。
#    换掉 default 之后全程不碰 ripgrep，任何 locale 下输出都一致。
#    （glob 不受影响，它是纯 Python 实现；只有 grep 会 shell 出去。）
mem = CompositeBackend(
    default=StoreBackend(namespace=lambda rt: SCRATCH_NS, store=store),                 # 临时那份
    routes={"/memories/": StoreBackend(namespace=lambda rt: NAMESPACE, store=store)},   # 持久那份
)
mem.write(TEMP_PATH, NOTE_BODY)
mem.write(MEMO_PATH, NOTE_BODY)
print(f"  两份落点                    : {store_keys(SCRATCH_NS)} / {store_keys(NAMESPACE)}")
for pattern in ("*.md", "/*.md", "/notes/*.md", "/memories/*.md"):
    print(f"  glob({pattern!r:<16}): {[m['path'] for m in mem.glob(pattern).matches]}")
print(f"  grep('2026', path='/')        : {[m['path'] for m in mem.grep('2026', path='/').matches]}")
print(f"  grep('2026', path='/memories/'): {[m['path'] for m in mem.grep('2026', path='/memories/').matches]}")
print("  => 期望: 不以 / 开头的模式会下发到每个路由、结果各自带回前缀，所以 '*.md' 两边都搜得到；")
print("     以 / 开头的模式锚定在根，没指向某个路由时直接跳过它，所以 '/*.md' 一个都搜不到")
print("     （顺带：default 和路由各用各的 namespace，所以两边互不干扰 —— 对照实验 4）")

# 实验 4
hr("实验 4：前缀的边界与撞车（纯后端调用，不花 LLM）")
bare.write("/memoriesx/a.md", NOTE_BODY)
print(f"  写 /memoriesx/a.md 后 store : {store_keys()}")
print(f"  写 /memoriesx/a.md 后 磁盘   : {disk_files('memoriesx')}   <- 没被 /memories/ 吃掉")
shared = StoreBackend(namespace=lambda rt: NAMESPACE, store=store)
both = CompositeBackend(
    default=FilesystemBackend(root_dir=ROOT_DIR, virtual_mode=True),
    routes={"/memories/": shared, "/cache/": shared},   # 文档里的写法：两个路由共用一个后端
)
both.write("/cache/note.md", "缓存里的另一份内容")
print(f"  往 /cache/note.md 写一份后   : {store_keys()}   <- 没多出新的 key")
print(f"  再读 {MEMO_PATH} 得到   : {both.read(MEMO_PATH).file_data['content']!r}")
print(f"  ls('/') 的挂载点             : {ls_paths(both.ls('/'))}")
print("  => 期望: /cache/note.md 把 /memories/note.md 覆盖掉了 —— 前缀剥掉后两者的 key 都是 '/note.md'。")
print("     想隔离得给每个路由不同的 namespace，光换成不同的路由前缀不够")
