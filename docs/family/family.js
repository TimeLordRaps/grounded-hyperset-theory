/* Family explorer — shared script, byte-identical in every repository.
 *
 * Reads family-graph.json (generated from the repositories by
 * tools/build_family_graph.py) and renders an ego-centric view: the repository
 * this page belongs to sits at the centre, every other part of the family is
 * placed around it, and every edge in the family is drawn, with the ones
 * touching the centre held at full strength. Clicking any node re-centres the
 * view without leaving the page, so one page explores the whole family.
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

  var W = 760, H = 560, CX = W / 2, CY = H / 2, R1 = 152, R2 = 248;

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

  function neighbours(id) {
    var set = {};
    graph.edges.forEach(function (e) {
      if (!enabled[e.kind]) return;
      if (e.source === id) set[e.target] = true;
      if (e.target === id) set[e.source] = true;
    });
    delete set[id];
    return set;
  }

  function layout() {
    var near = neighbours(focusId);
    var inner = [], outer = [];
    graph.nodes.forEach(function (n) {
      if (n.id === focusId) return;
      (near[n.id] ? inner : outer).push(n);
    });
    inner.sort(byTier);
    outer.sort(byTier);

    var pos = {};
    pos[focusId] = { x: CX, y: CY, ring: 0 };
    function place(list, radius) {
      var step = (Math.PI * 2) / Math.max(list.length, 1);
      list.forEach(function (n, i) {
        var a = -Math.PI / 2 + i * step;
        pos[n.id] = { x: CX + radius * Math.cos(a), y: CY + radius * Math.sin(a), ring: radius };
      });
    }
    place(inner, R1);
    place(outer, R2);
    return pos;
  }

  function edgePath(a, b, bow) {
    var mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
    var dx = b.x - a.x, dy = b.y - a.y;
    var len = Math.sqrt(dx * dx + dy * dy) || 1;
    var cx = mx + (-dy / len) * bow, cy = my + (dx / len) * bow;
    return "M" + a.x.toFixed(1) + " " + a.y.toFixed(1) +
           " Q" + cx.toFixed(1) + " " + cy.toFixed(1) +
           " " + b.x.toFixed(1) + " " + b.y.toFixed(1);
  }

  function trim(a, b, r) {
    var dx = b.x - a.x, dy = b.y - a.y;
    var len = Math.sqrt(dx * dx + dy * dy) || 1;
    return { x: b.x - (dx / len) * r, y: b.y - (dy / len) * r };
  }

  function radiusOf(n) {
    if (n.id === focusId) return 16;
    if (n.reserved || n.tier === "declared") return 10;
    return 12;
  }

  function drawGraph() {
    var pos = layout();
    var root = document.getElementById("graph");
    clear(root);

    var defs = svg("defs");
    KINDS.forEach(function (kind) {
      var m = svg("marker", {
        id: "arrow-" + kind, viewBox: "0 0 10 10", refX: "9", refY: "5",
        markerWidth: "6", markerHeight: "6", orient: "auto-start-reverse"
      }, [svg("path", { d: "M 0 0 L 10 5 L 0 10 z", fill: "var(--" + kind + ")" })]);
      defs.appendChild(m);
    });
    root.appendChild(defs);

    var gEdges = svg("g", { class: "edges" });
    var gNodes = svg("g", { class: "nodes" });
    root.appendChild(gEdges);
    root.appendChild(gNodes);

    graph.edges.forEach(function (e) {
      if (!enabled[e.kind]) return;
      var a = pos[e.source], b = pos[e.target];
      if (!a || !b) return;
      var incident = e.source === focusId || e.target === focusId;
      var bow = (KINDS.indexOf(e.kind) + 1) * 16 * (e.source < e.target ? 1 : -1);
      var end = trim(a, b, radiusOf(byId[e.target]) + 6);
      var width = Math.min(5, 1 + Math.log(e.weight + 1));
      gEdges.appendChild(svg("path", {
        class: "edge " + e.kind + (incident ? " incident" : " dimmed"),
        d: edgePath(a, end, bow),
        "stroke-width": width.toFixed(2),
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
      var g = svg("g", {
        class: "node" + (n.id === focusId ? " is-focus" : "") +
               (n.reserved ? " reserved" : "") + (related ? "" : " dimmed"),
        transform: "translate(" + p.x.toFixed(1) + "," + p.y.toFixed(1) + ")",
        tabindex: "0", role: "button",
        "aria-label": n.id + " — " + (n.tagline || n.tier)
      }, [
        svg("circle", {
          r: r,
          fill: n.reserved ? "none" : "var(--tier-" + n.tier + ")"
        }),
        svg("text", { y: r + 14, text: n.id }),
        n.counts.symbols
          ? svg("text", { y: r + 25, class: "count", text: n.counts.symbols + " symbols" })
          : svg("text", { y: r + 25, class: "count", text: n.reserved ? "reserved" : "no package" })
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
