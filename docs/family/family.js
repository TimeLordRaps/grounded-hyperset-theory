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
  var TIERS = ["foundation", "language", "applied", "combination", "declared"];
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

  function ringRadius(size) { return size < 2 ? 0 : Math.max(58, 16 * size); }

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
      if (comps[i].length > 1) return 2 * ringRadius(comps[i].length) + 40;
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
    var squeeze = cursor > H ? H / cursor : 1;
    var top = Math.max(0, (H - cursor * squeeze) / 2);

    var pos = {}, groups = [];
    bands.forEach(function (row, bi) {
      var y = top + centres[bi] * squeeze;
      var total = row.reduce(function (s, i) { return s + widthOf(i); }, 0);
      var x = (W - total) / 2;
      row.forEach(function (i) {
        placeComponent(comps[i], x + widthOf(i) / 2, y, pos, groups);
        x += widthOf(i);
      });
    });


    return { pos: pos, groups: groups, levels: levels.length, rows: bands.length };
  }

  function placeComponent(ids, cx, cy, pos, groups) {
    var members = ids.map(function (id) { return byId[id]; }).sort(byTier);
    if (members.length === 1) {
      pos[members[0].id] = { x: cx, y: cy, place: "down" };
      return;
    }
    var r = ringRadius(members.length);
    var stepA = (Math.PI * 2) / members.length;
    members.forEach(function (n, i) {
      var a = -Math.PI / 2 + i * stepA;
      var cos = Math.cos(a), sin = Math.sin(a);
      /* Labels go on the outward side of the ring. Hanging every one below its
         node puts the top node's label inside the ring, over the very cycle the
         ring exists to show, and leaves the two bottom nodes' labels -- which on
         a five-ring are only about 1.2r apart -- to collide with each other.
         Anything near the horizontal extremes is set beside its node instead,
         where there is room to run outward. */
      var place = Math.abs(cos) > 0.55 ? (cos > 0 ? "right" : "left")
                : (sin < 0 ? "up" : "down");
      pos[n.id] = { x: cx + r * cos, y: cy + r * sin, place: place };
    });
    groups.push({ x: cx, y: cy, r: r, size: members.length });
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

  function drawGraph() {
    var placed = layout();
    var pos = placed.pos;
    var root = document.getElementById("graph");
    clear(root);

    maxSymbols = 1;
    graph.nodes.forEach(function (n) {
      maxSymbols = Math.max(maxSymbols, n.counts.symbols || 0);
    });

    var active = activeEdges();
    var maxW = 1;
    active.forEach(function (e) { maxW = Math.max(maxW, e.weight); });
    /* Spread the weights across the full stroke range. The previous scale was
       1 + log(w + 1), which mapped the family's real range of 1 to 8 onto 1.7
       to 3.2 -- the heaviest edge in the graph was not twice the lightest. */
    function widthOf(w) {
      return maxW <= 1 ? 2.2 : 1.2 + 4.3 * (w - 1) / (maxW - 1);
    }

    var defs = svg("defs");
    KINDS.forEach(function (kind) {
      defs.appendChild(svg("marker", {
        id: "arrow-" + kind, viewBox: "0 0 10 10", refX: "9", refY: "5",
        markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse"
      }, [svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "var(--" + kind + ")" })]));
    });
    root.appendChild(defs);

    var gHulls = svg("g", { class: "hulls" });
    var gEdges = svg("g", { class: "edges" });
    var gNodes = svg("g", { class: "nodes" });
    root.appendChild(gHulls);
    root.appendChild(gEdges);
    root.appendChild(gNodes);

    placed.groups.forEach(function (g) {
      gHulls.appendChild(svg("circle", {
        class: "scc-hull", cx: g.x.toFixed(1), cy: g.y.toFixed(1), r: (g.r + 34).toFixed(1)
      }));
      gHulls.appendChild(svg("text", {
        class: "scc-label", x: g.x.toFixed(1), y: (g.y - g.r - 42).toFixed(1),
        text: g.size + " parts, each reaching every other"
      }));
    });

    active.forEach(function (e) {
      var a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      var dx = b.x - a.x, dy = b.y - a.y;
      var len = Math.sqrt(dx * dx + dy * dy) || 1;
      /* Bow with the edge's own length, so a short hop is not wrapped in a huge
         loop and a long one is not drawn flat. Reciprocal pairs bow opposite
         ways so both directions stay readable, and kinds are nudged apart on
         top of that. */
      var dir = e.source < e.target ? 1 : -1;
      var bow = dir * 0.085 * Math.min(len, 300) * (1 + 0.5 * KINDS.indexOf(e.kind));
      var c = control(a, b, bow);
      var ends = trimEnds(a, c, b, radiusOf(byId[e.source]) + 3,
                          radiusOf(byId[e.target]) + 7);
      var incident = e.source === focusId || e.target === focusId;
      gEdges.appendChild(svg("path", {
        class: "edge " + e.kind + (incident ? " incident" : " dimmed"),
        d: edgePath(ends.a, c, ends.b),
        "stroke-width": widthOf(e.weight).toFixed(2),
        "marker-end": "url(#arrow-" + e.kind + ")",
        opacity: incident ? 0.95 : 0.16
      }));
    });

    var near = neighbours(focusId);
    graph.nodes.forEach(function (n) {
      var p = pos[n.id];
      if (!p) return;
      var related = n.id === focusId || near[n.id];
      var r = radiusOf(n);
      var count = n.counts.symbols
        ? n.counts.symbols + " symbols"
        : (n.reserved ? "reserved" : "no package");
      var side = p.place === "left" || p.place === "right";
      var dx = side ? (p.place === "right" ? r + 9 : -(r + 9)) : 0;
      var nameY = side ? -2 : (p.place === "up" ? -(r + 23) : r + 14);
      var countY = side ? 11 : (p.place === "up" ? -(r + 10) : r + 27);
      var g = svg("g", {
        class: "node" + (n.id === focusId ? " is-focus" : "") +
               (n.reserved ? " reserved" : "") + (related ? "" : " dimmed"),
        transform: "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")",
        tabindex: "0", role: "button",
        "aria-label": n.id + " — " + (n.tagline || n.tier)
      }, [
        svg("circle", { r: r.toFixed(1), fill: n.reserved ? "none" : "var(--tier-" + n.tier + ")" }),
        svg("text", { x: dx.toFixed(1), y: nameY.toFixed(1), class: p.place, text: n.id }),
        svg("text", { x: dx.toFixed(1), y: countY.toFixed(1),
                      class: "count " + p.place, text: count })
      ]);
      g.addEventListener("click", function () { focus(n.id); });
      g.addEventListener("keydown", function (ev) {
        if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); focus(n.id); }
      });
      gNodes.appendChild(g);
    });
  }

  /* --------------------------------------------------------------- detail */

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
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", "#" + id);
    }
    drawGraph();
    drawDetail();
    drawApi(document.getElementById("search").value);
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
        drawGraph();
        drawDetail();
      });
      host.appendChild(b);
    });
  }

  function start(data) {
    graph = data;
    graph.nodes.forEach(function (n) { byId[n.id] = n; });
    if (!byId[focusId]) focusId = graph.nodes[0].id;
    var hash = (window.location.hash || "").replace(/^#/, "");
    if (byId[hash]) focusId = hash;

    document.getElementById("graph").setAttribute("viewBox", "0 0 " + W + " " + H);
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
    buildLegend();
    drawGraph();
    drawDetail();
    drawApi("");

    var search = document.getElementById("search");
    var timer = null;
    search.addEventListener("input", function () {
      window.clearTimeout(timer);
      timer = window.setTimeout(function () { drawApi(search.value); }, 90);
    });
    window.addEventListener("hashchange", function () {
      var h = (window.location.hash || "").replace(/^#/, "");
      if (byId[h] && h !== focusId) focus(h);
    });
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
