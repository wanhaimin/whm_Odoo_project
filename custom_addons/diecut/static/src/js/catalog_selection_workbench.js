/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, onWillUnmount, useState } from "@odoo/owl";

const OPERATOR_LABELS = {
    eq: "=",
    gte: ">=",
    lte: "<=",
    between: _t("区间"),
    contains: _t("包含"),
    in: _t("任选"),
};

function nextUid() {
    return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

export class DiecutSelectionWorkbench extends Component {
    static template = "diecut.SelectionWorkbench";

    setup() {
        this.actionService = useService("action");
        this.notification = useService("notification");
        this.orm = useService("orm");
        this.bodyClassName = "o_diecut_selection_workbench_active";
        this.scrollContainer = null;
        this.scrollContainerStyle = null;
        this.state = useState({
            loading: true,
            searching: false,
            errorMessage: "",
            keyword: "",
            brandId: "",
            categId: "",
            platformId: "",
            sceneIds: [],
            sort: "relevance",
            viewMode: "kanban",
            conditions: [],
            pendingParamId: "",
            results: [],
            resultCount: 0,
            compareParamIds: [],
            compareIds: [],
            compareDrawerOpen: false,
            counts: {
                items: 0,
                brands: 0,
                categories: 0,
                scenes: 0,
                platforms: 0,
                params: 0,
            },
            brands: [],
            categories: [],
            platforms: [],
            scenes: [],
            featuredScenes: [],
            params: [],
            compareParams: [],
            defaultCompareParamIds: [],
        });

        onWillStart(async () => {
            await this.loadBootstrap();
            await this.search();
        });

        onMounted(() => {
            document.body.classList.add(this.bodyClassName);
            const container = this.el?.closest(".o_action_manager");
            if (!container) {
                return;
            }
            this.scrollContainer = container;
            this.scrollContainerStyle = {
                overflow: container.style.overflow,
                overflowY: container.style.overflowY,
            };
            container.style.overflow = "auto";
            container.style.overflowY = "auto";
        });

        onWillUnmount(() => {
            document.body.classList.remove(this.bodyClassName);
            if (!this.scrollContainer || !this.scrollContainerStyle) {
                return;
            }
            this.scrollContainer.style.overflow = this.scrollContainerStyle.overflow || "";
            this.scrollContainer.style.overflowY = this.scrollContainerStyle.overflowY || "";
        });
    }

    async loadBootstrap() {
        this.state.loading = true;
        this.state.errorMessage = "";
        try {
            const categId = this.state.categId ? Number(this.state.categId) : false;
            const bootstrap = await this.orm.call("diecut.catalog.item", "get_selection_workbench_bootstrap", [categId]);
            this.state.counts = bootstrap.counts || this.state.counts;
            this.state.brands = bootstrap.brands || [];
            this.state.categories = bootstrap.categories || [];
            this.state.platforms = bootstrap.platforms || [];
            this.state.scenes = bootstrap.scenes || [];
            this.state.featuredScenes = bootstrap.featured_scenes || [];
            this.state.params = bootstrap.params || [];
            this.state.defaultCompareParamIds = bootstrap.default_compare_param_ids || [];
            if (!this.state.compareParamIds.length) {
                this.state.compareParamIds = [...this.state.defaultCompareParamIds];
            } else {
                const allowedParamIds = new Set(this.state.params.map((param) => param.id));
                this.state.compareParamIds = this.state.compareParamIds.filter((paramId) => allowedParamIds.has(paramId));
                if (!this.state.compareParamIds.length) {
                    this.state.compareParamIds = [...this.state.defaultCompareParamIds];
                }
            }
            this._pruneInvalidConditions();
            if (this.state.pendingParamId && !this.availableParams.some((param) => String(param.id) === this.state.pendingParamId)) {
                this.state.pendingParamId = "";
            }
        } catch (error) {
            this.state.errorMessage = error.message || _t("选型工作台加载失败");
        } finally {
            this.state.loading = false;
        }
    }

    get availableParams() {
        const categId = Number(this.state.categId || 0);
        return (this.state.params || []).filter((param) => {
            if (!categId) {
                return true;
            }
            return !param.allowed_category_ids.length || param.allowed_category_ids.includes(categId);
        });
    }

    get compareItems() {
        const compareIdSet = new Set(this.state.compareIds);
        return (this.state.results || []).filter((result) => compareIdSet.has(result.id));
    }

    get activeFilterChips() {
        const chips = [];
        for (const sceneId of this.state.sceneIds) {
            const scene = (this.state.scenes || []).find((entry) => entry.id === sceneId);
            if (scene) {
                chips.push({ key: `scene-${scene.id}`, label: `${_t("场景")}: ${scene.name}`, kind: "scene", id: scene.id });
            }
        }
        for (const condition of this.state.conditions) {
            const summary = this.getConditionSummary(condition);
            if (summary) {
                chips.push({ key: condition.uid, label: summary, kind: "condition", id: condition.uid });
            }
        }
        return chips;
    }

    get summaryText() {
        if (!this.state.results.length) {
            return _t("没有匹配结果，建议先减少参数条件或改用关键词检索。");
        }
        return _t("已在当前页面返回候选材料，可继续叠加参数、场景或对比。");
    }

    get canCompare() {
        return this.state.compareIds.length >= 2;
    }

    get sortOptions() {
        return [
            { value: "relevance", label: _t("按命中度") },
            { value: "brand", label: _t("按品牌") },
            { value: "series", label: _t("按系列") },
            { value: "thickness", label: _t("按厚度") },
        ];
    }

    get viewModeOptions() {
        return [
            { value: "kanban", label: "看板" },
            { value: "list", label: "列表" },
        ];
    }

    getParam(paramId) {
        return (this.state.params || []).find((param) => param.id === Number(paramId));
    }

    getOperatorOptions(condition) {
        const param = this.getParam(condition.paramId);
        const allowedOperators = param?.allowed_operators || ["contains"];
        return allowedOperators.map((operator) => ({
            value: operator,
            label: OPERATOR_LABELS[operator] || operator,
        }));
    }

    buildCondition(paramId) {
        const param = this.getParam(paramId) || this.availableParams[0];
        if (!param) {
            return null;
        }
        const operator = (param.allowed_operators || ["contains"])[0];
        return {
            uid: nextUid(),
            paramId: param.id,
            operator,
            value: "",
            valueTo: "",
            values: [],
        };
    }

    _pruneInvalidConditions() {
        const allowedParamIds = new Set(this.availableParams.map((param) => param.id));
        this.state.conditions = this.state.conditions.filter((condition) => allowedParamIds.has(Number(condition.paramId)));
    }

    updateField(fieldName, ev) {
        this.state[fieldName] = ev.target.value || "";
    }

    async updateCategory(ev) {
        this.state.categId = ev.target.value || "";
        await this.loadBootstrap();
        await this.search();
    }

    async updateSort(ev) {
        this.state.sort = ev.target.value || "relevance";
        await this.search();
    }

    setViewMode(mode) {
        this.state.viewMode = mode === "list" ? "list" : "kanban";
    }

    toggleScene(sceneId) {
        const normalizedId = Number(sceneId);
        const sceneIds = new Set(this.state.sceneIds);
        if (sceneIds.has(normalizedId)) {
            sceneIds.delete(normalizedId);
        } else {
            sceneIds.add(normalizedId);
        }
        this.state.sceneIds = [...sceneIds];
    }

    clearChip(chip) {
        if (chip.kind === "scene") {
            this.state.sceneIds = this.state.sceneIds.filter((sceneId) => sceneId !== chip.id);
        } else if (chip.kind === "condition") {
            this.removeCondition(chip.id);
        }
    }

    addCondition() {
        const selectedParamId = Number(this.state.pendingParamId || this.availableParams[0]?.id || 0);
        const condition = this.buildCondition(selectedParamId);
        if (!condition) {
            this.notification.add(_t("当前分类下没有可用于筛选的参数"), { type: "warning" });
            return;
        }
        this.state.conditions = [...this.state.conditions, condition];
        this.state.pendingParamId = "";
    }

    removeCondition(uid) {
        this.state.conditions = this.state.conditions.filter((condition) => condition.uid !== uid);
    }

    changeConditionParam(uid, ev) {
        const paramId = Number(ev.target.value || 0);
        const condition = this.buildCondition(paramId);
        if (!condition) {
            return;
        }
        this.state.conditions = this.state.conditions.map((entry) => (entry.uid === uid ? { ...condition, uid } : entry));
    }

    changeConditionOperator(uid, ev) {
        const operator = ev.target.value || "contains";
        this.state.conditions = this.state.conditions.map((entry) =>
            entry.uid === uid
                ? {
                      ...entry,
                      operator,
                      value: operator === "in" ? "" : entry.value,
                      valueTo: operator === "between" ? entry.valueTo : "",
                      values: operator === "in" ? entry.values : [],
                  }
                : entry
        );
    }

    changeConditionValue(uid, ev) {
        const value = ev.target.value || "";
        this.state.conditions = this.state.conditions.map((entry) => (entry.uid === uid ? { ...entry, value } : entry));
    }

    changeConditionValueTo(uid, ev) {
        const valueTo = ev.target.value || "";
        this.state.conditions = this.state.conditions.map((entry) => (entry.uid === uid ? { ...entry, valueTo } : entry));
    }

    changeConditionValues(uid, ev) {
        const values = [...ev.target.selectedOptions].map((option) => option.value);
        this.state.conditions = this.state.conditions.map((entry) => (entry.uid === uid ? { ...entry, values } : entry));
    }

    serializeConditions() {
        const serialized = [];
        for (const condition of this.state.conditions) {
            const param = this.getParam(condition.paramId);
            if (!param) {
                continue;
            }
            const item = {
                param_id: param.id,
                operator: condition.operator,
            };
            if (param.value_type === "float") {
                if (condition.value === "") {
                    continue;
                }
                item.value = Number(condition.value);
                if (condition.operator === "between" && condition.valueTo !== "") {
                    item.value_to = Number(condition.valueTo);
                }
            } else if (param.value_type === "boolean") {
                if (condition.value === "") {
                    continue;
                }
                item.value = condition.value === "true";
            } else if (param.value_type === "selection") {
                if (condition.operator === "in") {
                    if (!condition.values.length) {
                        continue;
                    }
                    item.values = [...condition.values];
                } else {
                    if (!condition.value) {
                        continue;
                    }
                    item.value = condition.value;
                }
            } else {
                if (!condition.value) {
                    continue;
                }
                item.value = condition.value;
            }
            serialized.push(item);
        }
        return serialized;
    }

    getConditionSummary(condition) {
        const param = this.getParam(condition.paramId);
        if (!param) {
            return "";
        }
        const operatorLabel = OPERATOR_LABELS[condition.operator] || condition.operator;
        if (param.value_type === "float") {
            if (condition.operator === "between") {
                return `${param.name} ${operatorLabel} ${condition.value || ""} ~ ${condition.valueTo || ""}`.trim();
            }
            return `${param.name} ${operatorLabel} ${condition.value || ""}`.trim();
        }
        if (param.value_type === "selection" && condition.operator === "in") {
            return `${param.name} ${operatorLabel} ${condition.values.join(" / ")}`;
        }
        if (param.value_type === "boolean") {
            const booleanLabel = condition.value === "true" ? _t("是") : condition.value === "false" ? _t("否") : "";
            return `${param.name} ${operatorLabel} ${booleanLabel}`.trim();
        }
        return `${param.name} ${operatorLabel} ${condition.value || ""}`.trim();
    }

    async search() {
        this.state.searching = true;
        this.state.errorMessage = "";
        try {
            const payload = {
                keyword: this.state.keyword,
                brand_id: this.state.brandId ? Number(this.state.brandId) : false,
                categ_id: this.state.categId ? Number(this.state.categId) : false,
                brand_platform_id: this.state.platformId ? Number(this.state.platformId) : false,
                scene_ids: [...this.state.sceneIds],
                sort: this.state.sort,
                conditions: this.serializeConditions(),
                compare_param_ids: [...this.state.compareParamIds],
                limit: 24,
            };
            const result = await this.orm.call("diecut.catalog.item", "get_selection_workbench_results", [payload]);
            this.state.results = result.results || [];
            this.state.resultCount = result.total || 0;
            this.state.compareParams = result.compare_params || [];
            const compareIdSet = new Set((result.results || []).map((item) => item.id));
            this.state.compareIds = this.state.compareIds.filter((itemId) => compareIdSet.has(itemId));
        } catch (error) {
            this.state.errorMessage = error.message || _t("查询失败");
        } finally {
            this.state.searching = false;
        }
    }

    async resetFilters() {
        this.state.keyword = "";
        this.state.brandId = "";
        this.state.categId = "";
        this.state.platformId = "";
        this.state.sceneIds = [];
        this.state.conditions = [];
        this.state.pendingParamId = "";
        this.state.sort = "relevance";
        this.state.compareIds = [];
        this.state.compareDrawerOpen = false;
        await this.loadBootstrap();
        await this.search();
    }

    toggleCompare(itemId) {
        const compareIds = new Set(this.state.compareIds);
        if (compareIds.has(itemId)) {
            compareIds.delete(itemId);
        } else {
            if (compareIds.size >= 4) {
                this.notification.add(_t("最多同时对比 4 个材料"), { type: "warning" });
                return;
            }
            compareIds.add(itemId);
        }
        this.state.compareIds = [...compareIds];
        if (this.state.compareIds.length) {
            this.state.compareDrawerOpen = true;
        }
    }

    toggleCompareDrawer() {
        this.state.compareDrawerOpen = !this.state.compareDrawerOpen;
    }

    async openRecord(recordId) {
        await this.actionService.doAction({
            type: "ir.actions.act_window",
            res_model: "diecut.catalog.item",
            res_id: recordId,
            views: [[false, "form"]],
            target: "current",
            context: {
                form_view_initial_mode: "edit",
            },
        });
    }

    isInCompare(recordId) {
        return this.state.compareIds.includes(recordId);
    }
}

registry.category("actions").add("diecut_selection_workbench", DiecutSelectionWorkbench);
