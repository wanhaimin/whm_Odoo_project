/** @odoo-module **/

/**
 * 材料型号清单 - 列显隐规则（仅在本视图生效，不影响原材料等其它列表）
 * 1) 按分类显示密度：泡棉/屏蔽材料等显示密度列，其他分类不显示。
 * 2) 全空列自动隐藏：当选择某一类时，若某列在当前结果集中全部为空则自动隐藏。
 * 仅当列表同时存在 product_tmpl_id、catalog_categ_id 列时执行（材料型号清单），原材料列表视图不生效。
 *
 * Odoo 19 SearchPanel 层级分类 DOM 结构：
 *   <li class="o_search_panel_category_value">
 *     <header class="active">          ← active 在 header 上
 *       <div class="o_search_panel_label">
 *         <span class="o_search_panel_label_title">泡棉类</span>
 *       </div>
 *     </header>
 *     <ul>  ← 子分类列表
 *       <li class="o_search_panel_category_value">
 *         <header class="active">  ← 如果选的是子分类
 *           ...
 *
 * Odoo 19 列表视图 DOM：
 *   <th data-name="field_name">  （表头）
 *   <td> 可能用 name="field_name" 或 data-name="field_name"（版本/渲染差异），需兼容两种
 *
 * 如何看 DOM（Chrome）：F12 → 选「元素」/ Elements → 左上角「选择元素」箭头点一下
 * → 再点列表里「特性」或「胶厚」列中任意一格 → 左侧会定位到该 <td> 或 .o_data_cell，
 * 看其 HTML 是 name="catalog_characteristics" 还是 data-name="catalog_characteristics"。
 * 控制台调试：在材料型号清单页打开控制台输入 window.__diecutCatalogDebug = true 回车，
 * 再切换一次左侧分类或刷新列表，会打印列名、每列找到的单元格数、显隐结果。
 */

const SHOW_KEYWORDS = {
    catalog_density: ["泡棉", "屏蔽材料", "金属箔", "石墨"],
};

const STYLE_ID = "diecut-dynamic-col-style";
let _lastFingerprint = "";

function getActiveCategoryPath() {
    const names = [];

    const activeHeader = document.querySelector(
        ".o_search_panel_category_value > header.active"
    );
    if (!activeHeader) return names;

    const selfLabel = activeHeader.querySelector(".o_search_panel_label_title");
    if (selfLabel) names.push(selfLabel.textContent.trim());

    let li = activeHeader.closest("li.o_search_panel_category_value");
    if (!li) return names;

    let parentLi = li.parentElement && li.parentElement.closest("li.o_search_panel_category_value");
    while (parentLi) {
        const parentLabel = parentLi.querySelector(
            ":scope > header .o_search_panel_label_title"
        );
        if (parentLabel) names.push(parentLabel.textContent.trim());
        parentLi = parentLi.parentElement && parentLi.parentElement.closest("li.o_search_panel_category_value");
    }

    return names;
}

/** 单元格是否视为“空”（无值） */
function isCellEmpty(td) {
    if (!td) return true;
    let text = (td.textContent || "").trim();
    if (text === "" || text === "—" || text === "-") return true;
    // 仅显示分类路径（如 原材料/胶带类/…）或省略号视为空，便于自动隐藏“特性”等未填列
    if (/^原材料\/.*$/.test(text) || text === "..." || /^\.\.\.$/.test(text)) return true;
    const num = parseFloat(String(text).replace(/,/g, ""));
    if (!Number.isNaN(num) && num === 0) return true;
    return false;
}

/** 取列表所在 table 或等效根（.o_list_view 可能是 div 包裹 table，或自身为 table，或 div 内直接 thead+tbody） */
function getListTable() {
    const list = document.querySelector(".o_list_view");
    if (!list) return null;
    if (list.tagName === "TABLE") return list;
    const table = list.querySelector ? list.querySelector("table") : null;
    if (table) return table;
    if (list.querySelector && list.querySelector("thead")) return list;
    return null;
}

