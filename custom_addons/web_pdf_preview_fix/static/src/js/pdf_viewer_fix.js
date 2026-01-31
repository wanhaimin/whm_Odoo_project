/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FileViewer } from "@web/core/file_viewer/file_viewer";

patch(FileViewer.prototype, {
    setup() {
        super.setup();
        this.fixCurrentPdfUrl();
    },

    activateFile(index) {
        super.activateFile(index);
        this.fixCurrentPdfUrl();
    },

    fixCurrentPdfUrl() {
        if (!this.state || !this.state.file) {
            return;
        }
        const file = this.state.file;
        // Only target PDFs that haven't been fixed yet
        if (file.isPdf && file.defaultSource && !file.defaultSource.includes('preview_fix')) {
            try {
                // We cannot mutate 'file' directly if it has getters/is frozen.
                // We create a proxy-like object that shadows 'defaultSource'
                const fixedUrl = file.defaultSource + (file.defaultSource.includes('?') ? '&' : '?') + 'preview_fix=1';

                // Create a new object inheriting from the original file
                const fixedFile = Object.create(file);

                // Explicitly define the property to shadow the getter/value on the prototype
                Object.defineProperty(fixedFile, 'defaultSource', {
                    value: fixedUrl,
                    writable: true,
                    enumerable: true,
                    configurable: true
                });

                // Update the state to use our fixed wrapper
                this.state.file = fixedFile;
            } catch (e) {
                console.warn("PDF Preview Fix: Failed to patch file object", e);
            }
        }
    }
});
