/** @odoo-module **/

function openFormulaModal(shell) {
    const modal = shell.querySelector("[data-diecut-formula-modal]");
    if (!modal) {
        return;
    }
    modal.classList.add("o_open");
    modal.setAttribute("aria-hidden", "false");
    shell.dataset.diecutFormulaOpen = "1";
    modal.querySelector(".o_diecut_formula_close")?.focus({ preventScroll: true });
}

function closeFormulaModal(modal) {
    if (!modal) {
        return;
    }
    modal.classList.remove("o_open");
    modal.setAttribute("aria-hidden", "true");
    const shell = modal.closest(".o_diecut_quote_excel_shell");
    if (shell) {
        delete shell.dataset.diecutFormulaOpen;
    }
}

document.addEventListener(
    "click",
    (ev) => {
        const shell = ev.target.closest(".o_diecut_quote_excel_shell");
        if (!shell) {
            return;
        }

        if (ev.target.closest("[data-diecut-formula-close]")) {
            ev.preventDefault();
            ev.stopPropagation();
            ev.stopImmediatePropagation();
            closeFormulaModal(shell.querySelector("[data-diecut-formula-modal]"));
            return;
        }

        if (!ev.target.closest("[data-diecut-formula-open]")) {
            return;
        }

        ev.preventDefault();
        ev.stopPropagation();
        ev.stopImmediatePropagation();
        openFormulaModal(shell);
    },
    true
);

document.addEventListener(
    "keydown",
    (ev) => {
        if (ev.key !== "Escape") {
            return;
        }
        const modal = document.querySelector(".o_diecut_formula_modal.o_open");
        if (!modal) {
            return;
        }
        ev.preventDefault();
        ev.stopPropagation();
        closeFormulaModal(modal);
    },
    true
);
