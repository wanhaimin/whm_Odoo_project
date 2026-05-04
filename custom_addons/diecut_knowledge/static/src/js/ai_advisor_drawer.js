/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, useRef, useState } from "@odoo/owl";

class AiAdvisorDrawer extends Component {
    static template = "diecut_knowledge.AiAdvisorDrawer";

    setup() {
        const params = this.props.params || {};
        this.modelName = params.model || "";
        this.recordId = params.record_id || 0;
        this.recordName = params.record_name || "";
        this.mode = params.mode || (this.modelName === "diecut.kb.article" ? "wiki" : "ai");
        this.sessionId = false;
        this.conversationId = "";
        this.notification = useService("notification");

        this.ui = useState({
            messages: [],
            loading: false,
            inputText: "",
            error: "",
            savingIds: [],
            likingIds: [],
            likedIds: [],
            streamAborted: false,
            wikiMode: this.mode === "wiki",
            modelProfiles: [],
            selectedModelProfileId: 0,
        });
        this.chatBodyRef = useRef("chatBody");
        this.abortController = null;
        this.openclawPollingIds = new Set();

        onWillStart(async () => {
            await this._openSession();
        });
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
        this.ui.streamAborted = false;
        this._pushMessage("user", text);

        const assistantMsg = { role: "assistant", content: "", id: Date.now() + Math.random(), question: text, canSave: false };
        this.ui.messages.push(assistantMsg);
        this.ui.loading = true;
        this._scrollBottom();

        const useOpenClaw = this._selectedModelProfile()?.protocol === "openclaw_worker";
        if (this.ui.wikiMode && !useOpenClaw) {
            // Wiki 模式：直接调 Wiki 查询（当前为一次查询，无对话历史）
            const streamOk = await this._tryWikiStream(assistantMsg, text);
            if (!streamOk) {
                await this._tryWikiBlocking(assistantMsg, text);
            }
        } else {
            // 标准模式：优先尝试 SSE 流式，失败时自动回退到 blocking RPC
            const streamOk = await this._tryStream(assistantMsg, text);
            if (!streamOk) {
                await this._tryBlocking(assistantMsg, text);
            }
        }
        this.ui.loading = false;
        if (!assistantMsg.content && !this.ui.error) {
            assistantMsg.content = "未收到 AI 回复，请稍后重试。";
        }
        this._scrollBottom();
    }

    async switchWikiMode(ev) {
        this.ui.wikiMode = Boolean(ev.target.checked);
        this.mode = this.ui.wikiMode ? "wiki" : "ai";
        this.ui.error = "";
        await this._openSession();
        this._scrollBottom();
    }

    async clearSession() {
        if (!this.sessionId || this.ui.loading) {
            return;
        }
        try {
            const result = await rpc("/diecut_knowledge/ai/session/clear", {
                session_id: this.sessionId,
            });
            if (result.ok) {
                this._applySessionPayload(result);
                this.notification.add("当前 AI 顾问会话已清空", { type: "success" });
            } else {
                this.notification.add(result.error || "清空失败", { type: "danger" });
            }
        } catch (err) {
            this.notification.add(err.message || "清空失败", { type: "danger" });
        }
    }

    async newSession() {
        if (this.ui.loading) {
            return;
        }
        if (this.sessionId) {
            await this.clearSession();
        } else {
            this.ui.messages.splice(0, this.ui.messages.length);
            this._addSystemMessage();
        }
    }

    async _openSession() {
        try {
            const result = await rpc("/diecut_knowledge/ai/session/open", {
                mode: this.mode,
                model: this.modelName,
                record_id: this.recordId,
                record_name: this.recordName,
                model_profile_id: this.ui.selectedModelProfileId || false,
            });
            if (result.ok) {
                this._applySessionPayload(result);
                this._applyModelOptions(result.model_options || {});
            } else if (!this.ui.messages.length) {
                this._addSystemMessage();
            }
        } catch (err) {
            console.warn("Failed to open AI advisor session:", err.message);
            if (!this.ui.messages.length) {
                this._addSystemMessage();
            }
        }
    }

