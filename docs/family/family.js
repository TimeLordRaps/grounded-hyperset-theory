/* Family explorer — shared script, byte-identical in every repository.
 *
 * Reads family-graph.json (generated from the repositories by
 * tools/build_family_graph.py) and lays the family out by its own structure:
 * strongly connected components, condensed and layered, so mutual citation
 * reads as a ring and everything between rings points one way down the page.
 * The repository this page belongs to is highlighted rather than moved, and
 * clicking any node moves the highlight, the detail panel and the API index
 * without disturbing the picture.
 *
 * No external dependencies, no network calls beyond the graph file itself.
 */

(function () {
  "use strict";

  var SVG = "http://www.w3.org/2000/svg";
  // "unplaced" is what the generator calls a member it has no tier for yet, so a
  // new repository is drawn the day it joins rather than waiting for a label.
  var TIERS = ["foundation", "language", "applied", "combination", "declared", "unplaced"];
  var KINDS = ["dependency", "import", "citation"];
  var KIND_NOTE = {
    dependency: "declared in pyproject.toml — installing the source pulls the target in",
    "import": "a Python module in the source imports the target",
    citation: "tracked prose (.md / .hm / .tex) names the target"
  };

  var W = 760, H = 560;

  var graph = null;
  var byId = {};
  var focusId = document.body.dataset.focus || "";
  var enabled = { dependency: true, "import": true, citation: true };
  var flatSymbols = [];

  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    apply(n, attrs, kids);
    return n;
  }
  function svg(tag, attrs, kids) {
    var n = document.createElementNS(SVG, tag);
    apply(n, attrs, kids);
    return n;
  }
  function apply(n, attrs, kids) {
    if (attrs) {
      Object.keys(attrs).forEach(function (k) {
        if (attrs[k] === null || attrs[k] === undefined) return;
        if (k === "text") { n.textContent = attrs[k]; }
        else if (k === "class") { n.setAttribute("class", attrs[k]); }
        else { n.setAttribute(k, attrs[k]); }
      });
    }
    (kids || []).forEach(function (c) {
      if (c === null || c === undefined) return;
      n.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    });
  }
  function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
  function byTier(a, b) {
    var d = TIERS.indexOf(a.tier) - TIERS.indexOf(b.tier);
    return d !== 0 ? d : (a.id < b.id ? -1 : 1);
  }

  /* ---------------------------------------------------------------- graph */

  function activeEdges() {
    return graph.edges.filter(function (e) {
      return enabled[e.kind] && byId[e.source] && byId[e.target];
    });
  }

  function neighbours(id) {
    var set = {};
    activeEdges().forEach(function (e) {
      if (e.source === id) set[e.target] = true;
      if (e.target === id) set[e.source] = true;
    });
    delete set[id];
    return set;
  }

  /* Strongly connected components of whatever subgraph is on screen.
   *
   * This is the structure the family actually has, and it is derived from the
   * edges rather than declared: a component with more than one member is a set
   * of parts that every one of which reaches every other. Tier, by contrast, is
   * an attribute someone wrote down. Laying out by tier draws the label; laying
   * out by component draws the thing.
   *
   * Iterative Tarjan. Recursion would be fine at ten nodes, but the graph is
   * generated from whatever repositories exist and that number is not fixed.
   */
  function components() {
    var adj = {};
    graph.nodes.forEach(function (n) { adj[n.id] = []; });
    activeEdges().forEach(function (e) {
      if (e.source !== e.target) adj[e.source].push(e.target);
    });

    var index = 0, stack = [], onStack = {}, idx = {}, low = {}, comps = [];

    function strong(root) {
      var work = [{ v: root, i: 0 }];
      while (work.length) {
        var f = work[work.length - 1];
        if (f.i === 0) {
          idx[f.v] = low[f.v] = index++;
          stack.push(f.v);
          onStack[f.v] = true;
        }
        var descended = false;
        var list = adj[f.v];
        while (f.i < list.length) {
          var w = list[f.i++];
          if (idx[w] === undefined) { work.push({ v: w, i: 0 }); descended = true; break; }
          if (onStack[w]) low[f.v] = Math.min(low[f.v], idx[w]);
        }
        if (descended) continue;
        if (low[f.v] === idx[f.v]) {
          var comp = [], x;
          do { x = stack.pop(); onStack[x] = false; comp.push(x); } while (x !== f.v);
          comps.push(comp);
        }
        work.pop();
        if (work.length) {
          var parent = work[work.length - 1].v;
          low[parent] = Math.min(low[parent], low[f.v]);
        }
      }
    }

    graph.nodes.forEach(function (n) { if (idx[n.id] === undefined) strong(n.id); });
    return comps;
  }

  /* A ring is an ellipse, not a circle. The canvas is landscape and a layered
     stack of components is tall and narrow, so height is the scarce dimension
     and width is free: widening the ring costs nothing and pulls the labels that
     actually collide -- the ones beside each other -- further apart. */
  var RING_ASPECT = 1.55;
  function ringRadius(size) { return size < 2 ? 0 : Math.max(58, 16 * size); }

  function countLabel(n) {
    return n.counts.symbols ? n.counts.symbols + " symbols"
         : (n.reserved ? "reserved" : "no package");
  }

  /* How far a node's drawing reaches past its own centre, in fixed pixels.
     Over-estimated on purpose: this feeds a fit solver, and the cost of being
     generous is a slightly smaller picture, while the cost of being tight is a
     clipped label. */
  var MAXR = 18;          /* the largest radiusOf can return */
  var HULL_PAD = 34;      /* hull circle beyond the ring it encloses */
  var HULL_CAP = 76;      /* and its caption above that, clear of the top node's
                             own label -- a ring always has a node at its top,
                             and the caption used to be set on the same line */

  function extents(n, p) {
    var wide = Math.max(n.id.length * 6.5, countLabel(n).length * 5.4) + 4;
    if (p.place === "right") return { l: MAXR, r: MAXR + 9 + wide, t: MAXR, b: 18 };
    if (p.place === "left") return { l: MAXR + 9 + wide, r: MAXR, t: MAXR, b: 18 };
    var half = Math.max(MAXR, wide / 2);
    if (p.place === "up") return { l: half, r: half, t: MAXR + 34, b: MAXR };
    return { l: half, r: half, t: MAXR, b: MAXR + 32 };
  }

  /* Scale the finished drawing to the canvas.
   *
   * Component sizes come from the graph, not from the space available, so the
   * published view -- four parts in a ring and one source above them -- was laid
   * out correctly and then drawn in a quarter of the canvas. Text does not scale
   * with the geometry, so the factor is solved against each node's own label
   * extent rather than applied to a bounding box: the largest scale at which
   * every node, ring and label still clears the margin. That subsumes the
   * downward squeeze this used to do, and works in both directions.
   */
  function fit(pos, groups) {
    var ids = Object.keys(pos);
    if (!ids.length) return 1;
    var M = 10, s = 4;
    var xs = ids.map(function (i) { return pos[i].x; });
    var ys = ids.map(function (i) { return pos[i].y; });
    var cx0 = (Math.min.apply(null, xs) + Math.max.apply(null, xs)) / 2;
    var cy0 = (Math.min.apply(null, ys) + Math.max.apply(null, ys)) / 2;

    /* A node sitting on the centre line is unaffected by the scale, so it
       constrains nothing; one already past the margin at any scale is left to
       the clamp below rather than collapsing the whole picture. */
    function cap(reach, room) {
      if (reach > 0.01) s = Math.min(s, room / reach);
    }

    ids.forEach(function (id) {
      var q = pos[id], e = extents(byId[id], q);
      cap(q.x - cx0, W / 2 - M - e.r);
      cap(cx0 - q.x, W / 2 - M - e.l);
      cap(q.y - cy0, H / 2 - M - e.b);
      cap(cy0 - q.y, H / 2 - M - e.t);
    });
    groups.forEach(function (g) {
      var dx = Math.abs(g.x - cx0), dy = g.y - cy0;
      cap(dx + g.rx, W / 2 - M - HULL_PAD);
      cap(dx, W / 2 - M - 94);
      cap(dy + g.ry, H / 2 - M - HULL_PAD);
      cap(g.ry - dy, H / 2 - M - HULL_CAP);
    });

    s = Math.max(0.3, Math.min(s, 2.6));
    ids.forEach(function (id) {
      pos[id].x = W / 2 + (pos[id].x - cx0) * s;
      pos[id].y = H / 2 + (pos[id].y - cy0) * s;
    });
    groups.forEach(function (g) {
      g.x = W / 2 + (g.x - cx0) * s;
      g.y = H / 2 + (g.y - cy0) * s;
      g.rx *= s;
      g.ry *= s;
    });
    return s;
  }

  /* Layered layout over the component condensation.
   *
   * A citation edge runs from the part that names another to the part named, so
   * the most-cited parts are sinks. Putting sinks at the bottom makes the page
   * read as a stack with the ground underneath, and because the condensation of
   * the components is acyclic, every edge between components then points the
   * same way down the page. Cycles are exactly and only what stays inside a
   * ring.
   *
   * Position does not depend on the focus, so the picture holds still while you
   * click through it. A layout that reshuffles on every click destroys the
   * mental model it just built.
   */
  function layout() {
    var comps = components();
    var compOf = {};
    comps.forEach(function (c, i) { c.forEach(function (id) { compOf[id] = i; }); });

    var preds = comps.map(function () { return {}; });
    activeEdges().forEach(function (e) {
      var a = compOf[e.source], b = compOf[e.target];
      if (a !== b) preds[b][a] = true;
    });

    var layer = comps.map(function () { return -1; });
    function depth(i) {
      if (layer[i] >= 0) return layer[i];
      layer[i] = 0;
      var d = 0;
      Object.keys(preds[i]).forEach(function (p) { d = Math.max(d, depth(+p) + 1); });
      layer[i] = d;
      return d;
    }
    comps.forEach(function (c, i) { depth(i); });

    var rows = {};
    comps.forEach(function (c, i) { (rows[layer[i]] = rows[layer[i]] || []).push(i); });
    var levels = Object.keys(rows).map(Number).sort(function (a, b) { return a - b; });

    /* Rows, not bands.
       A band has to reserve room for its widest ring plus the labels above and
       below it; spacing band *centres* evenly instead pushes the top of a tall
       ring off the canvas. And a level with many single-part components -- which
       is what the graph degenerates to when the citation edges are switched off,
       eleven of them at once -- has to wrap rather than run off the side. So a
       level is packed into as many rows as it needs, and rows, not levels, are
       what gets stacked. */
    var ABOVE = 54, BELOW = 40, GAP = 24, AVAIL = W - 24;

    function widthOf(i) {
      if (comps[i].length > 1) return 2 * ringRadius(comps[i].length) * RING_ASPECT + 40;
      return Math.max(96, comps[i][0].length * 6.8 + 26);
    }

    var bands = [];
    levels.forEach(function (L) {
      var ids = rows[L].slice().sort(function (a, b) {
        var d = comps[b].length - comps[a].length;
        return d !== 0 ? d : (comps[a][0] < comps[b][0] ? -1 : 1);
      });
      var row = [], used = 0;
      ids.forEach(function (i) {
        var w = widthOf(i);
        if (row.length && used + w > AVAIL) { bands.push(row); row = []; used = 0; }
        row.push(i);
        used += w;
      });
      if (row.length) bands.push(row);
    });

    var bandR = bands.map(function (row) {
      return row.reduce(function (m, i) { return Math.max(m, ringRadius(comps[i].length)); }, 0);
    });
    var centres = [], cursor = 0;
    bands.forEach(function (row, bi) {
      cursor += ABOVE + bandR[bi];
      centres.push(cursor);
      cursor += bandR[bi] + BELOW + (bi < bands.length - 1 ? GAP : 0);
    });
    var pos = {}, groups = [];
    bands.forEach(function (row, bi) {
      var y = centres[bi];
      var total = row.reduce(function (s, i) { return s + widthOf(i); }, 0);
      var x = (W - total) / 2;
      row.forEach(function (i) {
        placeComponent(comps[i], x + widthOf(i) / 2, y, pos, groups);
        x += widthOf(i);
      });
    });


    var scale = fit(pos, groups);
    return { pos: pos, groups: groups, levels: levels.length,
             rows: bands.length, scale: scale };
  }

  function placeComponent(ids, cx, cy, pos, groups) {
    var members = ids.map(function (id) { return byId[id]; }).sort(byTier);
    if (members.length === 1) {
      pos[members[0].id] = { x: cx, y: cy, place: "down" };
      return;
    }
    var ry = ringRadius(members.length), rx = ry * RING_ASPECT;
    var stepA = (Math.PI * 2) / members.length;
    members.forEach(function (n, i) {
      var a = -Math.PI / 2 + i * stepA;
      var dx = rx * Math.cos(a), dy = ry * Math.sin(a);
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      var cos = dx / len, sin = dy / len;
      /* Labels go on the outward side of the ring. Hanging every one below its
         node puts the top node's label inside the ring, over the very cycle the
         ring exists to show, and leaves the two bottom nodes' labels -- which on
         a five-ring are only about 1.2r apart -- to collide with each other.
         Anything near the horizontal extremes is set beside its node instead,
         where there is room to run outward. */
      var place = Math.abs(cos) > 0.55 ? (cos > 0 ? "right" : "left")
                : (sin < 0 ? "up" : "down");
      pos[n.id] = { x: cx + dx, y: cy + dy, place: place };
    });
    groups.push({ x: cx, y: cy, rx: rx, ry: ry, size: members.length });
  }

  function control(a, b, bow) {
    var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    var dx = b.x - a.x, dy = b.y - a.y;
    var len = Math.sqrt(dx * dx + dy * dy) || 1;
    return { x: mx + (-dy / len) * bow, y: my + (dx / len) * bow };
  }

  function edgePath(a, c, b) {
    return "M" + a.x.toFixed(1) + " " + a.y.toFixed(1) +
           " Q" + c.x.toFixed(1) + " " + c.y.toFixed(1) +
           " " + b.x.toFixed(1) + " " + b.y.toFixed(1);
  }

  /* Pull each end back to its node's rim along the curve's own tangent, which
     for a quadratic bezier points at the control point. Trimming along the
     straight chord instead leaves the arrowhead aimed past the node it lands
     on, by more the harder the edge is bowed. */
  function trimEnds(a, c, b, ra, rb) {
    function toward(p, q, d) {
      var dx = q.x - p.x, dy = q.y - p.y;
      var l = Math.sqrt(dx * dx + dy * dy) || 1;
      return { x: p.x + (dx / l) * d, y: p.y + (dy / l) * d };
    }
    return { a: toward(a, c, ra), b: toward(b, c, rb) };
  }

  var maxSymbols = 1;

  function radiusOf(n) {
    if (n.reserved) return 9;
    /* Area, not radius, tracks the symbol count, so a package with four times
       the API reads as four times the disc rather than four times the width. */
    var r = 8 + 7 * Math.sqrt((n.counts.symbols || 0) / maxSymbols);
    return n.id === focusId ? r + 3 : r;
  }

  /* ------------------------------------------------------------- viewport */

  /* The picture is a viewport onto a scene, not a fixed drawing. Everything
     below works in scene coordinates; the transform on <g id="scene"> is the
     only thing that changes when you zoom or pan, so nothing has to be
     re-rendered to move the camera. */
  var view = { k: 1, x: 0, y: 0 };
  var MIN_K = 0.25, MAX_K = 6;

  var svgRoot = null, scene = null, gHulls = null, gEdges = null, gNodes = null;
  var tip = null, matrixHost = null;

  var pos = {};        /* id -> { x, y, vx, vy, fx, fy } in scene coordinates */
  var hulls = [];      /* component rings, for the structure layout */
  var mode = "structure";
  var hoverId = null, hoverEdge = null;
  var trailFrom = null, trailNodes = {}, trailEdges = {};
  var anim = null, simAlpha = 0, simFrame = null;

  function applyView() {
    scene.setAttribute("transform",
      "translate(" + view.x.toFixed(2) + "," + view.y.toFixed(2) + ") " +
      "scale(" + view.k.toFixed(4) + ")");
    /* Strokes and text are scaled by the transform, so counter-scale them to
       keep hairlines hairline and labels legible at any zoom. */
    scene.style.setProperty("--k", view.k);
  }

  function clientToScene(ev) {
    var r = svgRoot.getBoundingClientRect();
    var sx = (ev.clientX - r.left) / r.width * W;
    var sy = (ev.clientY - r.top) / r.height * H;
    return { x: (sx - view.x) / view.k, y: (sy - view.y) / view.k };
  }

  function zoomAbout(px, py, factor) {
    var k = Math.max(MIN_K, Math.min(MAX_K, view.k * factor));
    if (k === view.k) return;
    /* Hold the scene point under the cursor still. */
    view.x = px - (px - view.x) * (k / view.k);
    view.y = py - (py - view.y) * (k / view.k);
    view.k = k;
    applyView();
  }

  function contentBox() {
    var ids = Object.keys(pos);
    if (!ids.length) return { x: 0, y: 0, w: W, h: H };
    var l = Infinity, t = Infinity, r = -Infinity, b = -Infinity;
    ids.forEach(function (id) {
      var p = pos[id], e = extents(byId[id], p);
      l = Math.min(l, p.x - e.l); r = Math.max(r, p.x + e.r);
      t = Math.min(t, p.y - e.t); b = Math.max(b, p.y + e.b);
    });
    hulls.forEach(function (g) {
      l = Math.min(l, g.x - g.rx - 34); r = Math.max(r, g.x + g.rx + 34);
      t = Math.min(t, g.y - g.ry - HULL_CAP); b = Math.max(b, g.y + g.ry + 34);
    });
    return { x: l, y: t, w: Math.max(1, r - l), h: Math.max(1, b - t) };
  }

  /* requestAnimationFrame does not fire while the document is hidden, and an
     animation that silently never finishes leaves the view stuck halfway -- a
     Fit that does nothing at all because the page was in a background tab is
     worse than one that jumps. Fall back to a timer, which keeps firing. */
  function raf(fn) {
    return document.hidden
      ? { timer: window.setTimeout(fn, 16) }
      : { frame: window.requestAnimationFrame(fn) };
  }

  /* The two schedulers hand out ids from separate pools, so a handle has to say
     which one it came from -- cancelling a timer id as if it were a frame id
     cancels nothing, or worse, something else. */
  function unraf(h) {
    if (!h) return;
    if (h.timer !== undefined) window.clearTimeout(h.timer);
    else window.cancelAnimationFrame(h.frame);
  }

  function fitView(animate) {
    var box = contentBox();
    var pad = 16;
    var k = Math.max(MIN_K, Math.min(MAX_K,
      Math.min((W - pad * 2) / box.w, (H - pad * 2) / box.h)));
    var target = {
      k: k,
      x: W / 2 - (box.x + box.w / 2) * k,
      y: H / 2 - (box.y + box.h / 2) * k
    };
    if (!animate) { view = target; applyView(); return; }
    var from = { k: view.k, x: view.x, y: view.y }, t0 = now();
    (function step() {
      var u = ease(Math.min(1, (now() - t0) / 340));
      view.k = from.k + (target.k - from.k) * u;
      view.x = from.x + (target.x - from.x) * u;
      view.y = from.y + (target.y - from.y) * u;
      applyView();
      if (u < 1) raf(step);
    })();
  }

  function now() { return window.performance ? window.performance.now() : Date.now(); }
  function ease(u) { return u < 0.5 ? 2 * u * u : 1 - Math.pow(-2 * u + 2, 2) / 2; }

  /* -------------------------------------------------------------- layouts */

  /* Every layout produces target positions for the same nodes; moving between
     them is an animation rather than a redraw, so you can watch one shape turn
     into another and keep track of which node is which. */

  function structureTargets() {
    var placed = layout();
    return { pos: placed.pos, hulls: placed.groups };
  }

  function radialTargets() {
    /* The focus at the centre, everything else ringed by how many edges away it
       is. This is the ego view -- a bad picture of the family and a good picture
       of one part's neighbourhood, which is why it is an option and not the
       default. */
    var dist = {}, queue = [focusId], adj = {};
    graph.nodes.forEach(function (n) { adj[n.id] = []; });
    activeEdges().forEach(function (e) {
      adj[e.source].push(e.target);
      adj[e.target].push(e.source);
    });
    dist[focusId] = 0;
    for (var qi = 0; qi < queue.length; qi++) {
      var v = queue[qi];
      adj[v].forEach(function (w) {
        if (dist[w] === undefined) { dist[w] = dist[v] + 1; queue.push(w); }
      });
    }
    var far = 0;
    graph.nodes.forEach(function (n) {
      if (dist[n.id] === undefined) dist[n.id] = -1;
      far = Math.max(far, dist[n.id]);
    });
    var rings = {};
    graph.nodes.forEach(function (n) {
      var d = dist[n.id] < 0 ? far + 1 : dist[n.id];
      (rings[d] = rings[d] || []).push(n);
    });
    var out = {};
    Object.keys(rings).map(Number).sort(function (a, b) { return a - b; })
      .forEach(function (d) {
        var members = rings[d].sort(byTier);
        if (d === 0) { out[members[0].id] = { x: W / 2, y: H / 2, place: "down" }; return; }
        var rx = 108 * d * 1.45, ry = 108 * d;
        var step = (Math.PI * 2) / members.length;
        members.forEach(function (n, i) {
          var a = -Math.PI / 2 + i * step + (d % 2 ? 0 : step / 2);
          var dx = rx * Math.cos(a), dy = ry * Math.sin(a);
          var len = Math.sqrt(dx * dx + dy * dy) || 1;
          var cs = dx / len, sn = dy / len;
          out[n.id] = {
            x: W / 2 + dx, y: H / 2 + dy,
            place: Math.abs(cs) > 0.55 ? (cs > 0 ? "right" : "left") : (sn < 0 ? "up" : "down")
          };
        });
      });
    return { pos: out, hulls: [] };
  }

  function gridTargets() {
    var ns = graph.nodes.slice().sort(byTier);
    var cols = Math.ceil(Math.sqrt(ns.length * 1.6));
    var cw = W / (cols + 0.5), rh = 118;
    var out = {};
    ns.forEach(function (n, i) {
      var c = i % cols, r = Math.floor(i / cols);
      out[n.id] = { x: cw * (c + 0.75), y: 70 + r * rh, place: "down" };
    });
    return { pos: out, hulls: [] };
  }

  /* --------------------------------------------------------- force layout */

  /* Hand-rolled because the page has no dependencies and eleven nodes do not
     need a quadtree. Structure is kept as a bias rather than thrown away: the
     y anchor is the node's layer in the condensation, so the stack survives,
     and members of a component attract each other, so a cycle still clumps. */
  var anchor = {};

  function prepareForce() {
    var placed = layout();
    anchor = {};
    Object.keys(placed.pos).forEach(function (id) {
      anchor[id] = { x: placed.pos[id].x, y: placed.pos[id].y };
    });
    graph.nodes.forEach(function (n) {
      if (!pos[n.id]) pos[n.id] = { x: W / 2, y: H / 2, vx: 0, vy: 0 };
      pos[n.id].vx = 0;
      pos[n.id].vy = 0;
    });
    simAlpha = 1;
  }

  function simStep() {
    var ids = graph.nodes.map(function (n) { return n.id; });
    var act = activeEdges();
    var i, j, a, b, dx, dy, d, f;

    for (i = 0; i < ids.length; i++) {
      a = pos[ids[i]];
      for (j = i + 1; j < ids.length; j++) {
        b = pos[ids[j]];
        dx = b.x - a.x; dy = b.y - a.y;
        d = Math.sqrt(dx * dx + dy * dy) || 0.01;
        f = 24000 / (d * d);
        if (d < 64) f += (64 - d) * 3.2;        /* hard collision */
        dx /= d; dy /= d;
        a.vx -= dx * f * 0.0016; a.vy -= dy * f * 0.0016;
        b.vx += dx * f * 0.0016; b.vy += dy * f * 0.0016;
      }
    }
    act.forEach(function (e) {
      if (e.source === e.target) return;
      a = pos[e.source]; b = pos[e.target];
      dx = b.x - a.x; dy = b.y - a.y;
      d = Math.sqrt(dx * dx + dy * dy) || 0.01;
      var rest = 150 - Math.min(48, e.weight * 8);
      f = (d - rest) * 0.012;
      dx /= d; dy /= d;
      a.vx += dx * f; a.vy += dy * f;
      b.vx -= dx * f; b.vy -= dy * f;
    });
    ids.forEach(function (id) {
      var p = pos[id], an = anchor[id];
      if (an) {
        p.vy += (an.y - p.y) * 0.030;            /* keep the layering */
        p.vx += (W / 2 - p.x) * 0.0016;
      }
      if (p.fx !== undefined) { p.x = p.fx; p.y = p.fy; p.vx = p.vy = 0; return; }
      p.vx *= 0.82; p.vy *= 0.82;
      p.x += p.vx * simAlpha;
      p.y += p.vy * simAlpha;
      var e = extents(byId[id], p);
      p.x = Math.max(e.l + 4, Math.min(W - e.r - 4, p.x));
      p.y = Math.max(e.t + 4, Math.min(H - e.b - 4, p.y));
    });
    ids.forEach(function (id) { pos[id].place = placeFor(id); });
    simAlpha *= 0.985;
  }

  /* With no ring to point away from, a label goes wherever its node is least
     crowded: the side with the fewest neighbours within reach. */
  function placeFor(id) {
    var p = pos[id], score = { left: 0, right: 0, up: 0, down: 0 };
    graph.nodes.forEach(function (n) {
      if (n.id === id) return;
      var q = pos[n.id], dx = q.x - p.x, dy = q.y - p.y;
      var d = Math.sqrt(dx * dx + dy * dy);
      if (d > 190) return;
      var w = (190 - d) / 190;
      score[dx > 0 ? "right" : "left"] += w * Math.abs(dx) / (d || 1);
      score[dy > 0 ? "down" : "up"] += w * Math.abs(dy) / (d || 1);
    });
    if (p.x < 130) score.left += 9;
    if (p.x > W - 130) score.right += 9;
    if (p.y < 60) score.up += 9;
    if (p.y > H - 60) score.down += 9;
    var best = "down", bv = Infinity;
    ["right", "left", "down", "up"].forEach(function (k) {
      if (score[k] < bv) { bv = score[k]; best = k; }
    });
    return best;
  }

  function runSim() {
    unraf(simFrame);
    (function loop() {
      simStep();
      paint();
      if (simAlpha > 0.02) simFrame = raf(loop);
      else simFrame = null;
    })();
  }

  /* ------------------------------------------------------------ animation */

  function targetsFor(m) {
    if (m === "radial") return radialTargets();
    if (m === "grid") return gridTargets();
    return structureTargets();
  }

  function moveTo(m, animate) {
    var t = targetsFor(m);
    hulls = t.hulls;
    var from = {};
    Object.keys(t.pos).forEach(function (id) {
      from[id] = pos[id] ? { x: pos[id].x, y: pos[id].y }
                         : { x: t.pos[id].x, y: t.pos[id].y };
      pos[id] = pos[id] || { x: t.pos[id].x, y: t.pos[id].y, vx: 0, vy: 0 };
      pos[id].place = t.pos[id].place;
      delete pos[id].fx; delete pos[id].fy;
    });
    var toHulls = hulls.map(function (g) { return { x: g.x, y: g.y, rx: g.rx, ry: g.ry }; });
    unraf(anim); anim = null;
    if (!animate) {
      Object.keys(t.pos).forEach(function (id) { pos[id].x = t.pos[id].x; pos[id].y = t.pos[id].y; });
      paint(); fitView(false); return;
    }
    /* Rings grow from nothing rather than sliding in at full size, which reads
       as the grouping being derived from where the nodes land. */
    var fromHulls = toHulls.map(function (g) { return { x: g.x, y: g.y, rx: 0, ry: 0 }; });
    var t0 = now();
    (function step() {
      var u = ease(Math.min(1, (now() - t0) / 520));
      Object.keys(t.pos).forEach(function (id) {
        pos[id].x = from[id].x + (t.pos[id].x - from[id].x) * u;
        pos[id].y = from[id].y + (t.pos[id].y - from[id].y) * u;
      });
      hulls.forEach(function (g, i) {
        g.rx = fromHulls[i].rx + (toHulls[i].rx - fromHulls[i].rx) * u;
        g.ry = fromHulls[i].ry + (toHulls[i].ry - fromHulls[i].ry) * u;
      });
      paint();
      if (u < 1) anim = raf(step);
      else { anim = null; fitView(true); }
    })();
  }

  /* Leaving force mode has to stop the simulation. moveTo cancels its own
     animation handle, not this one, so without it the sim keeps integrating in
     the background and pulls every node off the layout it was just moved to --
     visibly, because the component hulls do not move with it: the ring drifts
     out of its own circle. */
  function stopSim() {
    unraf(simFrame);
    simFrame = null;
    simAlpha = 0;
  }

  function relayout(animate) {
    if (mode !== "force") stopSim();
    if (mode === "matrix") { paintMatrix(); return; }
    matrixHost.hidden = true;
    svgRoot.hidden = false;
    if (mode === "force") {
      prepareForce();
      hulls = [];
      runSim();
      window.setTimeout(function () { fitView(true); }, 420);
    } else {
      moveTo(mode, animate !== false);
    }
  }

  /* ------------------------------------------------------- path following */

  /* Shortest directed path, so "does this part reach that one, and how" has an
     answer you can see rather than trace by eye. */
  function trace(from, to) {
    var adj = {};
    graph.nodes.forEach(function (n) { adj[n.id] = []; });
    activeEdges().forEach(function (e) { adj[e.source].push(e); });
    var prev = {}, seen = {}, queue = [from];
    seen[from] = true;
    for (var i = 0; i < queue.length; i++) {
      var v = queue[i];
      if (v === to) break;
      adj[v].forEach(function (e) {
        if (seen[e.target]) return;
        seen[e.target] = true; prev[e.target] = e; queue.push(e.target);
      });
    }
    if (!seen[to]) return null;
    var path = [], cur = to;
    while (cur !== from) { var e = prev[cur]; path.unshift(e); cur = e.source; }
    return path;
  }

  function setTrail(from, to) {
    trailNodes = {}; trailEdges = {};
    var path = from && to ? trace(from, to) : null;
    if (!path) return path;
    trailNodes[from] = true;
    path.forEach(function (e) {
      trailEdges[e.kind + "|" + e.source + "|" + e.target] = true;
      trailNodes[e.target] = true;
    });
    return path;
  }

  function edgeKey(e) { return e.kind + "|" + e.source + "|" + e.target; }

  /* --------------------------------------------------------------- paint */

  var maxSymbols = 1, maxW = 1;
  var nodeEls = {}, edgeEls = [];

  function paint() {
    if (mode === "matrix") return;
    clear(gHulls); clear(gEdges); clear(gNodes);
    nodeEls = {}; edgeEls = [];

    hulls.forEach(function (g) {
      if (g.rx < 1) return;
      gHulls.appendChild(svg("ellipse", {
        class: "scc-hull", cx: g.x.toFixed(1), cy: g.y.toFixed(1),
        rx: (g.rx + 34).toFixed(1), ry: (g.ry + 34).toFixed(1)
      }));
      gHulls.appendChild(svg("text", {
        class: "scc-label", x: g.x.toFixed(1), y: (g.y - g.ry - 64).toFixed(1),
        text: g.size + " parts, each reaching every other"
      }));
    });

    var active = activeEdges();
    maxW = 1;
    active.forEach(function (e) { maxW = Math.max(maxW, e.weight); });

    active.forEach(function (e) {
      var a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      var dir = e.source < e.target ? 1 : -1;
      var bow = dir * 0.085 * Math.min(len, 300) * (1 + 0.5 * KINDS.indexOf(e.kind));
      var c = control(a, b, bow);
      var ends = trimEnds(a, c, b, radiusOf(byId[e.source]) + 3,
                          radiusOf(byId[e.target]) + 7);
      var path = svg("path", {
        class: "edge " + e.kind,
        d: edgePath(ends.a, c, ends.b),
        "stroke-width": widthOf(e.weight).toFixed(2)
      });
      edgeEls.push({ e: e, el: path });
      gEdges.appendChild(path);
      /* A 2px stroke is not a hit target. The visible path stays untouchable and
         an invisible fat one beside it takes the pointer. */
      var hit = svg("path", { class: "edge-hit", d: edgePath(ends.a, c, ends.b) });
      hit.addEventListener("pointerenter", function (ev) { showEdgeTip(e, ev); });
      hit.addEventListener("pointerleave", hideTip);
      hit.addEventListener("click", function () { focus(e.source); });
      gEdges.appendChild(hit);
    });

    graph.nodes.forEach(function (n) {
      var p = pos[n.id];
      if (!p) return;
      var r = radiusOf(n);
      var side = p.place === "left" || p.place === "right";
      var dx = side ? (p.place === "right" ? r + 9 : -(r + 9)) : 0;
      var nameY = side ? -2 : (p.place === "up" ? -(r + 23) : r + 14);
      var countY = side ? 11 : (p.place === "up" ? -(r + 10) : r + 27);
      var g = svg("g", {
        class: "node",
        transform: "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")",
        tabindex: "0", role: "button",
        "aria-label": n.id + " — " + (n.tagline || n.tier)
      }, [
        svg("circle", { class: "halo", r: (r + 7).toFixed(1) }),
        svg("circle", { r: r.toFixed(1), fill: n.reserved ? "none" : "var(--tier-" + n.tier + ")" }),
        svg("text", { x: dx.toFixed(1), y: nameY.toFixed(1), class: p.place, text: n.id }),
        svg("text", { x: dx.toFixed(1), y: countY.toFixed(1),
                      class: "count " + p.place, text: countLabel(n) })
      ]);
      wireNode(g, n);
      nodeEls[n.id] = g;
      gNodes.appendChild(g);
    });
    restyle();
  }

  /* What is lit and what is faded is a class change, nothing more. Separating it
     from paint() is what makes hover cheap and, more to the point, correct:
     rebuilding the scene under the pointer destroys the element the pointer is
     over, so whatever it moves onto never gets its enter event. */
  function restyle() {
    var tracing = Object.keys(trailEdges).length > 0;
    var near = hoverId ? neighbours(hoverId) : null;

    edgeEls.forEach(function (rec) {
      var e = rec.e, lit;
      if (tracing) lit = !!trailEdges[edgeKey(e)];
      else if (hoverId) lit = e.source === hoverId || e.target === hoverId;
      else lit = e.source === focusId || e.target === focusId;
      rec.el.setAttribute("class", "edge " + e.kind + (lit ? " lit" : " dim"));
      rec.el.setAttribute("marker-end", "url(#arrow-" + e.kind + (lit ? "" : "-dim") + ")");
      rec.el.setAttribute("opacity", lit ? 0.96 : 0.13);
    });

    graph.nodes.forEach(function (n) {
      var g = nodeEls[n.id];
      if (!g) return;
      var p = pos[n.id];
      var lit = tracing ? !!trailNodes[n.id]
              : (hoverId ? (n.id === hoverId || (near && near[n.id])) : true);
      g.setAttribute("class", "node" + (n.id === focusId ? " is-focus" : "") +
        (n.reserved ? " reserved" : "") + (lit ? "" : " dim") +
        (p && p.fx !== undefined ? " pinned" : "") +
        (n.id === trailFrom ? " trail-from" : ""));
    });
  }

  function widthOf(w) { return maxW <= 1 ? 2.2 : 1.2 + 4.3 * (w - 1) / (maxW - 1); }

  /* ---------------------------------------------------------- interaction */

  function wireNode(g, n) {
    g.addEventListener("pointerenter", function (ev) {
      if (dragging) return;
      hoverId = n.id; showNodeTip(n, ev); restyle();
    });
    g.addEventListener("pointerleave", function () {
      if (dragging) return;
      hoverId = null; hideTip(); restyle();
    });
    g.addEventListener("pointerdown", function (ev) { startDrag(ev, n.id); });
    g.addEventListener("click", function (ev) {
      if (moved) { moved = false; return; }
      if (ev.shiftKey) { pickTrail(n.id); return; }
      focus(n.id);
    });
    g.addEventListener("keydown", function (ev) {
      if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); focus(n.id); }
      if (ev.key === "p" || ev.key === "P") { pickTrail(n.id); }
    });
  }

  function pickTrail(id) {
    if (trailFrom === null || trailFrom === id) {
      trailFrom = trailFrom === id ? null : id;
      trailNodes = {}; trailEdges = {};
      say(trailFrom ? "Path from " + trailFrom + " — shift-click a second part."
                    : "Path cleared.");
      restyle();
      return;
    }
    var path = setTrail(trailFrom, id);
    if (!path) {
      say(trailFrom + " does not reach " + id + " along the edge kinds now shown.");
    } else {
      say(trailFrom + " → " + id + " in " + path.length + " step" +
          (path.length === 1 ? "" : "s") + ": " +
          [trailFrom].concat(path.map(function (e) { return e.target; })).join(" → "));
    }
    trailFrom = null;
    restyle();
  }

  function say(text) {
    var host = document.getElementById("graph-say");
    if (host) host.textContent = text || "";
  }

  var dragging = null, moved = false, panFrom = null;

  function capture(ev) {
    try { svgRoot.setPointerCapture(ev.pointerId); } catch (err) { /* no such pointer */ }
  }

  function startDrag(ev, id) {
    ev.preventDefault();
    dragging = { id: id, at: clientToScene(ev) };
    moved = false;
    capture(ev);
  }

  function onPointerMove(ev) {
    if (dragging) {
      var s = clientToScene(ev);
      var p = pos[dragging.id];
      p.x = s.x; p.y = s.y;
      p.fx = s.x; p.fy = s.y;
      p.vx = p.vy = 0;
      moved = true;
      if (mode === "force") { simAlpha = Math.max(simAlpha, 0.55); if (!simFrame) runSim(); }
      else paint();
      return;
    }
    if (panFrom) {
      view.x = panFrom.vx + (ev.clientX - panFrom.cx) * (W / svgRoot.getBoundingClientRect().width);
      view.y = panFrom.vy + (ev.clientY - panFrom.cy) * (H / svgRoot.getBoundingClientRect().height);
      applyView();
      moved = true;
    }
  }

  function onPointerUp(ev) {
    if (dragging || panFrom) {
      try { svgRoot.releasePointerCapture(ev.pointerId); } catch (err) { /* already gone */ }
    }
    dragging = null;
    panFrom = null;
  }

  function showNodeTip(n, ev) {
    var e = edgesFor(n.id);
    tipHtml([
      el("b", { text: n.id }),
      el("span", { class: "t-tier", text: " " + n.tier +
        (n.visibility && n.visibility !== "public" ? " · " + n.visibility : "") }),
      n.tagline ? el("p", { text: n.tagline }) : null,
      el("p", { class: "t-facts", text:
        n.counts.symbols + " public symbols · " + e.out.length + " out · " +
        e.into.length + " in" }),
      el("p", { class: "t-hint", text: "click to focus · drag to move · shift-click to start a path" })
    ], ev);
  }

  function showEdgeTip(e, ev) {
    hoverEdge = e;
    var ev_files = (e.evidence || []).slice(0, 6);
    tipHtml([
      el("b", { text: e.source + " → " + e.target }),
      el("span", { class: "t-tier", text: " " + e.kind + " ×" + e.weight }),
      el("p", { text: KIND_NOTE[e.kind] }),
      ev_files.length ? el("p", { class: "t-facts", text: ev_files.join(", ") +
        (e.evidence.length > ev_files.length ? ", +" + (e.evidence.length - ev_files.length) + " more" : "") }) : null
    ], ev);
  }

  function tipHtml(kids, ev) {
    clear(tip);
    kids.forEach(function (k) { if (k) tip.appendChild(k); });
    tip.hidden = false;
    var host = svgRoot.parentNode.getBoundingClientRect();
    var x = ev.clientX - host.left + 14, y = ev.clientY - host.top + 14;
    if (x + 260 > host.width) x = Math.max(6, x - 288);
    if (y + 150 > host.height) y = Math.max(6, y - 170);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }

  function hideTip() { hoverEdge = null; tip.hidden = true; }

  /* --------------------------------------------------------- matrix view */

  /* A dense cyclic graph is hard to read as arcs and trivial to read as a
     matrix: the two blocks of mutual citation are visible as blocks, and the
     empty rectangle above the diagonal is the one-way bridge between them. */
  function paintMatrix() {
    svgRoot.hidden = true;
    matrixHost.hidden = false;
    clear(matrixHost);

    var comps = components();
    var order = [];
    comps.slice().sort(function (a, b) { return b.length - a.length; })
      .forEach(function (c) {
        c.slice().sort(function (x, y) { return byTier(byId[x], byId[y]); })
          .forEach(function (id) { order.push(id); });
      });
    var index = {};
    order.forEach(function (id, i) { index[id] = i; });
    /* One cell, possibly several edges: a pair can be both a declared dependency
       and a citation. Show the most specific kind rather than whichever was
       written last, and say in the title that the others are there. */
    var cell = {};
    activeEdges().forEach(function (e) {
      var k = e.source + "|" + e.target, had = cell[k];
      if (!had) { cell[k] = e; return; }
      cell[k] = KINDS.indexOf(e.kind) < KINDS.indexOf(had.kind) ? e : had;
      cell[k].alsoKinds = (had.alsoKinds || []).concat([e === cell[k] ? had.kind : e.kind]);
    });

    var compOf = {};
    comps.forEach(function (c, i) { c.forEach(function (id) { compOf[id] = i; }); });

    var table = el("table", { class: "matrix" });
    var head = el("tr", {}, [el("th", { class: "corner", text: "cites →" })]);
    order.forEach(function (id) {
      head.appendChild(el("th", { class: "col" }, [el("span", { text: id })]));
    });
    table.appendChild(head);

    order.forEach(function (src) {
      var tr = el("tr", {}, [el("th", { class: "row", text: src })]);
      order.forEach(function (dst) {
        var e = cell[src + "|" + dst];
        var same = compOf[src] === compOf[dst];
        var td = el("td", {
          class: (src === dst ? "self " : "") + (same ? "block " : "") + (e ? "on " + e.kind : "off"),
          title: e ? src + " → " + dst + " · " + e.kind + " ×" + e.weight +
                     (e.alsoKinds ? " (also " + e.alsoKinds.join(", ") + ")" : "") +
                     (e.evidence ? " · " + e.evidence.slice(0, 4).join(", ") : "")
                   : src + " does not name " + dst
        });
        if (e) {
          td.style.setProperty("--w", Math.min(1, 0.35 + e.weight / 8).toFixed(2));
          td.addEventListener("click", function () { focus(src); });
        }
        tr.appendChild(td);
      });
      table.appendChild(tr);
    });
    matrixHost.appendChild(table);
    matrixHost.appendChild(el("p", { class: "hint", text:
      "Rows name columns. Parts are ordered by component, so a solid square on the " +
      "diagonal is a set that all reach each other, and an empty rectangle off it is " +
      "a boundary nothing crosses." }));
  }

  /* --------------------------------------------------------------- chrome */

  function buildGraph() {
    var panel = document.getElementById("graph-panel");
    svgRoot = document.getElementById("graph");
    svgRoot.setAttribute("viewBox", "0 0 " + W + " " + H);
    clear(svgRoot);

    var defs = svg("defs");
    KINDS.forEach(function (kind) {
      [["", 1], ["-dim", 0.5]].forEach(function (v) {
        defs.appendChild(svg("marker", {
          id: "arrow-" + kind + v[0], viewBox: "0 0 10 10", refX: "9", refY: "5",
          markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse"
        }, [svg("path", { d: "M 0 0 L 10 5 L 0 10 z",
                          fill: "var(--" + kind + ")", opacity: v[1] })]));
      });
    });
    svgRoot.appendChild(defs);

    scene = svg("g", { id: "scene" });
    gHulls = svg("g", { class: "hulls" });
    gEdges = svg("g", { class: "edges" });
    gNodes = svg("g", { class: "nodes" });
    scene.appendChild(gHulls);
    scene.appendChild(gEdges);
    scene.appendChild(gNodes);
    svgRoot.appendChild(scene);

    tip = el("div", { class: "tip", hidden: "hidden" });
    matrixHost = el("div", { class: "matrix-host", hidden: "hidden" });
    var stage = svgRoot.parentNode;
    stage.appendChild(tip);
    stage.appendChild(matrixHost);

    svgRoot.addEventListener("wheel", function (ev) {
      ev.preventDefault();
      var s = clientToScene(ev);
      zoomAbout(s.x * view.k + view.x, s.y * view.k + view.y,
                ev.deltaY < 0 ? 1.12 : 1 / 1.12);
    }, { passive: false });
    svgRoot.addEventListener("pointerdown", function (ev) {
      if (dragging) return;
      ev.preventDefault();
      panFrom = { cx: ev.clientX, cy: ev.clientY, vx: view.x, vy: view.y };
      moved = false;
      /* Capture, for the same reason a node drag does: pointermove is bound to
         the svg, so without it a pan that leaves the panel stops dead halfway
         and only resumes if you happen to come back inside. */
      capture(ev);
    });
    svgRoot.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    svgRoot.addEventListener("dblclick", function () { fitView(true); });

    panel.addEventListener("keydown", function (ev) {
      var step = 40;
      if (ev.key === "+" || ev.key === "=") { zoomAbout(W / 2, H / 2, 1.2); }
      else if (ev.key === "-") { zoomAbout(W / 2, H / 2, 1 / 1.2); }
      else if (ev.key === "0" || ev.key === "f") { fitView(true); }
      else if (ev.key === "ArrowLeft" && ev.target === panel) { view.x += step; applyView(); }
      else if (ev.key === "ArrowRight" && ev.target === panel) { view.x -= step; applyView(); }
      else if (ev.key === "ArrowUp" && ev.target === panel) { view.y += step; applyView(); }
      else if (ev.key === "ArrowDown" && ev.target === panel) { view.y -= step; applyView(); }
      else return;
      ev.preventDefault();
    });

    maxSymbols = 1;
    graph.nodes.forEach(function (n) {
      maxSymbols = Math.max(maxSymbols, n.counts.symbols || 0);
    });
  }

  function buildToolbar() {
    var host = document.getElementById("graph-tools");
    if (!host) return;
    clear(host);

    var modes = [
      ["structure", "Structure", "components condensed and layered — cycles are rings, everything between them points down"],
      ["force", "Force", "live simulation you can pull apart; the layering is kept as a bias"],
      ["radial", "Neighbourhood", "the focused part at the centre, the rest ringed by distance from it"],
      ["grid", "Grid", "every part on a lattice, by tier — no structure, just an even look at them all"],
      ["matrix", "Matrix", "who names whom as a grid; components sit as blocks on the diagonal"]
    ];
    var group = el("div", { class: "seg", role: "group", "aria-label": "Layout" });
    modes.forEach(function (m) {
      var b = el("button", {
        type: "button", title: m[2], "data-mode": m[0],
        "aria-pressed": String(mode === m[0]), text: m[1]
      });
      b.addEventListener("click", function () {
        mode = m[0];
        group.querySelectorAll("button").forEach(function (x) {
          x.setAttribute("aria-pressed", String(x.dataset.mode === mode));
        });
        writeHash();
        relayout(true);
        say("");
      });
      group.appendChild(b);
    });
    host.appendChild(group);

    var zoom = el("div", { class: "seg", role: "group", "aria-label": "Zoom" });
    [["−", "zoom out", function () { zoomAbout(W / 2, H / 2, 1 / 1.25); }],
     ["+", "zoom in", function () { zoomAbout(W / 2, H / 2, 1.25); }],
     ["Fit", "fit the whole graph (f)", function () { fitView(true); }]
    ].forEach(function (b) {
      var btn = el("button", { type: "button", title: b[1], text: b[0] });
      btn.addEventListener("click", b[2]);
      zoom.appendChild(btn);
    });
    host.appendChild(zoom);

    var wide = el("button", { type: "button", class: "wide", text: "Expand",
                              title: "give the graph the whole window (Esc to leave)" });
    wide.addEventListener("click", function () {
      var panel = document.getElementById("graph-panel");
      var on = panel.classList.toggle("expanded");
      wide.textContent = on ? "Collapse" : "Expand";
      document.body.classList.toggle("has-expanded", on);
      window.setTimeout(function () { fitView(true); }, 60);
    });
    host.appendChild(wide);

    var reset = el("button", { type: "button", class: "wide", text: "Unpin all",
                               title: "release every node you have dragged" });
    reset.addEventListener("click", function () {
      Object.keys(pos).forEach(function (id) { delete pos[id].fx; delete pos[id].fy; });
      trailFrom = null; trailNodes = {}; trailEdges = {};
      say("");
      relayout(true);
    });
    host.appendChild(reset);
  }

  document.addEventListener("keydown", function (ev) {
    if (ev.key !== "Escape") return;
    var panel = document.getElementById("graph-panel");
    if (panel && panel.classList.contains("expanded")) {
      panel.classList.remove("expanded");
      document.body.classList.remove("has-expanded");
      var w = document.querySelector("#graph-tools .wide");
      if (w) w.textContent = "Expand";
      window.setTimeout(function () { fitView(true); }, 60);
    }
  });

  function drawGraph() { relayout(false); }

  function edgesFor(id) {
    var out = [], into = [];
    graph.edges.forEach(function (e) {
      if (!enabled[e.kind]) return;
      if (e.source === id) out.push(e);
      else if (e.target === id) into.push(e);
    });
    function rank(e) { return KINDS.indexOf(e.kind) * 1000 - e.weight; }
    out.sort(function (a, b) { return rank(a) - rank(b); });
    into.sort(function (a, b) { return rank(a) - rank(b); });
    return { out: out, into: into };
  }

  function edgeItem(e, other, direction) {
    var ev = e.evidence && e.evidence.length ? e.evidence[0] : "";
    var more = e.weight > 1 ? " +" + (e.weight - 1) + " more" : "";
    return el("li", {}, [
      el("span", { class: "kind " + e.kind, text: e.kind }),
      el("span", { text: direction + " " }),
      el("a", { href: "#" + other, text: other, title: KIND_NOTE[e.kind] }),
      ev ? el("span", { class: "ev", text: ev + more }) : null
    ]);
  }

  function drawDetail() {
    var n = byId[focusId];
    var host = document.getElementById("detail");
    clear(host);
    if (!n) return;

    host.appendChild(el("div", { class: "tier", text: n.tier }));
    host.appendChild(el("h3", { text: n.id }));
    if (n.tagline) host.appendChild(el("p", { class: "tagline", text: n.tagline }));

    if (n.reserved) {
      host.appendChild(el("div", { class: "banner", text:
        "Declared, not written. No repository, package, layer specification or check exists " +
        "for this field. It appears here because it is named in the field stack, and for no " +
        "other reason." }));
    } else if (!n.repo_url) {
      host.appendChild(el("div", { class: "banner", text:
        "No public remote. This repository exists locally only, so its links below are absent." }));
    }

    var links = el("div", { class: "links" });
    if (n.repo_url) links.appendChild(el("a", { href: n.repo_url, text: "Repository" }));
    if (n.pages_url && n.id !== focusOwner()) links.appendChild(el("a", { href: n.pages_url, text: "Its own pages" }));
    (n.papers || []).forEach(function (p) {
      if (p.slice(-4) === ".pdf") links.appendChild(el("a", {
        href: (n.repo_url || "") + "/blob/main/" + p, text: "Preprint (PDF)"
      }));
    });
    if (links.childNodes.length) host.appendChild(links);

    var facts = el("div", { class: "facts" });
    function fact(label, value) {
      facts.appendChild(el("span", {}, [el("b", { text: String(value) }), " " + label]));
    }
    if (n.package) {
      facts.appendChild(el("span", {}, ["package ", el("b", { text: n.package })]));
    }
    fact("public symbols", n.counts.symbols);
    fact("modules", n.counts.modules);
    fact("layer specs", n.counts.layers);
    fact("tracked files", n.counts.tracked_files);
    host.appendChild(facts);

    var e = edgesFor(n.id);
    host.appendChild(el("h2", { text: "Depends on / cites (" + e.out.length + ")" }));
    if (e.out.length) {
      host.appendChild(el("ul", { class: "edgelist" },
        e.out.map(function (x) { return edgeItem(x, x.target, "→"); })));
    } else {
      host.appendChild(el("p", { class: "hint", text: "Nothing. This part names no other part of the family." }));
    }
    host.appendChild(el("h2", { text: "Depended on / cited by (" + e.into.length + ")" }));
    if (e.into.length) {
      host.appendChild(el("ul", { class: "edgelist" },
        e.into.map(function (x) { return edgeItem(x, x.source, "←"); })));
    } else {
      host.appendChild(el("p", { class: "hint", text: "Nothing. No other part of the family names it." }));
    }
  }

  function focusOwner() { return document.body.dataset.focus || ""; }

  /* ------------------------------------------------------------------ api */

  function indexSymbols() {
    flatSymbols = [];
    graph.nodes.forEach(function (n) {
      (n.api || []).forEach(function (m) {
        m.symbols.forEach(function (s) {
          flatSymbols.push({
            repo: n.id, module: m.module, path: m.path, repo_url: n.repo_url,
            name: s.name, kind: s.kind, doc: s.doc || "", line: s.line,
            signature: s.signature || "", methods: s.methods || [],
            hay: (n.id + " " + m.module + " " + s.name + " " + (s.doc || "") + " " +
                  (s.methods || []).join(" ")).toLowerCase()
          });
        });
      });
    });
  }

  function highlight(text, q) {
    if (!q) return document.createTextNode(text);
    var frag = document.createDocumentFragment();
    var lower = text.toLowerCase(), i = 0, at;
    while ((at = lower.indexOf(q, i)) !== -1) {
      if (at > i) frag.appendChild(document.createTextNode(text.slice(i, at)));
      frag.appendChild(el("mark", { text: text.slice(at, at + q.length) }));
      i = at + q.length;
    }
    frag.appendChild(document.createTextNode(text.slice(i)));
    return frag;
  }

  function symbolRow(s, q) {
    var code = el("code");
    code.appendChild(highlight(s.name, q));
    if (s.signature) code.appendChild(document.createTextNode(s.signature));
    var row = el("div", { class: "sym" }, [
      s.repo_url
        ? el("a", { href: s.repo_url + "/blob/main/" + s.path + "#L" + s.line }, [code])
        : code,
      el("span", { class: "kind-tag", text: s.kind })
    ]);
    if (s.doc) {
      row.appendChild(el("div", { class: "doc" }, [highlight(s.doc, q)]));
    }
    if (s.methods.length) {
      row.appendChild(el("div", { class: "methods", text: s.methods.join(" · ") }));
    }
    return row;
  }

  function drawApi(query) {
    var q = (query || "").trim().toLowerCase();
    var host = document.getElementById("api-body");
    clear(host);

    var matches = q ? flatSymbols.filter(function (s) { return s.hay.indexOf(q) !== -1; }) : flatSymbols;
    var countEl = document.getElementById("count");
    countEl.textContent = q
      ? matches.length + " of " + flatSymbols.length + " symbols match “" + query.trim() + "”"
      : flatSymbols.length + " public symbols across " +
        graph.nodes.filter(function (n) { return n.counts.symbols; }).length + " packages";

    var grouped = {};
    matches.forEach(function (s) {
      (grouped[s.repo] = grouped[s.repo] || {});
      (grouped[s.repo][s.module] = grouped[s.repo][s.module] || []).push(s);
    });

    var ordered = graph.nodes.slice().sort(function (a, b) {
      if (a.id === focusId) return -1;
      if (b.id === focusId) return 1;
      return 0;
    });
    ordered.forEach(function (n) {
      var mods = grouped[n.id];
      if (!mods) return;
      var total = Object.keys(mods).reduce(function (a, k) { return a + mods[k].length; }, 0);
      var open = q ? true : n.id === focusId;
      var d = el("details", { class: "repo" + (n.id === focusId ? " is-focus" : "") }, [
        el("summary", {}, [
          el("span", { text: n.id }),
          el("span", { class: "pkg", text: n.package || "" }),
          el("span", { class: "n", text: total + (total === 1 ? " symbol" : " symbols") })
        ])
      ]);
      if (open) d.setAttribute("open", "");
      d.querySelector("summary").addEventListener("dblclick", function (ev) {
        ev.preventDefault();
        focus(n.id);
      });
      Object.keys(mods).sort().forEach(function (mod) {
        var block = el("div", { class: "module" }, [
          el("div", { class: "mod-name", text: mod })
        ]);
        mods[mod].forEach(function (s) { block.appendChild(symbolRow(s, q)); });
        d.appendChild(block);
      });
      host.appendChild(d);
    });

    if (!matches.length) {
      host.appendChild(el("p", { class: "hint", text: "No symbol matches that." }));
    }
  }

  /* ---------------------------------------------------------------- shell */

  function focus(id) {
    if (!byId[id]) return;
    focusId = id;
    writeHash();
    if (mode === "matrix") paintMatrix();
    else if (mode === "radial") relayout(true);
    else restyle();
    drawDetail();
    drawApi(document.getElementById("search").value);
  }

  /* The whole view lives in the URL, so a link carries the part you were
     looking at, the layout you were in and the edge kinds you had on. */
  function writeHash() {
    var off = KINDS.filter(function (k) { return !enabled[k]; });
    var h = "#" + focusId + (mode === "structure" ? "" : "&layout=" + mode) +
            (off.length ? "&off=" + off.join(",") : "");
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", h);
    }
  }

  function readHash() {
    var raw = (window.location.hash || "").replace("#", "");
    if (!raw) return null;
    var parts = raw.split("&");
    var out = { repo: parts[0] || null, layout: null, off: [] };
    parts.slice(1).forEach(function (p) {
      var i = p.indexOf("=");
      if (i < 0) return;
      var k = p.slice(0, i), v = p.slice(i + 1);
      if (k === "layout") out.layout = v;
      if (k === "off") out.off = v.split(",").filter(Boolean);
    });
    return out;
  }

  function buildLegend() {
    var host = document.getElementById("legend");
    clear(host);
    KINDS.forEach(function (kind) {
      var n = graph.totals.edges_by_kind[kind] || 0;
      var b = el("button", {
        type: "button", "aria-pressed": "true", title: KIND_NOTE[kind]
      }, [
        el("span", { class: "swatch " + kind }),
        kind + " (" + n + ")"
      ]);
      b.addEventListener("click", function () {
        enabled[kind] = !enabled[kind];
        b.setAttribute("aria-pressed", String(enabled[kind]));
        writeHash();
        trailFrom = null; trailNodes = {}; trailEdges = {};
        say("");
        relayout(true);
        drawDetail();
      });
      host.appendChild(b);
    });
  }

  function start(data) {
    graph = data;
    graph.nodes.forEach(function (n) { byId[n.id] = n; });
    if (!byId[focusId]) focusId = graph.nodes[0].id;
    var h0 = readHash();
    if (h0) {
      if (byId[h0.repo]) focusId = h0.repo;
      if (h0.layout) mode = h0.layout;
      h0.off.forEach(function (k) { if (k in enabled) enabled[k] = false; });
    }

    var home = byId[focusOwner()];
    var back = document.getElementById("back");
    if (back && home) {
      back.textContent = "← " + home.id;
      back.title = "back to this repository's own pages";
    }
    if (graph.note) {
      var host = document.getElementById("graph-panel");
      var msg = el("div", { class: "banner", text: graph.note });
      host.insertBefore(msg, host.firstChild.nextSibling);
    }
    document.getElementById("digest").textContent =
      (graph.view === "public" ? "published view " : "graph ") + graph.digest.slice(0, 12);
    document.getElementById("digest").title =
      "sha256 of the canonical graph payload: " + graph.digest;

    indexSymbols();
    buildGraph();
    buildToolbar();
    buildLegend();
    relayout(false);
    drawDetail();
    drawApi("");

    var search = document.getElementById("search");
    var timer = null;
    search.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { drawApi(search.value); }, 90);
    });
    window.addEventListener("hashchange", function () {
      var h = readHash();
      if (h && byId[h.repo] && h.repo !== focusId) focus(h.repo);
    });
    window.addEventListener("resize", function () {
      window.clearTimeout(fitTimer);
      fitTimer = window.setTimeout(function () { fitView(false); }, 120);
    });
    var fitTimer = null;
  }

  function fail(message) {
    var host = document.getElementById("detail");
    clear(host);
    host.appendChild(el("div", { class: "banner", text: message }));
  }

  fetch("family-graph.json", { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(start)
    .catch(function (err) {
      fail("Could not load family-graph.json (" + err.message + "). " +
           "Serve this directory over HTTP rather than opening the file directly.");
    });
})();
