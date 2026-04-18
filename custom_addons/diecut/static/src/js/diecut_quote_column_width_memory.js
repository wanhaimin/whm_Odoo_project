/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ListRenderer } from "@web/views/list/list_renderer";

const STORAGE_KEY = "diecut_quote_column_widths:diecut.quote";
const MIN_COLUMN_WIDTH = 30;
const HEADER_HORIZONTAL_PADDING = 20;
const TABLE_KEY_BY_MODEL = {
    "diecut.quote.material.line": "material_line_ids",
    "diecut.quote.manufacturing.line": "manufacturing_line_ids",
};

function readStoredWidths() {
    try {
        return JSON.parse(window.localStorage.getItem(STORAGE_KEY) || "{}");
    } catch (error) {
        return {};
    }
}

function writeStoredWidths(widths) {
    try {
        window.localStorage.setItem(STORAGE_KEY, JSON.stringify(widths));
    } catch (error) {
        // Browser storage can be disabled or full. In that case, keep Odoo defaults.
    }
}

function getTableKey(renderer) {
    return TABLE_KEY_BY_MODEL[renderer.props.list && renderer.props.list.resModel];
}

function getHeaderCells(table) {
    return [...table.querySelectorAll("thead th[data-name]")];
}

function getStoragePrefix(tableKey) {
    return `${tableKey}:`;
}

function getStoredColumnWidth(tableKey, columnName) {
    const width = readStoredWidths()[`${tableKey}:${columnName}`];
    if (!Number.isFinite(width) || width < MIN_COLUMN_WIDTH) {
        return null;
    }
    return Math.max(MIN_COLUMN_WIDTH, Math.round(width - HEADER_HORIZONTAL_PADDING));
}

patch(ListRenderer.prototype, {
    setup() {
        super.setup();

        const tableKey = getTableKey(this);
        if (!tableKey || !this.columnWidths) {
            return;
        }

        const originalStartResize = this.columnWidths.onStartResize.bind(this.columnWidths);
        this.columnWidths.onStartResize = (ev) => {
            const result = originalStartResize(ev);
            let handled = false;
            const persistOnce = () => {
                if (handled) {
                    return;
                }
                handled = true;
                window.removeEventListener("pointerup", persistOnce, true);
                window.removeEventListener("keydown", persistOnce, true);
                window.setTimeout(() => this._diecutQuoteSaveColumnWidths(), 0);
            };

            window.addEventListener("pointerup", persistOnce, true);
            window.addEventListener("keydown", persistOnce, true);
            return result;
        };

        const originalResetWidths = this.columnWidths.resetWidths.bind(this.columnWidths);
        this.columnWidths.resetWidths = (...args) => {
            this._diecutQuoteClearColumnWidths();
            return originalResetWidths(...args);
        };
    },

    getActiveColumns() {
        const columns = super.getActiveColumns();
        const tableKey = getTableKey(this);
        if (!tableKey) {
            return columns;
        }

        return columns.map((column) => {
            if (column.type !== "field" || !column.name) {
                return column;
            }
            const storedWidth = getStoredColumnWidth(tableKey, column.name);
            if (!storedWidth) {
                return column;
            }
            return {
                ...column,
                attrs: {
                    ...(column.attrs || {}),
                    width: `${storedWidth}px`,
                },
            };
        });
    },

    _diecutQuoteGetTable() {
        return this.tableRef && this.tableRef.el;
    },

    _diecutQuoteSaveColumnWidths() {
        const table = this._diecutQuoteGetTable();
        const tableKey = getTableKey(this);
        if (!table || !tableKey) {
            return;
        }

        const storagePrefix = getStoragePrefix(tableKey);
        const widths = readStoredWidths();
        for (const key of Object.keys(widths)) {
            if (key.startsWith(storagePrefix)) {
                delete widths[key];
            }
        }

        for (const th of getHeaderCells(table)) {
            const columnName = th.dataset.name;
            const width = Math.round(th.getBoundingClientRect().width);
            if (columnName && Number.isFinite(width) && width >= MIN_COLUMN_WIDTH) {
                widths[`${tableKey}:${columnName}`] = width;
            }
        }
        writeStoredWidths(widths);
    },

    _diecutQuoteClearColumnWidths() {
        const tableKey = getTableKey(this);
        if (!tableKey) {
            return;
        }

        const storagePrefix = getStoragePrefix(tableKey);
        const widths = readStoredWidths();
        for (const key of Object.keys(widths)) {
            if (key.startsWith(storagePrefix)) {
                delete widths[key];
            }
        }
        writeStoredWidths(widths);
    },
});