/** 当前列表中所有列名（来自表头 th[data-name]） */
function getListColumnNames() {
    const table = getListTable();
    if (!table) return [];
    const headers = table.querySelectorAll("th[data-name]");
    return Array.from(headers).map((th) => th.getAttribute("data-name")).filter(Boolean);
}

/**
 * 按“全空则隐藏”计算：用列索引取单元格，不依赖 td 的 name/data-name。
 * 返回 { result: { 字段名: 是否显示 }, columnIndices: { 字段名: 列索引0-based } }
 */
function computeVisibilityEmptyColumns() {
    const table = getListTable();
    const result = {};
    const columnIndices = {};
    if (!table) return { result, columnIndices };

    const list = document.querySelector(".o_list_view");
    const thead = table.querySelector("thead");
    const headerRow = thead ? thead.querySelector("tr") : null;
    let tbody = table.querySelector("tbody");
    if (!tbody && list) tbody = list.querySelector("tbody");
    const rows = tbody ? Array.from(tbody.querySelectorAll("tr.o_data_row, tr[data-id]")) : [];
    const ths = Array.from(table.querySelectorAll("th[data-name]"));

    if (!headerRow || ths.length === 0) return { result, columnIndices };

    for (let i = 0; i < ths.length; i++) {
        const name = ths[i].getAttribute("data-name");
        if (!name) continue;
        const colIdx = Array.from(headerRow.children).indexOf(ths[i]);
        columnIndices[name] = colIdx;

        let hasNonEmpty = false;
        if (colIdx >= 0) {
            for (const tr of rows) {
                const cell = tr.children[colIdx];
                if (cell && !isCellEmpty(cell)) {
                    hasNonEmpty = true;
                    break;
                }
            }
        }
        result[name] = hasNonEmpty;
    }
    return { result, columnIndices };
}

/** 密度列：仅当分类路径命中关键词时允许显示 */
function computeVisibilityDensity() {
    const pathNames = getActiveCategoryPath();
    const allow = pathNames.some((name) =>
        (SHOW_KEYWORDS.catalog_density || []).some((kw) => name.includes(kw))
    );
    return { catalog_density: allow };
}

/** 合并：先按“全空则隐藏”得到各列显隐，再对密度列按分类限制；返回 { visMap, columnIndices } */
function computeVisibility() {
    const { result: byEmpty, columnIndices } = computeVisibilityEmptyColumns();
    const byCategory = computeVisibilityDensity();

    const merged = { ...byEmpty };
    if (Object.prototype.hasOwnProperty.call(byCategory, "catalog_density")) {
        merged.catalog_density = (byEmpty.catalog_density !== false) && byCategory.catalog_density;
    }
    return { visMap: merged, columnIndices };
}

function applyVisibility(visMap, columnIndices = {}) {
    const fingerprint = JSON.stringify(visMap);
    if (fingerprint === _lastFingerprint) return;
    _lastFingerprint = fingerprint;

    let styleEl = document.getElementById(STYLE_ID);
    if (!styleEl) {
        styleEl = document.createElement("style");
        styleEl.id = STYLE_ID;
        document.head.appendChild(styleEl);
    }

    const rules = [];
    for (const [field, show] of Object.entries(visMap)) {
        const display = show ? "table-cell" : "none";
        rules.push(`.o_list_view th[data-name="${field}"] { display: ${display} !important; }`);
        const n = columnIndices[field];
        if (typeof n === "number" && n >= 0) {
            const nth = n + 1;
            rules.push(
                `.o_list_view table thead tr th:nth-child(${nth}) { display: ${display} !important; }`,
                `.o_list_view table tbody tr td:nth-child(${nth}) { display: ${display} !important; }`,
            );
        } else {
            rules.push(
                `.o_list_view td[name="${field}"], .o_list_view td[data-name="${field}"], .o_list_view [data-name="${field}"].o_data_cell { display: ${display} !important; }`,
            );
        }
    }
    styleEl.textContent = rules.join("\n");
}

