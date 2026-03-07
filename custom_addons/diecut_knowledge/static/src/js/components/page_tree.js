/** @odoo-module **/

import { Component, useState } from "@odoo/owl";

export class PageTree extends Component {
    static template = "diecut_knowledge.PageTree";
    static props = {
        pages: Array,
        selectedId: { type: Number, optional: true },
        onSelect: Function,
        searchText: { type: String, optional: true },
    };

    setup() {
        this.state = useState({
            expanded: {},
        });
    }

    get filteredPages() {
        const keyword = (this.props.searchText || "").trim().toLowerCase();
        if (!keyword) {
            return this.props.pages;
        }
        return this.props.pages.filter((page) => (page.name || "").toLowerCase().includes(keyword));
    }

    get roots() {
        const rootIds = new Set(this.filteredPages.map((p) => p.id));
        return this.filteredPages.filter((p) => !p.parent_id || !rootIds.has(p.parent_id));
    }

    childrenOf(parentId) {
        return this.filteredPages.filter((p) => p.parent_id === parentId);
    }

    hasChildren(nodeId) {
        return this.childrenOf(nodeId).length > 0;
    }

    isExpanded(nodeId) {
        const value = this.state.expanded[nodeId];
        return value !== false;
    }

    toggleNode(nodeId) {
        this.state.expanded[nodeId] = !this.isExpanded(nodeId);
    }

}
