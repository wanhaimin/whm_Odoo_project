/** @odoo-module **/

import { Component } from "@odoo/owl";

export class BlockNode extends Component {
    static template = "diecut_knowledge.BlockNode";
    static props = {
        block: Object,
        onUpdate: Function,
        onDelete: Function,
        onInsertAfter: Function,
        onSlash: Function,
        onOpenCommands: Function,
        onIndent: Function,
        onOutdent: Function,
        onDragStart: Function,
        onDropOn: Function,
        onFocusBlock: Function,
    };

    onTextChanged(ev) {
        const html = ev.target.innerHTML || "";
        const text = ev.target.innerText || "";
        this.props.onUpdate(this.props.block.id, {
            content: { ...(this.props.block.content || {}), html, text },
        });
    }

    onKeydown(ev) {
        if (ev.key === "/" && !ev.ctrlKey && !ev.metaKey && this._isCommandTrigger(ev.target)) {
            ev.preventDefault();
            this.props.onSlash(this.props.block.id);
        } else if (ev.key === "Tab" && !ev.shiftKey) {
            ev.preventDefault();
            this.props.onIndent(this.props.block.id);
        } else if (ev.key === "Tab" && ev.shiftKey) {
            ev.preventDefault();
            this.props.onOutdent(this.props.block.id);
        } else if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
            ev.preventDefault();
            this.props.onInsertAfter(this.props.block.id);
        } else if (ev.key === "Backspace" && !(ev.target.innerText || "").trim()) {
            ev.preventDefault();
            this.props.onDelete(this.props.block.id);
        } else if (ev.key === "Escape") {
            this.props.onSlash(false);
        }
    }

    get placeholder() {
        if (this.props.block.block_type === "heading1") {
            return "输入一级标题";
        }
        if (this.props.block.block_type === "heading2") {
            return "输入二级标题";
        }
        if (this.props.block.block_type === "todo") {
            return "输入待办事项";
        }
        if (this.props.block.block_type === "code") {
            return "输入代码";
        }
        return "输入内容，输入 / 选择块类型";
    }

    get textClass() {
        if (this.props.block.block_type === "code") {
            return "o_kb_block_text o_kb_block_text_code";
        }
        if (this.props.block.block_type === "heading1") {
            return "o_kb_block_text o_kb_block_h1";
        }
        if (this.props.block.block_type === "heading2") {
            return "o_kb_block_text o_kb_block_h2";
        }
        return "o_kb_block_text";
    }

    get contentHtml() {
        if (this.props.block.content?.html) {
            return this.props.block.content.html;
        }
        const text = this.props.block.content?.text || "";
        return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/\n/g, "<br>");
    }

    onDragStart(ev) {
        this.props.onDragStart(this.props.block.id);
        ev.dataTransfer.effectAllowed = "move";
    }

    onDrop(ev) {
        ev.preventDefault();
        this.props.onDropOn(this.props.block.id);
    }

    onFocusEditor() {
        this.props.onFocusBlock(this.props.block.id);
    }

    _isCommandTrigger(el) {
        const text = (el?.innerText || "").trim();
        return !text;
    }

    onOpenCommands() {
        this.props.onOpenCommands(this.props.block.id);
    }
}
