---
name: hello-skill
description: 一个最小、可真正运行的 Skill 示例。当用户想查看、测试或学习“最小可执行的 skill”结构，或说出类似“跑一个最小的 skill”“最小的能执行的 skill”时使用。演示 Skill 的最小必要结构：一个带 frontmatter 的 SKILL.md 加一个 bundled 脚本。
---

# Hello Skill（最小可执行 Skill 示例）

这是被调用时真的会*做事*的最小 Skill：它运行一个 bundled 脚本并把输出报告给用户。
只有两部分 —— `SKILL.md`（必需）和 `scripts/hello.py`（真正被执行的脚本）。

## 何时使用

当用户要求测试、演示或理解最小可运行 Skill 的结构时使用。

## 如何执行

1. 运行 bundled 脚本并捕获其输出：

   ```bash
   python "<skill_dir>/scripts/hello.py"
   ```

   将 `<skill_dir>` 替换为该 Skill 所在目录的绝对路径（即包含本 SKILL.md 的文件夹）。

2. 把脚本的输出打印回用户，作为“Skill 已成功运行”的确认。

这就是完整的工作流。没有额外文件，没有外部依赖。
