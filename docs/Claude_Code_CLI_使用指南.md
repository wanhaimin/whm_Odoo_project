# Claude Code CLI 完整使用指南

> 版本：Claude Code 2025 | 最后更新：2026-04-26

---

## 目录

1. [斜杠命令（Slash Commands）](#1-斜杠命令)
2. [键盘快捷键](#2-键盘快捷键)
3. [输入前缀语法（! # @）](#3-输入前缀语法)
4. [CLAUDE.md 配置文件](#4-claudemd-配置文件)
5. [Hooks 钩子系统](#5-hooks-钩子系统)
6. [MCP 服务器扩展](#6-mcp-服务器扩展)
7. [设置文件（settings.json）](#7-设置文件)
8. [IDE 集成](#8-ide-集成)
9. [权限模式](#9-权限模式)
10. [自定义 Skills](#10-自定义-skills)
11. [命令行启动参数](#11-命令行启动参数)
12. [环境变量](#12-环境变量)
13. [子代理（Subagents）](#13-子代理-subagents)
14. [其他实用功能](#14-其他实用功能)

---

## 1. 斜杠命令

在对话框中输入 `/` 即可触发，支持 Tab 自动补全。

### 1.1 内置命令

| 命令 | 说明 | 示例 |
|------|------|------|
| `/help` | 显示所有可用命令 | `/help` |
| `/model` | 切换 AI 模型 | `/model claude-opus-4-7` |
| `/effort` | 调整推理深度（low/medium/high/xhigh/max） | `/effort high` |
| `/clear` | 清空对话历史，重新开始 | `/clear` |
| `/compact` | 压缩对话上下文，释放 token | `/compact 专注于认证模块` |
| `/context` | 查看当前上下文窗口占用情况 | `/context` |
| `/memory` | 查看并编辑 CLAUDE.md 和自动记忆文件 | `/memory` |
| `/status` | 显示当前生效的配置来源 | `/status` |
| `/cost` | 查看本次会话的 API 用量和费用 | `/cost` |
| `/doctor` | 诊断配置和安装问题 | `/doctor` |
| `/permissions` | 查看和管理工具权限规则 | `/permissions` |
| `/mcp` | 管理 MCP 服务器（添加/删除/列表） | `/mcp` |
| `/skills` | 列出所有可用的 Skills | `/skills` |
| `/rename` | 重命名当前会话 | `/rename auth-feature` |
| `/resume` | 恢复之前的会话 | `/resume auth-feature` |
| `/add-dir` | 运行时添加工作目录 | `/add-dir ../shared-docs` |
| `/login` | 登录 Anthropic 账号 | `/login` |
| `/logout` | 退出登录 | `/logout` |
| `/bug` | 向 Claude Code 团队报告 Bug | `/bug` |
| `/vim` | 切换 Vim 输入模式 | `/vim` |
| `/fast` | 切换到更快的模型（Opus 4.6 Fast 模式） | `/fast` |
| `/init` | 初始化项目 CLAUDE.md | `/init` |

### 1.2 Skills 命令（需要安装对应 Skill）

| 命令 | 说明 |
|------|------|
| `/commit` | 暂存并提交当前改动 |
| `/pr` | 为当前改动创建 Pull Request |
| `/review` | 审查 PR 或代码变更 |
| `/security-review` | 对待提交改动进行安全审查 |
| `/loop` | 以固定间隔循环执行命令 |
| `/simplify` | 审查代码质量和简洁性 |
| `/batch` | 跨多个 worktree 并行执行变更 |
| `/ultrareview` | 多代理深度代码审查（计费功能） |
| `/schedule` | 安排后台代理在指定时间执行任务 |
| `/debug` | 启用调试日志 |

### 1.3 自定义 Skills

用户可创建自定义命令，存放于：
- `~/.claude/skills/<skill-name>/SKILL.md` — 个人全局 Skill
- `.claude/skills/<skill-name>/SKILL.md` — 项目级 Skill（可提交到 git）

调用方式：`/skill-name [参数]`

---

## 2. 键盘快捷键

### 2.1 终端模式

| 快捷键 | 功能 |
|--------|------|
| `Ctrl+C` | 中断 Claude 当前操作 |
| `Ctrl+D` | 退出会话（在空提示符时） |
| `Esc` | 取消多行输入，返回提示符 |
| `Esc Esc`（连按两次） | 回退到上一个检查点（撤销代码变更） |
| `Shift+Tab` | 循环切换权限模式：默认 → 自动接受 → 计划 → 自动 |
| `Ctrl+G` | 在文本编辑器中打开当前计划 |
| `Ctrl+O` | 切换详细输出模式（显示/隐藏思考过程） |
| `Alt+T`（Windows/Linux）/ `Option+T`（macOS） | 开关扩展思考模式 |
| `Shift+Enter` | 在输入框中换行（多行输入） |
| `↑ / ↓` | 浏览输入历史 |
| `Tab` | 自动补全命令和 Skill 名称 |
| `Ctrl+L` | 清屏 |

### 2.2 VS Code 扩展

| 快捷键 | 功能 |
|--------|------|
| `Cmd/Ctrl+Shift+Esc` | 在新标签页打开 Claude 对话 |
| `Cmd/Ctrl+Esc` | 在编辑器和 Claude 面板之间切换焦点 |
| `Option/Alt+K` | 插入文件引用（带行号） |
| `Cmd/Ctrl+N` | 开始新对话（需在设置中启用） |

---

## 3. 输入前缀语法

### 3.1 `!` 前缀：内联执行 Shell 命令

在提示框中直接运行 Shell 命令，结果显示在对话中：

```
! ls -la
! git status
! npm run build
! python manage.py migrate
```

> **提示**：这等同于要求 Claude 运行命令，适合快速查看输出而不需要 Claude 解释的场景。

### 3.2 `#` 前缀：写入记忆笔记

向自动记忆系统写入内容，Claude 在后续会话中会记住这些信息：

```
# 这个项目使用 pnpm，不用 npm
# API 需要在 Authorization 头中传 Bearer token
# 数据库端口是 5434，不是默认的 5432
```

### 3.3 `@` 前缀：引用文件/资源

将文件或目录内容注入到上下文中（不需要等 Claude 去读）：

```
@src/auth.ts                       引用单个文件
@src/components/                   引用整个目录
@src/auth.ts#15-40                 引用指定行范围（通过 Alt+K 插入）
@github:repos/owner/repo/issues    引用 MCP 资源
```

> **VS Code 用户**：使用 `Alt+K`（macOS: `Option+K`）快捷键，可以自动插入当前光标所在文件和行号的 `@` 引用。

---

## 4. CLAUDE.md 配置文件

### 4.1 作用

CLAUDE.md 是会话开始时自动加载的持久化指令文件，用于告诉 Claude：
- 项目的构建和测试命令
- 代码规范和命名约定
- 架构说明和重要路径
- 调试技巧和注意事项

### 4.2 文件位置和作用域

| 文件路径 | 作用域 | 是否共享 |
|----------|--------|---------|
| `C:\Program Files\ClaudeCode\CLAUDE.md`（Windows） | 全组织 | 所有用户 |
| `/Library/Application Support/ClaudeCode/CLAUDE.md`（macOS） | 全组织 | 所有用户 |
| `~/.claude/CLAUDE.md` | 当前用户所有项目 | 仅本人 |
| `./CLAUDE.md` 或 `./.claude/CLAUDE.md` | 当前项目 | 可提交 git 共享 |
| `./CLAUDE.local.md` | 当前项目 | 仅本人（不提交 git） |

**加载顺序**：组织级 → 用户级 → 项目级，后者可以覆盖前者。

### 4.3 文件结构示例

```markdown
# 我的项目

## 常用命令
- `python odoo-bin -u my_module` — 升级模块
- `python -m pytest tests/` — 运行测试
- `git log --oneline -10` — 查看最近提交

## 项目结构
- `custom_addons/` — 自定义 Odoo 模块
- `docs/` — 项目文档
- `tests/` — 测试文件

## 代码规范
- Python 使用 4 空格缩进
- 类名使用 PascalCase，方法名使用 snake_case
- 所有模型必须包含 `_description` 字段

## 注意事项
- 数据库端口为 5434（非默认 5432）
- 升级模块前先备份数据库
- 不要修改 `odoo/` 目录下的官方源码
```

### 4.4 导入其他文件

在 CLAUDE.md 中可以用 `@path` 引用其他文件内容：

```markdown
参见 @README.md 了解项目概述
参见 @docs/api-conventions.md 了解 API 规范
```

### 4.5 路径范围规则（.claude/rules/）

在 `.claude/rules/` 目录下创建 `.md` 文件，可以为特定路径设置专属规则：

```markdown
---
paths:
  - "custom_addons/**/*.py"
  - "tests/**/*.py"
---

# Odoo 模块开发规则
- 所有模型必须继承自 models.Model 或 models.TransientModel
- 视图 XML 必须包含 ir.model.access.csv 权限配置
- 禁止在模型中直接执行原始 SQL（使用 ORM）
```

### 4.6 快速初始化

```bash
/init    # Claude 会自动扫描项目并生成 CLAUDE.md
```

---

## 5. Hooks 钩子系统

Hooks 允许在 Claude Code 生命周期的特定节点自动执行 Shell 命令、HTTP 请求或 AI 判断，用于校验、日志记录、自动化和权限控制。

### 5.1 主要 Hook 事件

| Hook 事件 | 触发时机 | 常见用途 |
|-----------|---------|---------|
| `PreToolUse` | 工具调用**前** | 阻止危险命令，记录操作 |
| `PostToolUse` | 工具调用**成功后** | 运行格式化、触发通知 |
| `UserPromptSubmit` | 用户发送消息前 | 过滤敏感内容，添加上下文 |
| `SessionStart` | 会话开始时 | 初始化环境、加载配置 |
| `SessionEnd` | 会话结束时 | 清理临时文件、发送报告 |
| `PermissionRequest` | 出现权限确认弹窗时 | 自动批准或拒绝特定操作 |
| `Notification` | Claude Code 发送通知时 | 转发到钉钉/微信等 |
| `Stop` | Claude 完成一轮回复后 | 自动运行测试、检查代码质量 |

### 5.2 配置示例

在 `.claude/settings.json` 中配置：

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/check-dangerous.sh",
            "timeout": 10
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "permission_prompt",
        "hooks": [
          {
            "type": "command",
            "command": "curl -X POST https://your-webhook/notify -d '{\"msg\":\"Claude 需要你的确认\"}'"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python -m pytest tests/ --tb=no -q 2>&1 | tail -1"
          }
        ]
      }
    ]
  }
}
```

### 5.3 Hook 脚本返回值

`PreToolUse` 类型的 Hook 脚本可以通过退出码控制行为：

```bash
exit 0   # 允许工具执行
exit 2   # 阻止工具执行（Claude 会看到阻止原因）
exit 1   # 非阻断性错误，继续弹出权限提示
```

输出 JSON 可以提供更丰富的控制：

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny"
  }
}
```

### 5.4 Hook 中可用的环境变量

```bash
$CLAUDE_PROJECT_DIR    # 项目根目录（注意加引号："$CLAUDE_PROJECT_DIR"）
$CLAUDE_ENV_FILE       # 持久化环境变量到会话（SessionStart 中使用）
```

---

## 6. MCP 服务器扩展

MCP（Model Context Protocol）服务器为 Claude 提供访问外部工具、数据库、API 的能力。

### 6.1 添加 MCP 服务器

**命令行方式**：

```bash
# 添加本地进程服务器（stdio）
claude mcp add --transport stdio github node /path/to/github-server.js

# 添加远程 HTTP 服务器
claude mcp add --transport http my-api https://api.example.com/mcp \
  --header "Authorization: Bearer TOKEN"

# 查看已配置的服务器
claude mcp list

# 删除服务器
claude mcp remove github
```

**在设置文件中配置**（`.claude/settings.json`）：

```json
{
  "mcpServers": {
    "github": {
      "command": "node",
      "args": ["/path/to/github-mcp-server.js"],
      "env": {
        "GITHUB_TOKEN": "${GITHUB_TOKEN}"
      }
    },
    "my-api": {
      "transport": "http",
      "url": "https://api.example.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MY_API_TOKEN}"
      }
    }
  }
}
```

### 6.2 常用 MCP 服务器

| 服务器 | 功能 |
|--------|------|
| `github` | 仓库管理、PR 操作、Issue 追踪 |
| `slack` | 发送消息、管理频道 |
| `puppeteer` | 浏览器自动化、网页截图 |
| `memory` | 跨会话持久化键值存储 |
| `google-drive` | Google Drive 文件访问 |
| `sqlite` | 本地数据库查询 |
| `playwright` | 浏览器自动化测试 |

### 6.3 在对话中使用 MCP 资源

```
@github:repos/owner/repo/issues      引用 GitHub Issues
@github:repos/owner/repo/pulls/123   引用指定 PR
@slack:channels/general              引用 Slack 频道
```

### 6.4 在 VS Code 中管理

在对话框输入 `/mcp` 可以图形化管理 MCP 服务器：启用/禁用、重连、OAuth 认证。

---

## 7. 设置文件

### 7.1 文件位置和优先级

优先级从高到低：

| 级别 | 路径 | 共享 |
|------|------|------|
| 组织托管（最高） | `C:\Program Files\ClaudeCode\managed-settings.json` | 强制所有用户 |
| 命令行参数 | 启动时传入 | 仅当次运行 |
| 项目本地 | `.claude/settings.local.json` | 不提交 git |
| 项目共享 | `.claude/settings.json` | 提交 git |
| 用户全局（最低） | `~/.claude/settings.json` | 当前用户所有项目 |

### 7.2 常用配置项

```json
{
  "model": "claude-sonnet-4-6",
  "effortLevel": "medium",
  "theme": "dark",
  "autoMemoryEnabled": true,

  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Bash(git *)",
      "Bash(npm run *)",
      "Bash(python *)",
      "Read",
      "Edit(.claude/**)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Read(.env)"
    ],
    "additionalDirectories": ["../shared-docs/"]
  },

  "env": {
    "PYTHONPATH": "./src"
  },

  "mcpServers": {
    "github": {
      "command": "node",
      "args": ["/path/to/server.js"]
    }
  }
}
```

### 7.3 查看当前生效配置

```
/status    # 显示哪些配置文件正在生效
```

---

## 8. IDE 集成

### 8.1 VS Code 扩展

**安装**：在扩展市场搜索 "Claude Code" 并安装。

**打开方式**：
- 点击编辑器右上角的 ✦ 图标
- 点击左侧活动栏的 Claude 图标
- 命令面板：`Claude Code: Open in New Tab`
- 状态栏：点击底部 `✱ Claude Code`

**主要功能**：
- 侧边栏聊天面板
- 计划模式（Plan Mode）内联审查
- 自动接受编辑模式
- 检查点回退（撤销代码变更而不影响对话）
- 多会话 Tab 支持
- 会话历史搜索
- Chrome 浏览器集成（`@browser`）

**扩展设置**（VS Code settings.json）：

```json
{
  "claude-code.initialPermissionMode": "default",
  "claude-code.preferredLocation": "sidebar",
  "claude-code.autosave": true,
  "claude-code.useCtrlEnterToSend": false,
  "claude-code.respectGitIgnore": true
}
```

### 8.2 JetBrains 系列 IDE

支持：IntelliJ IDEA、PyCharm、WebStorm、CLion、GoLand 等。

**安装**：Settings → Plugins → Marketplace → 搜索 "Claude Code"

**打开方式**：
- 工具栏 Claude 图标
- 编辑器右键菜单 → Claude Code
- Tools 菜单 → Claude Code

功能与 VS Code 扩展基本一致。

---

## 9. 权限模式

### 9.1 模式说明

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `default` | 每次文件编辑和 Shell 命令都需确认 | 默认，安全交互 |
| `acceptEdits` | 自动接受文件编辑，安全的文件系统命令无需确认 | 快速迭代开发 |
| `plan` | 只读模式，先制定计划再执行 | 探索代码库、需求分析 |
| `auto` | 后台安全检查，自动执行（研究预览） | 高度信任环境 |
| `bypassPermissions` | 跳过所有提示（受保护目录除外） | 隔离的 CI 环境 |

**切换方式**：按 `Shift+Tab` 循环切换。

### 9.2 权限规则语法

在设置文件的 `permissions.allow` / `permissions.deny` 中配置：

```json
{
  "permissions": {
    "allow": [
      "Bash",                        // 允许所有 Bash 命令
      "Bash(npm run *)",             // 允许 npm run 开头的命令
      "Bash(git commit *)",          // 允许 git commit
      "Read",                        // 允许所有文件读取
      "Edit(./src/**/*.py)",         // 允许编辑 src 下的 Python 文件
      "WebFetch(domain:github.com)", // 允许访问 GitHub
      "mcp__github__*"               // 允许所有 GitHub MCP 工具
    ],
    "deny": [
      "Bash(rm -rf *)",              // 禁止递归删除
      "Bash(curl *)",                // 禁止 curl
      "Read(./.env)"                 // 禁止读取 .env 文件
    ]
  }
}
```

**规则优先级**：`deny > allow`，第一条匹配的规则生效。

### 9.3 通配符说明

- `Bash(npm run *)` — 前缀匹配（空格后的 `*`）
- `Read(*.env)` — 当前目录下匹配
- `Read(**/*.md)` — 递归匹配
- `Read(~/config)` — 家目录路径
- `Read(//absolute/path)` — 绝对路径

---

## 10. 自定义 Skills

### 10.1 目录结构

```
.claude/skills/my-skill/
├── SKILL.md          # 必须：Skill 定义和指令
├── template.md       # 可选：输出模板
└── examples/
    └── sample.md    # 可选：示例输出
```

### 10.2 SKILL.md 格式

```yaml
---
name: deploy-check
description: 部署前检查代码质量、测试和安全问题
argument-hint: "[环境名称]"
arguments: [environment]
allowed-tools: "Bash(npm *) Bash(git *) Read"
model: claude-sonnet-4-6
effort: high
---

对以下目标 $environment 环境执行部署前检查：

1. 运行完整测试套件
2. 检查是否有 TODO/FIXME 注释
3. 验证环境变量配置
4. 检查依赖安全漏洞

生成部署就绪报告。
```

### 10.3 Skill 中可用变量

| 变量 | 说明 |
|------|------|
| `$ARGUMENTS` | 所有传入参数 |
| `$ARGUMENTS[0]` / `$0` | 第一个参数 |
| `$environment` | 按 `arguments` 字段命名的参数 |
| `${CLAUDE_SESSION_ID}` | 当前会话 ID |
| `${CLAUDE_SKILL_DIR}` | Skill 目录路径 |

### 10.4 在 Skill 中执行 Shell 命令（预处理）

```yaml
---
name: git-context
---

当前 Git 状态：
!`git log --oneline -5`

修改文件列表：
!`git diff --name-only`

请基于以上信息分析本次提交的影响范围。
```

### 10.5 在子代理中运行 Skill

```yaml
---
name: deep-research
context: fork
agent: Explore
---

深入研究以下主题并返回详细报告...
```

---

## 11. 命令行启动参数

### 11.1 会话管理

```bash
claude                              # 交互模式
claude "帮我审查这段代码"            # 带初始提示启动
claude -p "查询"                    # 打印模式（非交互，输出后退出）
claude --continue                   # 恢复最近一次会话
claude --resume auth-feature        # 按名称恢复会话
claude -n "我的会话"                 # 命名本次会话
```

### 11.2 Worktree（隔离工作区）

```bash
claude --worktree feature-auth      # 在新 worktree 中开启隔离会话
claude --worktree                   # 自动生成 worktree 名称
claude --worktree bugfix-123        # 另一个并行隔离会话
```

> Worktree 让多个 Claude 会话并行工作，每个会话有独立的文件副本，互不干扰。

### 11.3 模型和推理

```bash
claude --model claude-opus-4-7      # 指定模型
claude --effort xhigh               # 推理深度
claude --system-prompt "你是..."    # 替换系统提示
claude --append-system-prompt "..."  # 追加到系统提示
```

### 11.4 权限控制

```bash
claude --permission-mode plan                    # 以计划模式启动
claude --dangerously-skip-permissions            # 跳过所有权限提示
claude --allowedTools "Bash(npm *)" "Read"       # 预批准工具
claude --disallowedTools "Bash(rm *)"            # 禁止工具
```

### 11.5 输出格式（非交互模式）

```bash
claude -p "查询" --output-format json            # JSON 格式输出
claude -p "查询" --output-format stream-json     # 流式 JSON
claude -p "查询" --output-format text            # 纯文本（默认）
claude -p "查询" --max-turns 5                   # 最大对话轮数
claude -p "查询" --max-budget-usd 1.00           # 费用上限
```

### 11.6 MCP 和插件

```bash
claude --mcp-config ./mcp.json                  # 加载 MCP 配置
claude --chrome                                  # 启用浏览器集成
claude --no-chrome                               # 禁用浏览器
```

### 11.7 调试

```bash
claude --debug                                   # 启用调试日志
claude --verbose                                 # 详细输出
claude --debug-file /tmp/debug.log               # 写入日志文件
```

---

## 12. 环境变量

```bash
# API 配置
ANTHROPIC_API_KEY=your-key            # API 密钥
ANTHROPIC_API_BASE=custom-endpoint    # 自定义端点（代理）

# 日志和遥测
CLAUDE_CODE_ENABLE_TELEMETRY=1        # 启用遥测数据收集
CLAUDE_CODE_DEBUG_LOGS_DIR=./logs     # 调试日志目录

# 推理控制
MAX_THINKING_TOKENS=10000             # 限制思考 token 预算
CLAUDE_CODE_EFFORT_LEVEL=high         # 设置推理深度

# 功能开关
CLAUDE_CODE_DISABLE_AUTO_MEMORY=1     # 禁用自动记忆
CLAUDE_CODE_USE_POWERSHELL_TOOL=1     # 使用 PowerShell 工具（Windows）

# 代理和网络
ANTHROPIC_PROXY_URL=http://proxy:8080  # HTTP 代理
```

---

## 13. 子代理（Subagents）

### 13.1 内置代理类型

| 代理 | 特点 | 适用场景 |
|------|------|---------|
| `Explore` | 只读工具，探索代码库 | 快速搜索和分析 |
| `Plan` | 制定实施方案 | 架构设计、任务拆解 |
| `general-purpose` | 完整工具集 | 通用任务 |

### 13.2 创建自定义代理

在 `.claude/agents/my-agent.md` 中创建：

```yaml
---
description: 专门处理数据库迁移的代理
tools: Bash,Read,Edit
---

你是一个数据库迁移专家。
在执行任何迁移前，必须：
1. 备份现有数据
2. 在测试环境验证
3. 输出回滚方案
```

### 13.3 并行多代理

```bash
/agents    # 在 VS Code 中图形化管理代理配置
```

通过 `--worktree` 启动多个独立会话实现并行工作：

```bash
claude --worktree feature-a    # 代理1：开发功能A
claude --worktree feature-b    # 代理2：同时开发功能B
```

---

## 14. 其他实用功能

### 14.1 扩展思考模式（Extended Thinking）

对复杂问题启用更深层的推理：

```
ultrathink    # 在对话中输入，触发最大深度思考
Alt+T         # 切换扩展思考开关（macOS: Option+T）
/effort max   # 设置最高推理深度
```

### 14.2 检查点和回退

```
Esc Esc       # 回退到上一个检查点（撤销代码，保留对话）
```

VS Code 中：悬停在消息上 → 点击回退按钮，可选择：
- 仅撤销代码变更
- 从此处分叉对话
- 同时撤销代码并分叉对话

### 14.3 自动记忆（Auto Memory）

Claude 会自动学习并记住：
- 发现的构建命令
- 调试技巧和踩坑经验
- 代码架构模式
- 你的个人偏好

记忆存储在：`~/.claude/projects/<项目名>/memory/`

```
/memory    # 查看和编辑所有自动记忆文件
```

### 14.4 `/loop` 循环执行

以固定间隔循环运行任务：

```
/loop 每天早上检查 CI 状态并报告失败的测试
/loop 监控 logs/error.log 文件，发现新错误时通知我
```

Claude 会自行决定合适的检查间隔，在后台持续运行。

### 14.5 `/schedule` 定时执行

安排后台代理在指定时间后执行：

```
/schedule 2周后清理所有已合并的 feature 分支
/schedule 检查下周一 CI 结果
```

### 14.6 Chrome 浏览器集成

```bash
claude --chrome     # 启动时启用浏览器集成
```

在对话中引用浏览器：

```
@browser 打开 localhost:3000 并检查控制台错误
@browser 截图当前页面并分析 UI 问题
```

### 14.7 `/ultrareview` 深度代码审查

对当前分支的所有变更进行多代理协作深度审查：

```
/ultrareview              # 审查当前分支
/ultrareview 123          # 审查指定 GitHub PR 编号
```

> 注意：此功能使用多个 AI 代理并行审查，会产生较高费用，适合正式合并前的最终审查。

### 14.8 沙箱模式

限制 Claude 只能访问指定路径和网络：

```json
{
  "sandbox": {
    "enabled": true,
    "filesystem": {
      "allowRead": ["/tmp", "./src"],
      "denyRead": ["~/.ssh", ".env"]
    },
    "network": {
      "allowedDomains": ["github.com", "*.npmjs.org"],
      "deniedDomains": ["internal.corp"]
    }
  }
}
```

---

## 附录：快速参考卡

### 最常用命令

```
/compact      压缩上下文（对话太长时使用）
/clear        重新开始对话
/memory       查看和编辑记忆文件
/status       查看当前配置
/cost         查看本次费用
Shift+Tab     切换权限模式
Esc Esc       撤销最近的代码变更
! <command>   直接运行 Shell 命令
# <note>      写入记忆笔记
@ <file>      引用文件内容
```

### 推荐工作流

```bash
# 1. 项目初始化
claude
/init                     # 生成 CLAUDE.md

# 2. 日常开发
claude --continue         # 恢复昨天的会话
@src/auth.ts              # 引用要修改的文件
Shift+Tab                 # 切换到自动接受模式加速迭代

# 3. 代码审查前
/review                   # 审查当前改动

# 4. 提交代码
/commit                   # 暂存并提交
/pr                       # 创建 PR
```

---

*本文档基于 Claude Code 2025 版本编写。如需反馈问题，可在 [GitHub Issues](https://github.com/anthropics/claude-code/issues) 提交。*
