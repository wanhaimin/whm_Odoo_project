/** @odoo-module **/

import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { useService } from "@web/core/utils/hooks";
import { Component, onWillStart, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";

const VIEW_MODES = ["overview", "sales", "engineering"];
const TYPE_COLORS = {
    brand: "#a78bfa",
    material: "#34d399",
    material_category: "#60a5fa",
    application: "#fb923c",
    process: "#c084fc",
    faq: "#f472b6",
    comparison: "#fbbf24",
    concept: "#94a3b8",
    query_answer: "#4ade80",
    source_summary: "#cbd5e1",
    source: "#64748b",
};

function hashHue(value) {
    const str = String(value || "");
    let h = 0;
    for (let i = 0; i < str.length; i++) {
        h = (h * 31 + str.charCodeAt(i)) >>> 0;
    }
    return h % 360;
}

class KbWikiGraph extends Component {
    static template = "diecut_knowledge.KbWikiGraph";

    setup() {
        this.action = useService("action");
        this.notification = useService("notification");
        this.canvasRef = useRef("canvas");
        this.state = useState({
            loading: true,
            query: "",
            nodeType: "all",
            linkType: "all",
            viewMode: "overview",
            brandFilter: "all",
            categoryFilter: "all",
            showOrphans: true,
            selectedNode: null,
            hoverNodeId: null,
            nodeTypes: [],
            linkTypes: [],
            brands: [],
            categories: [],
            allNodes: [],
            allLinks: [],
            nodes: [],
            links: [],
            width: 1280,
            height: 720,
            zoom: 1,
            tx: 0,
            ty: 0,
            tickCount: 0,
        });

        // Non-reactive bookkeeping (avoid OWL re-render storms during simulation tick)
        this._sim = null;
        this._rafPending = false;
        this._panState = null;
        this._dragState = null;
        this._neighbors = new Map();

        onWillStart(async () => {
            await this.loadGraph();
        });

        onMounted(() => {
            this._resize();
            window.addEventListener("resize", this._onWindowResize);
            window.addEventListener("mousemove", this._onWindowMouseMove);
            window.addEventListener("mouseup", this._onWindowMouseUp);
        });

        onWillUnmount(() => {
            this._stopSimulation();
            window.removeEventListener("resize", this._onWindowResize);
            window.removeEventListener("mousemove", this._onWindowMouseMove);
            window.removeEventListener("mouseup", this._onWindowMouseUp);
        });

        this._onWindowResize = () => this._resize();
        this._onWindowMouseMove = (ev) => {
            if (this._panState) this._onPanMove(ev);
            if (this._dragState) this._onNodeDragMove(ev);
        };
        this._onWindowMouseUp = (ev) => {
            if (this._panState) this._onPanEnd(ev);
            if (this._dragState) this._onNodeDragEnd(ev);
        };
    }

    // ---------------- Data loading ----------------

    async loadGraph() {
        this.state.loading = true;
        try {
            const payload = await rpc("/diecut_knowledge/wiki_graph/data", { limit: 200 });
            this.state.allNodes = payload.nodes || [];
            this.state.allLinks = payload.links || [];
            this.state.nodeTypes = payload.node_types || this._unique(this.state.allNodes.map((n) => n.type));
            this.state.linkTypes = payload.link_types || this._unique(this.state.allLinks.map((l) => l.type));
            this.state.brands = payload.brands || [];
            this.state.categories = payload.categories || [];
            this._applyFilters();
        } catch (error) {
            this.notification.add(`Wiki 图谱加载失败：${error.message || error}`, { type: "danger" });
            this.state.loading = false;
        }
    }

    // ---------------- Filtering ----------------

    _applyFilters() {
        const query = (this.state.query || "").trim().toLowerCase();
        const nodeType = this.state.nodeType;
        const linkType = this.state.linkType;
        const brandFilter = this.state.brandFilter;
        const categoryFilter = this.state.categoryFilter;
        const showOrphans = this.state.showOrphans;

        const nodes = this.state.allNodes.filter((node) => {
            if (nodeType !== "all" && node.type !== nodeType) return false;
            if (brandFilter !== "all") {
                const ids = node.brand_ids || [];
                if (!ids.includes(parseInt(brandFilter, 10))) return false;
            }
            if (categoryFilter !== "all") {
                if (node.category_id !== parseInt(categoryFilter, 10)) return false;
            }
            if (!showOrphans && (node.degree || 0) === 0) return false;
            return true;
        });

        const visibleIds = new Set(nodes.map((n) => n.id));
        const links = this.state.allLinks.filter((link) => {
            if (linkType !== "all" && link.type !== linkType) return false;
            return visibleIds.has(link.source) && visibleIds.has(link.target);
        });

        const matchedIds = query
            ? new Set(
                  nodes
                      .filter((n) =>
                          [n.label, n.summary, n.wiki_slug, n.brand_label, n.category_label]
                              .filter(Boolean)
                              .join(" ")
                              .toLowerCase()
                              .includes(query),
                      )
                      .map((n) => n.id),
              )
            : null;

        this._buildNeighborIndex(nodes, links);
        this._startSimulation(nodes, links, matchedIds);
    }

    _buildNeighborIndex(nodes, links) {
        const map = new Map();
        for (const node of nodes) map.set(node.id, new Set());
        for (const link of links) {
            const src = link.source;
            const tgt = link.target;
            if (map.has(src)) map.get(src).add(tgt);
            if (map.has(tgt)) map.get(tgt).add(src);
        }
        this._neighbors = map;
    }

    // ---------------- d3-force simulation ----------------

    _stopSimulation() {
        if (this._sim) {
            this._sim.stop();
            this._sim = null;
        }
    }

    _startSimulation(rawNodes, rawLinks, matchedIds) {
        this._stopSimulation();
        const d3 = window.d3;
        if (!d3 || !d3.forceSimulation) {
            this.notification.add("d3-force 库未加载，无法构建力导向图。", { type: "danger" });
            this.state.loading = false;
            return;
        }

        const width = this.state.width;
        const height = this.state.height;
        const cx = width / 2;
        const cy = height / 2;

        const carry = new Map();
        for (const n of this.state.nodes) {
            carry.set(n.id, { x: n.x, y: n.y, vx: n.vx, vy: n.vy });
        }

        const simNodes = rawNodes.map((node) => {
            const prev = carry.get(node.id);
            const r = node.nodeType === "source" ? 5 : Math.max(5, Math.min(22, 5 + (node.degree || 0) * 1.6));
            const sim = {
                ...node,
                r,
                color: this._colorFor(node),
                isMatched: matchedIds ? matchedIds.has(node.id) : true,
            };
            if (prev) {
                sim.x = prev.x;
                sim.y = prev.y;
                sim.vx = prev.vx;
                sim.vy = prev.vy;
            } else {
                const angle = Math.random() * Math.PI * 2;
                const radius = Math.random() * Math.min(width, height) * 0.3;
                sim.x = cx + Math.cos(angle) * radius;
                sim.y = cy + Math.sin(angle) * radius;
                sim.vx = 0;
                sim.vy = 0;
            }
            return sim;
        });
        const idIndex = new Map(simNodes.map((n) => [n.id, n]));
        const simLinks = rawLinks
            .map((link) => ({ ...link }))
            .filter((link) => idIndex.has(link.source) && idIndex.has(link.target));

        const sim = d3.forceSimulation(simNodes)
            .alpha(1)
            .alphaDecay(0.04)
            .velocityDecay(0.35)
            .force("link", d3.forceLink(simLinks).id((d) => d.id).distance(70).strength(0.6))
            .force("charge", d3.forceManyBody().strength(-220).distanceMax(420))
            .force("center", d3.forceCenter(cx, cy).strength(0.05))
            .force("collide", d3.forceCollide().radius((d) => d.r + 4).iterations(2))
            .force("clusterX", d3.forceX((d) => this._clusterAnchor(d).x).strength(0.18))
            .force("clusterY", d3.forceY((d) => this._clusterAnchor(d).y).strength(0.18));

        sim.on("tick", () => this._onTick());
        sim.on("end", () => this._onTick(true));

        this._sim = sim;
        this.state.nodes = simNodes;
        this.state.links = simLinks;
        if (this.state.selectedNode && !idIndex.has(this.state.selectedNode.id)) {
            this.state.selectedNode = null;
        }
        this._applyFocus();
        this.state.loading = false;
    }

    _clusterAnchor(node) {
        const width = this.state.width;
        const height = this.state.height;
        const cx = width / 2;
        const cy = height / 2;
        const radius = Math.min(width, height) * 0.32;

        let key;
        if (this.state.viewMode === "sales") {
            key = (node.brand_ids && node.brand_ids[0]) ? `b:${node.brand_ids[0]}` : "b:none";
        } else if (this.state.viewMode === "engineering") {
            key = node.category_id ? `c:${node.category_id}` : "c:none";
        } else {
            key = `t:${node.type || "source_summary"}`;
        }
        const hue = hashHue(key);
        const angle = (hue / 360) * Math.PI * 2;
        return { x: cx + Math.cos(angle) * radius, y: cy + Math.sin(angle) * radius };
    }

    _onTick(force) {
        if (!force && this._rafPending) return;
        this._rafPending = true;
        requestAnimationFrame(() => {
            this._rafPending = false;
            // d3-force mutates node.x/y on the raw objects; OWL doesn't see those writes.
            // Bump a counter so the component re-renders and re-reads the fresh positions.
            this.state.tickCount += 1;
        });
    }

    // ---------------- Selection / focus ----------------

    selectNode(node) {
        this.state.selectedNode = this.state.selectedNode && this.state.selectedNode.id === node.id ? null : node;
        this._applyFocus();
        if (this.state.selectedNode) this._centerOn(node);
    }

    clearSelection() {
        this.state.selectedNode = null;
        this._applyFocus();
    }

    _applyFocus() {
        const selected = this.state.selectedNode;
        const neighbors = selected ? this._neighbors.get(selected.id) || new Set() : null;
        for (const node of this.state.nodes) {
            node.isSelected = !!selected && node.id === selected.id;
            node.isNeighbor = !!neighbors && neighbors.has(node.id);
            node.isFaded = !!selected && !node.isSelected && !node.isNeighbor;
        }
        for (const link of this.state.links) {
            link.isFocused = !!selected && (link.source.id === selected.id || link.target.id === selected.id);
            link.isFaded = !!selected && !link.isFocused;
        }
    }

    _centerOn(node) {
        const targetX = this.state.width / 2 - node.x * this.state.zoom;
        const targetY = this.state.height / 2 - node.y * this.state.zoom;
        this.state.tx = targetX;
        this.state.ty = targetY;
    }

    openNode(node) {
        if (!node.model || !node.resId) return;
        if (node.nodeType === "source") {
            this.action.doAction({
                type: "ir.actions.act_window",
                name: node.label,
                res_model: node.model,
                res_id: node.resId,
                views: [[false, "form"]],
                target: "current",
            });
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            name: node.label,
            res_model: node.model,
            res_id: node.resId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    // ---------------- Toolbar handlers ----------------

    onSearch(ev) {
        this.state.query = ev.target.value || "";
        // Re-run filter to recompute matched flag without full sim restart if topology unchanged.
        const query = this.state.query.trim().toLowerCase();
        const matchedIds = query
            ? new Set(
                  this.state.allNodes
                      .filter((n) =>
                          [n.label, n.summary, n.wiki_slug, n.brand_label, n.category_label]
                              .filter(Boolean)
                              .join(" ")
                              .toLowerCase()
                              .includes(query),
                      )
                      .map((n) => n.id),
              )
            : null;
        for (const node of this.state.nodes) {
            node.isMatched = matchedIds ? matchedIds.has(node.id) : true;
        }
    }

    onNodeTypeChange(ev) {
        this.state.nodeType = ev.target.value || "all";
        this._applyFilters();
    }

    onLinkTypeChange(ev) {
        this.state.linkType = ev.target.value || "all";
        this._applyFilters();
    }

    onBrandChange(ev) {
        this.state.brandFilter = ev.target.value || "all";
        this._applyFilters();
    }

    onCategoryChange(ev) {
        this.state.categoryFilter = ev.target.value || "all";
        this._applyFilters();
    }

    setViewMode(mode) {
        if (!VIEW_MODES.includes(mode) || mode === this.state.viewMode) return;
        this.state.viewMode = mode;
        // Recolor + reheat simulation with new cluster anchors.
        for (const node of this.state.nodes) node.color = this._colorFor(node);
        if (this._sim) {
            this._sim.force("clusterX", window.d3.forceX((d) => this._clusterAnchor(d).x).strength(0.22));
            this._sim.force("clusterY", window.d3.forceY((d) => this._clusterAnchor(d).y).strength(0.22));
            this._sim.alpha(0.6).restart();
        }
    }

    toggleOrphans() {
        this.state.showOrphans = !this.state.showOrphans;
        this._applyFilters();
    }

    resetView() {
        this.state.zoom = 1;
        this.state.tx = 0;
        this.state.ty = 0;
    }

    refresh() {
        this.loadGraph();
    }

    // ---------------- Color ----------------

    _colorFor(node) {
        if (this.state.viewMode === "sales") {
            const brand = (node.brand_ids && node.brand_ids[0]) || 0;
            if (!brand) return "#475569";
            return `hsl(${hashHue(`b:${brand}`)}, 65%, 60%)`;
        }
        if (this.state.viewMode === "engineering") {
            const cat = node.category_id || 0;
            if (!cat) return "#475569";
            return `hsl(${hashHue(`c:${cat}`)}, 60%, 58%)`;
        }
        return TYPE_COLORS[node.type] || TYPE_COLORS.source_summary;
    }

    // ---------------- Pan / zoom / drag ----------------

    _resize() {
        const el = this.canvasRef.el;
        if (!el) return;
        const rect = el.getBoundingClientRect();
        if (rect.width > 0) this.state.width = rect.width;
        if (rect.height > 0) this.state.height = rect.height;
        if (this._sim) {
            const cx = this.state.width / 2;
            const cy = this.state.height / 2;
            this._sim.force("center", window.d3.forceCenter(cx, cy).strength(0.05));
            this._sim.alpha(0.3).restart();
        }
    }

    onWheel(ev) {
        ev.preventDefault();
        const delta = ev.deltaY > 0 ? 0.9 : 1.1;
        const newZoom = Math.max(0.2, Math.min(3, this.state.zoom * delta));
        const rect = ev.currentTarget.getBoundingClientRect();
        const px = ev.clientX - rect.left;
        const py = ev.clientY - rect.top;
        // keep cursor anchored
        const ratio = newZoom / this.state.zoom;
        this.state.tx = px - (px - this.state.tx) * ratio;
        this.state.ty = py - (py - this.state.ty) * ratio;
        this.state.zoom = newZoom;
    }

    onPanStart(ev) {
        if (ev.target.closest(".o_diecut_wiki_graph_node")) return;
        this._panState = { x: ev.clientX, y: ev.clientY, tx: this.state.tx, ty: this.state.ty };
    }

    _onPanMove(ev) {
        if (!this._panState) return;
        this.state.tx = this._panState.tx + (ev.clientX - this._panState.x);
        this.state.ty = this._panState.ty + (ev.clientY - this._panState.y);
    }

    _onPanEnd() {
        this._panState = null;
    }

    onNodeMouseDown(ev, node) {
        ev.stopPropagation();
        if (!this._sim) return;
        const rect = this.canvasRef.el.getBoundingClientRect();
        this._dragState = {
            node,
            offsetX: rect.left,
            offsetY: rect.top,
            shift: ev.shiftKey,
            moved: false,
        };
        node.fx = node.x;
        node.fy = node.y;
        this._sim.alphaTarget(0.3).restart();
    }

    _onNodeDragMove(ev) {
        const ds = this._dragState;
        if (!ds) return;
        ds.moved = true;
        const rect = this.canvasRef.el.getBoundingClientRect();
        const localX = (ev.clientX - rect.left - this.state.tx) / this.state.zoom;
        const localY = (ev.clientY - rect.top - this.state.ty) / this.state.zoom;
        ds.node.fx = localX;
        ds.node.fy = localY;
    }

    _onNodeDragEnd(ev) {
        const ds = this._dragState;
        this._dragState = null;
        if (!ds) return;
        if (this._sim) this._sim.alphaTarget(0);
        if (!ds.shift) {
            ds.node.fx = null;
            ds.node.fy = null;
        }
        if (!ds.moved) {
            this.selectNode(ds.node);
        }
    }

    onNodeDoubleClick(node) {
        this.openNode(node);
    }

    onNodeMouseEnter(node) {
        this.state.hoverNodeId = node.id;
    }

    onNodeMouseLeave() {
        this.state.hoverNodeId = null;
    }

    // ---------------- Metric panels ----------------

    get orphanNodes() {
        return this.state.nodes.filter((n) => (n.degree || 0) === 0).slice(0, 12);
    }

    get weakNodes() {
        return this.state.nodes
            .filter((n) => {
                if ((n.degree || 0) > 1) return false;
                if ((n.degree || 0) === 0) return false;
                return true;
            })
            .slice(0, 12);
    }

    get hubNodes() {
        return [...this.state.nodes]
            .filter((n) => n.nodeType === "article")
            .sort((a, b) => (b.degree || 0) - (a.degree || 0))
            .slice(0, 10);
    }

    // ---------------- View helpers ----------------

    get zoomTransform() {
        return `translate(${this.state.tx}, ${this.state.ty}) scale(${this.state.zoom})`;
    }

    get labelOpacity() {
        // Hide labels when zoomed out unless the node is a hub or selected/hovered
        return this.state.zoom < 0.7 ? 0 : 1;
    }

    nodeClass(node) {
        const cls = ["o_diecut_wiki_graph_node"];
        cls.push(node.nodeType === "source" ? "o_node_source" : "o_node_article");
        if (node.isSelected) cls.push("is_selected");
        if (node.isNeighbor) cls.push("is_neighbor");
        if (node.isFaded) cls.push("is_faded");
        if (node.isMatched === false) cls.push("is_dim");
        if (this.state.hoverNodeId === node.id) cls.push("is_hover");
        return cls.join(" ");
    }

    linkClass(link) {
        const cls = ["o_diecut_wiki_graph_link", `o_link_${link.type}`];
        if (link.isFocused) cls.push("is_focused");
        if (link.isFaded) cls.push("is_faded");
        return cls.join(" ");
    }

    nodeTransform(node) {
        // Counter-scale the whole node group (circle + label) so dot radius and
        // font size stay constant in screen pixels regardless of zoom.
        const inv = 1 / this.state.zoom;
        return `translate(${node.x}, ${node.y}) scale(${inv})`;
    }

    showLabel(node) {
        if (this.state.zoom >= 1.1) return true;
        if (this.state.zoom < 0.5) return node.isSelected;
        if (node.isSelected || node.isNeighbor) return true;
        if (this.state.hoverNodeId === node.id) return true;
        // top hubs get to keep labels at medium zoom
        return (node.degree || 0) >= 6;
    }

    formatPercent(value) {
        if (typeof value !== "number") return "-";
        return `${(value * 100).toFixed(0)}%`;
    }

    _unique(values) {
        return [...new Set((values || []).filter(Boolean))].sort();
    }
}

registry.category("actions").add("diecut_kb_wiki_graph", KbWikiGraph);
