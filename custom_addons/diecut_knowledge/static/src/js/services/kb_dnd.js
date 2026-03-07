/** @odoo-module **/

export function reorderByDrag(blocks, draggedId, targetId) {
    if (!draggedId || !targetId || draggedId === targetId) {
        return blocks;
    }
    const list = [...blocks];
    const from = list.findIndex((item) => item.id === draggedId);
    const to = list.findIndex((item) => item.id === targetId);
    if (from < 0 || to < 0) {
        return blocks;
    }
    const [moved] = list.splice(from, 1);
    list.splice(to, 0, moved);
    return list.map((item, index) => ({ ...item, sequence: (index + 1) * 10 }));
}
