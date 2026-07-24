import type { PoolGraph } from '../api/documents'

/**
 * Build a fully self-contained HTML page rendering a force-directed graph of
 * the pool's concepts, for embedding in a WebView (task.md §1a — the mobile
 * half of the Knowledge Graph). No external scripts/fonts/CDN are loaded (the
 * graph data is inlined and the force simulation is plain vanilla JS), so it
 * works offline and needs no network access from inside the WebView — the same
 * self-contained philosophy the web D3 page follows, minus a 270 KB D3 bundle
 * we'd otherwise have to inline into a string.
 *
 * ``repulsion`` scales how strongly nodes push apart (Loose/Medium/Tight
 * presets on the screen), mirroring the web page's "Node repulsion force"
 * slider. Colours match the app palette (indigo nodes, pink focus).
 */
export function graphHtml(graph: PoolGraph, repulsion: number): string {
  const payload = JSON.stringify({ nodes: graph.nodes, edges: graph.edges, repulsion })
  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1, user-scalable=no" />
<style>
  html, body { margin: 0; padding: 0; height: 100%; background: #FFFFFF; overflow: hidden; }
  svg { width: 100vw; height: 100vh; display: block; touch-action: none; }
  .edge { stroke: #A8A5BD; stroke-opacity: 0.5; stroke-width: 1.5; }
  .edge.hl { stroke: #EC4899; stroke-opacity: 0.9; }
  .node { fill: #6366F1; stroke: #ffffff; stroke-width: 2; }
  .node.focus { fill: #EC4899; }
  .node.dim { fill: #A8A5BD; opacity: 0.3; }
  .label { font-family: -apple-system, Roboto, sans-serif; font-size: 11px; fill: #1E1B2E; pointer-events: none; }
  .label.dim { opacity: 0.25; }
</style>
</head>
<body>
<svg id="g"><g id="edges"></g><g id="nodes"></g><g id="labels"></g></svg>
<script>
(function () {
  var DATA = ${payload};
  var W = window.innerWidth, H = window.innerHeight;
  var svgNS = "http://www.w3.org/2000/svg";
  var edgesG = document.getElementById("edges");
  var nodesG = document.getElementById("nodes");
  var labelsG = document.getElementById("labels");

  var nodes = DATA.nodes.map(function (n, i) {
    var a = (i / Math.max(DATA.nodes.length, 1)) * Math.PI * 2;
    return { id: n.id, label: n.label, r: 8 + Math.min(n.source_count || 1, 6) * 2,
             x: W / 2 + Math.cos(a) * 120, y: H / 2 + Math.sin(a) * 120, vx: 0, vy: 0, fixed: false };
  });
  var byId = {};
  nodes.forEach(function (n) { byId[n.id] = n; });
  var edges = DATA.edges.filter(function (e) { return byId[e.source] && byId[e.target]; });

  var REPULSION = DATA.repulsion * 30;
  var SPRING = 0.02, SPRING_LEN = 90, DAMP = 0.85, CENTER = 0.005;
  var focus = null;

  // Build SVG elements once, then move them each tick.
  var edgeEls = edges.map(function (e) {
    var l = document.createElementNS(svgNS, "line");
    l.setAttribute("class", "edge");
    edgesG.appendChild(l);
    return { el: l, e: e };
  });
  var nodeEls = nodes.map(function (n) {
    var c = document.createElementNS(svgNS, "circle");
    c.setAttribute("class", "node");
    c.setAttribute("r", n.r);
    nodesG.appendChild(c);
    var t = document.createElementNS(svgNS, "text");
    t.setAttribute("class", "label");
    t.setAttribute("dx", n.r + 3);
    t.setAttribute("dy", 4);
    t.textContent = n.label;
    labelsG.appendChild(t);
    return { c: c, t: t, n: n };
  });

  function neighborsOf(id) {
    var set = {}; set[id] = true;
    edges.forEach(function (e) {
      if (e.source === id) set[e.target] = true;
      if (e.target === id) set[e.source] = true;
    });
    return set;
  }

  function applyFocus() {
    var nb = focus ? neighborsOf(focus) : null;
    nodeEls.forEach(function (ne) {
      var cls = "node";
      if (focus) {
        if (ne.n.id === focus) cls += " focus";
        else if (!nb[ne.n.id]) cls += " dim";
      }
      ne.c.setAttribute("class", cls);
      ne.t.setAttribute("class", focus && !nb[ne.n.id] ? "label dim" : "label");
    });
    edgeEls.forEach(function (ee) {
      var on = focus && (ee.e.source === focus || ee.e.target === focus);
      ee.el.setAttribute("class", on ? "edge hl" : "edge");
    });
  }

  function step() {
    for (var i = 0; i < nodes.length; i++) {
      var a = nodes[i];
      for (var j = i + 1; j < nodes.length; j++) {
        var b = nodes[j];
        var dx = a.x - b.x, dy = a.y - b.y;
        var d2 = dx * dx + dy * dy || 0.01;
        var d = Math.sqrt(d2);
        var f = REPULSION / d2;
        var ux = dx / d, uy = dy / d;
        a.vx += ux * f; a.vy += uy * f;
        b.vx -= ux * f; b.vy -= uy * f;
      }
    }
    edges.forEach(function (e) {
      var a = byId[e.source], b = byId[e.target];
      var dx = b.x - a.x, dy = b.y - a.y;
      var d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      var f = (d - SPRING_LEN) * SPRING;
      var ux = dx / d, uy = dy / d;
      a.vx += ux * f; a.vy += uy * f;
      b.vx -= ux * f; b.vy -= uy * f;
    });
    nodes.forEach(function (n) {
      n.vx += (W / 2 - n.x) * CENTER;
      n.vy += (H / 2 - n.y) * CENTER;
      if (!n.fixed) {
        n.vx *= DAMP; n.vy *= DAMP;
        n.x += n.vx; n.y += n.vy;
        n.x = Math.max(n.r, Math.min(W - n.r, n.x));
        n.y = Math.max(n.r, Math.min(H - n.r, n.y));
      }
    });
    edgeEls.forEach(function (ee) {
      var a = byId[ee.e.source], b = byId[ee.e.target];
      ee.el.setAttribute("x1", a.x); ee.el.setAttribute("y1", a.y);
      ee.el.setAttribute("x2", b.x); ee.el.setAttribute("y2", b.y);
    });
    nodeEls.forEach(function (ne) {
      ne.c.setAttribute("cx", ne.n.x); ne.c.setAttribute("cy", ne.n.y);
      ne.t.setAttribute("x", ne.n.x); ne.t.setAttribute("y", ne.n.y);
    });
    requestAnimationFrame(step);
  }

  // Touch: drag the nearest node; a tap (no drag) focuses/unfocuses it.
  var dragging = null, moved = false;
  function nearest(x, y) {
    var best = null, bestD = 900;
    nodes.forEach(function (n) {
      var dx = n.x - x, dy = n.y - y, d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = n; }
    });
    return best;
  }
  var svg = document.getElementById("g");
  function pt(ev) { var t = ev.touches ? ev.touches[0] : ev; return { x: t.clientX, y: t.clientY }; }
  svg.addEventListener("touchstart", function (ev) {
    var p = pt(ev); dragging = nearest(p.x, p.y); moved = false;
    if (dragging) dragging.fixed = true;
  }, { passive: true });
  svg.addEventListener("touchmove", function (ev) {
    if (!dragging) return;
    var p = pt(ev); moved = true; dragging.x = p.x; dragging.y = p.y; dragging.vx = 0; dragging.vy = 0;
  }, { passive: true });
  svg.addEventListener("touchend", function () {
    if (dragging) {
      dragging.fixed = false;
      if (!moved) { focus = focus === dragging.id ? null : dragging.id; applyFocus(); }
    }
    dragging = null;
  }, { passive: true });

  applyFocus();
  requestAnimationFrame(step);
})();
</script>
</body>
</html>`
}
