/** @odoo-module **/

/**
 * Shift+Click 范围选择支持
 * 
 * 用于 diecut.quote 材料明细行的 is_checked 复选框。
 * 按住 Shift 键点击复选框时，会自动勾选/取消从上次点击到当前点击之间的所有行。
 */

const _shiftState = {
    lastClickedRow: -1,
    isProcessing: false,
};

document.addEventListener("click", async (ev) => {
    // 批量处理时忽略（防止循环触发）
    if (_shiftState.isProcessing) return;

    // 必须是 checkbox 点击
    const input = ev.target.closest("input[type='checkbox']");
    if (!input) return;

    // 必须是 is_checked 字段的单元格
    const cell = input.closest("td[name='is_checked']");
    if (!cell) return;

    // 获取行和表格
    const row = cell.closest("tr.o_data_row");
    const tbody = row?.closest("tbody");
    if (!row || !tbody) return;

    const allRows = [...tbody.querySelectorAll(":scope > tr.o_data_row")];
    const currentIndex = allRows.indexOf(row);

    // Shift+Click 范围选择
    if (ev.shiftKey && _shiftState.lastClickedRow >= 0 && _shiftState.lastClickedRow !== currentIndex) {
        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();

        _shiftState.isProcessing = true;

        const start = Math.min(_shiftState.lastClickedRow, currentIndex);
        const end = Math.max(_shiftState.lastClickedRow, currentIndex);
        // 目标状态 = 当前 checkbox 取反（因为 preventDefault 阻止了原生切换）
        const desiredState = !input.checked;

        for (let i = start; i <= end; i++) {
            const rowCb = allRows[i]?.querySelector("td[name='is_checked'] input[type='checkbox']");
            if (rowCb && rowCb.checked !== desiredState) {
                rowCb.click();
                // 等待 Owl 框架处理单次更新
                await new Promise((r) => setTimeout(r, 80));
            }
        }

        _shiftState.isProcessing = false;
        _shiftState.lastClickedRow = currentIndex;
        return;
    }

    // 普通点击：记录当前行索引
    _shiftState.lastClickedRow = currentIndex;
}, true); // capture phase: 在 Odoo 的处理器之前拦截
