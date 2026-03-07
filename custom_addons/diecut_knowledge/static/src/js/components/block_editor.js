/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { BlockNode } from "./block_node";
import { SlashMenu } from "./slash_menu";
import { reorderByDrag } from "../services/kb_dnd";

export class BlockEditor extends Component {
    static template = "diecut_knowledge.BlockEditor";
    static components = { BlockNode, SlashMenu };
    static props = {
        article: { type: Object, optional: true },
        blocks: Array,
        onBatchOps: Function,
    };

    setup() {
        this.state = useState({
            slashVisible: false,
            slashBlockId: false,
            draggedId: false,
            focusedBlockId: false,
            fontName: "Arial",
        });
    }

    updateBlock(blockId, patch) {
        this.props.onBatchOps([
            {
                type: "update",
                id: blockId,
                ...patch,
            },
        ]);
    }

    deleteBlock(blockId) {
        this.props.onBatchOps([{ type: "delete", id: blockId }]);
    }

    insertAfter(blockId) {
        const target = this.props.blocks.find((b) => b.id === blockId);
        const sequence = target ? target.sequence + 5 : (this.props.blocks.length + 1) * 10;
        this.props.onBatchOps([
            {
                type: "create",
                block_type: "paragraph",
                sequence,
                depth: target ? target.depth : 0,
                parent_block_id: target ? target.parent_block_id : false,
                content: { text: "" },
            },
        ]);
    }

    indentBlock(blockId) {
        const index = this.props.blocks.findIndex((b) => b.id === blockId);
        if (index <= 0) {
            return;
        }
        const block = this.props.blocks[index];
        const previous = this.props.blocks[index - 1];
        this.props.onBatchOps([
            {
                type: "update",
                id: blockId,
                parent_block_id: previous.id,
                depth: Math.min((previous.depth || 0) + 1, 5),
            },
        ]);
    }

    outdentBlock(blockId) {
        const block = this.props.blocks.find((b) => b.id === blockId);
        if (!block) {
            return;
        }
        this.props.onBatchOps([
            {
                type: "update",
                id: blockId,
                parent_block_id: false,
                depth: Math.max((block.depth || 0) - 1, 0),
            },
        ]);
    }

    showSlash(blockId) {
        if (!blockId) {
            this.state.slashVisible = false;
            this.state.slashBlockId = false;
            return;
        }
        this.state.slashVisible = true;
        this.state.slashBlockId = blockId;
    }

    openCommands(blockId) {
        this.showSlash(blockId);
    }

    applySlash(blockType) {
        if (this.state.slashBlockId) {
            this.updateBlock(this.state.slashBlockId, { block_type: blockType });
        }
        this.state.slashVisible = false;
        this.state.slashBlockId = false;
    }

    closeSlash() {
        this.state.slashVisible = false;
        this.state.slashBlockId = false;
    }

    dragStart(blockId) {
        this.state.draggedId = blockId;
    }

    dropOn(targetId) {
        const nextBlocks = reorderByDrag(this.props.blocks, this.state.draggedId, targetId);
        if (!nextBlocks.length) {
            return;
        }
        this.props.onBatchOps(
            nextBlocks.map((block) => ({
                type: "update",
                id: block.id,
                sequence: block.sequence,
            }))
        );
        this.state.draggedId = false;
    }

    addFirstBlock() {
        this.props.onBatchOps([
            {
                type: "create",
                block_type: "paragraph",
                sequence: 10,
                depth: 0,
                parent_block_id: false,
                content: { text: "" },
            },
        ]);
    }

    setFocusedBlock(blockId) {
        this.state.focusedBlockId = blockId;
    }

    format(command, value = null) {
        if (!this.state.focusedBlockId) {
            return;
        }
        document.execCommand(command, false, value);
        const editor = document.activeElement;
        if (editor) {
            editor.dispatchEvent(new Event("input", { bubbles: true }));
        }
    }

    onFontChange(ev) {
        const name = ev.target.value || "Arial";
        this.state.fontName = name;
        this.format("fontName", name);
    }
}
