# diecut_knowledge

后台知识库模块，提供 Notion 风格的页面树 + 块编辑工作台。

## 功能

- 左侧页面树（父子页面）
- 右侧块编辑器（标题/列表/待办/代码/分割线）
- 自动保存队列 + 手动保存按钮
- 页面元数据管理（状态、关联型号、品牌分类）

## 技术结构

- `diecut.kb.article`: 页面壳模型
- `diecut.kb.block`: 内容块模型
- `diecut.kb.editor.service`: 前端 RPC 服务入口

## 运维

- 模块安装：`-i diecut_knowledge`
- 模块升级：`-u diecut_knowledge`
- 卸载模块会删除本模块数据，请先备份。
