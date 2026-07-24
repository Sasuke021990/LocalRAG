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
 * slider. ``initialFocus`` (a node id) opens the graph with that concept
 * already highlighted, driven by the screen's "Highlight concept" picker —
 * changing it remounts the WebView (same as a repulsion change) with the new
 * focus baked in. Colours match the app palette (indigo nodes, pink focus).
 *
 * Supports one-finger pan (on empty space) / node-drag (on a node), and
 * two-finger pinch-to-zoom, mirroring the web page's scroll-to-zoom + drag.
 */
export function graphHtml(graph: PoolGraph, repulsion: number, initialFocus = ''): string {
  const payload = JSON.stringify({ nodes: graph.nodes, edges: graph.edges, repulsion, focus: initialFocus || null })
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
  /* White halo (paint-order: stroke) keeps overlapping labels legible. */
  .label { font-family: -apple-system, Roboto, sans-serif; font-size: 10px; fill: #1E1B2E;
           paint-order: stroke; stroke: #ffffff; stroke-width: 3px; stroke-linejoin: round;
           pointer-events: none; }
  .label.hidden { display: none; }
</style>
</head>
<body>
<svg id="g"><g id="viewport"><g id="edges"></g><g id="nodes"></g><g id="labels"></g></g></svg>
<script>
(function () {
  var DATA = ${payload};
  var W = window.innerWidth, H = window.innerHeight;
  var svgNS = "http://www.w3.org/2000/svg";
  var viewport = document.getElementById("viewport");
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
  var focus = DATA.focus && byId[DATA.focus] ? DATA.focus : null;

  // Pan/zoom state applied to the #viewport group -- node world coordinates
  // (n.x/n.y) never change from zooming, only how they're displayed.
  var view = { x: 0, y: 0, k: 1 };
  function applyTransform() {
    viewport.setAttribute("transform", "translate(" + view.x + "," + view.y + ") scale(" + view.k + ")");
  }
  function toWorld(sx, sy) {
    return { x: (sx - view.x) / view.k, y: (sy - view.y) / view.k };
  }

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
    t.textContent = n.label.length > 18 ? n.label.slice(0, 17) + "…" : n.label;
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
      // When a node is focused, only its own + its neighbours' labels stay —
      // the rest hide, so a dense graph declutters to just what you tapped.
      ne.t.setAttribute("class", focus && !nb[ne.n.id] ? "label hidden" : "label");
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

    // Direct position-based collision (not just velocity repulsion) so nodes
    // never cluster closer than a comfortable gap -- inverse-square repulsion
    // alone lets nodes drift too close on a dense graph, crossing their labels.
    for (var pi = 0; pi < 2; pi++) {
      for (var ci = 0; ci < nodes.length; ci++) {
        for (var cj = ci + 1; cj < nodes.length; cj++) {
          var ca = nodes[ci], cb = nodes[cj];
          var cdx = cb.x - ca.x, cdy = cb.y - ca.y;
          var cdist = Math.sqrt(cdx * cdx + cdy * cdy) || 0.01;
          var minDist = ca.r + cb.r + 46;
          if (cdist < minDist) {
            var overlap = (minDist - cdist) / 2;
            var cux = cdx / cdist, cuy = cdy / cdist;
            if (!ca.fixed) { ca.x -= cux * overlap; ca.y -= cuy * overlap; }
            if (!cb.fixed) { cb.x += cux * overlap; cb.y += cuy * overlap; }
          }
        }
      }
    }

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

  function nearest(worldX, worldY) {
    var best = null, bestD = 900;
    nodes.forEach(function (n) {
      var dx = n.x - worldX, dy = n.y - worldY, d = dx * dx + dy * dy;
      if (d < bestD) { bestD = d; best = n; }
    });
    return best;
  }

  var svg = document.getElementById("g");

  // One-finger: drag a node if the touch starts on one, else pan the canvas.
  // Two-finger: pinch-to-zoom, anchored at the pinch midpoint.
  var draggingNode = null, panning = false, moved = false;
  var lastPan = { x: 0, y: 0 };
  var pinch = null; // { startDist, startK, midScreen, startView }

  function touchDist(t0, t1) {
    var dx = t1.clientX - t0.clientX, dy = t1.clientY - t0.clientY;
    return Math.sqrt(dx * dx + dy * dy);
  }
  function touchMid(t0, t1) {
    return { x: (t0.clientX + t1.clientX) / 2, y: (t0.clientY + t1.clientY) / 2 };
  }

  svg.addEventListener("touchstart", function (ev) {
    moved = false;
    if (ev.touches.length >= 2) {
      draggingNode = null; panning = false;
      var t0 = ev.touches[0], t1 = ev.touches[1];
      pinch = { startDist: touchDist(t0, t1) || 1, startK: view.k, mid: touchMid(t0, t1), startView: { x: view.x, y: view.y } };
      return;
    }
    pinch = null;
    var t = ev.touches[0];
    var world = toWorld(t.clientX, t.clientY);
    var hit = nearest(world.x, world.y);
    if (hit) {
      draggingNode = hit; draggingNode.fixed = true; panning = false;
    } else {
      draggingNode = null; panning = true; lastPan = { x: t.clientX, y: t.clientY };
    }
  }, { passive: true });

  svg.addEventListener("touchmove", function (ev) {
    moved = true;
    if (pinch && ev.touches.length >= 2) {
      var t0 = ev.touches[0], t1 = ev.touches[1];
      var dist = touchDist(t0, t1) || 1;
      var k = Math.max(0.4, Math.min(3, pinch.startK * (dist / pinch.startDist)));
      // Keep the pinch midpoint visually anchored while scale changes.
      var worldMid = { x: (pinch.mid.x - pinch.startView.x) / pinch.startK, y: (pinch.mid.y - pinch.startView.y) / pinch.startK };
      view.k = k;
      view.x = pinch.mid.x - worldMid.x * k;
      view.y = pinch.mid.y - worldMid.y * k;
      applyTransform();
      return;
    }
    var t = ev.touches[0];
    if (draggingNode) {
      var world = toWorld(t.clientX, t.clientY);
      draggingNode.x = world.x; draggingNode.y = world.y; draggingNode.vx = 0; draggingNode.vy = 0;
    } else if (panning) {
      view.x += t.clientX - lastPan.x;
      view.y += t.clientY - lastPan.y;
      lastPan = { x: t.clientX, y: t.clientY };
      applyTransform();
    }
  }, { passive: true });

  svg.addEventListener("touchend", function (ev) {
    if (ev.touches.length >= 2) return; // still pinching with a finger left down
    pinch = null;
    if (draggingNode) {
      draggingNode.fixed = false;
      if (!moved) { focus = focus === draggingNode.id ? null : draggingNode.id; applyFocus(); }
    }
    draggingNode = null; panning = false;
  }, { passive: true });

  applyTransform();
  applyFocus();
  requestAnimationFrame(step);
})();
</script>
</body>
</html>`
}