/** 仅材料型号清单生效：该视图同时有 product_tmpl_id（系列）与 catalog_categ_id（分类），且为 product.product 列表；不依赖 optional 列（如 catalog_density 可能未勾选） */
function isCatalogVariantList() {
    const table = getListTable();
    if (!table) return false;
    const hasSeries = !!table.querySelector("th[data-name='product_tmpl_id']");
    const hasCatalogCateg = !!table.querySelector("th[data-name='catalog_categ_id']");
    return hasSeries && hasCatalogCateg;
}

function refresh() {
    if (!isCatalogVariantList()) {
        const styleEl = document.getElementById(STYLE_ID);
        if (styleEl) styleEl.textContent = "";
        if (_observeList) {
            _observeList.disconnect();
            _observeList = null;
        }
        return;
    }
    const { visMap, columnIndices } = computeVisibility();
    if (typeof window !== "undefined" && window.__diecutCatalogDebug) {
        const columnNames = getListColumnNames();
        const table = getListTable();
        const sample = {};
        const headerRow = table && table.querySelector("thead tr");
        const tbody = table && table.querySelector("tbody");
        const rows = tbody ? tbody.querySelectorAll("tr.o_data_row, tr[data-id]") : [];
        for (const name of columnNames) {
            const colIdx = columnIndices[name];
            let firstText = "";
            if (typeof colIdx === "number" && rows.length > 0 && rows[0].children[colIdx]) {
                firstText = (rows[0].children[colIdx].textContent || "").trim().slice(0, 30);
            }
            sample[name] = { colIdx, show: visMap[name], firstText };
        }
        console.log("[diecut 空列] 列名:", columnNames, "显隐:", visMap, "列索引:", columnIndices, "样本:", sample);
    }
    applyVisibility(visMap, columnIndices);
}

/** 点击列表格子时打开该记录的 FORM 视图（仅材料型号清单） */
function openFormOnCellClick(ev) {
    if (!isCatalogVariantList()) return;
    const cell = ev.target.closest("td, .o_data_cell");
    if (!cell) return;
    if (ev.target.closest("button, [role='button'], .o_list_button, input[type='checkbox'], input[type='text'], a.btn, .o_optional_columns_dropdown")) return;
    const row = cell.closest("tr.o_data_row, tr[data-id], .o_data_row[data-id], [data-id]");
    if (!row) return;
    const resId = row.getAttribute("data-id") || row.getAttribute("data-record-id");
    if (!resId) return;
    const hash = (window.location.hash || "").replace(/^#/, "");
    const params = new URLSearchParams(hash);
    params.set("id", resId);
    params.set("view_type", "form");
    if (!params.has("model")) params.set("model", "product.product");
    window.location.hash = params.toString();
    ev.preventDefault();
    ev.stopPropagation();
}

document.addEventListener("click", (ev) => {
    if (ev.target.closest(".o_search_panel")) {
        requestAnimationFrame(refresh);
        setTimeout(refresh, 80);
        setTimeout(refresh, 350);
    }
    openFormOnCellClick(ev);
}, true);

const listRoot = () => {
    const table = getListTable();
    return table ? table.querySelector("tbody") : document.querySelector(".o_list_view tbody");
};
let _observeList = null;
function startObservingList() {
    if (_observeList || !isCatalogVariantList()) return;
    const body = listRoot();
    if (!body) return;
    _observeList = new MutationObserver(() => {
        requestAnimationFrame(refresh);
    });
    _observeList.observe(body, { childList: true, subtree: true });
}
setInterval(() => {
    if (!document.querySelector(".o_search_panel")) return;
    if (isCatalogVariantList()) {
        if (!_observeList) startObservingList();
        refresh();
    }
}, 500);
