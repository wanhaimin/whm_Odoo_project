/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onMounted, onPatched, onWillStart, onWillUnmount, useRef, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { View } from "@web/views/view";
import { PageTree } from "./components/page_tree";

class KbWorkspace extends Component {
    static template = "diecut_knowledge.KbWorkspace";
    static components = { PageTree, View };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        this.editorShellRef = useRef("editorShell");
        this.statusHostRef = useRef("statusHost");
        this.state = useState({
            loading: true,
            pages: [],
            selectedId: false,
            searchText: "",
            newPageTitle: "",
            tocItems: [],
        });
        this._tocObserver = null;
        this._tocObservedNode = null;
        this._tocRefreshTimer = null;
        this._tocInputHandler = null;
        this._statusRelocateTimer = null;
        this._onFormSaved = this.onFormSaved.bind(this);
        this._formViewPropsCache = null;
        this._formViewPropsCacheKey = null;

        onWillStart(async () => {
            await this.loadTree();
            if (this.state.pages.length) {
                this.state.selectedId = this.state.pages[0].id;
            }
            this.state.loading = false;
        });

        onMounted(() => {
            this._bindEditorObserver();
            this._scheduleRefreshToc();
            this._scheduleRelocateStatusIndicator();
        });
        onPatched(() => {
            this._bindEditorObserver();
            this._scheduleRefreshToc();
            this._scheduleRelocateStatusIndicator();
        });
        onWillUnmount(() => {
            this._unbindEditorObserver();
            if (this._tocRefreshTimer) {
                clearTimeout(this._tocRefreshTimer);
                this._tocRefreshTimer = null;
            }
            if (this._statusRelocateTimer) {
                clearTimeout(this._statusRelocateTimer);
                this._statusRelocateTimer = null;
            }
        });
    }

    async loadTree() {
        this.state.pages = await this.orm.call("diecut.kb.editor.service", "load_tree", []);
    }

    selectPage(articleId) {
        this.state.selectedId = articleId;
        this._formViewPropsCache = null;
        this._formViewPropsCacheKey = null;
        this._clearStatusHost();
        this._scheduleRefreshToc();
        this._scheduleRelocateStatusIndicator();
    }

    onSearchInput(ev) {
        this.state.searchText = ev.target.value || "";
    }

    onNewPageInput(ev) {
        this.state.newPageTitle = ev.target.value || "";
    }

    async createPage() {
        const title = (this.state.newPageTitle || "").trim();
        try {
            const result = await this.orm.call("diecut.kb.editor.service", "create_page", [title, this.state.selectedId || false]);
            this.state.newPageTitle = "";
            await this.loadTree();
            if (result?.id) {
                this.state.selectedId = result.id;
                this._formViewPropsCache = null;
                this._formViewPropsCacheKey = null;
            }
            this.notification.add("已创建新页面", { type: "success" });
        } catch (error) {
            const message = error?.data?.message || error?.message || "创建页面失败";
            this.notification.add(message, { type: "danger" });
        }
    }

    async archiveCurrentPage() {
        if (!this.state.selectedId) {
            return;
        }
        const ok = window.confirm("确认删除当前页面？删除后将从工作台隐藏（可在后台页面管理中恢复）。");
        if (!ok) {
            return;
        }
        try {
            const result = await this.orm.call("diecut.kb.editor.service", "archive_page", [this.state.selectedId]);
            if (!result?.ok) {
                throw new Error(result?.error || "archive_failed");
            }
            const deletedId = this.state.selectedId;
            await this.loadTree();
            const next = this.state.pages.find((p) => p.id !== deletedId);
            this.state.selectedId = next ? next.id : false;
            this._formViewPropsCache = null;
            this._formViewPropsCacheKey = null;
            this.notification.add("页面已删除", { type: "success" });
        } catch (error) {
            const message = error?.data?.message || error?.message || "删除页面失败";
            this.notification.add(message, { type: "danger" });
        }
    }

    async onFormSaved() {
        await this.loadTree();
        this._scheduleRefreshToc();
        this._scheduleRelocateStatusIndicator();
    }

    openRecycleBin() {
        this.action.doAction("diecut_knowledge.action_diecut_kb_article_recycle");
    }

    onTocClick(ev) {
        const headingId = ev.currentTarget?.dataset?.headingId;
        this._scrollToHeading(headingId);
    }

    onTocSelectChange(ev) {
        const headingId = ev.target?.value;
        this._scrollToHeading(headingId);
    }

    _scrollToHeading(headingId) {
        if (!headingId || !this.editorShellRef.el) {
            return;
        }
        const heading = this.editorShellRef.el.querySelector(`[data-kb-heading-id='${headingId}']`);
        if (heading) {
            heading.scrollIntoView({ behavior: "smooth", block: "start" });
        }
    }

    _scheduleRefreshToc() {
        if (this._tocRefreshTimer) {
            clearTimeout(this._tocRefreshTimer);
        }
        this._tocRefreshTimer = setTimeout(() => {
            this._tocRefreshTimer = null;
            this._refreshToc();
        }, 120);
    }

    _refreshToc() {
        const root = this.editorShellRef.el;
        if (!root) {
            if (this.state.tocItems.length) {
                this.state.tocItems = [];
            }
            return;
        }
        const headings = root.querySelectorAll(
            ".o_field_html .note-editable h1, .o_field_html .note-editable h2, .o_field_html .note-editable h3, .o_field_html .note-editable h4, .o_field_html .o_readonly h1, .o_field_html .o_readonly h2, .o_field_html .o_readonly h3, .o_field_html .o_readonly h4"
        );
        const toc = [];
        let index = 0;
        for (const heading of headings) {
            const text = (heading.textContent || "").trim();
            if (!text) {
                continue;
            }
            index += 1;
            const id = `h${index}`;
            heading.dataset.kbHeadingId = id;
            toc.push({
                id,
                level: Number((heading.tagName || "H1").replace("H", "")) || 1,
                text,
            });
        }
        if (!this._isSameToc(this.state.tocItems, toc)) {
            this.state.tocItems = toc;
        }
    }

    _isSameToc(oldToc, newToc) {
        if (oldToc.length !== newToc.length) {
            return false;
        }
        for (let i = 0; i < oldToc.length; i += 1) {
            const a = oldToc[i];
            const b = newToc[i];
            if (a.id !== b.id || a.level !== b.level || a.text !== b.text) {
                return false;
            }
        }
        return true;
    }

    _findEditorObservedNode() {
        const root = this.editorShellRef.el;
        if (!root) {
            return null;
        }
        return (
            root.querySelector(".o_field_html .note-editable") ||
            root.querySelector(".o_field_html .o_readonly") ||
            root
        );
    }

    _unbindEditorObserver() {
        if (this._tocObserver) {
            this._tocObserver.disconnect();
            this._tocObserver = null;
        }
        if (this._tocObservedNode && this._tocInputHandler) {
            this._tocObservedNode.removeEventListener("input", this._tocInputHandler);
        }
        this._tocObservedNode = null;
        this._tocInputHandler = null;
    }

    _bindEditorObserver() {
        const node = this._findEditorObservedNode();
        if (!node || node === this._tocObservedNode) {
            return;
        }
        this._unbindEditorObserver();
        this._tocObservedNode = node;
        this._tocObserver = new MutationObserver(() => this._scheduleRefreshToc());
        this._tocObserver.observe(node, {
            childList: true,
            subtree: true,
            characterData: true,
        });
        this._tocInputHandler = () => this._scheduleRefreshToc();
        node.addEventListener("input", this._tocInputHandler);
    }

    _clearStatusHost() {
        const host = this.statusHostRef.el;
        if (host) {
            host.replaceChildren();
        }
    }

    _scheduleRelocateStatusIndicator() {
        if (this._statusRelocateTimer) {
            clearTimeout(this._statusRelocateTimer);
        }
        this._statusRelocateTimer = setTimeout(() => {
            this._statusRelocateTimer = null;
            this._relocateStatusIndicator();
        }, 60);
    }

    _relocateStatusIndicator() {
        const host = this.statusHostRef.el;
        const root = this.editorShellRef.el;
        if (!host || !root || !this.state.selectedId) {
            this._clearStatusHost();
            return;
        }
        const indicator = root.querySelector(".o_form_status_indicator");
        if (!indicator) {
            return;
        }
        if (host.firstElementChild && host.firstElementChild !== indicator) {
            host.replaceChildren();
        }
        if (indicator.parentElement !== host) {
            host.appendChild(indicator);
        }
    }

    get selectedBreadcrumbs() {
        if (!this.state.selectedId || !this.state.pages.length) {
            return [];
        }
        const byId = new Map(this.state.pages.map((item) => [item.id, item]));
        const labels = [];
        let current = byId.get(this.state.selectedId);
        let guard = 0;
        while (current && guard < 30) {
            labels.unshift(current.name || `#${current.id}`);
            current = current.parent_id ? byId.get(current.parent_id) : null;
            guard += 1;
        }
        return labels;
    }

    get formViewProps() {
        if (!this.state.selectedId) {
            return null;
        }
        const formViewId = Number(this.props.action?.params?.form_view_id || 0) || false;
        const cacheKey = `${this.state.selectedId}:${formViewId || 0}`;
        if (this._formViewPropsCache && this._formViewPropsCacheKey === cacheKey) {
            return this._formViewPropsCache;
        }
        this._formViewPropsCacheKey = cacheKey;
        this._formViewPropsCache = {
            type: "form",
            resModel: "diecut.kb.article",
            resId: this.state.selectedId,
            viewId: formViewId,
            views: [[formViewId || false, "form"]],
            context: {
                edit: true,
                create: false,
                form_view_initial_mode: "edit",
            },
            display: {
                controlPanel: {},
            },
            readonly: false,
            preventEdit: false,
            preventCreate: true,
            className: "o_diecut_kb_embedded_form",
            onSave: this._onFormSaved,
        };
        return this._formViewPropsCache;
    }
}

registry.category("actions").add("diecut_knowledge_workspace", KbWorkspace);