    _applySessionPayload(payload) {
        this.sessionId = payload.session_id || false;
        this.conversationId = payload.conversation_id || "";
        if (payload.model_profile_id) {
            this.ui.selectedModelProfileId = payload.model_profile_id;
        }
        const messages = (payload.messages || []).map((msg) => ({
            id: msg.id || Date.now() + Math.random(),
            role: msg.role,
            content: msg.content || "",
            question: msg.question || "",
            sourceLayer: msg.sourceLayer || "",
            sourceRefs: msg.sourceRefs || [],
            articles: msg.articles || [],
            citations: msg.citations || [],
            compileJobId: msg.compileJobId || false,
            canSave: Boolean(msg.canSave),
            savedArticleId: msg.savedArticleId || false,
            likedArticleId: msg.likedArticleId || false,
            openclawRunId: msg.openclawRunId || false,
            asyncState: msg.asyncState || "",
        }));
        this.ui.messages.splice(0, this.ui.messages.length, ...messages);
        this.ui.likedIds.splice(
            0,
            this.ui.likedIds.length,
            ...messages.filter((msg) => msg.likedArticleId).map((msg) => msg.id)
        );
        if (!this.ui.messages.length) {
            this._addSystemMessage();
        }
        for (const msg of this.ui.messages) {
            if (msg.openclawRunId && ["queued", "running"].includes(msg.asyncState)) {
                this._pollOpenClawMessage(msg);
            }
        }
    }

    _applyModelOptions(options) {
        const profiles = options.profiles || [];
        this.ui.modelProfiles.splice(0, this.ui.modelProfiles.length, ...profiles);
        if (!this.ui.selectedModelProfileId) {
            this.ui.selectedModelProfileId = options.default_id || (profiles[0] && profiles[0].id) || 0;
        }
    }

    onModelProfileChange(ev) {
        this.ui.selectedModelProfileId = parseInt(ev.target.value || "0", 10) || 0;
    }

    _selectedModelProfile() {
        return this.ui.modelProfiles.find((profile) => profile.id === this.ui.selectedModelProfileId) || null;
    }

