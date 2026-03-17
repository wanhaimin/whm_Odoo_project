/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { _t } from "@web/core/l10n/translation";
import { SearchBar } from "@web/search/search_bar/search_bar";

const QUICK_SEARCH_FIELDS = [
    "code",
    "name",
    "series_id.name",
    "selection_search_text",
    "function_tag_ids.name",
    "function_tag_ids.alias_text",
    "application_tag_ids.name",
    "application_tag_ids.alias_text",
    "feature_tag_ids.name",
    "feature_tag_ids.alias_text",
];

const QUICK_SEARCH_ITEM_LABEL = "智能选型";
const QUICK_SEARCH_FILTER_DESCRIPTION = "选型检索";

function buildOrDomain(term) {
    const leaves = QUICK_SEARCH_FIELDS.map((fieldName) => [fieldName, "ilike", term]);
    if (leaves.length === 1) {
        return leaves[0];
    }
    return [...Array(leaves.length - 1).fill("|"), ...leaves];
}

function buildCombinedDomain(query) {
    const terms = query
        .split(/[\s,;，；]+/)
        .map((term) => term.trim())
        .filter(Boolean)
        .slice(0, 4);
    const effectiveTerms = terms.length ? terms : [query.trim()];
    let domain = null;
    for (const term of effectiveTerms) {
        const termDomain = buildOrDomain(term);
        domain = domain ? ["&", domain, termDomain] : termDomain;
    }
    return domain || [];
}

patch(SearchBar.prototype, {
    isDiecutCatalogQuickSearchEnabled() {
        return this.env.searchModel?.resModel === "diecut.catalog.item";
    },

    getSearchPlaceholder() {
        if (this.isDiecutCatalogQuickSearchEnabled()) {
            return "可直接输入型号、应用、特性、功能词，回车搜索";
        }
        return _t("Search...");
    },

    _getDiecutQuickSearchItem(trimmedQuery) {
        return {
            id: Date.now(),
            isDiecutUnifiedSearch: true,
            title: `${QUICK_SEARCH_ITEM_LABEL}: ${trimmedQuery}`,
            searchItemDescription: QUICK_SEARCH_ITEM_LABEL,
            preposition: _t("for"),
            label: trimmedQuery,
        };
    },

    _clearDiecutQuickSearchFilters() {
        const groupIds = new Set();
        for (const queryElem of this.env.searchModel.query || []) {
            const searchItem = this.env.searchModel.searchItems[queryElem.searchItemId];
            if (searchItem?.diecutQuickSearch) {
                groupIds.add(searchItem.groupId);
            }
        }
        for (const groupId of groupIds) {
            this.env.searchModel.deactivateGroup(groupId);
        }
    },

    _applyDiecutQuickSearch(query) {
        const trimmedQuery = (query || "").trim();
        if (!trimmedQuery || !this.isDiecutCatalogQuickSearchEnabled()) {
            return;
        }
        this._clearDiecutQuickSearchFilters();
        this.env.searchModel.createNewFilters([
            {
                description: QUICK_SEARCH_FILTER_DESCRIPTION,
                tooltip: `${QUICK_SEARCH_FILTER_DESCRIPTION}: ${trimmedQuery}`,
                domain: buildCombinedDomain(trimmedQuery),
                invisible: "True",
                diecutQuickSearch: true,
            },
        ]);
        this.inputDropdownState.close();
        this.resetState();
    },

    onSearchKeydown(ev) {
        if (ev.key === "Enter" && this.isDiecutCatalogQuickSearchEnabled()) {
            const query = ev.target?.value || this.state.query;
            if ((query || "").trim()) {
                ev.preventDefault();
                ev.stopPropagation();
                this._applyDiecutQuickSearch(query);
                return;
            }
        }
    },

    async computeState(options = {}) {
        await super.computeState(...arguments);
        const trimmedQuery = this.state.query.trim();
        if (!trimmedQuery || !this.isDiecutCatalogQuickSearchEnabled()) {
            return;
        }
        this.items.unshift(this._getDiecutQuickSearchItem(trimmedQuery));
    },

    selectItem(item) {
        if (item?.isDiecutUnifiedSearch) {
            this._applyDiecutQuickSearch(item.label);
            return;
        }
        return super.selectItem(...arguments);
    },

    onClickSearchIcon() {
        if (this.isDiecutCatalogQuickSearchEnabled() && this.state.query.trim()) {
            const item = this.items.find((entry) => entry.id === this.lastActiveItemId);
            if (!item) {
                this._applyDiecutQuickSearch(this.state.query);
                return;
            }
        }
        return super.onClickSearchIcon(...arguments);
    },
});
