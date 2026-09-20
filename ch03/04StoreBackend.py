"""StoreBackend（LangGraph Store 后端）功能验证脚本

对应 ch03.md「可插拔的存储后端 / 4.StoreBackend：跨会话持久化」。

要验证的结论：
  1. 文件既不在 state 里（连 files 键都没有），也不在磁盘上，
     而是躺在 LangGraph Store 的 (namespace, key) 记录里 —— 一条普通的数据记录
  2. 不需要 checkpointer：换 thread_id、换 agent 实例、换 StoreBackend 实例，
     只要还连着同一个 store 对象，就读得到
  3. 隔离靠 namespace：同一个 store，换一个 namespace 就是另一套「文件系统」
  4. namespace 工厂只有在图内执行时才摸得到 rt.server_info；
     本地 server_info 是 None，直接 rt.server_info.user.identity 会 AttributeError，必须兜底

⚠️ 与 02/03 的区别：本脚本没有 root_dir，不碰磁盘，全程只跟一个 store 对象打交道。
"""
import os

from deepagents import create_deep_agent
from deepagents.backends import StoreBackend
from langgraph.store.memory import InMemoryStore

from utility import get_model, ask, hr

NAMESPACE = ("local-user",)       # 本地兜底出来的命名空间
NOTE_PATH = "/memories/note.md"   # agent 看到的虚拟路径，同时就是 store 里的 key
NOTE_BODY = "2026年9月20日是星期天"

def user_namespace(user_id: str):
    """文档里的 namespace 工厂：线上按用户隔离，本地兜底成固定 user_id。

    部署到 LangSmith 时 rt.server_info.user.identity 能拿到真实用户身份；
    本地 invoke 时 rt.server_info 是 None（已实测），访问 .user 会抛 AttributeError。
    """
    return lambda rt: (rt.server_info.user.identity,) if rt.server_info else (user_id,)

# 全局共用的那个 store：本脚本里所有「跨会话」结论都靠它成立
store = InMemoryStore()

def store_keys(namespace: tuple[str, ...] = NAMESPACE) -> list[str]:
    """store 里真实躺着哪些 key。这就是 StoreBackend 的「文件系统」，用 BaseStore 自己就能查。"""
    return sorted(item.key for item in store.search(namespace))

def seen_in_trace(out: dict, needle: str) -> bool:
    """工具返回或模型回答里是否出现过某段内容。"""
    return any(needle in str(m.content) for m in out["messages"])

# 实验 0
hr("实验 0：后端能脱离 agent 单独用吗？（不经 LLM，秒级、确定性）")
try:
    # A) 没有 store，namespace 也不读 rt —— 卡在「没有 store」
    StoreBackend(namespace=lambda rt: NAMESPACE).write(NOTE_PATH, NOTE_BODY)
except RuntimeError as exc:
    print(f"  A) 不给 store，图外直接 write   : RuntimeError({str(exc)[:62]}...)")

try:
    # B) 给了 store，但 namespace 去读 rt —— 卡在「Runtime 不存在」
    StoreBackend(namespace=user_namespace("local-user"), store=store).ls("/memories")
except RuntimeError as exc:
    print(f"  B) 给了 store，但 namespace 读 rt: RuntimeError({str(exc)[:62]}...)")

# 图外不读 rt，就能像 02 里的 FilesystemBackend 一样直接使
backend = StoreBackend(namespace=lambda rt: NAMESPACE, store=store)
backend.write(NOTE_PATH, NOTE_BODY)
print(f"  C) namespace 不读 rt：read() 读回 {backend.read(NOTE_PATH).file_data['content']!r}")
print(f"     ls('/memories')  : {[e['path'] for e in backend.ls('/memories').entries]}")
item = store.search(NAMESPACE)[0]
print(f"     store 里的原始记录: namespace={item.namespace}  key={item.key!r}")
print(f"                        value 字段={sorted(item.value)}  content={item.value['content']!r}")
print("  => 期望: 只要显式给 store，后端裸调可用；而且「文件」就是 store 里一条 key 带路径的记录")
print("     （A/B 说明：它天生是给图内用的，出了图要么显式给 store，要么别在 namespace 里读 rt）")