    async _tryStream(msg, text) {
        try {
            const params = new URLSearchParams();
            params.append("query", text);
            params.append("model", this.modelName);
            params.append("record_id", this.recordId);
            params.append("conversation_id", this.conversationId);
            params.append("session_id", this.sessionId || "");
            params.append("mode", this.mode);
            params.append("record_name", this.recordName);
            params.append("model_profile_id", this.ui.selectedModelProfileId || "");

            this.abortController = new AbortController();
            const response = await fetch("/diecut_knowledge/ai/chat_stream", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: params,
                signal: this.abortController.signal,
            });
            if (!response.ok) return false;
            if (!response.body) return false;

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let streamDone = false;
            let gotAnswer = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const raw = line.slice(6).trim();
                    if (!raw) continue;

                    try {
                        const event = JSON.parse(raw);
                        if (event.error) {
                            this.ui.error = event.error;
                            streamDone = true;
                            break;
                        }
                        if (event.done) {
                            this.conversationId = event.conversation_id || this.conversationId;
                            this.sessionId = event.session_id || this.sessionId;
                            msg.id = event.message_id || msg.id;
                            if (!msg.content && event.full_answer) {
                                msg.content = event.full_answer;
                            }
                            gotAnswer = Boolean(msg.content);
                            msg.canSave = gotAnswer;
                            if (event.citations) {
                                msg.citations = event.citations.map(function(c) {
                                    return {
                                        title: c.title || "",
                                        score: c.score ? Math.round(c.score * 100) + "%" : "",
                                    };
                                });
                            }
                            streamDone = true;
                            break;
                        }
                        if (event.token !== undefined) {
                            msg.content += event.token;
                            gotAnswer = true;
                            msg.canSave = true;
                            this._scrollBottom();
                        }
                    } catch (e) {
                        // skip malformed JSON
                    }
                }
                if (streamDone) break;
            }
            return gotAnswer;
        } catch (err) {
            if (err.name !== "AbortError") {
                console.warn("SSE stream failed, falling back to blocking mode:", err.message);
            }
            return false;
        }
    }

    async _tryBlocking(msg, text) {
        try {
            const result = await rpc("/diecut_knowledge/ai/chat", {
                query: text,
                model: this.modelName,
                record_id: this.recordId,
                conversation_id: this.conversationId,
                session_id: this.sessionId,
                mode: this.mode,
                record_name: this.recordName,
                message_id: msg.id,
                model_profile_id: this.ui.selectedModelProfileId || false,
            });
            if (result.ok) {
                this.conversationId = result.conversation_id || this.conversationId;
                this.sessionId = result.session_id || this.sessionId;
                msg.id = result.message_id || msg.id;
                msg.content = result.answer || "(空响应)";
                msg.canSave = Boolean(result.answer) && !result.queued;
                if (result.queued) {
                    msg.openclawRunId = result.openclaw_run_id || false;
                    msg.asyncState = "queued";
                    this._pollOpenClawMessage(msg);
                }
                if (result.citations) {
                    msg.citations = result.citations.map(function(c) {
                        return {
                            title: c.name || c.title || "",
                            score: c.score ? Math.round(c.score * 100) + "%" : "",
                        };
                    });
                }
            } else {
                this.ui.error = result.error || "调用失败";
                if (!msg.content) {
                    this.ui.messages = this.ui.messages.filter(m => m.id !== msg.id || m.content);
                }
            }
        } catch (err) {
            this.ui.error = err.message || "网络错误";
            if (!msg.content) {
                this.ui.messages = this.ui.messages.filter(m => m.id !== msg.id || m.content);
            }
        }
    }

    async _tryWikiStream(msg, text) {
        try {
            const params = new URLSearchParams();
            params.append("query", text);
            params.append("session_id", this.sessionId || "");
            params.append("mode", this.mode);
            params.append("model", this.modelName);
            params.append("record_id", this.recordId);
            params.append("record_name", this.recordName);
            params.append("model_profile_id", this.ui.selectedModelProfileId || "");

            this.abortController = new AbortController();
            const response = await fetch("/diecut_knowledge/wiki/chat_stream", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: params,
                signal: this.abortController.signal,
            });
            if (!response.ok) return false;
            if (!response.body) return false;

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = "";
            let streamDone = false;
            let gotAnswer = false;

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (!line.startsWith("data: ")) continue;
                    const raw = line.slice(6).trim();
                    if (!raw) continue;

                    try {
                        const event = JSON.parse(raw);
                        if (event.error) {
                            this.ui.error = event.error;
                            streamDone = true;
                            break;
                        }
                        if (event.done) {
                            this.sessionId = event.session_id || this.sessionId;
                            msg.id = event.message_id || msg.id;
                            if (!msg.content && event.full_answer) {
                                msg.content = event.full_answer;
                            }
                            gotAnswer = Boolean(msg.content);
                            msg.canSave = gotAnswer;
                            if (event.articles) {
                                msg.articles = event.articles;
                            }
                            msg.sourceLayer = event.source_layer || msg.sourceLayer;
                            msg.sourceRefs = event.source_refs || msg.sourceRefs;
                            msg.compileJobId = event.compile_job_id || msg.compileJobId;
                            streamDone = true;
                            break;
                        }
                        if (event.token !== undefined) {
                            msg.content += event.token;
                            gotAnswer = true;
                            msg.canSave = true;
                            this._scrollBottom();
                        }
                    } catch (e) {
                        // skip malformed JSON
                    }
                }
                if (streamDone) break;
            }
            return gotAnswer;
        } catch (err) {
            if (err.name !== "AbortError") {
                console.warn("Wiki stream failed, falling back to blocking:", err.message);
            }
            return false;
        }
    }

    async _tryWikiBlocking(msg, text) {
        try {
            const result = await rpc("/diecut_knowledge/wiki/chat", {
                query: text,
                session_id: this.sessionId,
                mode: this.mode,
                model: this.modelName,
                record_id: this.recordId,
                record_name: this.recordName,
                message_id: msg.id,
                model_profile_id: this.ui.selectedModelProfileId || false,
            });
            if (result.ok) {
                this.sessionId = result.session_id || this.sessionId;
                msg.id = result.message_id || msg.id;
                msg.content = result.answer || "(空响应)";
                msg.canSave = Boolean(result.answer);
                if (result.articles) {
                    msg.articles = result.articles;
                }
                msg.sourceLayer = result.source_layer || msg.sourceLayer;
                msg.sourceRefs = result.source_refs || msg.sourceRefs;
                msg.compileJobId = result.compile_job_id || msg.compileJobId;
            } else {
                this.ui.error = result.error || "查询失败";
                if (!msg.content) {
                    this.ui.messages = this.ui.messages.filter(m => m.id !== msg.id || m.content);
                }
            }
        } catch (err) {
            this.ui.error = err.message || "网络错误";
            if (!msg.content) {
                this.ui.messages = this.ui.messages.filter(m => m.id !== msg.id || m.content);
            }
        }
    }

    async _pollOpenClawMessage(message) {
        if (!message?.id || this.openclawPollingIds.has(message.id)) {
            return;
        }
        this.openclawPollingIds.add(message.id);
        try {
            while (["queued", "running"].includes(message.asyncState || "queued")) {
                await this._sleep(2000);
                const result = await rpc("/diecut_knowledge/ai/openclaw_status", {
                    message_id: message.id,
                });
                if (!result.ok) {
                    this.ui.error = result.error || "OpenClaw 状态查询失败";
                    break;
                }
                message.asyncState = result.async_state || "";
                if (result.answer) {
                    message.content = result.answer;
                }
                if (result.async_state === "done") {
                    message.canSave = Boolean(result.can_save);
                    break;
                }
                if (result.async_state === "failed") {
                    message.canSave = false;
                    this.ui.error = result.error || result.answer || "OpenClaw 任务失败";
                    break;
                }
                this._scrollBottom();
            }
        } catch (err) {
            this.ui.error = err.message || "OpenClaw 状态查询失败";
        } finally {
            this.openclawPollingIds.delete(message.id);
            this._scrollBottom();
        }
    }

    _sleep(ms) {
        return new Promise((resolve) => setTimeout(resolve, ms));
    }

    async likeMessage(message) {
        if (!message?.content || !message.question || this.ui.likedIds.includes(message.id) || this.ui.likingIds.includes(message.id)) {
            return;
        }
        this.ui.likingIds.push(message.id);
        try {
            const result = await rpc("/diecut_knowledge/ai/like_answer", {
                question: message.question,
                answer: message.content,
                model: this.modelName,
                record_id: this.recordId,
                record_name: this.recordName,
                message_id: message.id,
            });
            if (result.ok) {
                message.likedArticleId = result.article_id;
                if (!this.ui.likedIds.includes(message.id)) {
                    this.ui.likedIds.push(message.id);
                }
            }
        } catch (err) {
            console.warn("Failed to like AI answer:", err.message);
        } finally {
            this.ui.likingIds = this.ui.likingIds.filter((id) => id !== message.id);
        }
    }

    async saveMessage(message) {
        if (!message?.content || !message.canSave || !message.question || this.ui.savingIds.includes(message.id)) {
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
                message_id: message.id,
            });
            if (result.ok) {
                message.savedArticleId = result.article_id;
                message.canSave = false;
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
        if (this.abortController) {
            this.abortController.abort();
        }
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
