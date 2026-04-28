/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, useRef, useState } from "@odoo/owl";

class AiAdvisorDrawer extends Component {
    static template = "diecut_knowledge.AiAdvisorDrawer";

    setup() {
        const params = this.props.params || {};
        this.modelName = params.model || "";
        this.recordId = params.record_id || 0;
        this.recordName = params.record_name || "";
        this.conversationId = "";
        this.notification = useService("notification");

        this.ui = useState({
            messages: [],
            loading: false,
            inputText: "",
            error: "",
            savingIds: [],
        });
        this.chatBodyRef = useRef("chatBody");
        this._addSystemMessage();
    }

    get hasMessages() {
        return this.ui.messages.length > 0;
    }

    get canSend() {
        return this.ui.inputText.trim() !== "" && !this.ui.loading;
    }

    onInputKeydown(ev) {
        if (ev.key === "Enter" && !ev.shiftKey) {
            ev.preventDefault();
            this.send();
        }
    }

    async send() {
        const text = this.ui.inputText.trim();
        if (!text || this.ui.loading) {
            return;
        }

        this.ui.inputText = "";
        this.ui.error = "";
        this._pushMessage("user", text);
        this.ui.loading = true;
        this._scrollBottom();

        try {
            const result = await rpc("/diecut_knowledge/ai/chat", {
                query: text,
                model: this.modelName,
                record_id: this.recordId,
                conversation_id: this.conversationId,
            });
            if (result.ok) {
                this.conversationId = result.conversation_id || this.conversationId;
                this._pushMessage("assistant", result.answer || "(空响应)", { question: text });
            } else {
                this.ui.error = result.error || "调用失败";
            }
        } catch (err) {
            this.ui.error = err.message || "网络错误";
        }
        this.ui.loading = false;
        this._scrollBottom();
    }

    async saveMessage(message) {
        if (!message?.content || !message.question || this.ui.savingIds.includes(message.id)) {
            return;
        }
        this.ui.savingIds.push(message.id);
        try {
            const result = await rpc("/diecut_knowledge/ai/save_answer", {
                question: message.question,
                answer: message.content,
                model: this.modelName,
                record_id: this.recordId,
                record_name: this.recordName,
            });
            if (result.ok) {
                message.savedArticleId = result.article_id;
                this.notification.add(`已保存为知识文章：${result.article_name}`, { type: "success" });
            } else {
                this.notification.add(result.error || "保存失败", { type: "danger" });
            }
        } catch (err) {
            this.notification.add(err.message || "保存失败", { type: "danger" });
        } finally {
            this.ui.savingIds = this.ui.savingIds.filter((id) => id !== message.id);
        }
    }

    close() {
        this.props.close();
    }

    onClickBackdrop(ev) {
        if (ev.target.classList.contains("o_diecut_ai_overlay")) {
            this.close();
        }
    }

    _pushMessage(role, content, extra = {}) {
        this.ui.messages.push({ role, content, id: Date.now() + Math.random(), ...extra });
    }

    _addSystemMessage() {
        if (this.recordName) {
            this._pushMessage("system", `当前: ${this.recordName}`);
        }
    }

    _scrollBottom() {
        const el = this.chatBodyRef?.el;
        if (el) {
            requestAnimationFrame(() => {
                el.scrollTop = el.scrollHeight;
            });
        }
    }
}

AiAdvisorDrawer.props = {
    params: { type: Object, optional: true },
    close: { type: Function },
};

function openAiAdvisorDrawer(env, action) {
    let closeDrawer;
    closeDrawer = env.services.overlay.add(AiAdvisorDrawer, {
        params: action.params || {},
        close: () => closeDrawer?.(),
    });
}

registry.category("actions").add("diecut_ai_advisor", openAiAdvisorDrawer);

