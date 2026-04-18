# 实现计划：部署 `chatter_ai_assistant` 为 Odoo AI 助手

## 目标
- 将 `custom_addons/chatter_ai_assistant` 模块在 Odoo 19 中部署为 AI 助手，提供聊天、代码生成等功能。
- 确保模块依赖的 OpenAI / OpenClaw 配置完整，菜单中文化，安全访问控制到位。

## 步骤概览
1. **检查模块结构**
   - 确认 `__manifest__.py`、`models/`、`views/`、`controllers/`、`static/` 等目录完整。
2. **更新依赖**
   - 在 `__manifest__.py` 中加入 `depends`：`['base', 'mail']`（如需 `web`、`website` 视情况添加）。
3. **配置 OpenAI / OpenClaw**
   - 在 Odoo 系统参数 (`ir.config_parameter`) 中新增 `chatter_ai_assistant.openai_api_key`。
   - 若使用 OpenClaw，确保 `/opt/openclaw-state/openclaw.json` 正确，环境变量 `OPENAI_API_KEY` 已设置。
4. **模型实现**
   - 在 `models/chat_message.py`（示例）中实现 `ChatMessage` 模型，字段包括 `role`, `content`, `timestamp`。
   - 使用 `@api.model` 方法封装调用 OpenAI API（使用 `self.env['ir.config_parameter'].sudo().get_param('chatter_ai_assistant.openai_api_key')` 获取密钥）。
5. **安全访问**
   - 在 `security/ir.model.access.csv` 中为 `chat.message` 添加 `read,write,create,unlink` 权限，限定给 `base.group_user`。
   - 如需仅管理员使用，可限制到 `base.group_system`。
6. **视图与菜单**
   - 在 `views/chat_assistant_menu.xml` 中新增中文菜单 `AI 助手`，放在 `Settings > Technical` 或自定义主菜单下。
   - 创建 `form`/`tree` 视图展示聊天记录，使用 `<field name="content" widget="html"/>`。
   - 为聊天窗口添加 `action`，指向 `ir.actions.client`，使用 Owl 前端组件。
7. **前端组件**
   - 在 `static/src/js/chat_assistant.js` 中使用 Owl `Component` 实现聊天框 UI（输入框、发送按钮、消息列表）。
   - 使用 `patch` 扩展 Odoo `mail.ChatComposer`（若想在邮件撰写时直接调用）。
   - 添加 CSS（`static/src/css/chat_assistant.css`）实现暗色主题、微动画，符合项目的视觉要求。
8. **控制器**
   - 在 `controllers/main.py` 中提供 JSON RPC `/chatter_ai_assistant/chat`，接收前端请求，调用模型方法返回 AI 响应。
9. **资产加载**
   - 在 `__manifest__.py` 的 `assets` 部分注册 JS、CSS：
     ```python
     'assets': {
         'web.assets_backend': [
             'chatter_ai_assistant/static/src/js/chat_assistant.js',
             'chatter_ai_assistant/static/src/css/chat_assistant.css',
         ],
     },
     ```
10. **本地化**
    - 所有 UI 文本使用中文 `string` 参数，例如 `string='聊天记录'`、`string='发送'`。
11. **模块升级 & 测试**
    - 运行 `docker exec my_odoo_project_devcontainer-web-1 odoo -d odoo -u chatter_ai_assistant --stop-after-init` 完成升级。
    - 在浏览器登录 Odoo，进入 `AI 助手` 菜单，验证聊天功能是否正常。
12. **错误处理 & 日志**
    - 在模型方法中捕获 `openai.error.OpenAIError`，记录到 `_logger.error`，并向前端返回友好提示。
13. **文档**
    - 在 `README.md` 中补充部署说明、使用指南、常见问题。

## 交付物
- 完整的 `chatter_ai_assistant` 模块代码（已更新的 `__manifest__`, `models/`, `views/`, `controllers/`, `static/`）。
- 本实现计划文档（本文件），等待确认后执行。

## 后续步骤
请确认以上计划是否符合您的需求，或提供额外的定制要求（例如特定的 UI 风格、权限限制等）。确认后我将开始实际代码编写与部署。
