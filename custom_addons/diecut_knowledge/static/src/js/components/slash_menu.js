/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

const COMMANDS = [
    { type: "paragraph", label: "正文" },
    { type: "heading1", label: "一级标题" },
    { type: "heading2", label: "二级标题" },
    { type: "bulleted_list", label: "无序列表" },
    { type: "numbered_list", label: "有序列表" },
    { type: "todo", label: "待办" },
    { type: "quote", label: "引用" },
    { type: "code", label: "代码" },
    { type: "divider", label: "分割线" },
];

export class SlashMenu extends Component {
    static template = "diecut_knowledge.SlashMenu";
    static props = {
        visible: Boolean,
        onSelect: Function,
    };

    setup() {
        this.state = useState({ query: "" });
    }

    get commands() {
        const keyword = (this.state.query || "").trim().toLowerCase();
        if (!keyword) {
            return COMMANDS;
        }
        return COMMANDS.filter((item) => item.label.toLowerCase().includes(keyword));
    }

    onQueryInput(ev) {
        this.state.query = ev.target.value || "";
    }

    selectCommand(command) {
        this.state.query = "";
        this.props.onSelect(command.type);
    }
}