# 实验 1
hr("实验 1：让 agent 写文件，文件到底落在哪？")
agent = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=StoreBackend(namespace=user_namespace("local-user")),  # 不给 store，靠 get_store() 拿图里的
    store=store,  # 注意：依然不传 checkpointer
)
out1 = ask(agent, f"请调用 write_file 工具，把「{NOTE_BODY}」写入 {NOTE_PATH}。", "t-1")
print(f"\n  out1 的顶层键        : {sorted(out1.keys())}")
print(f"  out1.get('files')    : {out1.get('files')}")
print(f"  磁盘上存在 memories/note.md 吗: {os.path.exists(os.path.join('memories', 'note.md'))}")
print(f"  （对照）02 的 notes/test.md   : {os.path.exists(os.path.join('notes', 'test.md'))}")
print(f"  store 里的 key        : {store_keys()}")
print("  => 期望: 没有 files 键、磁盘上没有文件，只有 store 的 key（既不是 state，也不是磁盘）")
print("     ⚠️ backend 里没传 store 也能跑，是因为图执行时 get_store() 拿到的就是这个 store")

# 实验 2
hr("实验 2：换一个 thread_id（连对话历史都没有），文件还在吗？")
out2 = ask(agent, f"读取 {NOTE_PATH}，如果读不到就直接说文件不存在。", "brand-new-thread")
print(f"\n  新线程读到了吗        : {seen_in_trace(out2, NOTE_BODY)}")
print("  => 期望: 读得到。没有 checkpointer 意味着上一轮的对话早没了，文件却还在")
print("     （对照 01StateBackend 实验 3：StateBackend 换个 thread 就空了）")

# 实验 3
hr("实验 3：换 agent 实例、换 StoreBackend 实例，还读得到吗？")
agent2 = create_deep_agent(
    model=get_model(),
    system_prompt="你是一个文件操作助手，按照指令操作文件",
    backend=StoreBackend(namespace=user_namespace("local-user"), store=store),  # 新实例，复用 store
)
out3 = ask(agent2, f"读取 {NOTE_PATH}，把内容原样告诉我。", "t-3")
print(f"\n  新实例读到了吗        : {seen_in_trace(out3, NOTE_BODY)}")
fresh_backend = StoreBackend(namespace=lambda rt: NAMESPACE, store=InMemoryStore())
print(f"  但换一个全新 store 读 : {fresh_backend.read(NOTE_PATH).error!r}")
print("  => 期望: 共用 store 就读得到，换 store 就读不到 —— 持久性住在 store 里，")
print("     不在 agent 里，也不在 StoreBackend 实例里")

# 实验 4
hr("实验 4：namespace 换一个，等于换了一套文件系统（纯后端调用，不花 LLM）")
other = StoreBackend(namespace=lambda rt: ("other-user",), store=store)
print(f"  local-user  看到      : {[e['path'] for e in backend.ls('/memories').entries]}")
print(f"  other-user  看到      : {other.ls('/memories').entries}")
print(f"  other-user  read 报错 : {other.read(NOTE_PATH).error!r}")
print(f"  同一个 store 里的全部 : {store_keys(NAMESPACE)} / {store_keys(('other-user',))}")
print("  => 期望: 数据一份没少，但 other-user 什么也看不到。隔离靠 namespace 前缀，不靠 store 实例")
print("     （线上那个 (rt.server_info.user.identity,) 就是在给每个用户划出这样一个前缀）")

# 实验 5
hr("实验 5：delete 掉之后，store 里真的没了吗？")
ask(agent, f"请调用 delete 工具删除 {NOTE_PATH}。", "t-5")
print(f"\n  delete 后的 store key : {store_keys()}")
print(f"  backend.read 的结果   : {backend.read(NOTE_PATH).error!r}")
print("  => 期望: key 从 store 里消失，read 报文件不存在")
