/** @odoo-module **/

export class KbSaveQueue {
    constructor({ delay = 700, onFlush }) {
        this.delay = delay;
        this.onFlush = onFlush;
        this._timer = null;
        this._ops = [];
        this._running = false;
    }

    enqueue(op) {
        if (!op) {
            return;
        }
        this._ops.push(op);
        this._schedule();
    }

    clear() {
        this._ops = [];
        if (this._timer) {
            clearTimeout(this._timer);
            this._timer = null;
        }
    }

    async flushNow() {
        if (this._running || !this._ops.length) {
            return;
        }
        this._running = true;
        const ops = [...this._ops];
        this._ops = [];
        try {
            await this.onFlush(ops);
        } catch (error) {
            this._ops = [...ops, ...this._ops];
            throw error;
        } finally {
            this._running = false;
            if (this._ops.length) {
                this._schedule();
            }
        }
    }

    _schedule() {
        if (this._timer) {
            clearTimeout(this._timer);
        }
        this._timer = setTimeout(() => {
            this._timer = null;
            this.flushNow();
        }, this.delay);
    }
}
