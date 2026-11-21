// Pacta site: theme, live countdowns, copy buttons, live pre-flight checker, control-plane inspector, index filter + drawers,
// request builder, self-serve Base USDC checkout, and host-gated X conversion measurement (uwt.js on pacta.wtf / pacta.fractalneurons.com only). Data comes from this site's own /api/v1/*.json files; the one exception is the
// pre-flight checker, which calls Pacta's own free API (data-api on .pf) only after an explicit submit or preset click.
// Record text is inserted with textContent (never innerHTML). Every control works without a mail client.
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c !== null && c !== undefined) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }
  function short(h, a, b) { return h.slice(0, a) + "…" + h.slice(-b); }
  // v4.4 (R-V4): link markers are inline Lucide arrows (aria-hidden), never a raw → / ↗ glyph: the self-hosted Inter subset has
  // no arrows, so a raw glyph shows as a missing-glyph box wherever the OS lacks a fallback font. Same markup as ui.arrow().
  var ARROW_D = { right: "M5 12h14M12 5l7 7-7 7", "up-right": "M7 7h10v10M7 17 17 7" };
  function arrowIcon(kind) {
    var s = document.createElementNS("http://www.w3.org/2000/svg", "svg"), p = document.createElementNS("http://www.w3.org/2000/svg", "path");
    s.setAttribute("class", "i ia"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("aria-hidden", "true");
    p.setAttribute("d", ARROW_D[kind] || ARROW_D.right); s.appendChild(p);
    return s;
  }
  // a link whose visible text is the label followed by the arrow (kind "up-right" for external links)
  function arrowLink(attrs, label, kind) { return el("a", attrs, [String(label), arrowIcon(kind)]); }
  // v4.2: a staging build (build_site.py --base-path) records its mount on <html data-base-path>; runtime site links follow it
  // same rule as build_site.valid_base_path(): segments of [A-Za-z0-9._-], never a standalone "." or ".." (no escaping the mount)
  var BASE = (function () { var b = document.documentElement.getAttribute("data-base-path") || ""; return /^(?:\/(?!\.{1,2}(?:\/|$))[A-Za-z0-9._-]+)+$/.test(b) ? b : ""; })();
  function siteUrl(u) { var m = /^https:\/\/pacta\.wtf(\/[^\s"<>]*)$/.exec(String(u)); return BASE && m ? BASE + m[1] : String(u); }
  function num(n) { return Number(n).toLocaleString("en-US"); }

  // ---- opt-in Founder / internal QA tag (?internal=1 sets pacta_internal=1; ?internal=0 or footer [Turn off] clears it) ----
  // Normal external visitors NEVER write to browser storage; getItem is read-only unless ?internal=1 or ?internal=0 is in the URL.
  var INTERNAL_QA_KEY = "pacta_internal";
  function clearInternalQaStorage() { try { localStorage.removeItem(INTERNAL_QA_KEY); } catch (e) { /* storage disabled */ } }
  function stripInternalParam() {
    try {
      var raw = String((location && location.search) || "");
      if (!/[?&]internal=[01](?:&|$)/.test(raw)) return;
      var parts = raw.replace(/^\?/, "").split("&").filter(function (kv) { return kv && !/^internal=[01]$/.test(kv); });
      var nextSearch = parts.length ? "?" + parts.join("&") : "";
      var nextUrl = String((location && location.pathname) || "/") + nextSearch + String((location && location.hash) || "");
      if (window.history && typeof window.history.replaceState === "function") window.history.replaceState(null, "", nextUrl);
    } catch (e) { /* ignore */ }
  }
  function syncInternalQaFlag() {
    var search = String((location && location.search) || "");
    var host = String((location && location.hostname) || "");
    var m = /(?:^|[?&])internal=(1|0)(?:&|$)/.exec(search);
    var param = m ? m[1] : null;
    if (param === "1") {
      try { localStorage.setItem(INTERNAL_QA_KEY, "1"); } catch (e) { /* storage disabled */ }
      stripInternalParam();
      window.__pactaInternal = 1;
      return;
    }
    if (param === "0") {
      clearInternalQaStorage();
      stripInternalParam();
      window.__pactaInternal = 0;
      return;
    }
    var stored = null;
    try { stored = localStorage.getItem(INTERNAL_QA_KEY); } catch (e) { /* storage disabled */ }
    window.__pactaInternal = (stored === "1" || host === "pacta.dri.network") ? 1 : 0;
  }
  syncInternalQaFlag();
  function isInternalQa() { return window.__pactaInternal === 1; }
  function checkerCallerAgent() { return isInternalQa() ? "pacta-founder-qa" : "pacta-wtf-checker"; }
  function initInternalQaBadge() {
    if (!isInternalQa()) return;
    var wrap = $(".ftr .wrap") || $(".ftr");
    if (!wrap || $("[data-internal-qa-badge]", wrap)) return;
    var offBtn = el("button", { type: "button", class: "qa-mode-off", "data-internal-qa-off": "1", text: "Turn off" });
    var bar = el("div", { class: "qa-mode-bar", "data-internal-qa-badge": "1", role: "status" }, [
      el("span", { class: "qa-mode-dot", "aria-hidden": "true" }),
      el("span", { text: "Internal QA mode active (excluded from external funnel) · " }),
      offBtn
    ]);
    offBtn.addEventListener("click", function () {
      clearInternalQaStorage();
      window.__pactaInternal = 0;
      bar.hidden = true;
    });
    wrap.appendChild(bar);
  }

  // ---- theme: Paper (default) / Slate ---------------------------------------------------------------
  // ---- theme: Light / Dark / System (U2) on a .dark class; System follows prefers-color-scheme, also when it changes ----------
  function applyTheme(pref) {
    var dark = pref === "dark" || (pref === "system" && systemDark());
    document.documentElement.classList.toggle("dark", dark);
    document.documentElement.setAttribute("data-theme-pref", pref);
    var word = pref === "system" ? "System" : pref === "dark" ? "Dark" : "Light";
    $$("[data-theme-set]").forEach(function (b) {
      b.setAttribute(b.hasAttribute("data-theme-sheet") ? "aria-pressed" : "aria-checked", String(b.getAttribute("data-theme-set") === pref));
    });
    var btn = $("[data-theme-btn]"); if (btn) btn.setAttribute("aria-label", "Theme: " + word);
    $$("[data-theme-label]").forEach(function (n) { n.textContent = word; });   // v4.7 W5: the visible label follows theme.js state
  }
  function setThemePref(pref) {
    if (pref !== "light" && pref !== "dark") pref = "system";
    try { if (pref === "system") localStorage.removeItem(THEME_KEY); else localStorage.setItem(THEME_KEY, pref); } catch (e) { /* private mode */ }
    applyTheme(pref);
  }
  function initTheme() {
    applyTheme(themePref());
    var root = $("[data-theme-menu]"), btn = $("[data-theme-btn]"), menu = $("#theme-menu");
    if (btn && menu) {
      var close = function (focusBtn) { menu.hidden = true; btn.setAttribute("aria-expanded", "false"); if (focusBtn) btn.focus(); };
      var open = function () {
        menu.hidden = false; btn.setAttribute("aria-expanded", "true");
        var cur = $('[aria-checked="true"]', menu) || $("[data-theme-set]", menu); if (cur) cur.focus();
      };
      btn.addEventListener("click", function () { if (menu.hidden) open(); else close(false); });
      menu.addEventListener("click", function (ev) {
        var it = ev.target && ev.target.closest ? ev.target.closest("[data-theme-set]") : null; if (!it) return;
        setThemePref(it.getAttribute("data-theme-set")); close(true);
      });
      menu.addEventListener("keydown", function (ev) {
        var items = $$("[data-theme-set]", menu), i = items.indexOf(document.activeElement);
        if (ev.key === "Escape") { ev.preventDefault(); close(true); }
        else if (ev.key === "ArrowDown") { ev.preventDefault(); items[(i + 1) % items.length].focus(); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); items[(i - 1 + items.length) % items.length].focus(); }
        else if (ev.key === "Tab") close(false);
      });
      document.addEventListener("click", function (ev) { if (!menu.hidden && root && !root.contains(ev.target)) close(false); });
    }
    $$("[data-theme-sheet]").forEach(function (b) { b.addEventListener("click", function () { setThemePref(b.getAttribute("data-theme-set")); }); });
    try {
      var mq = window.matchMedia("(prefers-color-scheme: dark)"), follow = function () { if (themePref() === "system") applyTheme("system"); };
      if (mq.addEventListener) mq.addEventListener("change", follow); else if (mq.addListener) mq.addListener(follow);
    } catch (e) { /* no matchMedia */ }
  }

  // ---- countdowns (an ETA is when execution becomes possible, not a guarantee) -----------------------
  function fmt(sec) {
    var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
    return (d ? d + "d " : "") + h + "h " + m + "m";
  }
  // the hero livebar names the next queued ETA that has not elapsed yet (the static build names the earliest one)
  function advanceLivebar(now) {
    var lb = $(".livebar[data-etas]"); if (!lb) return;
    var next = (lb.getAttribute("data-etas") || "").split(";").map(function (x) {
      var i = x.indexOf("|"); return { eta: parseInt(x.slice(0, i), 10), p: x.slice(i + 1) };
    }).filter(function (o) { return o.eta > now && o.p; })[0];
    var p = $(".lb-p", lb), cd = $(".countdown", lb), wrap = $(".lb-next", lb);
    if (!p || !cd || !wrap) return;
    if (next) { p.textContent = next.p; cd.setAttribute("data-eta", String(next.eta)); }
    else { wrap.textContent = "Next: every queued operation is past its ETA; check the Radar for execution state"; }
  }
  function tick() {
    var now = Math.floor(Date.now() / 1000);
    advanceLivebar(now);
    $$("[data-eta]").forEach(function (n) {
      var eta = parseInt(n.getAttribute("data-eta"), 10);
      if (!eta) return;
      n.textContent = eta > now ? "Execution window opens in " + fmt(eta - now) : "Window open — verify execution state";
    });
  }

  // ---- live timelock re-check (read-only): one GET to the free /v1/briefs/live-timelocks on timelock briefs and #radar.
  //      Badges (data-ops) change only through textContent + class; any failure keeps the static block-pinned state.
  //      No polling, no reload, no markup from the network. --------------------------------------------------------------
  var OP_LABEL = { executed: "EXECUTED", ready: "WINDOW OPEN", pending: "WAITING", unknown: "CANCELLED OR UNKNOWN", mixed: "MIXED" };
  var OP_STATES = ["executed", "ready", "pending", "unknown", "mixed"];
  var LIVE_TL_RE = /^https:\/\/(?:api\.pacta\.wtf|pacta\.fractalneurons\.com|pacta-x402\.pacta\.workers\.dev)\/v1\/briefs\/live-timelocks(\?[a-z_=&.-]*)?$/;
  function liveOpState(op) {
    var l = op && typeof op.live === "object" && op.live ? op.live : {};
    if (l.isOperationDone === true || l.status === "done") return "executed";
    if (l.status === "ready" && l.isOperationPending !== false) return "ready";
    if (l.status === "pending") return "pending";
    if (l.status === "unset") return "unknown";
    return null;
  }
  function setOpState(b, st) {
    b.textContent = OP_LABEL[st];
    OP_STATES.forEach(function (c) { b.classList.toggle(c, c === st); });
    b.setAttribute("data-opstate", st);
    b.setAttribute("data-live", "1");
  }
  // v4.6: the radar is multi-chain. Block numbers are kept per chain (an Ethereum and a Base block are never compared).
  function blkFmt(n) { return "#" + n.toLocaleString("en-US"); }
  function blkPill(b) { return (b.ethereum ? blkFmt(b.ethereum) : "") + (b.base ? (b.ethereum ? " · " : "") + "Base " + blkFmt(b.base) : ""); }
  function blkLine(b) {
    return b.ethereum && b.base ? "blocks Ethereum " + blkFmt(b.ethereum) + " and Base " + blkFmt(b.base)
      : "block " + (b.base ? "Base " + blkFmt(b.base) : blkFmt(b.ethereum));
  }
  function applyLiveTimelocks(j, viaSource) {
    if (!j || typeof j !== "object" || !Array.isArray(j.operations)) return null;
    var by = {}, chainOf = {}, blk = {};
    j.operations.forEach(function (op) {
      var id = op && typeof op.opId === "string" ? op.opId.toLowerCase() : "", st = liveOpState(op);
      var ch = op && op.chain === "base" ? "base" : "ethereum";
      if (/^0x[0-9a-f]{64}$/.test(id) && st) { by[id] = st; chainOf[id] = ch; }
      var n = op && op.block ? op.block.number : null;
      if (typeof n === "number" && isFinite(n) && n > 0 && (!blk[ch] || n > blk[ch])) blk[ch] = Math.floor(n);
    });
    var updated = 0;
    $$("[data-ops]").forEach(function (b) {
      var ids = (b.getAttribute("data-ops") || "").toLowerCase().split(/\s+/).filter(Boolean);
      var sts = ids.map(function (i) { return by[i]; });
      if (!sts.length || sts.some(function (s) { return !s; })) return;     // every operation must have been re-read
      var before = b.getAttribute("data-opstate"), st = sts.every(function (s) { return s === sts[0]; }) ? sts[0] : "mixed";
      setOpState(b, st);
      updated++;
      var banner = b.closest(".poststatus"), clause = banner && $(".ps-clause", banner), bch = chainOf[ids[0]], bb = blk[bch];
      if (banner && st !== before) {
        OP_STATES.forEach(function (c) { banner.classList.toggle(c, c === st); });
        if (clause) clause.textContent = "(live re-check" + (bb ? " at " + (bch === "base" ? "Base " : "") + "block " + blkFmt(bb) : "") + ": " + OP_LABEL[st]
          + "; the finalized-block reading below is superseded)";
      }
    });
    if (updated) radarCounts();
    var any = !!(blk.ethereum || blk.base);
    if (updated && any) {
      $$("[data-live-line]").forEach(function (n) {
        n.textContent = "Live re-check at the latest " + blkLine(blk) + " via " + (viaSource || "the free /v1/briefs/live-timelocks") + ".";
      });
    }
    return any ? blk : null;
  }
  // Radar header counts follow the badges: executed operations are never counted as queued (re-derived after a live re-check).
  // M4: radar header counts follow the rows (one per radar.json item, by state). N5 (v4.3): executed rows are counted by their
  // operations so the line never reads as a total: "1 ready · 1 pending · Executed (2 ops)" (same text as build_site.radar_counts_text)
  var RADAR_ORDER = ["ready", "pending", "mixed", "unknown", "executed"];
  var RADAR_WORD = { ready: "window open", pending: "waiting", mixed: "mixed", unknown: "cancelled or unknown", executed: "executed" };
  function opsWord(n) { return n + (n === 1 ? " op" : " ops"); }
  function radarPart(s, rows, ops) {
    if (s === "executed") return "Executed (" + opsWord(ops) + ")";
    return rows + " " + RADAR_WORD[s] + (ops !== rows ? " (" + opsWord(ops) + ")" : "");
  }
  function radarCounts() {
    var out = $("[data-radar-counts]"); if (!out) return;
    var by = {}, ops = {};
    $$("#radar tr[data-radar-row]").forEach(function (tr) {
      var b = $("[data-ops]", tr), n = b ? (b.getAttribute("data-ops") || "").split(/\s+/).filter(Boolean).length : 0;
      var st = b ? b.getAttribute("data-opstate") : tr.getAttribute("data-radar-row");
      if (!RADAR_WORD[st]) st = "unknown";
      tr.setAttribute("data-radar-row", st); tr.classList.toggle("is-executed", st === "executed");
      by[st] = (by[st] || 0) + 1; ops[st] = (ops[st] || 0) + n;
    });
    out.textContent = RADAR_ORDER.filter(function (s) { return by[s]; }).map(function (s) { return radarPart(s, by[s], ops[s]); }).join(" · ");
    // the home radar strip repeats the same counts, so it follows every re-label (visitor clock, live re-check)
    $$("[data-radar-counts-mirror]").forEach(function (m) { m.textContent = out.textContent; });
  }
  // Item 6: a row still Waiting in the pinned snapshot turns Window open once its ETA has passed on the visitor's clock (no network);
  // the live re-check below then confirms Executed / Window open from the chain.
  function radarClockPass() {
    var now = Date.now() / 1000, changed = 0;
    $$("[data-opstate=\"pending\"][data-ops]").forEach(function (b) {
      var row = b.closest("tr, li, article, .poststatus") || b.parentNode, cd = row ? $(".countdown[data-eta]", row) : null;
      var eta = cd ? parseInt(cd.getAttribute("data-eta"), 10) : 0;
      if (eta > 1 && eta <= now) { b.textContent = OP_LABEL.ready; OP_STATES.forEach(function (c) { b.classList.toggle(c, c === "ready"); }); b.setAttribute("data-opstate", "ready"); changed++; }
    });
    if (changed) radarCounts();
  }
  function radarMulticallFallback() {
    var trs = $$("#radar tr[data-timelock]");
    if (!trs.length) return Promise.resolve(null);
    var byChain = {};
    trs.forEach(function (tr) {
      var ch = tr.getAttribute("data-chain") === "base" ? "base" : "ethereum";
      var tl = tr.getAttribute("data-timelock") || "", kind = tr.getAttribute("data-tl-kind") || "oz";
      var etas = (tr.getAttribute("data-op-etas") || "").split(",").map(function (x) { return parseInt(x, 10) || 0; });
      var b = $("[data-ops]", tr);
      if (!ADDR_RE.test(tl) || !b) return;
      var ids = (b.getAttribute("data-ops") || "").toLowerCase().split(/\s+/).filter(function (x) { return /^0x[0-9a-f]{64}$/.test(x); });
      if (!byChain[ch]) byChain[ch] = [];
      ids.forEach(function (opId, idx) {
        byChain[ch].push({ timelock: tl, kind: kind, opId: opId, eta: etas[idx] || 0 });
      });
    });
    var chains = Object.keys(byChain);
    if (!chains.length) return Promise.resolve(null);
    return Promise.all(chains.map(function (ch) {
      var list = byChain[ch];
      return rpcCall(ch, "eth_getBlockByNumber", ["latest", false]).then(function (blkRes) {
        var blkObj = blkRes && blkRes.result;
        if (!blkObj || typeof blkObj.number !== "string") return [];
        var bHex = blkObj.number, bNum = parseInt(bHex, 16), bTs = parseInt(blkObj.timestamp || "0x0", 16);
        if (!(bNum > 0)) return [];
        var calls = [], meta = [];
        list.forEach(function (item) {
          var arg = item.opId.slice(2);
          if (item.kind === "compound") {
            meta.push({ item: item, idx: calls.length, kind: "compound" });
            calls.push({ target: item.timelock, allowFailure: true, callData: "0xf2b06537" + arg });
          } else {
            meta.push({ item: item, idx: calls.length, kind: "oz" });
            calls.push({ target: item.timelock, allowFailure: true, callData: "0x2ab0f529" + arg });
            calls.push({ target: item.timelock, allowFailure: true, callData: "0x584b153e" + arg });
            calls.push({ target: item.timelock, allowFailure: true, callData: "0xd45c4435" + arg });
          }
        });
        return rpcCall(ch, "eth_call", [{ to: MULTICALL3_ADDR, data: encodeAggregate3(calls) }, bHex]).then(function (mcRes) {
          var dec = decodeAggregate3(mcRes && mcRes.result);
          if (!dec || dec.length !== calls.length) return [];
          var out = [];
          meta.forEach(function (m) {
            var live = null;
            if (m.kind === "compound") {
              var rQ = dec[m.idx];
              if (rQ && rQ.success && rQ.returnData.length >= 66) {
                var queued = !/^0+$/.test(rQ.returnData.slice(-64));
                var eta = m.item.eta;
                if (queued) {
                  var rdy = eta > 0 && bTs >= eta && bTs <= eta + 1209600;
                  live = { status: rdy ? "ready" : "pending", isOperationPending: true, isOperationDone: false };
                } else {
                  live = eta > 0 && bTs >= eta ? { status: "done", isOperationDone: true } : { status: "unset", isOperationPending: false, isOperationDone: false };
                }
              }
            } else {
              var rD = dec[m.idx], rP = dec[m.idx + 1], rT = dec[m.idx + 2];
              if (rD && rD.success && rP && rP.success && rD.returnData.length >= 66 && rP.returnData.length >= 66) {
                var isDone = !/^0+$/.test(rD.returnData.slice(-64));
                var isPend = !/^0+$/.test(rP.returnData.slice(-64));
                var ts = rT && rT.success && rT.returnData.length >= 66 ? parseInt(rT.returnData.slice(-64), 16) : 0;
                if (isDone) live = { status: "done", isOperationDone: true };
                else if (isPend) live = { status: ts > 1 && bTs >= ts ? "ready" : "pending", isOperationPending: true, isOperationDone: false };
                else live = { status: "unset", isOperationPending: false, isOperationDone: false };
              }
            }
            if (live) out.push({ opId: m.item.opId, chain: ch, live: live, block: { number: bNum } });
          });
          return out;
        });
      });
    })).then(function (arrs) {
      var allOps = [];
      arrs.forEach(function (a) { a.forEach(function (x) { allOps.push(x); }); });
      return allOps.length ? { operations: allOps } : null;
    }).catch(function () { return null; });
  }
  function initLiveTimelocks() {
    radarClockPass();
    var host = $("[data-live-timelocks]");
    if (!host || typeof fetch !== "function" || !$("[data-ops]")) { liveSettled(false, null); return; }
    var url = host.getAttribute("data-live-timelocks") || "";
    if (!LIVE_TL_RE.test(url)) { liveSettled(false, null); return; }
    $$("[data-live-status-text]").forEach(function (n) { n.textContent = "Checking live chain state…"; });
    $$("[data-live-status] .spinner").forEach(function (n) { n.hidden = false; });
    var ctl = typeof AbortController === "function" ? new AbortController() : null;
    var done = false, guard = setTimeout(function () {
      if (done) return;
      done = true; LIVE_FAILED = true;
      if (ctl) { try { ctl.abort(); } catch (e) { /* already settled */ } }
      liveSettled(false, null); freshness();
    }, 9000);
    function settle(ok, blk) { if (done) return; done = true; clearTimeout(guard); liveSettled(ok, blk); freshness(); }
    function tryBrowserMulticall() {
      radarMulticallFallback().then(function (mc) {
        if (done) return;
        if (mc && Array.isArray(mc.operations) && mc.operations.length) {
          var blk = applyLiveTimelocks(mc, "Multicall3 RPC in your browser");
          LIVE_OK_AT = Math.floor(Date.now() / 1000); LIVE_FAILED = false; settle(true, blk);
        } else { LIVE_FAILED = true; settle(false, null); }
      });
    }
    var init = { cache: "no-store", headers: { Accept: "application/json" } };
    if (ctl) init.signal = ctl.signal;
    fetch(url, init)
      .then(function (r) { if (done) return null; return r && r.status === 200 ? r.json() : null; })
      .then(function (j) {
        if (done) return;   // the fallback already showed the pinned snapshot: a late payload never changes a badge
        if (j && typeof j === "object" && Array.isArray(j.operations)) {
          var blk = applyLiveTimelocks(j); LIVE_OK_AT = Math.floor(Date.now() / 1000); LIVE_FAILED = false; settle(true, blk);
        } else { tryBrowserMulticall(); }
      }, function () { tryBrowserMulticall(); /* Worker unreachable: try direct Multicall3 RPC, else keep static state */ })
      .catch(function () { tryBrowserMulticall(); });
  }
  // V01: the hero form drives the full #pf-form checker (same validation, timeout and states) and scrolls to the result
  // /for-protocols/: live badge preview + copyable Markdown / HTML for the selected protocol (attributes and textContent only)
  function initBadgeWidget() {
    var w = $("[data-badge-widget]"); if (!w) return;
    var sel = $("[data-bw-select]", w), img = $("[data-bw-img]", w), base = w.getAttribute("data-base") || "https://pacta.wtf";
    if (!sel || !img) return;
    sel.addEventListener("change", function () {
      var slug = String(sel.value || ""); if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(slug)) return;
      var name = sel.options && sel.selectedIndex >= 0 && sel.options[sel.selectedIndex] ? sel.options[sel.selectedIndex].textContent : slug;
      img.setAttribute("src", "../badges/" + slug + ".svg");
      var pres = $$(".term pre", w);
      if (pres[0]) pres[0].textContent = "[![Pacta Control Plane](" + base + "/badges/" + slug + ".svg)](" + base + "/protocols/" + slug + "/)";
      if (pres[1]) pres[1].textContent = '<a href="' + base + "/protocols/" + slug + '/"><img src="' + base + "/badges/" + slug + '.svg" alt="Pacta Control Plane: ' + name + '" height="20"></a>';
    });
  }
  // ---- Website Edge v3: protocol scorecards (#scorecards) ------------------------------------------------------------------
  var SC_STATE = { g: "Strong", b: "Moderate", a: "Weak", n: "Not determined", u: "Uncompared" };
  var SC_GRADE = { delta: "Delta", recent_change: "Changed recently", docs_updated: "Docs updated", unresolved: "Unresolved", protective: "Protective", aligned: "Aligned", observed: "Observed" };
  var SC_VARIANT = { delta: "warning", recent_change: "info", docs_updated: "outline", unresolved: "outline", protective: "info", aligned: "neutral", observed: "outline" };
  var SC_LETTER = { g: "S", b: "M", a: "W", n: "—", u: "—" };
  var SC_RADIUS = { g: 1, b: 0.78, a: 0.56, n: 1, u: 1 };
  var SC_CHAIN = { ethereum: "Ethereum", base: "Base" };
  var SVG_NS = "http://www.w3.org/2000/svg";
  // the same geometry as tools/scorecard.py rosette_svg(): five 72-degree slices clockwise from 12 o'clock
  // the same geometry as tools/scorecard.py rosette_svg(): five 72-degree slices clockwise from 12 o'clock inside a hairline ring;
  // slice length is the colour-independent cue (strong 100 %, moderate 78 %, weak 56 %, hollow full slice when not determined)
  function rosette(fs, size, name, interactive) {
    if (typeof document.createElementNS !== "function") return null;
    var svg = document.createElementNS(SVG_NS, "svg"), c = size / 2, r = size / 2 - 1.5;
    svg.setAttribute("class", "rosette" + (interactive ? " rosette-i" : "")); svg.setAttribute("width", String(size)); svg.setAttribute("height", String(size));
    svg.setAttribute("viewBox", "0 0 " + size + " " + size); svg.setAttribute("role", "img");
    if (interactive) {   // one keyboard stop (>= 24 px) whose Tooltip lists the five factors; slices show their own on hover
      svg.setAttribute("tabindex", "0");
      svg.setAttribute("data-tip", fs.map(function (f) { return String(f.label) + ": " + SC_STATE[/^[gbanu]$/.test(f.state) ? f.state : "n"]; }).join("\n"));
    }
    svg.setAttribute("aria-label", (name ? name + " control-strength graphic: " : "Control-strength graphic: ")
      + fs.map(function (f) { return f.label + " " + String(SC_STATE[f.state] || "").toLowerCase(); }).join("; "));
    var ring = document.createElementNS(SVG_NS, "circle");
    ring.setAttribute("class", "r-ring"); ring.setAttribute("cx", c.toFixed(1)); ring.setAttribute("cy", c.toFixed(1)); ring.setAttribute("r", r.toFixed(1));
    svg.appendChild(ring);
    fs.forEach(function (f, i) {
      var st = /^[gbanu]$/.test(f.state) ? f.state : "n", rr = r * SC_RADIUS[st];
      var a0 = (-90 + 72 * i + 1.5) * Math.PI / 180, a1 = (-90 + 72 * (i + 1) - 1.5) * Math.PI / 180;
      var p = document.createElementNS(SVG_NS, "path"), lbl = String(f.label) + ": " + SC_STATE[st];
      p.setAttribute("class", "r-" + st);
      p.setAttribute("d", "M" + c.toFixed(1) + " " + c.toFixed(1) + "L" + (c + rr * Math.cos(a0)).toFixed(1) + " " + (c + rr * Math.sin(a0)).toFixed(1)
        + "A" + rr.toFixed(1) + " " + rr.toFixed(1) + " 0 0 1 " + (c + rr * Math.cos(a1)).toFixed(1) + " " + (c + rr * Math.sin(a1)).toFixed(1) + "Z");
      if (interactive) p.setAttribute("data-tip", lbl);
      if (interactive) { var t = document.createElementNS(SVG_NS, "title"); t.textContent = lbl; p.appendChild(t); }
      svg.appendChild(p);
    });
    return svg;
  }
  function gradePill(card) {
    var g = SC_GRADE[card.grade] ? card.grade : "observed";
    var w = el("span", {}, [el("span", { "class": "grade g-" + g, "data-slot": "badge", "data-variant": SC_VARIANT[g], text: SC_GRADE[g] })]);
    if (card.subPill) w.appendChild(el("span", { "class": "grade-sub", text: String(card.subPill) }));
    else if (card.reconciled) w.appendChild(el("span", { "class": "grade-sub", text: "Reconciled" }));
    return w;
  }
  function factorList(card) {
    var dl = el("dl", { "class": "factors" });
    (card.factors || []).forEach(function (f) {
      var st = /^[gbanu]$/.test(f.state) ? f.state : "n";
      var dd = el("dd", {}, [el("b", { text: SC_STATE[st] }), " · " + String(f.value || "")]);
      // a human caption (surface, chain, block) when the build supplies one; never a raw internal record id as visible prose
      if (f.evidenceCaption) dd.appendChild(el("small", { "class": "ev", "data-record-id": String(f.evidenceRecordId || ""), text: "Evidence: " + String(f.evidenceCaption) }));
      else if (f.evidence) dd.appendChild(el("small", { "class": "ev", text: "Evidence: " + String(f.evidence) }));
      dl.appendChild(el("div", { "data-factor": String(f.key), "data-state": st }, [
        el("dt", {}, [el("span", { "class": "fdot r-" + st, "aria-hidden": "true", text: SC_LETTER[st] }), String(f.label)]), dd]));
    });
    return dl;
  }
  // a drawer's live RPC re-read of the protocol's lead record, pinned to a fresh eth_blockNumber (same rules as the inspector)
  function scLive(box) {
    if (!box || box.getAttribute("data-live-ready")) return;
    box.setAttribute("data-live-ready", "1");
    var ch = box.getAttribute("data-probe-chain") === "base" ? "base" : "ethereum", target = box.getAttribute("data-probe-target") || "";
    var slot = box.getAttribute("data-probe-kind") === "eth_getStorageAt", sos = box.getAttribute("data-probe-sos") || "";
    var data = box.getAttribute("data-probe-data") || sos, sig = box.getAttribute("data-probe-sig") || "call";
    if (!ADDR_RE.test(target)) return;
    box.appendChild(liveVerifyBtn("Verify live on RPC", function () {
      return liveBlock(ch).then(function (b) {
        var call = slot ? rpcCall(ch, "eth_getStorageAt", [target, sos, b.hex]) : rpcCall(ch, "eth_call", [{ to: target, data: data }, b.hex]);
        return call.then(function (x) {
          return ["Live at block #" + b.n + " (" + b.hex + "): " + (slot ? "slot " + sos : sig), "Raw: " + String(x.result),
            "Decoded: " + decodeWord(x.result), hosts(b, x) + " · " + (b.ms + x.ms) + " ms"];
        });
      });
    }));
  }
  function fmtTvlUsd(v) {
    if (typeof v !== "number" || !isFinite(v) || v <= 0) return "";
    if (v >= 1e9) return "$" + (v < 10e9 ? (v / 1e9).toFixed(2) : (v / 1e9).toFixed(1)) + "B TVL";
    if (v >= 1e6) return "$" + (v < 100e6 ? (v / 1e6).toFixed(1) : Math.round(v / 1e6).toLocaleString("en-US")) + "M TVL";
    if (v >= 1e3) return "$" + Math.round(v / 1e3).toLocaleString("en-US") + "K TVL";
    return "$" + Math.round(v).toLocaleString("en-US") + " TVL";
  }
  var SC_RANK = { delta: 0, protective: 1, aligned: 2, observed: 3 };
  function scRows(card, prefix, ident) {
    var nets = (card.chains || []).map(function (c) { return SC_CHAIN[c] || c; }).join(" · ");
    var tvlVal = typeof card.tvlUsd === "number" && card.tvlUsd > 0 ? Math.round(card.tvlUsd) : -1;
    var tvlTxt = fmtTvlUsd(tvlVal);
    var subMeta = tvlTxt ? nets + " · " + tvlTxt : nets;
    var slug = String(card.slug), did = "sc-d-" + slug, pre = /^(\.\.\/)*$/.test(prefix || "") ? (prefix || "") : "";
    var tog = el("button", { "class": "sc-toggle", type: "button", "aria-expanded": "false", "aria-controls": did, text: String(card.name) });
    var idn = ident && own(ident, slug) ? ident[slug] : null;   // B8: the server's identity (icon, ticker) for the same cell
    var pidKids = [el("img", { "class": "pid-logo", src: idn ? pre + String(idn[0]) : protoIconSrc(slug), alt: "", width: "22", height: "22",
      loading: "lazy", decoding: "async" }), tog];
    if (idn && idn[1]) pidKids.push(el("span", { "class": "pid-tk mono", text: String(idn[1]) }));
    var ros = rosette(card.factors || [], 32, card.name, false);
    var eas = card.easAttested !== false;
    var row = el("tr", { "class": "sc-row", "data-slug": slug, "data-name": String(card.name || "").toLowerCase(),
      "data-grade": String(card.grade), "data-tvl": String(tvlVal), "data-eas": eas ? "1" : "0",
      "data-baskets": (card.baskets || []).join(" "), "data-search": String(card.search || "") }, [
      el("td", {}, [el("span", { "class": "pid" }, pidKids), el("span", { "class": "sc-chain", text: subMeta })]), el("td", {}, [gradePill(card)]),
      el("td", {}, ros ? [ros] : [String(SC_GRADE[card.grade] || "")]), el("td", { "class": "sc-find", text: String(card.summary_short || card.finding || "") }),
      el("td", { "class": "sc-chev" }, [el("span", { "class": "chev", "aria-hidden": "true" }, [svgIcon("m6 9 6 6 6-6")])])]);
    var p = card.probe || {}, n = card.records;
    var noun = eas ? (n === 1 ? "attested check" : "attested checks") : (n === 1 ? "block-pinned check" : "block-pinned checks");
    var live = el("div", { "class": "sc-live", "data-probe-chain": String(p.chain || ""), "data-probe-target": String(p.target_contract || ""),
      "data-probe-kind": String(p.check_type || ""), "data-probe-sos": String(p.selector_or_slot || ""), "data-probe-data": String(p.repro_calldata || ""),
      "data-probe-sig": String(p.call_signature || "") });
    var big = rosette(card.factors || [], 72, card.name, true);
    var dr = el("div", { "class": "sc-dr" }, [
      el("div", { "class": "sc-ros" }, [big, el("span", { "class": "sc-meta", text: "Hover or focus a slice" })]),
      el("div", {}, [scEvidence(card), factorList(card)]),
      el("p", { "class": "sc-meta", text: (eas ? "Base EAS attested" : "Observed, not EAS-attested") + " · " + n + " " + noun + " · pinned block #" + num(card.pinnedBlock) }),
      live]);
    if (p.target_contract) dr.appendChild(term(castCmd(p), "Reproduce on any archive node", "Copy the cast reproduction for " + String(card.name)));
    dr.appendChild(el("p", { "class": "links" }, [arrowLink({ href: pre + "protocols/" + slug + "/" }, "Full scorecard for " + String(card.name))]));
    var drawer = el("tr", { "class": "sc-drawer", id: did, hidden: "" }, [el("td", { colspan: "5" }, [dr])]);
    return [row, drawer];
  }
  function initScorecards() {
    var root = $("#scorecards"); if (!root) return;
    var body = $("[data-sc-body]", root), q = $("#sc-q", root), qclr = $("[data-sc-qclear]", root), bsel = $("[data-sc-basket]", root);
    var empty = $("[data-sc-empty]", root), more = $("[data-sc-all]", root);
    if (!body) return;
    var prefix = body.getAttribute("data-prefix") || "", filt = "all", bkt = "all", easOnly = false, sortMode = "tvl", hydrated = body.hasAttribute("data-full"), loading = null;
    function rows() { return $$("tr.sc-row", body); }
    function drawerOf(r) { return $("#" + "sc-d-" + r.getAttribute("data-slug")); }
    function setOpen(r, open) {
      var d = drawerOf(r), t = $(".sc-toggle", r); if (!d) return;
      d.hidden = !open; r.classList.toggle("open", open);
      if (t) t.setAttribute("aria-expanded", String(open));
      if (open) scLive($(".sc-live", d));
    }
    function closeAll() { rows().forEach(function (r) { setOpen(r, false); }); }
    function sortDomRows() {
      var rs = rows().slice();
      rs.sort(function (a, b) {
        var na = a.getAttribute("data-name") || "", nb = b.getAttribute("data-name") || "";
        if (sortMode === "az") return na < nb ? -1 : na > nb ? 1 : 0;
        var ga = SC_RANK[a.getAttribute("data-grade")] !== undefined ? SC_RANK[a.getAttribute("data-grade")] : 9;
        var gb = SC_RANK[b.getAttribute("data-grade")] !== undefined ? SC_RANK[b.getAttribute("data-grade")] : 9;
        if (ga !== gb) return ga - gb;
        var ta = parseInt(a.getAttribute("data-tvl") || "-1", 10), tb = parseInt(b.getAttribute("data-tvl") || "-1", 10);
        if (ta !== tb) return tb - ta;
        return na < nb ? -1 : na > nb ? 1 : 0;
      });
      rs.forEach(function (r) {
        var d = drawerOf(r);
        r.remove();
        body.appendChild(r);
        if (d) { d.remove(); body.appendChild(d); }
      });
    }
    function apply() {
      var t = q ? String(q.value || "").trim().toLowerCase() : "", shown = 0;
      rows().forEach(function (r) {
        var g = r.getAttribute("data-grade"), bs = (r.getAttribute("data-baskets") || "").split(" ");
        var easOk = !easOnly || r.getAttribute("data-eas") === "1";
        var ok = easOk && (filt === "all" || g === filt) && (bkt === "all" || bs.indexOf(bkt) >= 0) && (!t || (r.getAttribute("data-search") || "").indexOf(t) >= 0);
        r.hidden = !ok; if (ok) shown++;
        if (!ok) setOpen(r, false);
      });
      if (shown === 0) closeAll();   // F02: zero matches never leave a stale drawer open
      if (empty) empty.hidden = shown !== 0;
      if (qclr) qclr.hidden = !(q && q.value);
      return shown;
    }
    function hydrate() {
      if (hydrated) return Promise.resolve(true);
      if (loading) return loading;
      if (typeof fetch !== "function") return Promise.resolve(false);
      loading = fetch(body.getAttribute("data-src") || "api/v1/scorecards.json").then(function (res) { return res.json(); }).then(function (d) {
        var cards = d && Array.isArray(d.protocols) ? d.protocols.slice() : [];
        if (!cards.length) return false;
        cards.sort(function (a, b) {
          var ga = SC_RANK[a.grade] !== undefined ? SC_RANK[a.grade] : 9, gb = SC_RANK[b.grade] !== undefined ? SC_RANK[b.grade] : 9;
          if (ga !== gb) return ga - gb;
          var ta = typeof a.tvlUsd === "number" && a.tvlUsd > 0 ? a.tvlUsd : -1, tb = typeof b.tvlUsd === "number" && b.tvlUsd > 0 ? b.tvlUsd : -1;
          if (ta !== tb) return tb - ta;
          var na = String(a.name || "").toLowerCase(), nb = String(b.name || "").toLowerCase();
          return na < nb ? -1 : na > nb ? 1 : 0;
        });
        body.textContent = "";
        var ident = {};
        try { ident = JSON.parse(body.getAttribute("data-ident") || "{}") || {}; } catch (e) { ident = {}; }
        cards.forEach(function (c) { scRows(c, prefix, ident).forEach(function (n) { body.appendChild(n); }); });
        hydrated = true;
        if (more) more.hidden = true;
        return true;
      }).catch(function () { loading = null; return false; });
      return loading;
    }
    function then(fn) { return function () { var a = arguments; body.setAttribute("data-all", ""); hydrate().then(function () { fn.apply(null, a); }); }; }
    // U4: the whole row is the trigger (the name stays the focusable button); links inside the row keep their own behaviour
    body.addEventListener("click", function (ev) {
      var t = ev.target; if (!t || !t.closest) return;
      var r = t.closest("tr.sc-row"); if (!r || t.closest("a")) return;
      var d = drawerOf(r); if (!d) return;
      setOpen(r, d.hidden);
    });
    if (q) {
      q.addEventListener("focus", function () { hydrate(); });
      q.addEventListener("input", then(function () { apply(); }));
    }
    if (qclr) qclr.addEventListener("click", function () { if (q) { q.value = ""; q.focus(); } apply(); });
    if (bsel) bsel.addEventListener("change", then(function () { bkt = String(bsel.value || "all"); apply(); }));
    $$("[data-sc-f]", root).forEach(function (b) {
      b.addEventListener("click", then(function () {
        filt = b.getAttribute("data-sc-f") || "all";
        easOnly = false;
        $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        apply();
      }));
    });
    $$("[data-sc-sort]", root).forEach(function (b) {
      b.addEventListener("click", then(function () {
        var sm = b.getAttribute("data-sc-sort") || "tvl";
        $$("[data-sc-sort]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        if (sm === "gaps") {
          sortMode = "tvl"; filt = "delta"; easOnly = false;
          $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-f") === "delta")); });
        } else if (sm === "eas") {
          sortMode = "tvl"; filt = "all"; easOnly = true;
          $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-f") === "all")); });
        } else {
          sortMode = sm === "az" ? "az" : "tvl"; easOnly = false;
          if (filt === "delta" && sm === "tvl") {
            filt = "all";
            $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-f") === "all")); });
          }
        }
        sortDomRows();
        apply();
      }));
    });
    if (more) more.addEventListener("click", then(function () { apply(); }));
    // v4.7: /scorecards/?grade=delta|protective|aligned|observed&q=…&basket=… (closed enums; q is plain text, at most 80 chars)
    var qs = {};
    String(location.search || "").replace(/^\?/, "").split("&").forEach(function (kv) {
      var i = kv.indexOf("="); if (i > 0) { try { qs[kv.slice(0, i)] = decodeURIComponent(kv.slice(i + 1).replace(/\+/g, " ")); } catch (e) { /* malformed */ } }
    });
    var g0 = GRADE_WORD[qs.grade] ? qs.grade : null, b0 = null;
    if (bsel && typeof qs.basket === "string") $$("option", bsel).forEach(function (o) { var v = o.getAttribute("value"); if (v && v !== "all" && v === qs.basket) b0 = v; });
    var q0 = typeof qs.q === "string" ? qs.q.slice(0, 80) : "";
    if (g0 || b0 || q0) {
      then(function () {
        if (g0) { filt = g0; $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-f") === g0)); }); }
        if (b0) { bkt = b0; bsel.value = b0; }
        if (q0 && q) q.value = q0;
        apply();
      })();
    }
    var clr = empty && $("[data-sc-clear]", empty);
    if (clr) clr.addEventListener("click", function () {
      filt = "all"; bkt = "all"; easOnly = false; sortMode = "tvl"; if (q) q.value = ""; if (bsel) bsel.value = "all";
      $$("[data-sc-f]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-f") === "all")); });
      $$("[data-sc-sort]", root).forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-sc-sort") === "tvl")); });
      sortDomRows();
      apply();
    });
  }
  // hero receipt strip: the pinned, attested receipt renders instantly (text only); the live check runs through the checker
  // V6: the hero examples load their pinned receipt into the proof card (text and attributes only) and run the live check
  // N1 (v4.3): a "Try:" click also fills the checker (#pf-form chain + address, any previous error cleared) and submits it at
  // once, so the verdict-first result renders in #pf-out right under the form. One click = one live check.
  var pfSelectFromChip = null, pfSelectedMeta = null;
  function tryReceipt(b) {
    var form = $("#pf-form"), a = b.getAttribute("data-pf-address") || "";
    if (!form || !ADDR_RE.test(a)) return;
    var ch = $('select[name="chain"]', form), ad = $('input[name="address"]', form), err = $("#pf-addr-error");
    var cVal = b.getAttribute("data-pf-chain") === "base" ? "base" : "ethereum";
    if (ch) ch.value = cVal;
    if (ad) { ad.value = a; ad.setAttribute("value", a); ad.removeAttribute("aria-invalid"); }   // property + attribute: DOM snapshots agree
    if (err) { err.textContent = ""; err.hidden = true; }
    if (typeof pfSelectFromChip === "function") pfSelectFromChip(b, cVal, a);
    form.dispatchEvent(new Event("submit", { cancelable: true }));
    // P2-2 (v4.4): bring the form into view (scroll-margin-top clears the sticky top bar), so the filled address and the result
    // card right under it are seen together
    if (form.scrollIntoView) { try { form.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) { /* old browsers */ } }
  }
  function initReceipts() {
    var card = $("[data-proof-card]"), chips = $$("[data-receipt]");
    chips.forEach(function (b) {
      b.addEventListener("click", function () {
        chips.forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        tryReceipt(b);
        if (!card) return;
        var set = function (sel, v) { var n = $(sel, card); if (n) n.textContent = v; };
        set("[data-pc-name]", b.getAttribute("data-r-name") || "");
        set("[data-pc-docs]", b.getAttribute("data-r-docs") || "");
        set("[data-pc-chain]", b.getAttribute("data-r-chain") || "");
        set("[data-pc-block]", (b.getAttribute("data-r-net") || "") + " #" + num(b.getAttribute("data-r-block") || 0));
        var uid = b.getAttribute("data-r-uid") || "", u = $("[data-pc-uid]", card);
        if (u && /^0x[0-9a-fA-F]{64}$/.test(uid)) {
          if (u.tagName === "A") { u.setAttribute("href", "https://base.easscan.org/attestation/view/" + uid); u.setAttribute("title", uid); }
          u.textContent = short(uid, 10, 6);
        }
        var h = $("[data-pc-href]", card), href = b.getAttribute("data-r-href") || "";
        if (h && /^(\.\.\/)*protocols\/[a-z0-9-]+\/$/.test(href)) h.setAttribute("href", href);
      });
    });
  }
  function initHeroCheck() {
    var f = $("[data-hero-check]"), pf = $("#pf-form"); if (!f || !pf) return;
    f.addEventListener("submit", function (ev) {
      ev.preventDefault();
      var ch = $('select[name="chain"]', pf), ad = $('input[name="address"]', pf);
      if (ch) ch.value = ($('select[name="chain"]', f) || {}).value === "base" ? "base" : "ethereum";
      if (ad) ad.value = String(($('input[name="address"]', f) || {}).value || "").trim();
      pf.dispatchEvent(new Event("submit", { cancelable: true }));
      var hin = $('input[name="address"]', f);   // the checker validates synchronously: mirror its aria state onto the hero input
      if (hin && ad && ad.getAttribute("aria-invalid") === "true") { hin.setAttribute("aria-invalid", "true"); hin.setAttribute("aria-describedby", "pf-msg"); }
      else if (hin) { hin.removeAttribute("aria-invalid"); hin.removeAttribute("aria-describedby"); }
      var box = $(".pf"); if (box) { try { box.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) { /* old browsers */ } }
    });
  }
  function initRefresh() {
    $$("[data-radar-refresh]").forEach(function (b) { b.addEventListener("click", function () { initLiveTimelocks(); initAges(); }); });
  }

  // ---- first-party beacon hooks: b.js defines window.pactaBeacon (and applies DNT / https / redaction); without it
  //      nothing is sent. copy_mcp_url / copy_curl by what a copy button copies, copy_skill_md, primary CTAs. --------
  function initBeaconHooks() {
    document.addEventListener("click", function (ev) {
      var B = window.pactaBeacon, x = ev.target, c, a, q, t;
      if (typeof B !== "function" || !x || !x.closest) return;
      if ((c = x.closest(".copy"))) {
        q = c.getAttribute("data-copy");
        if (q === null) { t = c.closest(".term"); t = t && t.querySelector("pre"); q = t ? t.textContent : ""; }
        if (/\/mcp\b/.test(q)) B("copy_mcp_url"); else if (/^curl /.test(q)) B("copy_curl");
      } else if ((a = x.closest("a"))) {
        if (/SKILL\.md$/.test(a.getAttribute("href") || "")) B("copy_skill_md");
        else if (a.closest('a.primary,a[data-variant="default"],.memo-foot a,a[data-cta]')) B("cta_click");
      }
    }, true);
  }

  // ---- X Ads conversion measurement (pixel rjbqn): external queue in JS (0 'unsafe-inline' in script-src), host-gated
  //      so uwt.js loads ONLY on pacta.wtf and pacta.fractalneurons.com (staging / localhost keep window.__pactaTwqEvents
  //      in memory with zero network calls to X). Lead (tw-rjbqn-rjhie) dedupes once per page load; Purchase (tw-rjbqn-rjhif)
  //      fires only on non-canary, non-replay /v1/orders/verify 200 responses and dedupes orderId in browser storage.
  var X_PIXEL_ID = "rjbqn", X_LEAD_EVENT = "tw-rjbqn-rjhie", X_PURCHASE_EVENT = "tw-rjbqn-rjhif";
  var X_UWT_SRC = "https://static.ads-twitter.com/uwt.js", X_PURCHASE_KEY = "pacta-x-purchased";
  var xLeadSent = false, xPurchasedMem = {};
  function xIsProdHost() {
    var h = String((location && location.hostname) || "");
    return h === "pacta.wtf" || h === "pacta.fractalneurons.com";
  }
  function xCallTwq() {
    var a = Array.prototype.slice.call(arguments);
    if (typeof window.twq === "function") {
      var q = window.__pactaTwqEvents, n0 = Array.isArray(q) ? q.length : 0;
      window.twq.apply(window, a);
      if (Array.isArray(q) && q.length === n0) q.push(a);
    }
  }
  function initXPixel() {
    if (!Array.isArray(window.__pactaTwqEvents)) window.__pactaTwqEvents = [];
    if (!window.twq) {
      var s = function () {
        var a = Array.prototype.slice.call(arguments);
        window.__pactaTwqEvents.push(a);
        if (s.exe) s.exe.apply(s, a); else s.queue.push(a);
      };
      s.version = "1.1";
      s.queue = [];
      window.twq = s;
    }
    if ($("[data-nf]") || window.pactaRescued) return;
    xCallTwq("config", X_PIXEL_ID);
    if (xIsProdHost() && !isInternalQa() && !$('script[src="' + X_UWT_SRC + '"]')) {
      var sc = document.createElement("script");
      sc.async = true;
      sc.setAttribute("async", "");
      sc.setAttribute("src", X_UWT_SRC);
      var hd = document.head || $("head") || document.documentElement;
      if (hd) hd.appendChild(sc);
    }
  }
  function xTrackLead() {
    if (xLeadSent || isInternalQa()) return;
    xLeadSent = true;
    try { xCallTwq("event", X_LEAD_EVENT, {}); } catch (e) { /* ignore */ }
  }
  function xTrackPurchase(j, s, isReplay, txHash) {
    if (!j || j.internalCanary === true || j.qa_test === true || isReplay) return;
    var orderId = String(j.orderId || j.order_id || j.id || txHash || "").trim();
    if (!orderId || own(xPurchasedMem, orderId)) return;
    var seen = [];
    try {
      var raw = localStorage.getItem(X_PURCHASE_KEY);
      var parsed = raw ? JSON.parse(raw) : [];
      if (Array.isArray(parsed)) seen = parsed;
    } catch (e) { seen = []; }
    if (seen.indexOf(orderId) >= 0) return;
    xPurchasedMem[orderId] = 1;
    seen.push(orderId);
    if (seen.length > 50) seen = seen.slice(seen.length - 50);
    try { localStorage.setItem(X_PURCHASE_KEY, JSON.stringify(seen)); } catch (e) { /* storage disabled */ }
    try {
      xCallTwq("event", X_PURCHASE_EVENT, { value: Number(s.amount), currency: "USD", conversion_id: orderId });
    } catch (e) { /* ignore */ }
  }

  // ---- copy to clipboard (works on http(s) and file://) ---------------------------------------------
  function copyText(text) {
    function legacy() {
      return new Promise(function (resolve, reject) {
        var ta = el("textarea", { readonly: "", style: "position:fixed;top:-1000px;opacity:0" });
        ta.value = text; document.body.appendChild(ta); ta.select();
        try { document.execCommand("copy") ? resolve() : reject(); } catch (e) { reject(e); } finally { ta.remove(); }
      });
    }
    // the async Clipboard API can be refused (permissions, embedded contexts): fall back to the selection copy
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text).then(null, legacy);
    return legacy();
  }

  function flash(btn, ok) {
    var s = $("span", btn) || btn;
    if (!btn.hasAttribute("data-label")) btn.setAttribute("data-label", s.textContent);
    clearTimeout(btn._t);
    btn.classList.toggle("done", ok);
    s.textContent = ok ? "Copied" : "Press Ctrl+C";
    btn._t = setTimeout(function () { s.textContent = btn.getAttribute("data-label"); btn.classList.remove("done"); }, 1600);
  }
  function initCopy() {
    document.addEventListener("click", function (ev) {
      var b = ev.target && ev.target.closest ? ev.target.closest("[data-copy],[data-copy-from],[data-copy-term]") : null;
      if (!b) return;
      ev.preventDefault(); ev.stopPropagation();
      var src = b.hasAttribute("data-copy-term") ? $("pre", b.closest(".term")) : $("#" + b.getAttribute("data-copy-from"));
      var text = b.hasAttribute("data-copy") ? b.getAttribute("data-copy") : (src ? src.textContent : "");
      if (b.hasAttribute("data-copy-prefix")) text = b.getAttribute("data-copy-prefix") + "\n" + text;   // e.g. "To: <address>" + the brief
      copyText(text).then(function () {
        flash(b, true);
        toast("Copied to clipboard");
        var st = $("#req-status"); if (st && b.closest("#req-form, .req-side")) st.textContent = "Copied. Paste it into an email to " + REQ_TO + " from any mail app.";
      }, function () { flash(b, false); toast("Copy failed: select the text and press Ctrl+C"); });
    });
  }

  // ---- data -------------------------------------------------------------------------------------------
  var DATA = null, BYID = {};
  function loadData() {
    return fetch(document.documentElement.getAttribute("data-api") || "api/v1/index.json")
      .then(function (r) { return r.json(); })
      .then(function (d) { DATA = d; d.entries.forEach(function (e) { BYID[e.id] = e; }); return d; });
  }

  // ---- homepage hydration (V04): the static page ships a curated sample; the full record set comes from /api/v1/index.json on
  //      interaction (search, filter, basket, Show all, a #r- link, Open in inspector). Mirrors index_rows() in build_site.py.
  var EXPL = { ethereum: ["Etherscan", "https://etherscan.io"], base: ["Basescan", "https://basescan.org"] };
  var CHAIN_LABEL = { ethereum: "Ethereum Mainnet (chain id 1)", base: "Base Mainnet (chain id 8453)" };
  function ensureData() { return DATA ? Promise.resolve(DATA) : loadData(); }
  function sortedEntries(d) {
    return d.entries.map(function (e, i) { return [e, i]; }).sort(function (x, y) {
      var a = x[0], b = y[0], pa = a.protocol.toLowerCase(), pb = b.protocol.toLowerCase();
      return (b.sprint - a.sprint) || (pa < pb ? -1 : pa > pb ? 1 : 0) || (x[1] - y[1]);
    }).map(function (x) { return x[0]; });
  }
  function explorerLink(e) {
    var x = EXPL[chainOf(e)];
    return arrowLink({ href: x[1] + "/block/" + e.block_number, target: "_blank", rel: "noopener" }, x[0], "up-right");
  }
  function searchText(e) {
    return ["protocol", "category", "surface", "target_contract", "target_label", "onchain_observed", "classification", "sprint"]
      .map(function (k) { return e[k] === undefined || e[k] === null ? "" : String(e[k]); }).join(" ").toLowerCase();
  }
  function indexRow(e) {
    var proofEl = e.base_eas_uid ? arrowLink({ href: "https://base.easscan.org/attestation/view/" + e.base_eas_uid, target: "_blank", rel: "noopener" }, "EAS", "up-right")
      : el("span", { "class": "muted", text: "Hash-pinned" });
    var row = el("tr", { "data-class": e.classification, "class": "rec", "data-id": e.id, "data-search": searchText(e) }, [
      el("td", {}, [el("b", { "class": "ell", text: e.protocol }), el("span", { "class": "sub ell", text: e.category })]),
      el("td", { "class": "hide-s" }, [el("span", { "class": "ell", text: e.target_label }), el("span", { "class": "sub" }, hexref(e.target_contract))]),
      el("td", {}, [recBadge(e)]),
      el("td", { "class": "hide-m num nowrap" }, [secs(e.observed_delay_seconds) + " ", el("span", { "class": "muted", text: "/ " + secs(e.documented_delay_seconds) })]),
      el("td", { "class": "hide-m nowrap" }, [el("span", { "class": "num", text: "S" + e.sprint + " · #" + num(e.block_number) }), el("span", { "class": "sub" }, [proofEl])]),
      el("td", { "class": "x" }, [el("a", { "class": "inspect-btn", href: "#r-" + e.id, "aria-expanded": "false", "aria-controls": "r-" + e.id, text: "Details" })])]);
    var repo = "https://github.com/Fractal-Neurons/pacta/blob/main/";
    var kv = el("dl", { "class": "kv" }, [
      el("dt", { text: "Pinned block" }), el("dd", {}, [CHAIN_LABEL[chainOf(e)] + " ", el("span", { "class": "num", text: "#" + num(e.block_number) }), " · ", explorerLink(e), " · "].concat(hexref(e.block_hash, 8, 6))),
      el("dt", { text: "Delay" }), el("dd", {}, [delayCmp(e)]),
      el("dt", { text: "Summary" }), el("dd", {}, [arrowLink({ href: repo + e.summary_doc, target: "_blank", rel: "noopener" }, "Attested summary document", "up-right")]),
      el("dt", { text: "SHA-256" }), el("dd", {}, hexref(e.summary_sha256, 10, 6)),
      el("dt", { text: "Proof" }), el("dd", {}, [proof(e)])]);
    var drawer = el("tr", { "class": "drawer", id: "r-" + e.id }, [el("td", { colspan: "6" }, [el("div", { "class": "drawer-in" }, [
      el("div", {}, [el("p", { "class": "drawer-title", text: e.surface }), el("span", { "class": "label", text: "On-chain observation" }),
        el("p", { "class": "obs-text" }, prose(e.onchain_observed || "")),
        el("p", { "class": "obs-text" }, [el("span", { "class": "label", text: "Documented" }), el("br")].concat(prose(e.documented_reference || ""))),
        el("p", { "class": "obs-text" }, [el("button", { "class": "linkish", type: "button", "data-inspect": e.id, text: "Open in inspector ↑" })])]),
      el("div", {}, [kv, term(castCmd(e))])])])]);
    return [row, drawer];
  }

  // ---- record rendering (mirrors sheet() in tools/build_site.py) -------------------------------------
  var CLS = { parameter_delta: ["delta", "Parameter delta"], protective_delta: ["protect", "Protective delta"], aligned_baseline: ["", "Aligned baseline"] };
  function badge(c, text, extra) { var k = CLS[c] || CLS.aligned_baseline; return el("span", { "class": ("badge " + (extra || k[0])).trim(), text: text || k[1] }); }
  // a record of a protocol whose comparison does not establish a documented breach (index.json scorecard_status_overrides, from
  // tools/scorecard_corrections.json) shows the neutral status, never "Parameter delta"
  function recBadge(e) {
    var o = DATA && DATA.scorecard_status_overrides ? DATA.scorecard_status_overrides[e.id] : null;
    return o && (o.status === "unresolved" || o.status === "recent_change" || o.status === "docs_updated")
      ? el("span", { "class": "badge " + o.status, text: String(o.label || (o.status === "unresolved" ? "Unresolved" : "Changed recently")) })
      : badge(e.classification);
  }
  // Exact compact duration: 0 -> 0s, 1 -> 1s, 86400 -> 1d, 129600 -> 1d 12h (mirrors secs() in tools/build_site.py)
  function secs(s) {
    if (s === null || s === undefined) return "—";
    var parts = []; s = Math.floor(s);
    [["d", 86400], ["h", 3600], ["m", 60], ["s", 1]].forEach(function (u) {
      if (s >= u[1]) { parts.push(Math.floor(s / u[1]) + u[0]); s = s % u[1]; }
    });
    return parts.join(" ") || "0s";
  }
  function copyBtn(v, label) {
    return el("button", { "class": "copy", "data-slot": "button", "data-variant": "ghost", "data-size": "sm", type: "button", "data-copy": v,
      "aria-label": "Copy " + String(v) }, [el("span", { text: label || "Copy" })]);
  }
  function hexref(v, a, b) { return [el("span", { "class": "addr", title: v, text: short(v, a || 6, b || 4) }), copyBtn(v)]; }
  function delayCmp(e) {
    var o = e.observed_delay_seconds, d = e.documented_delay_seconds;
    if ((o === null || o === undefined) && (d === null || d === undefined)) return el("span", { "class": "muted", text: "No timelock delay in this record" });
    var warn = o !== null && o !== undefined && d !== null && d !== undefined && o !== d;
    return el("span", { "class": "cmp" }, [
      el("span", { "class": "chip obs" + (warn ? " warn" : "") }, [el("i", { text: "Observed" }), el("b", { text: secs(o) })]),
      el("span", { "class": "vs", text: "vs" }),
      el("span", { "class": "chip" }, [el("i", { text: "Docs" }), el("b", { text: secs(d) })])]);
  }
  function multisig(text) {
    var seen = []; (text.match(/\b\d+-of-\d+\b/g) || []).forEach(function (x) { if (seen.indexOf(x) < 0) seen.push(x); });
    return seen.length ? seen.join(" · ") : null;
  }
  function proxyAdmin(text) {
    var m = text.match(/ProxyAdmin \((0x[0-9a-fA-F]{40})\)/) || text.match(/admin\(\) = [A-Za-z ]*\((0x[0-9a-fA-F]{40})\)/);
    return m ? m[1] : null;
  }
  // Runnable as-is: full signature + every argument (call_signature / call_args in /api/v1/index.json).
  // A record's chain (index.json records without one are Ethereum Mainnet); the RPC variable is never taken from the feed.
  function chainOf(e) { return e && e.chain === "base" ? "base" : "ethereum"; }
  function castCmd(e) {
    var rpc = '--rpc-url "' + (chainOf(e) === "base" ? "$BASE_RPC_URL" : "$ETH_RPC_URL") + '"';
    var first = e.check_type === "eth_getStorageAt"
      ? "cast storage " + e.target_contract + " \\\n  " + e.selector_or_slot + " \\\n  --block " + e.block_number + " " + rpc
      : "cast call " + e.target_contract + ' \\\n  "' + (e.call_signature || e.selector_or_slot) + '"' +
        (e.call_args && e.call_args.length ? " " + e.call_args.join(" ") : "") + " \\\n  --block " + e.block_number + " " + rpc;
    return first + "\ncast block " + e.block_number + " --field hash " + rpc + "\n# expect " + e.block_hash;
  }
  function term(cmd, title, what) {
    var b = el("button", { "class": "copy", "data-slot": "button", "data-variant": "ghost", "data-size": "sm", type: "button", "data-copy-term": "",
      "aria-label": what || ("Copy command: " + (title || "command")) }, [el("span", { text: "Copy" })]);
    return el("div", { "class": "term" }, [el("div", { "class": "term-h" }, [el("span", { text: title || "Reproduce on any archive node" }), b]),
      el("pre", { text: cmd })]);
  }
  function proof(e) {
    if (e.base_eas_uid) return arrowLink({ href: "https://base.easscan.org/attestation/view/" + e.base_eas_uid, target: "_blank", rel: "noopener" }, "Base EAS attestation " + short(e.base_eas_uid, 6, 4), "up-right");
    return el("span", { text: "Pending Base EAS batch attestation · pinned by block hash and summary SHA-256" });
  }
  // 32-byte hashes in prose are shortened with the full value in a tooltip (mirrors prose() in build_site.py)
  function prose(text) {
    var out = [], last = 0, re = /0x[0-9a-fA-F]{64}(?![0-9a-fA-F])/g, m;
    while ((m = re.exec(text))) {
      out.push(text.slice(last, m.index));
      out.push(el("span", { "class": "hx", title: m[0], text: short(m[0], 8, 6) }));
      last = m.index + m[0].length;
    }
    out.push(text.slice(last));
    return out;
  }
  // "What differs" (mirrors tools/control_diff.py for one record): Safe thresholds paired by k (then n), timelock delays compared;
  // a flagged record with no structured pair lists its surface with the first observed / documented sentence. Text only.
  function thresholds(t) {
    var out = [], re = /\b(\d{1,2})\s*-?\s*of\s*-?\s*(\d{1,2})\b/gi, m;
    while ((m = re.exec(t || ""))) { var k = +m[1], n = +m[2], key = k + "-of-" + n; if (k <= n && out.indexOf(key) < 0) out.push(key); }
    return out;
  }
  function fmtDelay(s) {
    if (typeof s !== "number") return null;
    if (s === 0) return "0 s (no delay)";
    var u = [["d", 86400], ["h", 3600], ["min", 60]];
    for (var i = 0; i < u.length; i++) if (s % u[i][1] === 0) return (s / u[i][1]) + " " + u[i][0];
    return s + " s";
  }
  // visible text of a quoted documentation excerpt: Markdown bold (**x**) and inline TeX ($5/9$) markers removed (mirrors build_site.plain)
  function plainText(t) {
    return String(t || "").replace(/\*\*([^*\n]+)\*\*|__([^_\n]+)__/g, function (m, a, b) { return a || b; })
      .replace(/\$([0-9][0-9\/.,+\- ]*)\$/g, "$1").replace(/\s*\(record\s+[a-z0-9_-]+\)/g, "");
  }
  function firstSentence(t) {
    t = plainText(t).replace(/\s+/g, " ").trim();
    // the first '.' or ';' followed by a space (or the end); a ';' inside parentheses never ends the sentence (mirrors control_diff.py)
    // ...and never inside an open quotation ('…' / "…"; an apostrophe inside a word is not a quote; mirrors control_diff.py)
    var Q = { "'": "'", '"': '"', "\u2018": "\u2019", "\u201c": "\u201d" };
    for (var i = 0, d = 0, q = null; i < t.length; i++) {
      var c = t.charAt(i), pv = i ? t.charAt(i - 1) : " ", nx = i + 1 < t.length ? t.charAt(i + 1) : " ";
      if (q) { if (c === Q[q] && !(c === "'" && /[A-Za-z0-9]/.test(nx))) q = null; continue; }
      if (Q[c] && !/[A-Za-z0-9]/.test(pv) && nx !== " ") { q = c; continue; }
      if (c === "(") d++; else if (c === ")") d--;
      if (i > 0 && (c === "." || (c === ";" && d <= 0)) && (i + 1 === t.length || t.charAt(i + 1) === " ")) { t = t.slice(0, i + 1); break; }
    }
    return t.length <= 220 ? t : t.slice(0, 219).replace(/\s+$/, "") + "…";
  }
  function whatDiffers(e) {
    if (e.classification !== "parameter_delta" && e.classification !== "protective_delta") return null;
    var changed = [], matched = [], paired = false, obs = thresholds(e.onchain_observed), doc = thresholds(e.documented_reference);
    doc.forEach(function (d) {
      // only a protective record lists a matching parameter as "matched" (mirrors tools/control_diff.py)
      if (obs.indexOf(d) >= 0) { if (e.classification === "protective_delta") matched.push([e.surface || e.target_label || "Safe threshold", d]); return; }
      var dk = d.split("-of-"), o = obs.filter(function (x) { return x.split("-of-")[0] === dk[0] && doc.indexOf(x) < 0; })[0]
        || obs.filter(function (x) { return x.split("-of-")[1] === dk[1] && doc.indexOf(x) < 0; })[0];
      if (o) { changed.push([e.surface || e.target_label || "Safe threshold", o, d]); paired = true; }
    });
    var od = fmtDelay(e.observed_delay_seconds), dd = fmtDelay(e.documented_delay_seconds);
    var dl = e.surface || e.target_label || "Timelock delay";   // the record's own scope, never reduced to the bare generic label
    if (od && dd) { if (e.observed_delay_seconds === e.documented_delay_seconds) { if (e.classification === "protective_delta") matched.push([dl, od]); } else { changed.push([dl, od, dd]); paired = true; } }
    if (!paired) changed.push([e.surface || e.id, firstSentence(e.onchain_observed), firstSentence(e.documented_reference)]);
    return { changed: changed, matched: matched };
  }
  function whatDiffersBox(e) {
    var wd = whatDiffers(e); if (!wd) return null;
    var co = DATA && DATA.scorecard_wording_overrides ? DATA.scorecard_wording_overrides[e.id] : null;
    if (co) {   // a declarative correction: its headline and pinned block lead, its scope follows; no generic per-parameter lines
      var cb = el("div", { "class": "whatdiffers" + (co.unresolved || co.docsUpdated ? " unresolved" : co.recentChange ? " recent_change" : ""), "data-what-differs": "" },
        [el("h2", { "class": "wd-h", text: co.unresolved ? "Verification scope" : co.docsUpdated ? "Docs updated" : co.recentChange ? "Changed recently" : "What differs" })]);
      if (co.headline) cb.appendChild(el("p", { "class": "wd-lead", "data-wd-headline": "" }, [el("strong", { text: String(co.headline) }), " ",
        el("span", { "class": "wd-block mono", text: "(#" + num(co.pinnedBlock) + ")" })]));
      if (co.scope) cb.appendChild(el("p", { "class": "wd-scope", "data-wd-scope": "", text: String(co.scope) }));
      if (wd.matched.length) {
        cb.appendChild(el("p", { "class": "wd-l", text: "Matched" }));
        var cm = el("ul", { "class": "wd-matched" });
        wd.matched.forEach(function (m) { cm.appendChild(el("li", { "data-wd-matched": "", text: m[0] + ": " + m[1] })); });
        cb.appendChild(cm);
      }
      return cb;
    }
    var box = el("div", { "class": "whatdiffers", "data-what-differs": "" }, [el("h2", { "class": "wd-h", text: "What differs" }),
      el("p", { "class": "wd-l", text: "Changed / discrepant" })]);
    var ul = el("ul", { "class": "wd-changed" });
    wd.changed.forEach(function (c) {
      ul.appendChild(el("li", { "data-wd-changed": "" }, [el("b", { text: c[0] }), ": ", el("span", { "class": "obs", text: c[1] }), " observed vs ",
        el("span", { "class": "doc", text: c[2] }), " documented"]));
    });
    box.appendChild(ul);
    if (wd.matched.length) {
      box.appendChild(el("p", { "class": "wd-l", text: "Matched" }));
      var um = el("ul", { "class": "wd-matched" });
      wd.matched.forEach(function (m) { um.appendChild(el("li", { "data-wd-matched": "", text: m[0] + ": " + m[1] })); });
      box.appendChild(um);
    }
    return box;
  }
  function renderSheet(e) {
    var panel = $("#insp-panel"); if (!panel || !e) return;
    var obs = e.onchain_observed || "", ms = multisig(obs), pa = proxyAdmin(obs);
    var repo = "https://github.com/Fractal-Neurons/pacta/blob/main/";
    var rows = [
      ["Category", [e.category]],
      ["Target contract", [e.target_label + " · "].concat(hexref(e.target_contract))],
      ["Timelock delay", [delayCmp(e)]]];
    if (ms) rows.push(["Safe quorum", [el("span", { "class": "mono", text: ms })]]);
    if (pa) rows.push(["EIP-1967 ProxyAdmin", hexref(pa)]);
    rows.push(["Pinned block", [chainOf(e) === "base" ? "Base " : "", el("span", { "class": "num", text: "#" + num(e.block_number) }), " ",
      badge(null, "Scanner-pinned (L1 finalized)", "final")]]);
    rows.push(["Canonical block hash", hexref(e.block_hash, 8, 6)]);
    rows.push(["Proof", [proof(e)]]);
    rows.push(["Summary", [arrowLink({ href: repo + e.summary_doc, target: "_blank", rel: "noopener" }, e.summary_doc.split("/").pop(), "up-right"), " · SHA-256 "].concat(hexref(e.summary_sha256, 8, 4))]);
    var dl = el("dl", { "class": "kv" });
    rows.forEach(function (r) { dl.appendChild(el("dt", { text: r[0] })); dl.appendChild(el("dd", {}, r[1])); });
    panel.textContent = "";
    panel.appendChild(el("div", { "class": "sheet-h" }, [el("h3", { text: e.protocol }), recBadge(e)]));
    panel.appendChild(el("p", { "class": "sheet-sub", text: e.surface }));
    var wdb = whatDiffersBox(e); if (wdb) panel.appendChild(wdb);
    panel.appendChild(dl);
    panel.appendChild(el("p", { "class": "obs-text" }, prose(obs)));
    panel.appendChild(term(castCmd(e)));
    panel.appendChild(el("p", { "class": "pf-section", text: "Pinned documentation comparison above; replay the same read live:" }));
    panel.appendChild(liveVerifyBtn("Verify live on RPC", function () {
      var ch = chainOf(e), slot = e.check_type === "eth_getStorageAt";
      return liveBlock(ch).then(function (b) {
        var call = slot ? rpcCall(ch, "eth_getStorageAt", [e.target_contract, e.selector_or_slot, b.hex])
          : rpcCall(ch, "eth_call", [{ to: e.target_contract, data: e.repro_calldata || e.selector_or_slot }, b.hex]);
        return call.then(function (x) {
          return ["Live at block #" + b.n + " (" + b.hex + "): " + (slot ? "slot " + e.selector_or_slot : (e.call_signature || "call")),
            "Raw: " + String(x.result), "Decoded: " + decodeWord(x.result), hosts(b, x) + " · " + (b.ms + x.ms) + " ms"];
        });
      });
    }));
  }

  // ---- inspector workbench ---------------------------------------------------------------------------
  function initInspector() {
    var list = $("#insp-list"); if (!list) return;
    var q = $("#insp-q"), count = $("#insp-count"), filt = "all", hydrated = false, bkt = "all";
    var bRules = {};
    $$("[data-insp-basket]").forEach(function (b) {
      var k = b.getAttribute("data-insp-basket"), rx = b.getAttribute("data-basket-re");
      try { bRules[k] = { re: rx ? new RegExp(rx, "i") : null, chain: b.getAttribute("data-basket-chain") }; } catch (e) { /* skip */ }
    });
    function inBasket(e) {
      if (bkt === "all") return true;
      var r = bRules[bkt]; if (!r || !e) return false;
      return !!((r.re && r.re.test(e.category || "")) || (r.chain && chainOf(e) === r.chain));
    }
    var links = $$("a[data-id]", list);
    function inspItem(e) {
      var dc = (CLS[e.classification] || CLS.aligned_baseline)[0];
      return el("li", {}, [el("a", { href: "#r-" + e.id, "data-id": e.id, "data-class": e.classification }, [
        el("span", { "class": ("dot " + dc).trim() }), el("span", { "class": "p", text: e.protocol }), el("span", { "class": "sp", text: "S" + e.sprint }),
        el("span", { "class": "s", text: e.surface })])]);
    }
    function hydrate() {
      if (hydrated) return Promise.resolve();
      return ensureData().then(function (d) {
        if (hydrated) return;
        hydrated = true;
        var cur = links.filter(function (a) { return a.getAttribute("aria-current") === "true"; })[0];
        var curId = cur ? cur.getAttribute("data-id") : null;
        list.textContent = "";
        sortedEntries(d).forEach(function (e) { list.appendChild(inspItem(e)); });
        links = $$("a[data-id]", list);
        links.forEach(function (a) { a.setAttribute("aria-current", String(a.getAttribute("data-id") === curId)); });
        $$("[data-insp-all]").forEach(function (b) { b.hidden = true; });
      });
    }
    function select(id, scroll) {
      var e = BYID[id]; if (!e) return false;
      links.forEach(function (a) { a.setAttribute("aria-current", String(a.getAttribute("data-id") === id)); });
      renderSheet(e);
      if (scroll) $("#inspector").scrollIntoView({ behavior: "smooth", block: "start" });
      return true;
    }
    var panel = $("#insp-panel"), empty = null;
    function clearFilters() {
      if (q) q.value = ""; filt = "all"; bkt = "all";
      $$("[data-insp-basket]").forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-insp-basket") === "all")); });
      $$(".bench-filter button").forEach(function (o) { o.setAttribute("aria-pressed", String(o.getAttribute("data-f") === "all")); });
      apply();
    }
    function showEmpty(on) {
      if (!panel) return;
      if (on && !empty) {
        empty = el("div", { "class": "insp-empty", "data-insp-empty": "" }, [el("p", { text: "No record matches these filters." })]);
        var btn = el("button", { type: "button", "class": "btn sm", "data-insp-clear": "", text: "Clear filters" });
        btn.addEventListener("click", clearFilters);
        empty.appendChild(btn);
        panel.parentNode.appendChild(empty);
      }
      if (empty) empty.hidden = !on;
      panel.hidden = !!on;
    }
    function apply() {
      var t = (q && q.value || "").trim().toLowerCase(), shown = 0;
      links.forEach(function (a) {
        var e = BYID[a.getAttribute("data-id")];
        var hay = e ? JSON.stringify(e).toLowerCase() : a.textContent.toLowerCase();
        var ok = (filt === "all" || a.getAttribute("data-class") === filt) && (!t || hay.indexOf(t) >= 0) && inBasket(e);
        a.parentNode.hidden = !ok; if (ok) shown++;
      });
      if (count) count.textContent = shown + " of " + links.length + " records";
      var vis = links.filter(function (a) { return !a.parentNode.hidden; });
      showEmpty(vis.length === 0);
      var cur = links.filter(function (a) { return a.getAttribute("aria-current") === "true"; })[0];
      if (vis.length && (!cur || cur.parentNode.hidden)) select(vis[0].getAttribute("data-id"), false);
    }
    list.addEventListener("click", function (ev) {
      var a = ev.target.closest("a[data-id]"); if (!a || !DATA) return;   // without data, the link opens the index drawer
      ev.preventDefault(); select(a.getAttribute("data-id"), false);
    });
    list.addEventListener("keydown", function (ev) {
      if (ev.key !== "ArrowDown" && ev.key !== "ArrowUp") return;
      var vis = links.filter(function (a) { return !a.parentNode.hidden; }), i = vis.indexOf(document.activeElement);
      if (i < 0) return; ev.preventDefault();
      var n = vis[Math.max(0, Math.min(vis.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))]; n.focus(); select(n.getAttribute("data-id"), false);
    });
    function hydrated_(fn) { return function () { var self = this, args = arguments; hydrate().then(function () { fn.apply(self, args); }, function () { fn.apply(self, args); }); }; }
    if (q) {
      q.addEventListener("focus", function () { hydrate().catch(function () { /* the sample keeps working */ }); });
      q.addEventListener("input", hydrated_(function () {
        apply();
        var first = links.filter(function (a) { return !a.parentNode.hidden; })[0];
        if (first && q.value.trim()) select(first.getAttribute("data-id"), false);
      }));
    }
    $$(".bench-filter button").forEach(function (b) {
      b.addEventListener("click", hydrated_(function () {
        filt = b.getAttribute("data-f");
        $$(".bench-filter button").forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        apply();
      }));
    });
    $$("[data-insp-all]").forEach(function (b) { b.addEventListener("click", hydrated_(function () { apply(); })); });
    $$("[data-insp-basket]").forEach(function (b) {
      b.addEventListener("click", hydrated_(function () {
        bkt = b.getAttribute("data-insp-basket") || "all";
        $$("[data-insp-basket]").forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        apply();
      }));
    });
    document.addEventListener("click", function (ev) {
      var b = ev.target.closest("[data-inspect]"); if (!b || !DATA) return;
      ev.preventDefault(); select(b.getAttribute("data-inspect"), true);
    });
  }

  // ---- public index: filter + inline drawers ---------------------------------------------------------
  function initIndex() {
    var tbody = $("#matrix tbody"), rows = $$("#matrix tbody tr.rec"); if (!rows.length || !tbody) return;
    var q = $("#matrix-q"), count = $("#matrix-count"), cls = "all", hydrated = false;
    function hydrate() {
      if (hydrated) return Promise.resolve();
      return ensureData().then(function (d) {
        if (hydrated) return;
        hydrated = true;
        tbody.textContent = "";
        sortedEntries(d).forEach(function (e) { indexRow(e).forEach(function (n) { tbody.appendChild(n); }); });
        rows = $$("#matrix tbody tr.rec");
        $$("[data-ix-all]").forEach(function (b) { b.hidden = true; });
      });
    }
    function drawer(r) { return document.getElementById("r-" + r.getAttribute("data-id")); }
    function toggle(r, open) {
      var d = drawer(r); if (!d) return;
      open = open === undefined ? !d.classList.contains("open") : open;
      d.classList.toggle("open", open); r.classList.toggle("open", open);
      var b = $(".inspect-btn", r); if (b) { b.setAttribute("aria-expanded", String(open)); b.textContent = open ? "Close" : "Details"; }
    }
    function apply() {
      var t = (q && q.value || "").trim().toLowerCase(), shown = 0;
      rows.forEach(function (r) {
        var ok = (cls === "all" || r.getAttribute("data-class") === cls) && (!t || r.getAttribute("data-search").indexOf(t) >= 0);
        r.hidden = !ok; if (!ok) toggle(r, false); else shown++;
      });
      if (count) count.textContent = shown + " of " + rows.length + " records shown";
    }
    tbody.addEventListener("click", function (ev) {
      var r = ev.target.closest("tr.rec"); if (!r) return;
      if (ev.target.closest("a:not(.inspect-btn),button")) return;
      ev.preventDefault(); toggle(r);
    });
    function after(fn) { return function () { var a = arguments; hydrate().then(function () { fn.apply(null, a); }, function () { fn.apply(null, a); }); }; }
    if (q) q.addEventListener("input", after(apply));
    $$("#index .seg button").forEach(function (b) {
      b.addEventListener("click", after(function () {
        cls = b.getAttribute("data-class");
        $$("#index .seg button").forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        apply();
      }));
    });
    $$("[data-ix-all]").forEach(function (b) { b.addEventListener("click", after(apply)); });
    function openRow(id, smooth) {
      var r = rows.filter(function (x) { return x.getAttribute("data-id") === id; })[0];   // no selector parsing
      if (r) { r.hidden = false; toggle(r, true); r.scrollIntoView(smooth ? { behavior: "smooth", block: "center" } : { block: "center" }); return; }
      if (hydrated) return;
      hydrate().then(function () { if (rows.some(function (x) { return x.getAttribute("data-id") === id; })) openRow(id, smooth); }, function () { /* sample only */ });
    }
    function openFromHash() {
      var m = location.hash.match(/^#r-(.+)$/); if (!m) return;
      var id = m[1];
      try { id = decodeURIComponent(id); } catch (e) { /* keep the raw fragment */ }
      openRow(id, false);
    }
    document.addEventListener("click", function (ev) {
      var a = ev.target.closest("a[data-open]"); if (!a) return;
      ev.preventDefault();
      openRow(a.getAttribute("data-open"), true);
    });
    window.addEventListener("hashchange", openFromHash);
    openFromHash();
    apply();
  }

  // ---- request builder: brief + GitHub intake + Gmail compose + copy ---------------------------------
  // Tracks: 24h dossier (default), free 7-day fix re-verification, wholesale sweep, Continuous Control-Plane Monitoring, high-throughput API SLA. The
  // public data itself is free for everyone, so nothing here gates access. GitHub dropdown strings must match
  // .github/ISSUE_TEMPLATE/request-scan.yml. Paid tracks settle by Option A (commercial invoice, default) or Option B
  // (direct on-chain USDC to the Pacta treasury, an EOA).
  var REQ_TO = "pacta@dri.network";
  var SPONSOR_POOL_ADDRESS = "";
  var TRACK = {
    community: ["Free factual re-verification within 7 days (merged docs or on-chain fix)", "Free factual re-verification within 7 days (merged docs or on-chain fix)",
                "Pacta free 7-day fix re-verification request", ""],
    "wholesale-150": ["Wholesale Coverage Sweep — 20 or more protocols ($150 / protocol, by arrangement)", "Wholesale Coverage Sweep — 20 or more protocols ($150 / protocol, by arrangement)",
                      "Pacta wholesale sweep request", "$150 per protocol"],
    clearance: ["Custom Control-Plane Dossier (by arrangement)",
                "Custom Control-Plane Dossier (by arrangement)",
                "Pacta custom dossier request", "by arrangement"],
    continuous: ["Custom webhook alerts (by arrangement)",
                 "Custom webhook alerts (by arrangement)",
                 "Pacta custom webhook alerts request", "by arrangement"],
    api_sla: ["Enterprise / High-Throughput API SLA (priced on scope)",
              "Enterprise / High-Throughput API SLA (priced on scope)",
              "Pacta enterprise API SLA request", "the scoped amount (quoted on the invoice)"]
  };
  var SETTLE = {
    invoice: ["Option A — formal commercial invoice (PDF) & counterparty settlement (no upfront transfer; invoice on scope confirmation)",
              "Option A: formal commercial invoice (PDF) and counterparty settlement"],
    direct: ["Option B — direct on-chain USDC settlement", "Option B: direct on-chain USDC settlement"]
  };
  var TX_RE = /^0x[0-9a-fA-F]{64}$/;
  function own(o, k) { return typeof k === "string" && Object.prototype.hasOwnProperty.call(o, k); }
  // ---- URL prefill (/request/?tier=…&protocol=…&forum=…&settlement=…, also /?…#request): closed enums and sanitised
  //      text only, written with .value / .checked, never as markup. PREFILL-BEGIN
  var BAD_CHARS = /[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/g;
  function cleanText(v, max) { return String(v || "").replace(BAD_CHARS, "").replace(/\s+/g, " ").trim().slice(0, max); }
  function cleanForum(v) {
    var s = String(v || "").trim(), u;
    if (!s || s.length > 300 || /[\u0000-\u0020\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060-\u2069\ufeff]/.test(s)) return "";
    try { u = new URL(s); } catch (e) { return ""; }
    return u.protocol === "https:" && !u.username && !u.password && u.hostname ? s : "";
  }
  function readPrefill(search) {
    var q, out = {};
    try { q = new URLSearchParams(search || ""); } catch (e) { return out; }
    var t = q.get("tier"), st = q.get("settlement"), p = cleanText(q.get("protocol"), 80), f = cleanForum(q.get("forum"));
    if (t === "rapid-500") t = "community";
    if (own(TRACK, t)) out.tier = t;
    if (own(SETTLE, st)) out.settlement = st;
    if (p) out.protocol = p;
    if (f) out.forum = f;
    return out;
  }
  // PREFILL-END
  function initRequest() {
    var form = $("#req-form"); if (!form) return;
    var out = $("#req-brief"), gh = $("#req-gh"), gm = $("#req-gmail"), st = $("#req-status"), pay = $("#req-pay");
    var txField = $("#req-tx-field"), txHint = $("#req-tx-hint"), txIn = $("#req-tx"), sum = $("#req-pay-sum"), direct = $("#req-direct");
    var done = $("#req-done"), send = $("#req-send"), api = form.getAttribute("data-api") || "";
    var treasury = form.getAttribute("data-treasury") || "";
    function val(n) { var x = form.elements[n]; return x ? String(x.value || "").trim() : ""; }
    function tier() { var x = $('input[name="tier"]:checked', form); return x && own(TRACK, x.value) ? x.value : "clearance"; }
    function settlement() { var x = $('input[name="settlement"]:checked', document); return x && own(SETTLE, x.value) ? x.value : "invoice"; }
    var combo = initCombo(form, function () { update(); });
    function protocols() { return combo.values().map(function (x) { return x.name; }); }
    function fieldErr(inputId, errId, text) {
      var inp = $("#" + inputId), m = $("#" + errId);
      if (m) { m.textContent = text || ""; m.hidden = !text; }
      if (inp) { if (text) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid"); }
    }
    function update() {
      if (!out) return;
      var t = tier(), paid = t !== "community", s = settlement(), dir = paid && s === "direct";
      var ps = protocols(), org = val("org"), scope = val("scope"), contact = val("contact");
      var forum = val("forum"), tx = dir ? val("tx") : "", txOk = !tx || TX_RE.test(tx);
      var subj = TRACK[t][2] + (org ? " — " + org : "");
      var lines = ["Subject: " + subj, "",
        "Track: " + TRACK[t][0],
        "Organization: " + (org || "(not given)"),
        "Protocols in scope: " + (ps.length ? ps.join(", ") : "(none selected)")];
      if (scope) lines.push("Scope:", scope);
      if (forum) lines.push("Forum proposal: " + forum);
      if (paid) {
        lines.push("Settlement: " + SETTLE[s][0]);
        if (dir) {
          lines.push("Payment: " + (tx ? tx + (txOk ? "" : "  (check: not a 0x-prefixed 32-byte transaction hash)")
                                       : "not yet sent; please confirm scope first") + " — " + TRACK[t][3] +
                     " in USDC to the Pacta treasury (direct settlement EOA) " + treasury + " on Base or Ethereum");
        }
      }
      lines.push("Contact: " + (contact || "(not given)"));
      lines.push("", "Source: https://pacta.wtf/request/");   // Item 16: canonical, never a staging or local URL
      out.textContent = lines.join("\n");
      if (pay) pay.hidden = !paid;
      if (sum) sum.textContent = paid ? TRACK[t][0].replace(/ \((.*)\)$/, " · $1") : "";
      if (direct) direct.hidden = !dir;
      if (txField) txField.hidden = !dir;
      if (txIn) { if (txOk) txIn.removeAttribute("aria-invalid"); else txIn.setAttribute("aria-invalid", "true"); }
      if (txHint) txHint.textContent = txOk ? "A 66-character hash starting with 0x." : "That does not look like a transaction hash (0x + 64 hex characters).";
      var title = "[Pacta Scope] " + (org || (ps.length ? ps.slice(0, 3).join(", ") : TRACK[t][2].replace(/^Pacta | request$/g, "")));
      var p = new URLSearchParams({ template: "request-scan.yml", title: title });
      p.set("repo_or_portfolio_url", forum || scope.split(/\s+/).filter(function (w) { return /^https?:\/\//.test(w); })[0] || "");
      p.set("commitments_and_addresses", ["Protocols: " + (ps.join(", ") || "-"), scope].filter(Boolean).join("\n"));
      p.set("package_tier", TRACK[t][1]);
      if (paid) p.set("settlement_preference", SETTLE[s][1]);
      if (forum) p.set("forum_proposal_url", forum);
      if (dir && tx && txOk) p.set("payment_tx_hash", tx);
      p.set("contact_channel", contact);
      if (gh) gh.href = "https://github.com/Fractal-Neurons/pacta/issues/new?" + p.toString();
      if (gm) gm.href = "https://mail.google.com/mail/?view=cm&fs=1&to=" + encodeURIComponent(REQ_TO) + "&su=" + encodeURIComponent(subj) +
        "&body=" + encodeURIComponent(lines.slice(2).join("\n"));
    }
    // the request body, or null with every problem shown next to its field
    function payload() {
      var t = tier(), sel = combo.values(), org = val("org"), scope = val("scope"), forum = val("forum"), contact = val("contact"), ok = true;
      var subj = "";
      if (sel.length) {
        var parts = [], i;
        for (i = 0; i < sel.length; i++) {
          var next = (sel[i].slug || cleanSubject(sel[i].name).toLowerCase());
          if ((parts.concat([next]).join(", ") + (i < sel.length - 1 ? " and " + (sel.length - i - 1) + " more" : "")).length > 120) break;
          parts.push(next);
        }
        subj = parts.join(", ") + (parts.length < sel.length ? " and " + (sel.length - parts.length) + " more" : "");
      } else subj = cleanSubject(org).slice(0, 120);
      if (subj.length < 2) { fieldErr("req-proto-q", "req-proto-err", "Choose at least one protocol, or name your organization."); ok = false; }
      else fieldErr("req-proto-q", "req-proto-err", "");
      if (org && /[@<>]/.test(org)) { fieldErr("req-org", "req-org-err", "Keep contact details and markup out of the organization name."); ok = false; }
      else fieldErr("req-org", "req-org-err", "");
      if (PII_RE.test(scope)) { fieldErr("req-scope", "req-scope-err", "Remove emails, @handles, IP addresses or HTML from Scope; put a contact in Contact."); ok = false; }
      else fieldErr("req-scope", "req-scope-err", "");
      var cleanForumUrl = forum ? cleanForum(forum) : "";
      if (forum && (!cleanForumUrl || cleanForumUrl.length > 200)) { fieldErr("req-forum", "req-forum-err", "Use a public https:// link of up to 200 characters."); ok = false; }
      else fieldErr("req-forum", "req-forum-err", "");
      var c = contact.replace(/^github:/i, "");
      if (contact && (JUNK_CONTACT.test(contact) || contact.length > 120 || !(EMAIL_RE.test(c) || TG_RE.test(c) || GH_RE.test(c)))) {
        fieldErr("req-contact", "req-contact-err", "Use a work email, a @telegram handle or a GitHub username, or leave it empty."); ok = false;
      } else fieldErr("req-contact", "req-contact-err", "");
      if (!ok) return null;
      var cap = cutWords(TRACK[t][0] + (scope ? ": " + scope.replace(BAD_CHARS, "") : "."), 280);
      var body = { caller_agent: "pacta-web", requester_role: val("requester_role"), caller_purpose: val("caller_purpose"),
        request_type: val("request_type"), target_subject: subj, requested_capability: cap, urgency_track: URGENCY[t] };
      Object.keys(REQ_ENUMS).forEach(function (k) { if (REQ_ENUMS[k].indexOf(body[k]) < 0) body[k] = REQ_ENUMS[k][k === "requester_role" ? 5 : k === "caller_purpose" ? 6 : 0]; });
      if (cleanForumUrl) body.forum_proposal_url = cleanForumUrl;
      if (contact) body.contact_handle = contact;
      return body;
    }
    function busy(on) {
      if (!send) return;
      send.disabled = on; send.setAttribute("aria-busy", String(on));
      var sp = $(".spinner", send), l = $("[data-req-label]", send);
      if (sp) sp.hidden = !on; if (l) l.textContent = on ? "Sending…" : "Send request";
    }
    function status(t, bad) { if (st) { st.textContent = t; st.style.color = bad ? "var(--destructive)" : ""; } }
    function showDone(j) {
      if (!done) return;
      var set = function (sel, v) { var n = $(sel, done); if (n) n.textContent = v; };
      var up = j.status === "upvoted_existing";
      set("[data-req-id]", String(j.request_id));
      set("[data-req-st]", up ? "Added your vote to an existing request" : "Queued");
      set("[data-req-votes]", typeof j.demand_votes === "number" ? String(j.demand_votes) : "1");
      set("[data-req-done-title]", up ? "Request recorded" : "Request received");
      set("[data-req-done-text]", up ? "Someone asked for the same scope; your request was added to it." : "Your request is in the queue. Keep the ID for follow-up.");
      var fr = $("[data-req-fast-row]", done), fa = $("[data-req-fast]", done), fu = String(j.fast_track_url || "");
      if (fr && fa && /^https:\/\/[^\s"<>]+$/.test(fu)) { fa.setAttribute("href", fu); fr.hidden = false; } else if (fr) fr.hidden = true;
      form.hidden = true; done.hidden = false;
      try { done.focus(); } catch (e) { /* focus is best effort */ }
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();   // no navigation, no inline handler (CSP-safe)
      status("", false);
      var body = payload();
      if (!body) { status("Fix the highlighted fields, then send again.", true); var f = $('[aria-invalid="true"]', form); if (f) f.focus(); return; }
      if (!REQ_API_RE.test(api) || typeof fetch !== "function") { status("This browser cannot send the form; open a GitHub issue or copy the brief instead.", true); return; }
      busy(true);
      var init = { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(body) };
      try { if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") init.signal = AbortSignal.timeout(15000); } catch (x) { /* none */ }
      fetch(api, init).then(function (res) { return res.json().then(function (j) { return { status: res.status, j: j }; }, function () { return { status: res.status, j: {} }; }); })
        .then(function (x) {
          busy(false);
          var j = x.j || {};
          if (x.status === 200 && /^REQ-\d{4}-[A-Za-z0-9]+$/.test(String(j.request_id || ""))) { showDone(j); return; }
          if (x.status === 429) status("Too many requests from this network (HTTP 429). Wait a few minutes, or open a GitHub issue.", true);
          else status("The API answered HTTP " + x.status + (j.detail ? ": " + String(j.detail) : j.error ? ": " + String(j.error) : "") + ". Fix the form, or open a GitHub issue.", true);
        }, function () { busy(false); status("Could not reach the API. Open a GitHub issue or copy the brief instead.", true); });
    });
    var again = done && $("[data-req-again]", done);
    if (again) again.addEventListener("click", function () { done.hidden = true; form.hidden = false; status("", false); var f = $('input[name="tier"]:checked', form); if (f) f.focus(); });
    function pick(name, v) {
      var r = $$('input[name="' + name + '"]').filter(function (x) { return x.value === v; })[0];
      if (r) r.checked = true;
      return !!r;
    }
    function preselect(t) { if (pick("tier", t)) update(); }
    function prefill(o) {
      if (o.tier) pick("tier", o.tier);
      if (o.settlement) pick("settlement", o.settlement);
      if (o.protocol) {
        var orgIn = form.elements.org, hit = combo.select(o.protocol);
        if (orgIn && !String(orgIn.value || "").trim()) {
          var v = combo.values(); orgIn.value = hit && v.length ? v[v.length - 1].name : o.protocol;
        }
      }
      if (o.forum && form.elements.forum) form.elements.forum.value = o.forum;
    }
    form.addEventListener("input", update);
    form.addEventListener("change", update);
    document.addEventListener("change", function (ev) { if (ev.target && ev.target.getAttribute && ev.target.getAttribute("name") === "settlement" && !form.contains(ev.target)) update(); });
    if (gh) gh.addEventListener("click", function () { status("Opened in a new tab. If nothing appeared, use Copy brief.", false); });
    if (gm) gm.addEventListener("click", function () { status("Opened in a new tab. If nothing appeared, use Copy brief.", false); });
    document.addEventListener("click", function (ev) {
      var a = ev.target && ev.target.closest ? ev.target.closest("a[data-tier]") : null; if (!a) return;
      if ((a.getAttribute("href") || "").charAt(0) === "#") { preselect(a.getAttribute("data-tier")); }
    });
    prefill(readPrefill(location.search));
    update();
  }

  // ---- Option B v2: one product per page (/scan/, /webhook/, /seal/). ONE primary action: a 1-click browser-wallet transfer of the
  //      exact Base USDC amount (transfer only, never an approval), or, without a browser wallet, the manual transfer drawer; then
  //      POST /v1/orders/verify. The order is frozen once validated and every control locks until it settles. Everything returned
  //      is written as text. The payee, token, chain and amounts are constants here; the page's data-* never decide where money goes.
  var CO_TREASURY = "0x4348DF1BEFAffcbA248B5118B1b782B1B2bdEd14", CO_USDC = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913", CO_CHAIN = "0x2105";
  var CO_SKU = {
    "wallet-report-9": { atomic: 9000000, amount: "9.00", route: "scan", label: "Full Wallet & Safe Exposure Report", needTarget: true, needContact: false },
    "instant-scan-19": { atomic: 19000000, amount: "19.00", route: "scan", label: "Instant Contract & Safe Deep-Scan", needTarget: true, needContact: false },
    "radar-webhook-49": { atomic: 49000000, amount: "49.00", route: "webhook", label: "Live Timelock & Signer Webhook", needTarget: false, needContact: true,
                          contactMissing: "Enter where the alerts should go." },
    "reverify-seal-99": { atomic: 99000000, amount: "99.00", route: "seal", label: "24h Mainnet Control-Plane Seal", needTarget: true, needContact: true,
                          contactMissing: "Enter a team contact so the verifiers can reach you." }
  };
  // webhook-49 / wallet-guard-49 forward to the free watch pilot door (no paid webhook is sold)
  var CO_TIER = { "wallet-9": "wallet-report-9", "wallet-guard-49": "watch-pilot", "instant-19": "instant-scan-19", "webhook-49": "watch-pilot", "seal-99": "reverify-seal-99" };
  // the Worker's order codes (POST /v1/orders/verify, OpenAPI): CO_RETRY are polled with the same frozen order; the rest are final
  var CO_ERR = {
    tx_already_used: "This transaction hash already unlocked another order.",
    insufficient_amount: "The transfer is below the price. Send the exact amount shown, to the treasury shown.",
    tx_failed: "That transaction failed on Base.",
    providers_disagree: "Two Base RPC providers disagree about this transaction. Wait a minute, then press Verify again.",
    tx_not_found: "Base has not indexed this transaction yet. Wait a minute, then press Verify again with the same hash.",
    tx_not_confirmed: "The transaction is not confirmed on Base yet. Wait a minute, then press Verify again with the same hash.",
    order_rpc_unavailable: "Base RPC providers did not answer. Press Verify again in a minute with the same hash.",
    report_unavailable: "Your payment is recorded; the order is not finished yet. Press Verify again with the same hash.",
    order_not_recorded: "Your payment is recorded; the order is not finished yet. Press Verify again with the same hash.",
    order_not_settled: "Your payment is recorded; the order is not finished yet. Press Verify again with the same hash.",
    orders_unavailable: "Checkout verification is unavailable right now. Keep the transaction hash and send it through the request form.",
    invalid_order: "The verifier refused the request. Check the fields above.",
    rate_limited: "Too many attempts. Wait a minute, then try again."
  };
  var CO_RETRY = /^(tx_not_found|tx_not_confirmed|order_rpc_unavailable|report_unavailable|order_not_recorded|order_not_settled|payment_in_progress)$/;
  var CO_ADDR = /^0x[0-9a-fA-F]{40}$/;
  function coSkuFrom(search) {   // ?tier=instant-19|webhook-49|seal-99 (or the SKU itself): a closed enum, never markup
    var q, t, s;
    try { q = new URLSearchParams(search || ""); } catch (e) { return ""; }
    t = q.get("tier"); s = q.get("sku");
    return own(CO_TIER, t) ? CO_TIER[t] : own(CO_SKU, s) ? s : own(CO_SKU, t) ? t : "";
  }
  function coPad(hex) { return ("0000000000000000000000000000000000000000000000000000000000000000" + hex).slice(-64); }
  // ERC-20 transfer(address,uint256): selector 0xa9059cbb, the treasury, the exact amount (6 decimals). Never approve().
  function coTransferData(atomic) { return "0xa9059cbb" + coPad(CO_TREASURY.slice(2).toLowerCase()) + coPad(Number(atomic).toString(16)); }
  function coContactOk(v) {   // a webhook must be https; anything else is a handle or an email
    if (!v) return true;
    if (/^[a-z][a-z0-9+.-]*:/i.test(v)) { try { var u = new URL(v); return u.protocol === "https:" && !u.username && !u.password && !!u.hostname; } catch (e) { return false; } }
    return v.length <= 200;
  }
  var CO_MOBILE_UA = /Android|iPhone|iPad|iPod|Mobile/i;
  function coHasInjectedWallet() { return !!(window.ethereum && typeof window.ethereum.request === "function"); }
  function coIsMobileNoWallet() {
    var ua = (typeof navigator === "object" && navigator && navigator.userAgent) || (window.navigator && window.navigator.userAgent) || "";
    return !coHasInjectedWallet() && CO_MOBILE_UA.test(String(ua));
  }
  function coCanonicalPath(pathname, route) {
    var p = String(pathname || "");
    if (BASE && p.indexOf(BASE + "/") === 0) p = p.slice(BASE.length);
    p = p.replace(/^\/website-test(?=\/)/, "");
    if (p && p.slice(-1) !== "/") p += "/";
    return /^\/(?:scan|seal|webhook)\/$/.test(p) ? p : "/" + route + "/";
  }
  function coDeepLinkPair(pathname, route, rawSearch, chainVal, addrVal) {
    var s0 = String(rawSearch || "").replace(BAD_CHARS, ""), qs = "";
    if (s0 && s0.charAt(0) !== "?") s0 = "?" + s0;
    if (CO_ADDR.test(String(addrVal || ""))) {
      try {
        var q = new URLSearchParams(s0), ch = chainVal === "base" ? "base" : "ethereum";
        if (q.get("address") === addrVal && (q.get("chain") || ch) === ch && q.has("chain")) qs = s0;
        else { q.set("chain", ch); q.set("address", addrVal); qs = "?" + q.toString(); }
      } catch (e) { qs = s0; }
    } else {
      qs = s0;
    }
    var canon = coCanonicalPath(pathname, route) + qs;
    return {
      canon: canon,
      metamask: "https://metamask.app.link/dapp/pacta.wtf" + canon,
      coinbase: "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + canon)
    };
  }
  function initCheckout() {
    var form = $("#co-form"); if (!form) return;
    var k = form.getAttribute("data-sku"); if (!own(CO_SKU, k)) return;
    var s = CO_SKU[k], api = form.getAttribute("data-api") || "", st = $("#co-status"), res = $("#co-result"), btn = $("#co-verify"), wal = $("#co-wallet");
    var drawer = $("#co-manual"), spin = btn ? $(".spinner", btn) : null, busy = false, report = null, pfF = $("#pf-form");
    // /scan/: the free live checker above the order is the scanner; its chain and address are the order's target
    function fld(n) {
      var x = form.elements[n];
      if (x) return x;
      if (pfF && n === "target_address") return $('input[name="address"]', pfF);
      if (pfF && n === "target_chain") return $('select[name="chain"]', pfF);
      return null;
    }
    function val(n) { var x = fld(n); return x ? String(x.value || "").trim() : ""; }
    // /webhook/: one visible field (a timelock / Safe address or an indexed protocol) feeds the two order fields the verifier reads
    var watch = $("#co-watch", form), watchHint = $("[data-co-watch-hint]", form), watchTip = watchHint ? watchHint.textContent : "";
    function syncWatch() {
      var v = String(watch.value || "").trim(), t = fld("target_address"), d = fld("protocol_or_docs");
      if (/^0x/i.test(v)) { if (t) t.value = v; if (d) d.value = ""; }
      else { if (t) t.value = ""; if (d) d.value = cleanText(v, 80); }
      $$("[data-co-pick]", form).forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
      if (watchHint) watchHint.textContent = watchTip;
    }
    if (watch) watch.addEventListener("input", syncWatch);
    function err(inp, errId, text) {
      var m = $("#" + errId);
      if (m) { m.textContent = text || ""; m.hidden = !text; }
      if (inp) { if (text) inp.setAttribute("aria-invalid", "true"); else inp.removeAttribute("aria-invalid"); }
    }
    function status(text, bad) { if (st) { st.textContent = text || ""; if (bad) st.setAttribute("data-bad", ""); else st.removeAttribute("data-bad"); } }
    function lockables() {   // Pay, Verify, every order field, the scanner's fields and the example chips
      return [btn, wal].concat($$("input, select, textarea", form)).concat(pfF ? $$("input, select, button", pfF) : []).concat($$("[data-receipt], [data-co-pick]"));
    }
    function setBusy(on) {   // one payment or verification at a time: everything above stays locked until it settles
      busy = on;
      lockables().forEach(function (x) { if (x) x.disabled = on; });
      if (btn) { if (on) btn.setAttribute("aria-busy", "true"); else btn.removeAttribute("aria-busy"); }
      if (spin) spin.hidden = !on;
    }
    function clearResult() { if (res) res.hidden = true; report = null; }
    function validate(needTx) {
      var t = val("target_address"), d = val("protocol_or_docs"), c = val("webhook_or_contact"), tx = val("tx_hash"), ok = true;
      var tErr = t ? (CO_ADDR.test(t) ? "" : "Enter a 0x address: 0x followed by 40 hexadecimal characters.")
                   : s.needTarget ? "Enter the contract or Safe address." : (d ? "" : "Pick a protocol, or enter a timelock or Safe address.");
      var cErr = c ? (coContactOk(c) ? "" : "Use an https:// webhook URL, an email or a @handle.") : s.needContact ? s.contactMissing : "";
      var xErr = needTx ? (TX_RE.test(tx) ? "" : (tx ? "A Base transaction hash is 0x followed by 64 hexadecimal characters." : "Paste the Base transaction hash of your payment.")) : "";
      var tIn = watch || fld("target_address"), cIn = fld("webhook_or_contact"), xIn = fld("tx_hash");
      err(tIn, "co-target-err", tErr); err(cIn, "co-contact-err", cErr); err(xIn, "co-tx-err", xErr);
      [[tIn, tErr], [cIn, cErr], [xIn, xErr]].some(function (p) { if (p[1]) { if (p[0] && p[0].focus) p[0].focus(); ok = false; return true; } return false; });
      return ok;
    }
    function body() {   // the order as validated; empty optional fields are left out (the API refuses an empty target_address)
      var o = { sku: k, tx_hash: val("tx_hash"), chain: "base", target_chain: val("target_chain") === "base" ? "base" : "ethereum" };
      var t = val("target_address"), d = cleanText(val("protocol_or_docs"), 200), c = cleanText(val("webhook_or_contact"), 200);
      if (t) o.target_address = t;
      if (d) o.protocol_or_docs = d;
      if (c) o.webhook_or_contact = c;
      return o;
    }
    function coError(code, http) {
      var c = /^[a-z0-9_]{1,40}$/.test(code || "") ? code : "";
      return CO_ERR[c] || (http === 404 && !c ? "The verifier is not available yet. Keep the transaction hash and send it through the request form."
        : "Not verified (HTTP " + http + (c ? ", " + c : "") + "). Keep the transaction hash and try again.");
    }
    function row(sel, kids) { var d = $(sel, res); if (!d) return; d.textContent = ""; [].concat(kids).forEach(function (x) { d.appendChild(typeof x === "string" ? document.createTextNode(x) : x); }); }
    function render(j, b, isReplay) {
      var order = j.order_id || j.orderId || j.id || "", stx = String(j.status || "verified");
      report = j;
      row("[data-co-r-order]", String(order || "—").slice(0, 80));
      row("[data-co-r-sku]", s.label + " · " + s.amount + " USDC");
      row("[data-co-r-pay]", [arrowLink({ href: "https://basescan.org/tx/" + b.tx_hash, target: "_blank", rel: "noopener" }, "tx " + short(b.tx_hash, 6, 4), "up-right")]);
      row("[data-co-r-status]", stx.slice(0, 60));
      var pre = $("#co-json"); if (pre) pre.textContent = JSON.stringify(j, null, 2);
      if (res) { res.hidden = false; if (res.focus) res.focus(); }
      status("Verified. Your result is below.");
      xTrackPurchase(j, s, isReplay, b.tx_hash);
    }
    function verify(retries) {
      if (busy || !validate(true)) return;
      var order = body();   // frozen before the fetch: retries resend exactly this order
      setBusy(true); clearResult(); attempt(order, retries);
    }
    function attempt(b, retries) {   // stays busy across the confirmation retries; unlocks only once the order is settled
      var ctl = typeof AbortController === "function" ? new AbortController() : null, guard = 0;
      status("Checking the payment on Base…");
      if (ctl) guard = setTimeout(function () { ctl.abort(); }, 75000);
      var opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) };
      if (ctl) opts.signal = ctl.signal;
      fetch(api, opts).then(function (r) {
        var replay = !!(r.headers && typeof r.headers.get === "function" && r.headers.get("Pacta-Idempotent-Replay") === "true");
        return r.text().then(function (t) { var j = null; try { j = JSON.parse(t); } catch (e) { j = null; } return { s: r.status, j: j, replay: replay }; });
      }).then(function (x) {
        clearTimeout(guard);
        if (x.s === 200 && x.j && typeof x.j === "object") { setBusy(false); render(x.j, b, x.replay); return; }
        var code = x.j && typeof x.j.error === "string" ? x.j.error : "";
        if (retries > 0 && (x.s === 202 || x.s === 425 || CO_RETRY.test(code))) {
          status("Waiting for Base to confirm the transaction…");
          setTimeout(function () { attempt(b, retries - 1); }, 4000);
          return;
        }
        setBusy(false); status(coError(code, x.s), true);
      }).catch(function () {
        clearTimeout(guard); setBusy(false);
        status("Could not reach the verifier. Your payment is safe: keep the transaction hash and try again, or send it through the request form.", true);
      });
    }
    function pay(eth) {
      if (busy || !validate(false)) return;
      var order = body(), from = "";   // frozen now: the hash the wallet returns is added, nothing else changes
      setBusy(true);   // locked BEFORE the first wallet request: a second click can never open a second transfer
      status("Confirm the transfer of exactly " + s.amount + " USDC on Base in your wallet…");
      eth.request({ method: "eth_requestAccounts" }).then(function (a) {
        from = a && a[0] ? String(a[0]) : "";
        if (!CO_ADDR.test(from)) throw new Error("no account");
        return eth.request({ method: "eth_chainId" });
      }).then(function (c) {
        if (String(c).toLowerCase() === CO_CHAIN) return c;
        return eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CO_CHAIN }] }).then(function () { return eth.request({ method: "eth_chainId" }); });
      }).then(function (c) {
        if (String(c).toLowerCase() !== CO_CHAIN) throw new Error("wrong chain");
        return eth.request({ method: "eth_sendTransaction", params: [{ from: from, to: CO_USDC, value: "0x0", data: coTransferData(s.atomic) }] });
      }).then(function (h) {
        if (!TX_RE.test(String(h || ""))) throw new Error("no hash");
        var t = fld("tx_hash"); if (t) t.value = String(h);
        status("Transfer sent. Waiting for Base to confirm…");
        order.tx_hash = String(h);
        clearResult(); attempt(order, 15);   // still locked: the order frozen at Pay is verified
      }).catch(function (e) {
        var code = e && e.code;
        setBusy(false);
        status(code === 4001 ? "Cancelled in the wallet. Nothing was sent."
          : code === 4902 ? "Add Base (chain 8453) to your wallet, or pay with the manual transfer below."
          : "The wallet did not send the transfer. You can pay with the manual transfer below.", true);
      });
    }
    function manual() {   // no browser wallet: the order is checked first, then the manual transfer drawer opens with what to send
      if (busy || !validate(false)) return;
      if (drawer) { drawer.setAttribute("open", ""); try { drawer.scrollIntoView({ block: "nearest" }); } catch (e) { /* old browsers */ } }
      status("No browser wallet here. Send exactly " + s.amount + " USDC on Base to the address below, then paste the transaction hash.");
      var t = fld("tx_hash"); if (t && t.focus) t.focus();
    }
    if (wal) wal.addEventListener("click", function () {
      if (!busy) xTrackLead();
      var eth = window.ethereum;
      if (eth && typeof eth.request === "function") pay(eth); else manual();
    });
    if (drawer) {
      drawer.addEventListener("toggle", function () { if (drawer.open || drawer.hasAttribute("open")) xTrackLead(); });
      var sumEl = $("summary", drawer);
      if (sumEl) sumEl.addEventListener("click", function () { if (!drawer.hasAttribute("open")) xTrackLead(); });
    }
    form.addEventListener("submit", function (ev) { ev.preventDefault(); verify(5); });
    // /webhook/: quick picks fill the chain, the timelock or Safe (when the protocol has one) and the protocol name
    $$("[data-co-pick]", form).forEach(function (b) {
      b.addEventListener("click", function () {
        if (busy) return;
        var ch = fld("target_chain"), t = fld("target_address"), d = fld("protocol_or_docs"), a = b.getAttribute("data-address") || "";
        if (ch) ch.value = b.getAttribute("data-chain") === "base" ? "base" : "ethereum";
        if (t) t.value = CO_ADDR.test(a) ? a : "";
        if (d) d.value = cleanText(b.getAttribute("data-protocol"), 80);
        if (watch) watch.value = cleanText(b.getAttribute("data-protocol"), 80);
        if (watchHint) watchHint.textContent = CO_ADDR.test(a)
          ? "Alerts watch its indexed controller " + short(a, 6, 4) + " on " + (b.getAttribute("data-chain") === "base" ? "Base" : "Ethereum") + "."
          : "Alerts cover the protocol's indexed timelocks and Safes.";
        $$("[data-co-pick]", form).forEach(function (o) { o.setAttribute("aria-pressed", String(o === b)); });
        err(watch || t, "co-target-err", "");
      });
    });
    // ?chain=ethereum|base&address=0x... prefill (when opened inside MetaMask or Coinbase Wallet via 1-tap mobile deep-link)
    try {
      var uq = new URLSearchParams(location.search || ""), uch = uq.get("chain"), uad = uq.get("address");
      var ch0 = fld("target_chain"), ad0 = fld("target_address");
      if (ch0 && (uch === "ethereum" || uch === "base")) ch0.value = uch;
      if (ad0 && !ad0.value && CO_ADDR.test(String(uad || ""))) { ad0.value = String(uad); ad0.setAttribute("value", String(uad)); }
      if (watch && !watch.value && CO_ADDR.test(String(uad || ""))) { watch.value = String(uad); watch.setAttribute("value", String(uad)); }
    } catch (e) { /* ignore malformed query */ }
    var dlBox = $("[data-co-deeplinks]", form), dlMm = $("[data-co-metamask]", form), dlCb = $("[data-co-coinbase]", form);
    function syncDeepLinks() {
      if (!dlBox) return;
      var pair = coDeepLinkPair(location.pathname, s.route, location.search, val("target_chain"), val("target_address"));
      if (dlMm) dlMm.setAttribute("href", pair.metamask);
      if (dlCb) dlCb.setAttribute("href", pair.coinbase);
      var show = coIsMobileNoWallet();
      dlBox.hidden = !show;
      if (show) form.setAttribute("data-mobile-webview", "true"); else form.removeAttribute("data-mobile-webview");
    }
    if (dlBox) {
      syncDeepLinks();
      if (dlMm) dlMm.addEventListener("click", xTrackLead);
      if (dlCb) dlCb.addEventListener("click", xTrackLead);
      var tCh = fld("target_chain"), tAd = fld("target_address");
      if (tCh) tCh.addEventListener("change", syncDeepLinks);
      if (tAd) { tAd.addEventListener("input", syncDeepLinks); tAd.addEventListener("change", syncDeepLinks); }
      if (watch) { watch.addEventListener("input", syncDeepLinks); watch.addEventListener("change", syncDeepLinks); }
      $$("[data-receipt], [data-co-pick]", document).forEach(function (b) { b.addEventListener("click", function () { setTimeout(syncDeepLinks, 0); }); });
    }
    // ?protocol=<slug> (the protocol pages' seal link): the indexed protocol's own contract and name, from the public catalog
    var pf = readPrefill(location.search);
    if (pf.protocol && !pfF) {
      var d0 = fld("protocol_or_docs"); if (d0 && !d0.value) d0.value = pf.protocol;
      if (watch && !watch.value) watch.value = pf.protocol;
      lookupData().then(function (d) {
        var hit = (d || []).filter(function (x) { return x.slug === pf.protocol; })[0], it = hit && hit.it;
        if (!it || busy) return;
        var a = k === "radar-webhook-49" ? it.controllerAddress : ((it.preflightArgs && it.preflightArgs.address) || it.primaryContract);
        var ch = fld("target_chain"), t = fld("target_address"), dd = fld("protocol_or_docs");
        if (ch && !val("target_address")) ch.value = it.chain === "base" ? "base" : "ethereum";
        if (t && !t.value && CO_ADDR.test(String(a || ""))) t.value = String(a);
        if (dd && dd.value === pf.protocol) dd.value = cleanText(it.name, 80);
        if (watch && watch.value === pf.protocol) watch.value = cleanText(it.name, 80);
        syncDeepLinks();
      });
    }
    var dl = $("[data-co-download]", form), pr = $("[data-co-print]", form);
    if (dl) dl.addEventListener("click", function () {
      if (!report || typeof Blob !== "function" || !URL.createObjectURL) return;
      var a = document.createElement("a"), u = URL.createObjectURL(new Blob([JSON.stringify(report, null, 2)], { type: "application/json" }));
      a.setAttribute("href", u); a.setAttribute("download", "pacta-" + k + ".json"); document.body.appendChild(a); a.click(); a.remove();
      setTimeout(function () { URL.revokeObjectURL(u); }, 1000);
    });
    if (pr) pr.addEventListener("click", function () {
      var h = document.documentElement; h.classList.add("co-print");
      try { window.print(); } finally { h.classList.remove("co-print"); }
    });
  }
  // /request/: ?tier=wallet-9 | instant-19 | webhook-49 | seal-99 forwards cleanly (keeping a valid protocol=)
  function initLauncher() {
    var bar = $("[data-launcher]"), k = coSkuFrom(location.search); if (!bar || !k) return;
    var p = readPrefill(location.search), qs = p.protocol ? "?protocol=" + encodeURIComponent(p.protocol) : "";
    var a = $('a[data-sku="' + k + '"]', bar);
    var href = a ? a.getAttribute("href") + qs
      : (k === "wallet-report-9" || k === "instant-scan-19") ? "../scan/" + qs
      : k === "reverify-seal-99" ? "../seal/" + qs : "";
    if (!href) return;
    if (a) a.setAttribute("aria-current", "true");
    try { location.replace(href); } catch (e) { /* the highlighted product link stays */ }
  }

  // ---- /miniapp/: Farcaster Frame v2 / Coinbase Base App embedded control-plane check + 1-tap Base USDC upgrade ----
  function initMiniApp() {
    var root = $("#ma-root"); if (!root) return;
    var api = (root.getAttribute("data-api") || "").replace(/\/+$/, "");
    var verifyApi = root.getAttribute("data-verify-api") || "";
    var badgeBase = root.getAttribute("data-badges") || "../badges/";
    var wPill = $("#ma-wallet-pill", root), cForm = $("#ma-check-form", root), cHid = $("#ma-chain", root), cAddr = $("#ma-address", root);
    var cSub = $("#ma-submit", root), cErr = $("#ma-addr-err", root), segBtns = $$("[data-ma-chain]", root), presets = $$("[data-ma-preset]", root);
    var vSec = $("#ma-verdict", root), vPill = $("#ma-v-pill", root), vTitle = $("#ma-v-title", root), vBadge = $("#ma-v-badge", root);
    var vSum = $("#ma-v-summary", root), vTarget = $("#ma-v-target", root), vCtrl = $("#ma-v-ctrl", root), vDelay = $("#ma-v-delay", root), vProv = $("#ma-v-prov", root);
    var bScan = $("#ma-buy-scan", root), bSeal = $("#ma-buy-seal", root), mContact = $("#ma-contact", root), mContactErr = $("#ma-contact-err", root);
    var pStatus = $("#ma-pay-status", root), rBox = $("#ma-receipt", root), rSku = $("#ma-r-sku", root), rOrd = $("#ma-r-order", root);
    var rTx = $("#ma-r-tx", root), rJson = $("#ma-r-json", root), mDrawer = $("#ma-manual", root), mTx = $("#ma-tx", root);
    var mSku = $("#ma-manual-sku", root), mVerify = $("#ma-verify-btn", root), dlCb = $("[data-ma-coinbase]", root), dlMm = $("[data-ma-metamask]", root);
    var provider = null, busy = false, checkSeq = 0;

    // 1. Lightweight Farcaster Mini-App / Frame v2 ready() handshake (zero external CDN script)
    window.__pactaMiniAppReady = true;
    try {
      if (window.parent && window.parent !== window && typeof window.parent.postMessage === "function") {
        window.parent.postMessage({ type: "fc:frame:ready", method: "ready", params: {} }, "*");
        window.parent.postMessage({ id: "pacta-fc-ready", type: "APPLY", path: ["actions", "ready"], argumentList: [{}] }, "*");
      }
    } catch (e) { /* standalone browser context */ }

    // 2. EIP-6963 / EIP-1193 / EIP-5792 Base wallet detection
    function setProvider(p, label) {
      if (!p || typeof p.request !== "function") return;
      provider = p;
      if (wPill) {
        wPill.textContent = label || (p.isCoinbaseWallet ? "Base / Coinbase Wallet Ready" : p.isMetaMask ? "MetaMask Ready" : "Embedded Wallet Ready");
        wPill.setAttribute("data-state", "ready");
      }
      if (typeof p.request === "function") {
        try {
          Promise.resolve(p.request({ method: "wallet_getCapabilities" })).then(function (caps) {
            if (caps && typeof caps === "object") root.setAttribute("data-eip5792", "true");
          }).catch(function () { /* standard EIP-1193 wallet */ });
        } catch (e) { /* ignore */ }
      }
    }
    window.addEventListener("eip6963:announceProvider", function (ev) {
      var d = ev && ev.detail;
      if (d && d.provider && (!provider || (d.info && /coinbase|base/i.test(d.info.name || "")))) {
        setProvider(d.provider, d.info && d.info.name ? d.info.name + " Ready" : "Base Wallet Ready");
      }
    });
    try { window.dispatchEvent(new Event("eip6963:requestProvider")); } catch (e) { /* synthetic DOM */ }
    if (!provider && window.ethereum && typeof window.ethereum.request === "function") setProvider(window.ethereum);
    if (!provider && wPill) { wPill.textContent = "Read-Only · Deep-Link Ready"; wPill.setAttribute("data-state", "readonly"); }

    function curChain() { return cHid && cHid.value === "ethereum" ? "ethereum" : "base"; }
    function setChain(ch) {
      var v = ch === "ethereum" ? "ethereum" : "base";
      if (cHid) cHid.value = v;
      segBtns.forEach(function (b) { b.setAttribute("aria-checked", String(b.getAttribute("data-ma-chain") === v)); });
      syncMaLinks();
    }
    function syncMaLinks() {
      var a = String((cAddr && cAddr.value) || "").trim(), ch = curChain();
      var qs = CO_ADDR.test(a) ? "?chain=" + ch + "&address=" + a : "";
      var canon = "/miniapp/" + qs;
      if (dlMm) dlMm.setAttribute("href", "https://metamask.app.link/dapp/pacta.wtf" + canon);
      if (dlCb) dlCb.setAttribute("href", "https://go.cb-wallet.com/dapp?cb_url=" + encodeURIComponent("https://pacta.wtf" + canon));
    }
    segBtns.forEach(function (b) {
      b.addEventListener("click", function () { if (!busy) setChain(b.getAttribute("data-ma-chain")); });
    });
    if (cAddr) cAddr.addEventListener("input", syncMaLinks);

    // Optional ?chain=&address= URL prefill
    try {
      var q0 = new URLSearchParams(location.search || ""), qCh = q0.get("chain"), qAd = q0.get("address");
      if (qCh === "ethereum" || qCh === "base") setChain(qCh);
      if (cAddr && CO_ADDR.test(String(qAd || ""))) { cAddr.value = String(qAd); cAddr.setAttribute("value", String(qAd)); }
    } catch (e) { /* ignore */ }
    syncMaLinks();

    function showAddrErr(msg) {
      if (cErr) { cErr.textContent = msg || ""; cErr.hidden = !msg; }
      if (cAddr) { if (msg) cAddr.setAttribute("aria-invalid", "true"); else cAddr.removeAttribute("aria-invalid"); }
    }
    function fmtDelaySec(sec) {
      var n = Number(sec || 0);
      if (!n || n <= 0) return "0 s (no delay)";
      if (n % 86400 === 0) return (n / 86400) + "d (" + n + " s)";
      if (n % 3600 === 0) return (n / 3600) + "h (" + n + " s)";
      return n + " s";
    }
    function renderMaVerdict(ch, addr, pf, catIt) {
      var cls = catIt && catIt.classification;
      // a protocol the corrections registry marks Unresolved / Changed recently is never shown as a documentation difference
      var neutral = catIt && (catIt.scorecardStatus === "unresolved" || catIt.scorecardStatus === "recent_change" || catIt.scorecardStatus === "docs_updated");
      var status = !catIt ? "UNINDEXED" : neutral ? ({ unresolved: "UNRESOLVED", recent_change: "CHANGED RECENTLY", docs_updated: "DOCS UPDATED" })[catIt.scorecardStatus]
        : (cls === "parameter_delta" || cls === "mixed" ? "DOCUMENTATION DIFFERENCE" : "ALIGNED");
      var tone = status === "ALIGNED" ? "aligned" : status === "DOCUMENTATION DIFFERENCE" ? "delta" : "unindexed";
      if (vSec) vSec.setAttribute("data-ma-status", status);
      if (vPill) { vPill.textContent = status; vPill.setAttribute("data-tone", tone); }
      var chainLbl = ch === "base" ? "Base" : "Ethereum";
      if (vTitle) vTitle.textContent = (catIt && catIt.name ? catIt.name : short(addr, 6, 4)) + " · " + chainLbl;
      if (vBadge) {
        if (catIt && catIt.slug) {
          vBadge.setAttribute("src", badgeBase + catIt.slug + ".svg");
          vBadge.setAttribute("alt", "Pacta verification: " + status);
          vBadge.hidden = false;
        } else {
          vBadge.hidden = true;
        }
      }
      var ctl = (pf && (pf.controller || pf.controllerSummary)) || {};
      var ctlTxt = ctl.kind === "multisig_safe" && ctl.safeThreshold ? ctl.safeThreshold + "-of-" + ctl.safeOwnerCount + " Safe"
        : ctl.kind === "timelock" ? "Timelock" + (ctl.address ? " " + short(ctl.address, 6, 4) : "")
        : ctl.kind === "eoa" ? "EOA" + (ctl.address ? " " + short(ctl.address, 6, 4) : "")
        : pf && pf.verdict === "IMMUTABLE_NO_ADMIN" ? "No upgrade/admin slot" : (ctl.kind || "Contract");
      var dSec = ctl.timelockDelaySec != null ? ctl.timelockDelaySec : (pf && pf.timelockDelaySec != null ? pf.timelockDelaySec : null);
      var hScore = pf && typeof pf.riskScore === "number" ? " · Heuristic score " + pf.riskScore + "/100" : "";
      if (vSum) {
        vSum.textContent = (pf && (pf.summary || pf.oneLineVerdict) ? String(pf.summary || pf.oneLineVerdict)
          : "Block-pinned control-plane read completed.") + hScore;
      }
      if (vTarget) vTarget.textContent = ch + ":" + short(addr, 6, 4) + (pf && pf.block && pf.block.number ? " @ #" + pf.block.number : "");
      if (vCtrl) vCtrl.textContent = ctlTxt;
      if (vDelay) vDelay.textContent = dSec != null ? fmtDelaySec(dSec) : (pf && pf.verdict === "IMMUTABLE_NO_ADMIN" ? "Immutable" : "0 s (no timelock)");
      if (vProv) {
        vProv.textContent = "";
        if (catIt && catIt.slug) {
          vProv.appendChild(el("a", { href: "../protocols/" + catIt.slug + "/", text: "Published scorecard" }));
        } else {
          vProv.textContent = "Live RPC read (unindexed)";
        }
      }
    }

    function runMaCheck() {
      var a = String((cAddr && cAddr.value) || "").trim(), ch = curChain();
      if (!CO_ADDR.test(a)) {
        showAddrErr("Enter a 0x address: 0x followed by 40 hexadecimal characters.");
        if (cAddr && cAddr.focus) cAddr.focus();
        return;
      }
      showAddrErr("");
      syncMaLinks();
      var my = ++checkSeq;
      if (cSub) cSub.disabled = true;
      if (vSum) vSum.textContent = "Reading " + short(a, 6, 4) + " on " + (ch === "base" ? "Base" : "Ethereum") + "…";
      if (typeof window.pactaBeacon === "function") { try { window.pactaBeacon("live_checker_submit", ch + ":" + a.toLowerCase()); } catch (e) { /* ignore */ } }
      xTrackLead();
      var pfUrl = api + "/v1/check/preflight?chain=" + ch + "&address=" + a + "&caller_agent=" + checkerCallerAgent() + "&requester_role=individual_user&caller_purpose=general_research";
      Promise.all([
        fetch(pfUrl, { headers: { Accept: "application/json" } }).then(function (r) { return r.json().then(function (b) { return { s: r.status, b: b }; }); }),
        lookupData().catch(function () { return []; })
      ]).then(function (pair) {
        if (my !== checkSeq) return;
        if (cSub) cSub.disabled = false;
        var res = pair[0], lk = pair[1] || [];
        var body = res.b || {}, pf = body.verdict ? body : (body.result && body.result.verdict ? body.result : null);
        if (res.s !== 200 || !pf) {
          if (vSum) vSum.textContent = "Could not complete live check (HTTP " + res.s + "). Retry in a moment.";
          return;
        }
        var hit = lk.filter(function (x) {
          var pa = x.it && x.it.preflightArgs;
          return (pa && String(pa.address || "").toLowerCase() === a.toLowerCase()) || (pf.indexedProtocol && x.slug === pf.indexedProtocol.slug);
        })[0];
        var catIt = (hit && hit.it) || pf.indexedProtocol || null;
        renderMaVerdict(ch, a, pf, catIt);
      }).catch(function () {
        if (my !== checkSeq) return;
        if (cSub) cSub.disabled = false;
        if (vSum) vSum.textContent = "Network error while reading the control plane. Check your connection and retry.";
      });
    }

    if (cForm) cForm.addEventListener("submit", function (ev) { ev.preventDefault(); if (!busy) runMaCheck(); });
    presets.forEach(function (b) {
      b.addEventListener("click", function () {
        if (busy) return;
        setChain(b.getAttribute("data-chain"));
        if (cAddr) cAddr.value = b.getAttribute("data-address") || "";
        runMaCheck();
      });
    });

    // 3. 1-tap Base USDC upgrade ($19 Scan / $99 Seal) -> Base 0x2105 USDC transfer -> /v1/orders/verify
    function setPayStatus(msg, bad) {
      if (!pStatus) return;
      pStatus.textContent = msg || "";
      if (bad) pStatus.setAttribute("data-bad", ""); else pStatus.removeAttribute("data-bad");
    }
    function setMaBusy(on) {
      busy = on;
      [bScan, bSeal, cSub, mVerify, cAddr, mContact, mTx, mSku].concat(segBtns).concat(presets).forEach(function (x) { if (x) x.disabled = on; });
    }
    function verifyMaOrder(order, skuObj, retries) {
      setPayStatus("Verifying Base USDC receipt…");
      fetch(verifyApi, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(order) })
        .then(function (r) {
          var replay = !!(r.headers && typeof r.headers.get === "function" && r.headers.get("Pacta-Idempotent-Replay") === "true");
          return r.text().then(function (t) { var j = null; try { j = JSON.parse(t); } catch (e) { j = null; } return { s: r.status, j: j, replay: replay }; });
        })
        .then(function (x) {
          if (x.s === 200 && x.j && typeof x.j === "object") {
            setMaBusy(false);
            var oid = x.j.order_id || x.j.orderId || x.j.id || "—";
            if (rSku) rSku.textContent = skuObj.label + " · " + skuObj.amount + " USDC";
            if (rOrd) rOrd.textContent = String(oid).slice(0, 80);
            if (rTx) {
              rTx.textContent = "";
              rTx.appendChild(arrowLink({ href: "https://basescan.org/tx/" + order.tx_hash, target: "_blank", rel: "noopener" }, "tx " + short(order.tx_hash, 6, 4), "up-right"));
            }
            if (rJson) rJson.textContent = JSON.stringify(x.j, null, 2);
            if (rBox) rBox.hidden = false;
            setPayStatus("Verified on Base. Your deliverable receipt is unlocked below.");
            xTrackPurchase(x.j, skuObj, x.replay, order.tx_hash);
            return;
          }
          var code = x.j && typeof x.j.error === "string" ? x.j.error : "";
          if (retries > 0 && (x.s === 202 || x.s === 425 || CO_RETRY.test(code))) {
            setPayStatus("Waiting for Base confirmation…");
            setTimeout(function () { verifyMaOrder(order, skuObj, retries - 1); }, 4000);
            return;
          }
          setMaBusy(false);
          setPayStatus(CO_ERR[code] || ("Verification returned HTTP " + x.s + (code ? " (" + code + ")" : "") + "."), true);
        })
        .catch(function () {
          setMaBusy(false);
          setPayStatus("Could not reach the verifier. Keep your transaction hash and press Verify tx.", true);
        });
    }

    function startMaUpgrade(skuKey) {
      if (busy || !own(CO_SKU, skuKey)) return;
      var skuObj = CO_SKU[skuKey];
      var a = String((cAddr && cAddr.value) || "").trim(), ct = cleanText(String((mContact && mContact.value) || "").trim(), 200);
      if (!CO_ADDR.test(a)) { showAddrErr("Enter a 0x contract address above first."); if (cAddr && cAddr.focus) cAddr.focus(); return; }
      showAddrErr("");
      var ctErr = ct ? (coContactOk(ct) ? "" : "Use an https:// webhook, email, or @handle.") : (skuObj.needContact ? skuObj.contactMissing : "");
      if (mContactErr) { mContactErr.textContent = ctErr; mContactErr.hidden = !ctErr; }
      if (ctErr) { if (mContact && mContact.focus) mContact.focus(); return; }

      xTrackLead();
      var eth = provider || (window.ethereum && typeof window.ethereum.request === "function" ? window.ethereum : null);
      if (!eth) {
        if (mDrawer) mDrawer.setAttribute("open", "");
        if (mSku) mSku.value = skuKey;
        setPayStatus("Open in Coinbase / Base Wallet below, or send " + skuObj.amount + " Base USDC and paste the tx hash.");
        if (mTx && mTx.focus) mTx.focus();
        return;
      }
      var order = { sku: skuKey, chain: "base", target_chain: curChain(), target_address: a };
      if (ct) order.webhook_or_contact = ct;
      var from = "";
      setMaBusy(true);
      if (rBox) rBox.hidden = true;
      setPayStatus("Confirm " + skuObj.amount + " USDC on Base in your wallet…");
      eth.request({ method: "eth_requestAccounts" }).then(function (accs) {
        from = accs && accs[0] ? String(accs[0]) : "";
        if (!CO_ADDR.test(from)) throw new Error("no account");
        return eth.request({ method: "eth_chainId" });
      }).then(function (cid) {
        if (String(cid).toLowerCase() === CO_CHAIN) return cid;
        return eth.request({ method: "wallet_switchEthereumChain", params: [{ chainId: CO_CHAIN }] }).then(function () { return eth.request({ method: "eth_chainId" }); });
      }).then(function (cid) {
        if (String(cid).toLowerCase() !== CO_CHAIN) throw new Error("wrong chain");
        return eth.request({ method: "eth_sendTransaction", params: [{ from: from, to: CO_USDC, value: "0x0", data: coTransferData(skuObj.atomic) }] });
      }).then(function (txh) {
        if (!TX_RE.test(String(txh || ""))) throw new Error("no hash");
        order.tx_hash = String(txh);
        if (mTx) mTx.value = String(txh);
        if (mSku) mSku.value = skuKey;
        verifyMaOrder(order, skuObj, 15);
      }).catch(function (e) {
        setMaBusy(false);
        var code = e && e.code;
        setPayStatus(code === 4001 ? "Cancelled in wallet. Nothing was sent." : "Wallet transfer did not complete; you can also verify a manual tx below.", true);
      });
    }

    if (bScan) bScan.addEventListener("click", function () { startMaUpgrade("instant-scan-19"); });
    if (bSeal) bSeal.addEventListener("click", function () { startMaUpgrade("reverify-seal-99"); });
    if (dlCb) dlCb.addEventListener("click", xTrackLead);
    if (dlMm) dlMm.addEventListener("click", xTrackLead);
    if (mVerify) mVerify.addEventListener("click", function () {
      if (busy) return;
      var skuKey = (mSku && own(CO_SKU, mSku.value)) ? mSku.value : "instant-scan-19";
      var skuObj = CO_SKU[skuKey];
      var a = String((cAddr && cAddr.value) || "").trim(), txh = String((mTx && mTx.value) || "").trim();
      var ct = cleanText(String((mContact && mContact.value) || "").trim(), 200);
      if (!CO_ADDR.test(a)) { showAddrErr("Enter a 0x contract address above."); return; }
      if (!TX_RE.test(txh)) { setPayStatus("Paste a 64-hex 0x Base transaction hash.", true); return; }
      if (skuObj.needContact && !ct) { setPayStatus(skuObj.contactMissing, true); return; }
      xTrackLead();
      var order = { sku: skuKey, tx_hash: txh, chain: "base", target_chain: curChain(), target_address: a };
      if (ct) order.webhook_or_contact = ct;
      setMaBusy(true);
      verifyMaOrder(order, skuObj, 5);
    });
  }
  // ---- live pre-flight checker (free API; runs only on an explicit submit / preset click) ---------------
  var ADDR_RE = /^0x[0-9a-fA-F]{40}$/;
  var SLOT_IMPL = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc";
  var SLOT_BEACON = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50";
  var SLOT_PROXIABLE = "0xc5f16f0fcc639fa48a6947836d9850f504798523bf8c9a3a87d5876cf622bcf7";
  // V7: amber is for warnings only; neutral and good verdicts get the neutral badge
  var VERDICT_VARIANT = { IMMUTABLE_NO_ADMIN: "neutral", TIMELOCK_PROTECTED: "neutral", UNDEPLOYED_OR_EOA: "neutral", ZERO_DELAY_TIMELOCK_RISK: "warning",
    MULTISIG_NO_TIMELOCK: "warning", INSTANT_EOA_ADMIN_RISK: "warning", UNCLASSIFIED_CONTRACT_CONTROLLER: "warning" };
  function pfCasts(r) {
    var rpc = r.chain === "base" ? "$BASE_RPC_URL" : "$ETH_RPC_URL", b = " --block " + r.pinnedBlock + " --rpc-url " + rpc, c = [];
    c.push("cast block " + r.pinnedBlock + " --field hash --rpc-url " + rpc + (/^0x[0-9a-f]{64}$/.test(String(r.pinnedBlockHash || "")) ? "   # expect " + r.pinnedBlockHash : ""));
    c.push("cast code " + r.address + b);
    c.push("cast storage " + r.address + " " + (r.proxyType === "eip1822" ? SLOT_PROXIABLE : r.proxyType === "eip1967_beacon" ? SLOT_BEACON : SLOT_IMPL) + b);
    if (r.proxyType === "eip1967_beacon" && ADDR_RE.test(String(r.beacon || ""))) {
      c.push("cast call " + r.beacon + ' "implementation()(address)"' + b);
      c.push("cast call " + r.beacon + ' "owner()(address)"' + b);
    }
    c.push("cast call " + r.address + ' "owner()(address)"' + b);
    var k = r.controller || {};
    if (k.address && k.kind === "multisig_safe") {
      c.push("cast call " + k.address + ' "getThreshold()(uint256)"' + b);
      c.push("cast call " + k.address + ' "getOwners()(address[])"' + b);
    }
    if (k.address && k.kind === "timelock") c.push("cast call " + k.address + ' "getMinDelay()(uint256)"' + b);
    return c;
  }
  // Plain-English verdicts (the raw enum stays one click away, with the full JSON)
  var VERDICT_TEXT = { IMMUTABLE_NO_ADMIN: "No standard upgrade or admin authority detected", TIMELOCK_PROTECTED: "Changes wait behind a timelock",
    ZERO_DELAY_TIMELOCK_RISK: "Timelock with a zero delay: changes can land instantly", MULTISIG_NO_TIMELOCK: "A multisig can change it with no delay",
    INSTANT_EOA_ADMIN_RISK: "A single key can change it instantly", UNCLASSIFIED_CONTRACT_CONTROLLER: "Controller needs further review",
    UNDEPLOYED_OR_EOA: "No contract code at this address (EOA or not deployed)" };
  function verdictText(v) { return VERDICT_TEXT[v] || String(v); }
  function rawDetails(r) {
    return el("details", { "class": "acc pf-raw", "data-slot": "accordion-item", "data-pf-raw": "" }, [
      el("summary", { "data-slot": "accordion-trigger", text: "Raw verdict and JSON" }),
      el("div", { "data-slot": "accordion-content" }, [el("p", {}, [el("code", { text: String(r.verdict) })]), el("pre", { "class": "pf-json", text: JSON.stringify(r, null, 2) })])]);
  }
  // ---- one-click "Verify live on RPC": CORS public endpoints, first answer wins (fallback on error), latency in ms; text only
  var LIVE_RPCS = { ethereum: ["https://ethereum-rpc.publicnode.com", "https://eth.drpc.org"],
    base: ["https://base-rpc.publicnode.com", "https://mainnet.base.org"] };
  function rpcCall(chain, method, params) {
    var urls = LIVE_RPCS[chain === "base" ? "base" : "ethereum"], i = 0;
    function attempt() {
      var url = urls[i], t0 = Date.now();
      var opts = { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ jsonrpc: "2.0", id: 1, method: method, params: params }) };
      if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") { try { opts.signal = AbortSignal.timeout(8000); } catch (e) { /* none */ } }
      return fetch(url, opts).then(function (res) { return res.json(); }).then(function (j) {
        if (!j || j.error || j.result === undefined) throw new Error(j && j.error ? String(j.error.message || "rpc error") : "no result");
        return { result: j.result, ms: Date.now() - t0, rpc: url.replace(/^https:\/\//, "") };
      }).catch(function (e) { i++; if (i < urls.length) return attempt(); throw e; });
    }
    return attempt();
  }
  // every live read is pinned to one fresh block: eth_blockNumber first, then the read(s) at that exact hex block number
  var EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103";
  function liveBlock(chain) {
    return rpcCall(chain, "eth_blockNumber", []).then(function (x) {
      var hx = String(x.result).toLowerCase();
      if (!/^0x[0-9a-f]{1,16}$/.test(hx)) throw new Error("bad eth_blockNumber");
      return { hex: hx, n: parseInt(hx, 16), rpc: x.rpc, ms: x.ms };
    });
  }
  function hosts(a, b) { return a.rpc === b.rpc ? a.rpc : a.rpc + " + " + b.rpc; }
  // first 32-byte ABI word as uint256 (decimal) and, when it is a left-padded 20-byte value, as an address
  function decodeWord(hex) {
    var h = String(hex || "").replace(/^0x/i, "").toLowerCase();
    if (!/^[0-9a-f]*$/.test(h)) return "not hex";
    if (!h.length) return "empty (0 bytes)";
    var w = h.length >= 64 ? h.slice(0, 64) : (new Array(65 - h.length).join("0") + h);
    var dec = typeof BigInt === "function" ? BigInt("0x" + w).toString() : (/^0{51}/.test(w) ? String(parseInt(w, 16)) : "n/a");
    var t = "uint256 " + dec;
    if (/^0{24}/.test(w) && !/^0{32}/.test(w)) t += " = address 0x" + w.slice(24);
    if (h.length > 64) t += " (first of " + Math.ceil(h.length / 64) + " words)";
    return t;
  }
  function liveVerifyBtn(label, job) {
    var wrap = el("div", { "class": "live-verify", "data-live-verify": "" });
    var btn = el("button", { type: "button", "class": "btn sm", "data-live-verify-btn": "", text: label });
    var res = el("p", { "class": "live-verify-out", "data-live-verify-out": "", "aria-live": "polite" });
    btn.addEventListener("click", function () {
      if (typeof fetch !== "function") { res.textContent = "This browser cannot call an RPC; use the cast commands."; return; }
      res.textContent = "Calling a public RPC…";
      job().then(function (t) {
        res.textContent = "";
        [].concat(t).forEach(function (line) { res.appendChild(el("span", { "class": "lv-line", text: String(line) })); });
      }, function (e) { res.textContent = "Live RPC check failed (" + String(e && e.message || e) + "); use the cast commands."; });
    });
    wrap.appendChild(btn); wrap.appendChild(res);
    return wrap;
  }
  function pfRow(k, v) { return el("div", {}, [el("dt", { text: k }), el("dd", {}, [v])]); }
  function pfAddr(v) { return ADDR_RE.test(String(v || "")) ? el("span", {}, hexref(v, 8, 6)) : "none"; }
  // confidence framing next to the score: coverage (indexed_verified / unindexed_bytecode_heuristic), confidence, method, limits
  function pfAssess(out, r) {
    var a = r && r.assessment; if (!a || typeof a !== "object") return;
    var cov = a.coverage === "indexed_verified" ? "Indexed & verified record" : "Unindexed: bytecode heuristic only";
    out.appendChild(el("p", { "class": "pf-assess", "data-pf-assess": "" }, [el("b", { text: "Confidence " + String(a.confidence || "n/a") }),
      " · " + cov + (a.method ? " · " + String(a.method) : "")]));
    if (Array.isArray(a.limits) && a.limits.length) out.appendChild(el("p", { "class": "pf-assess", text: "Limits: " + a.limits.map(String).join(" ") }));
  }
  // the catalog classification in the site's one vocabulary (/methodology/#docs-vs-chain); a protocol whose records are mixed is
  // Delta as soon as one changed parameter is a parameter_delta (a protocol is Delta if any of its records is Delta)
  var DVC = { parameter_delta: ["Delta", "warning"], protective_delta: ["Protective", "info"], aligned_baseline: ["Aligned", "neutral"],
    rpc_observed: ["Observed", "outline"] };
  function docsVsChain(m) {
    var c = String(m.classification || ""), wd = m.whatDiffers || {};
    if (Object.prototype.hasOwnProperty.call(DVC, c)) return DVC[c];
    if (Array.isArray(wd.changed) && wd.changed.some(function (x) { return x && x.classification === "parameter_delta"; })) return DVC.parameter_delta;
    return null;
  }
  // v4.5 G-P2-6: a Changed line stays <= 140 characters (the full quote is on the record page) and a threshold line names its Safe
  // when the record's own text does ("Matched: Security Council Safe threshold 3-of-5")
  var WD_MAX = 140;
  function clip(s, max) {
    s = String(s); if (s.length <= max) return s;
    var c = s.slice(0, max - 1), i = c.lastIndexOf(" ");
    return (i > max / 2 ? c.slice(0, i) : c).replace(/[\s,;:(]+$/, "") + "…";
  }
  function safeLabel(value, texts) {
    var v = String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), name = "([A-Z][A-Za-z]+(?: [A-Z][A-Za-z]+){0,3})";
    var re = new RegExp(name + " (?:Safe |multisig )?" + v + "(?![0-9])|(?:^|[^0-9])" + v + " " + name);
    for (var i = 0; i < texts.length; i++) {
      var m = re.exec(String(texts[i] || "")), n = m ? String(m[1] || m[2] || "").replace(/ (Safe|Multisig|multisig)$/, "") : "";
      if (n && !/^(Safe|The|A|An|Multisig|Gnosis)$/.test(n)) return n;
    }
    return "";
  }
  function wdTexts(wd, rid) {
    var t = [];
    (wd.changed || []).forEach(function (c) { if (c && c.recordId === rid) t.push(c.parameter, c.observed, c.documented); });
    (wd.matched || []).forEach(function (c) { if (c && c.recordId === rid && c.parameter !== "Safe threshold") t.push(c.parameter); });
    return t;
  }
  function wdLine(kind, c, wd) {
    var lbl = c.parameter === "Safe threshold" ? safeLabel(kind === "Matched" ? c.value : c.documented, wdTexts(wd, c.recordId)) : "";
    var p = lbl ? lbl + " Safe threshold" : String(c.parameter);
    var line = kind === "Changed" ? "Changed: " + p + " " + String(c.observed) + " observed vs " + String(c.documented) + " documented"
      : "Matched: " + p + (lbl ? " " : ": ") + String(c.value);
    return kind === "Changed" && line.length > WD_MAX ? clip("Changed: " + p, WD_MAX) : clip(line, WD_MAX);
  }
  // R-V1 (v4.4): the indexed record answers "is this protocol's documentation accurate?", so it sits right under the metrics
  function pfMatch(out, m) {
    if (!m || typeof m !== "object" || !/^https:\/\/pacta\.wtf\/protocols\/[a-z0-9-]+\/$/.test(String(m.url || ""))) return;
    var dv = docsVsChain(m);
    var head = el("p", { "class": "pf-match-head" }, [el("b", { text: "Indexed by Pacta: " + String(m.name || m.slug) })]);
    if (dv) head.appendChild(el("span", { "data-slot": "badge", "data-variant": dv[1], "data-pf-dvc": "", text: "Docs vs chain: " + dv[0] }));
    var box = el("div", { "class": "pf-match", "data-pf-match": "" }, [head]);
    var wd = m.whatDiffers;
    if (wd && Array.isArray(wd.changed)) {
      wd.changed.forEach(function (c) { box.appendChild(el("p", { "data-pf-changed": "", text: wdLine("Changed", c, wd) })); });
      (wd.matched || []).forEach(function (c) { box.appendChild(el("p", { "data-pf-matched": "", text: wdLine("Matched", c, wd) })); });
    }
    box.appendChild(el("p", { "class": "pf-match-foot" }, [m.pinnedBlock ? "Record pinned at block " + num(m.pinnedBlock) + " · " : "",
      arrowLink({ href: siteUrl(m.url) }, "Full record")]));
    out.appendChild(box);
  }
  // live RPC unavailable for an indexed target: the Worker answers from the pinned catalog record (never a dead end)
  // live RPC unavailable for an indexed target: the Worker answers from the pinned catalog record (never a dead end)
  function pfFallback(out, b) {
    out.textContent = "";
    var card = el("div", { "data-slot": "card", "class": "pf-card", "data-pf-result": "" }, [
      el("div", { "class": "pf-verdict-row" }, [el("span", { "data-slot": "badge", "data-variant": "outline", text: "Pinned record" }),
        el("p", { "class": "pf-verdict-title pf-verdict", text: "Live RPC unavailable: showing the block-pinned record" })])]);
    pfAssess(card, b);
    card.appendChild(el("p", { text: String(b.summary || "") }));
    pfMatch(card, b.catalogMatch);
    appendWalletDepositPrompt(card);
    out.appendChild(card);
    notifyScanCheckComplete(b.chain || (b.catalogMatch && b.catalogMatch.chain), b.address);
  }
  // v4.4 (F3b): controller kinds in words, never a raw snake_case enum (the raw JSON stays one click away)
  var CTL_LABEL = { multisig_safe: "Safe multisig", timelock: "Timelock", eoa: "Single key (EOA)", contract: "Contract",
    access_control: "Role-based access control", none: "None" };
  function ctlLabel(kind) {
    var k = String(kind || "none");
    return Object.prototype.hasOwnProperty.call(CTL_LABEL, k) ? CTL_LABEL[k] : k.replace(/_/g, " ");
  }
  // U5 / R-V1 (v4.4): verdict, then score / confidence / coverage, then the indexed docs-vs-chain record (when the address is in the
  // catalog), one visible scope sentence, the summary and the facts; methodology and limits, cast commands and raw JSON are collapsed
  function pfRender(out, r) {
    out.textContent = "";
    var caps = r.capabilities || {}, k = r.controller || {}, v = String(r.verdict || ""), variant = VERDICT_VARIANT[v] || "warning";
    var capList = Object.keys(caps).filter(function (x) { return caps[x] === true; });
    var risk = typeof r.riskScore === "number" ? String(r.riskScore) + "/100" : "n/a";
    var a = r.assessment && typeof r.assessment === "object" ? r.assessment : {};
    var ctl = ctlLabel(k.kind);
    if (typeof k.safeThreshold === "number") ctl += " (" + k.safeThreshold + "-of-" + (typeof k.safeOwnerCount === "number" ? k.safeOwnerCount : "?") + ")";
    if (typeof k.timelockDelaySec === "number") ctl += " (" + secs(k.timelockDelaySec) + " delay)";
    if (typeof k.roleAdminCount === "number") ctl += " (" + k.roleAdminCount + " DEFAULT_ADMIN_ROLE members)";
    var addr = ADDR_RE.test(String(r.address || "")) ? String(r.address) : "";
    var card = el("div", { "data-slot": "card", "class": "pf-card", "data-pf-result": "" });
    card.appendChild(el("p", { "class": "pf-section", text: "Live contract check · " + (r.chain === "base" ? "Base" : "Ethereum") + " · block " + num(r.pinnedBlock) }));
    card.appendChild(el("div", { "class": "pf-verdict-row" }, [el("span", { "data-slot": "badge", "data-variant": variant, "data-pf-badge": "", text: variant === "warning" ? "Warning" : "Result" }),
      el("p", { "class": "pf-verdict-title pf-verdict", "data-pf-verdict": "", text: verdictText(v) })]));
    card.appendChild(el("dl", { "class": "pf-metrics" }, [
      el("div", {}, [el("dt", { text: "Heuristic score" }), el("dd", { "data-pf-risk": "", text: risk })]),
      el("div", {}, [el("dt", { text: "Confidence" }), el("dd", { text: String(a.confidence || "n/a") })]),
      el("div", {}, [el("dt", { text: "Covers" }), el("dd", { text: "This address only" })])]));
    pfMatch(card, r.catalogMatch);
    card.appendChild(el("p", { "class": "pf-scope", "data-pf-scope": "", text: "The verdict and heuristic score cover only this one contract address"
      + (addr ? " (" + short(addr, 6, 4) + ")" : "") + ", not the whole protocol." }));
    if (r.summary) card.appendChild(el("p", { "class": "s", text: String(r.summary) }));
    card.appendChild(el("dl", { "class": "pf-dl" }, [
      pfRow("Chain / block", (r.chain === "base" ? "Base" : "Ethereum") + " · block " + num(r.pinnedBlock)),
      pfRow("Contract", pfAddr(r.address)),
      pfRow("Proxy", r.isProxy ? "yes" : "no"),
      pfRow("Implementation", pfAddr(r.implementation)),
      pfRow("Controller", ADDR_RE.test(String(k.address || "")) ? el("span", {}, [ctl + " ", pfAddr(k.address)]) : ctl),
      pfRow("Zero-delay upgrade", r.canUpgradeZeroDelay === true ? "yes" : r.canUpgradeZeroDelay === false ? "no" : "unknown"),
      pfRow("Capabilities", capList.length ? capList.map(function (x) { return String(x).replace(/_/g, " "); }).join(", ") : "none seen"),
      pfRow("Paused", r.paused === true ? "yes" : r.paused === false ? "no" : "n/a"),
      pfRow("Pinned block hash", /^0x[0-9a-f]{64}$/.test(String(r.pinnedBlockHash || "")) ? el("span", {}, hexref(r.pinnedBlockHash, 10, 6)) : "n/a"),
      pfRow("Checked at (UTC)", typeof r.checkedAt === "string" ? r.checkedAt : (typeof r.blockTimestamp === "number" ? new Date(r.blockTimestamp * 1000).toISOString() : "n/a"))]));
    var acc = el("div", { "data-slot": "accordion" }), lim = el("div", { "data-slot": "accordion-content" });
    pfAssess(lim, r);
    lim.appendChild(el("p", { "class": "pf-assess", text: "A protocol's Docs-vs-chain status is on its scorecard: a protocol can be Delta while one of its "
      + "contracts has no admin, and an Aligned protocol can still have a contract a multisig can change." }));
    lim.appendChild(el("p", { "class": "pf-assess" }, [arrowLink({ href: siteUrl("https://pacta.wtf/methodology/#live-checker") },
      "How the heuristic score differs from Docs vs chain")]));
    acc.appendChild(el("details", { "class": "acc pf-limits", "data-slot": "accordion-item", "data-pf-limits": "" },
      [el("summary", { "data-slot": "accordion-trigger", text: "Methodology & single-address scope limits" }), lim]));
    if (r.isContract !== false && addr && /^\d+$/.test(String(r.pinnedBlock)))
      acc.appendChild(accItem("Reproduce with cast (pinned block)", [term(pfCasts(r).join("\n"), "Foundry cast", "Copy the cast commands for " + addr)]));
    acc.appendChild(rawDetails(r));
    card.appendChild(acc);
    if (/^\d+$/.test(String(r.pinnedBlock)))
      card.appendChild(liveVerifyBtn("Verify live on RPC", function () {
        var ch = r.chain === "base" ? "base" : "ethereum", want = String(r.pinnedBlockHash || "").toLowerCase();
        function fail(what) { return function (e) { return what + " failed (" + String(e && e.message || e) + ")"; }; }
        var pinned = rpcCall(ch, "eth_getBlockByNumber", ["0x" + Number(r.pinnedBlock).toString(16), false]).then(function (x) {
          var h = String(x.result && x.result.hash).toLowerCase();
          return "Pinned block #" + r.pinnedBlock + " hash " + h + (want ? (h === want ? " matches the pinned hash" : " differs from the pinned hash " + want) : "")
            + " · " + x.rpc + " · " + x.ms + " ms";
        }, fail("Pinned block check"));
        var live = !addr ? Promise.resolve("Live read skipped: no contract address") : liveBlock(ch).then(function (b) {
          return rpcCall(ch, "eth_getCode", [addr, b.hex]).then(function (c) {
            var bytes = Math.max(0, String(c.result).length - 2) / 2, ms = b.ms + c.ms;
            var head = "Live at block #" + b.n + " (" + b.hex + "): eth_getCode " + bytes + " bytes";
            if (!bytes) return [head + " (no contract code)", hosts(b, c) + " · " + ms + " ms"];
            var what = r.isProxy ? "EIP-1967 admin slot" : "owner()";
            var read = r.isProxy ? rpcCall(ch, "eth_getStorageAt", [addr, EIP1967_ADMIN_SLOT, b.hex])
              : rpcCall(ch, "eth_call", [{ to: addr, data: "0x8da5cb5b" }, b.hex]);
            return read.then(function (y) {
              return [head, what + ": " + String(y.result), "Decoded: " + decodeWord(y.result), hosts(b, y) + " · " + (ms + y.ms) + " ms"];
            }, function (e) { return [head, what + ": no answer (" + String(e && e.message || e) + ")", hosts(b, c) + " · " + ms + " ms"]; });
          });
        }, fail("Live block read"));
        return Promise.all([pinned, live]).then(function (x) { return [].concat(x[0], x[1]); });
      }));
    appendWalletDepositPrompt(card);
    out.appendChild(card);
    notifyScanCheckComplete(r.chain, r.address);
  }

  // ---- Multicall3 Wallet & Gnosis Safe Exposure Scanner (Worker /v1/check/wallet-exposure + browser-direct fallback) ----
  var MULTICALL3_ADDR = "0xcA11bde05977b3631167028862bE2a173976CA11";
  var WL_TOKENS = null, WL_LOADING = null, pfFocusForWallet = null;
  function walletTokensData() {
    if (WL_TOKENS) return Promise.resolve(WL_TOKENS);
    if (WL_LOADING) return WL_LOADING;
    if (typeof fetch !== "function") return Promise.resolve(null);
    var box = $(".pf[data-wallet-tokens]");
    var url = (box && box.getAttribute("data-wallet-tokens")) || (BASE + "/api/v1/wallet-tokens.json");
    WL_LOADING = fetch(url, { headers: { Accept: "application/json" } }).then(function (r) {
      if (!r.ok) throw new Error("wallet catalog HTTP " + r.status);
      return r.json();
    }).then(function (d) {
      WL_TOKENS = d && typeof d === "object" ? d : null;
      return WL_TOKENS;
    }).catch(function () { WL_LOADING = null; return null; });
    return WL_LOADING;
  }
  function u256Word(n) {
    var s = Number(n).toString(16);
    return ("0000000000000000000000000000000000000000000000000000000000000000" + s).slice(-64);
  }
  function encodeAggregate3(calls) {
    var heads = "", tails = "", off = calls.length * 32;
    for (var i = 0; i < calls.length; i++) {
      var c = calls[i], d = String(c.callData || "0x").slice(2).toLowerCase();
      var byteLen = d.length / 2, rem = d.length % 64;
      var padded = rem === 0 ? d : d + new Array(65 - rem).join("0");
      heads += u256Word(off);
      var tPad = ("000000000000000000000000" + String(c.target || "").slice(2).toLowerCase()).slice(-64);
      var elem = tPad + u256Word(c.allowFailure ? 1 : 0) + u256Word(96) + u256Word(byteLen) + padded;
      tails += elem;
      off += elem.length / 2;
    }
    return "0x82ad56cb" + u256Word(32) + u256Word(calls.length) + heads + tails;
  }
  function decodeAggregate3(rawHex) {
    if (typeof rawHex !== "string" || rawHex.indexOf("0x") !== 0 || rawHex.length < 130) return null;
    var h = rawHex.slice(2).toLowerCase();
    var arrOff = parseInt(h.slice(0, 64), 16);
    var arrStart = arrOff * 2;
    if (!(arrStart >= 0) || arrStart + 64 > h.length) return null;
    var len = parseInt(h.slice(arrStart, arrStart + 64), 16);
    var base = arrStart + 64;
    if (!(len >= 0 && len <= 1000) || base + len * 64 > h.length) return null;
    var out = [];
    for (var i = 0; i < len; i++) {
      var rel = parseInt(h.slice(base + i * 64, base + (i + 1) * 64), 16);
      var t = base + rel * 2;
      if (!(t >= 0) || t + 128 > h.length) return null;
      var success = !/^0+$/.test(h.slice(t, t + 64));
      var dOff = parseInt(h.slice(t + 64, t + 128), 16);
      var dStart = t + dOff * 2;
      if (!(dStart >= 0) || dStart + 64 > h.length) return null;
      var dLen = parseInt(h.slice(dStart, dStart + 64), 16);
      if (!(dLen >= 0) || dStart + 64 + dLen * 2 > h.length) return null;
      out.push({ success: success, returnData: "0x" + h.slice(dStart + 64, dStart + 64 + dLen * 2) });
    }
    return out;
  }
  function decodeOwnersArray(rawHex) {
    if (typeof rawHex !== "string" || rawHex.indexOf("0x") !== 0 || rawHex.length < 130) return null;
    var h = rawHex.slice(2).toLowerCase();
    var off = parseInt(h.slice(0, 64), 16) * 2;
    if (!(off >= 0) || off + 64 > h.length) return null;
    var len = parseInt(h.slice(off, off + 64), 16);
    if (!(len >= 1 && len <= 100) || off + 64 + len * 64 > h.length) return null;
    var owners = [];
    for (var i = 0; i < len; i++) {
      var w = h.slice(off + 64 + i * 64, off + 64 + (i + 1) * 64);
      if (!/^0{24}[0-9a-f]{40}$/.test(w)) return null;
      owners.push("0x" + w.slice(24));
    }
    return owners;
  }
  function decodeErc20Symbol(rawHex) {
    if (typeof rawHex !== "string" || rawHex.indexOf("0x") !== 0 || rawHex.length < 66) return null;
    var h = rawHex.slice(2), hexBytes = "";
    if (h.length === 64) {
      hexBytes = h.replace(/(?:00)+$/, "");
    } else if (h.length >= 128) {
      var off = parseInt(h.slice(0, 64), 16) * 2;
      if (!(off >= 0) || off + 64 > h.length) return null;
      var byteLen = parseInt(h.slice(off, off + 64), 16);
      if (!(byteLen >= 1 && byteLen <= 32) || off + 64 + byteLen * 2 > h.length) return null;
      hexBytes = h.slice(off + 64, off + 64 + byteLen * 2);
    } else return null;
    if (!hexBytes || hexBytes.length % 2 !== 0 || hexBytes.length > 64) return null;
    var out = "";
    for (var i = 0; i < hexBytes.length; i += 2) {
      var code = parseInt(hexBytes.slice(i, i + 2), 16);
      if (code === 0) break;
      if (code < 32 || code > 126) return null;
      out += String.fromCharCode(code);
    }
    var s = out.trim();
    return s.length >= 1 && s.length <= 28 ? s : null;
  }
  function formatTokenUnits(rawBig, decimals) {
    if (typeof BigInt !== "function") return String(rawBig);
    var b = BigInt(rawBig);
    if (decimals === 0) return b.toString();
    var p = "1" + new Array(decimals + 1).join("0");
    var base = BigInt(p), whole = b / base, rem = (b % base).toString();
    var frac = new Array(Math.max(0, decimals - rem.length) + 1).join("0") + rem;
    var keep = whole >= BigInt(1000) ? 2 : whole >= BigInt(1) ? 4 : 6;
    var trimmed = frac.slice(0, Math.min(decimals, keep)).replace(/0+$/, "");
    var wholeFmt = whole.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
    return trimmed ? wholeFmt + "." + trimmed : wholeFmt;
  }
  function verdictGradeFromScore(sc) {
    return sc <= 20 ? "A" : sc <= 40 ? "B" : sc <= 60 ? "C" : sc <= 80 ? "D" : "F";
  }
  function buildWalletExposureResult(wallet, custody, blocks, positions, protosMap, extra) {
    var rank = { DELTA: 0, OBSERVED: 1, PROTECTIVE: 2, ALIGNED: 3 };
    var allPos = positions.slice().sort(function (a, b) {
      var ra = rank[a.status] !== undefined ? rank[a.status] : 9, rb = rank[b.status] !== undefined ? rank[b.status] : 9;
      var da = typeof a.observedDelaySeconds === "number" ? a.observedDelaySeconds : 1e12;
      var db = typeof b.observedDelaySeconds === "number" ? b.observedDelaySeconds : 1e12;
      return (ra - rb) || (da - db) || String(a.slug).localeCompare(String(b.slug));
    });
    var alignedCount = 0, protectiveCount = 0, adverseGapCount = 0, observedCount = 0, delays = [], risks = [];
    allPos.forEach(function (p) {
      if (p.status === "ALIGNED") { alignedCount++; risks.push(p.observedDelaySeconds !== null && p.observedDelaySeconds >= 86400 ? 10 : 20); }
      else if (p.status === "PROTECTIVE") { protectiveCount++; risks.push(15); }
      else if (p.status === "DELTA") {
        adverseGapCount++;
        risks.push(p.observedDelaySeconds === 0 ? 85 : (p.observedDelaySeconds !== null && p.observedDelaySeconds < 86400 ? 75 : 65));
      } else { observedCount++; risks.push(45); }
      if (typeof p.observedDelaySeconds === "number") delays.push(p.observedDelaySeconds);
    });
    var total = allPos.length;
    var shortestSec = delays.length ? Math.min.apply(null, delays) : null;
    var maxR = risks.length ? Math.max.apply(null, risks) : 0;
    var avgR = risks.length ? risks.reduce(function (s, x) { return s + x; }, 0) / risks.length : 0;
    var riskScore = total === 0 ? 0 : Math.min(100, Math.round(maxR * 0.65 + avgR * 0.35 + (adverseGapCount >= 2 ? 8 : 0)));
    var grade = total === 0 ? "A" : verdictGradeFromScore(riskScore);
    var head = total === 0
      ? "No indexed DeFi positions detected in " + short(wallet, 6, 4) + " across Ethereum + Base Multicall3 scan"
      : "Found " + total + " active DeFi position" + (total === 1 ? "" : "s") + " in " + short(wallet, 6, 4)
        + " \u2014 " + (alignedCount + protectiveCount) + " ALIGNED, " + adverseGapCount + " FLAGGED"
        + (observedCount > 0 ? ", " + observedCount + " OBSERVED" : "");
    var flagged = allPos.filter(function (p) { return p.status === "DELTA" || p.status === "OBSERVED"; });
    var allBreakdowns = flagged.map(function (item) {
      var pr = (protosMap && protosMap[item.slug]) || {};
      var uid0 = (item.baseEasUids && item.baseEasUids[0]) || null;
      return {
        slug: item.slug,
        protocolName: item.protocolName,
        status: item.status,
        chain: item.chain,
        tokenAddress: item.tokenAddress,
        symbol: item.symbol,
        formattedBalance: item.formattedBalance,
        pinnedBlock: item.pinnedBlock,
        documentedDelaySeconds: item.documentedDelaySeconds,
        observedDelaySeconds: item.observedDelaySeconds,
        controllerAddress: pr.controllerAddress || null,
        controllerKind: pr.controllerKind || null,
        baseEasUids: item.baseEasUids || [],
        easScanUrl: uid0 ? "https://base.easscan.org/attestation/view/" + uid0 : null,
        scorecardUrl: item.scorecardUrl,
        summaryShort: pr.summary_short || "",
        whatDiffers: pr.whatDiffers || { changed: [], matched: [] }
      };
    });
    var deltas = allBreakdowns.filter(function (b) { return b.status === "DELTA"; });
    var topGap = deltas.length > 0 ? deltas[0] : null;
    var byCtrl = {}, sharedCtrls = [];
    allPos.forEach(function (p) {
      var pr = (protosMap && protosMap[p.slug]) || {};
      var ca = pr.controllerAddress ? String(pr.controllerAddress).toLowerCase() : "";
      if (!ca) return;
      if (!byCtrl[ca]) byCtrl[ca] = { address: pr.controllerAddress, kind: pr.controllerKind || "controller", protocols: [] };
      if (byCtrl[ca].protocols.indexOf(p.protocolName) < 0) byCtrl[ca].protocols.push(p.protocolName);
    });
    Object.keys(byCtrl).forEach(function (k) { if (byCtrl[k].protocols.length >= 2) sharedCtrls.push(byCtrl[k]); });
    var out = {
      schema: "pacta.wallet_exposure.v1",
      tier: "free_full",
      wallet: wallet,
      address: wallet,
      custody: custody || { isSafe: false, chains: [], threshold: null, ownerCount: null },
      blocks: blocks || { ethereum: null, base: null },
      summary: {
        totalPositions: total,
        alignedCount: alignedCount,
        protectiveCount: protectiveCount,
        adverseGapCount: adverseGapCount,
        observedCount: observedCount,
        portfolioRiskScore: riskScore,
        grade: grade,
        shortestExitWindowSec: shortestSec,
        headline: head
      },
      positions: allPos,
      topAdverseGapPreview: topGap,
      allGapBreakdowns: allBreakdowns,
      sharedControllers: sharedCtrls,
      lockedFlaggedPositionsCount: 0
    };
    if (extra) { Object.keys(extra).forEach(function (k) { out[k] = extra[k]; }); }
    return out;
  }
  function multicallBatchedChain(chain, mcAddr, blkHex, calls) {
    if (!calls.length) return Promise.resolve([]);
    var CHUNK = 450, chunks = [];
    for (var i = 0; i < calls.length; i += CHUNK) chunks.push(calls.slice(i, i + CHUNK));
    return Promise.all(chunks.map(function (ch) {
      return rpcCall(chain, "eth_call", [{ to: mcAddr, data: encodeAggregate3(ch) }, blkHex]).then(function (r) {
        var dec = decodeAggregate3(String(r.result || ""));
        if (!dec || dec.length !== ch.length) return ch.map(function () { return { success: false, returnData: "0x" }; });
        return dec;
      }).catch(function () {
        return ch.map(function () { return { success: false, returnData: "0x" }; });
      });
    })).then(function (parts) {
      var flat = [];
      parts.forEach(function (p) { p.forEach(function (x) { flat.push(x); }); });
      return flat;
    });
  }
  function scanChainDirect(chain, wallet, wt) {
    var mcAddr = (wt && wt.multicall3) || MULTICALL3_ADDR;
    var candidates = (wt && wt[chain]) || [];
    var protos = (wt && wt.protocols) || {};
    var padW = ("000000000000000000000000" + wallet.slice(2).toLowerCase()).slice(-64);
    var balData = "0x70a08231" + padW;
    return liveBlock(chain).then(function (blk) {
      var p1Calls = [
        { target: wallet, allowFailure: true, callData: "0xe75235b8" },
        { target: wallet, allowFailure: true, callData: "0xa0e67e2b" }
      ];
      candidates.forEach(function (c) { p1Calls.push({ target: c[0], allowFailure: true, callData: balData }); });
      return multicallBatchedChain(chain, mcAddr, blk.hex, p1Calls).then(function (p1) {
        var thR = p1[0], owR = p1[1];
        var th = thR && thR.success && /^0x[0-9a-fA-F]{64}$/.test(thR.returnData) ? parseInt(thR.returnData.slice(2), 16) : null;
        var owners = owR && owR.success ? decodeOwnersArray(owR.returnData) : null;
        var isSafe = !!(th !== null && th >= 1 && th <= 50 && owners && owners.length >= th);
        var hits = [];
        for (var i = 0; i < candidates.length; i++) {
          var r = p1[2 + i];
          if (r && r.success && r.returnData.length === 66 && /^0x[0-9a-fA-F]{64}$/.test(r.returnData)) {
            var nonZero = !/^0x0+$/.test(r.returnData);
            if (nonZero) hits.push({ addr: candidates[i][0], slug: candidates[i][1], symHint: candidates[i][2] || "", rawHex: r.returnData });
          }
        }
        if (!hits.length) {
          return { chain: chain, block: { number: blk.n, hash: null }, safe: isSafe ? { threshold: th, ownerCount: owners.length } : null, positions: [] };
        }
        var p2Calls = [];
        hits.forEach(function (h) {
          p2Calls.push({ target: h.addr, allowFailure: true, callData: "0x95d89b41" });
          p2Calls.push({ target: h.addr, allowFailure: true, callData: "0x313ce567" });
        });
        return multicallBatchedChain(chain, mcAddr, blk.hex, p2Calls).then(function (p2) {
          var pos = [];
          for (var j = 0; j < hits.length; j++) {
            var h = hits[j], symR = p2[2 * j], decR = p2[2 * j + 1];
            if (!decR || !decR.success || !/^0x[0-9a-fA-F]{64}$/.test(decR.returnData)) continue;
            var dec = parseInt(decR.returnData.slice(2), 16);
            if (!(dec >= 0 && dec <= 36)) continue;
            var onSym = symR && symR.success ? decodeErc20Symbol(symR.returnData) : null;
            if (!onSym) continue;
            var pr = protos[h.slug];
            if (!pr) continue;
            var rawVal = typeof BigInt === "function" ? BigInt(h.rawHex) : h.rawHex;
            pos.push({
              chain: chain,
              chainId: chain === "base" ? 8453 : 1,
              tokenAddress: h.addr,
              symbol: h.symHint || onSym,
              onchainSymbol: onSym,
              decimals: dec,
              rawBalance: String(rawVal),
              formattedBalance: formatTokenUnits(rawVal, dec),
              slug: h.slug,
              protocolName: pr.name,
              status: pr.status,
              classification: pr.classification,
              easAttested: !!pr.easAttested,
              pinnedBlock: pr.pinnedBlock || null,
              observedDelaySeconds: typeof pr.observedDelaySeconds === "number" ? pr.observedDelaySeconds : null,
              documentedDelaySeconds: typeof pr.documentedDelaySeconds === "number" ? pr.documentedDelaySeconds : null,
              baseEasUids: pr.baseEasUids || [],
              scorecardUrl: "https://pacta.wtf/protocols/" + h.slug + "/"
            });
          }
          return { chain: chain, block: { number: blk.n, hash: null }, safe: isSafe ? { threshold: th, ownerCount: owners.length } : null, positions: pos };
        });
      });
    });
  }
  function browserDirectWalletScan(wallet) {
    return walletTokensData().then(function (wt) {
      if (!wt) throw new Error("wallet catalog unavailable");
      return Promise.all([scanChainDirect("ethereum", wallet, wt), scanChainDirect("base", wallet, wt)]).then(function (crs) {
        var blocks = { ethereum: null, base: null }, safeChains = [], primarySafe = null, allPos = [];
        crs.forEach(function (cr) {
          blocks[cr.chain] = cr.block;
          if (cr.safe) {
            safeChains.push(cr.chain);
            if (!primarySafe || cr.safe.threshold > primarySafe.threshold) primarySafe = cr.safe;
          }
          cr.positions.forEach(function (p) { allPos.push(p); });
        });
        var custody = {
          isSafe: safeChains.length > 0,
          chains: safeChains,
          threshold: primarySafe ? primarySafe.threshold : null,
          ownerCount: primarySafe ? primarySafe.ownerCount : null
        };
        return buildWalletExposureResult(wallet, custody, blocks, allPos, wt.protocols, { source: "browser_multicall3" });
      });
    });
  }
  function demoWalletExposure(mode, wt) {
    var d = wt && wt.demos && wt.demos[mode];
    if (!d) return null;
    var protos = wt.protocols || {};
    var pos = (d.holdings || []).map(function (h) {
      var pr = protos[h.slug] || {};
      return {
        chain: h.chain,
        chainId: h.chain === "base" ? 8453 : 1,
        tokenAddress: h.address,
        symbol: h.symbol,
        onchainSymbol: h.symbol,
        decimals: 18,
        rawBalance: "1",
        formattedBalance: h.formattedBalance,
        slug: h.slug,
        protocolName: pr.name || h.slug,
        status: pr.status || "OBSERVED",
        classification: pr.classification || "rpc_observed",
        easAttested: !!pr.easAttested,
        pinnedBlock: pr.pinnedBlock || null,
        observedDelaySeconds: typeof pr.observedDelaySeconds === "number" ? pr.observedDelaySeconds : null,
        documentedDelaySeconds: typeof pr.documentedDelaySeconds === "number" ? pr.documentedDelaySeconds : null,
        baseEasUids: pr.baseEasUids || [],
        scorecardUrl: "https://pacta.wtf/protocols/" + h.slug + "/"
      };
    });
    return buildWalletExposureResult(d.wallet, d.custody, d.blocks, pos, protos, { isDemo: true, demoMode: mode, demoLabel: d.label });
  }
  function appendWalletDepositPrompt(card) {
    if (!$(".pf[data-wallet-scanner]")) return;
    var bar = el("div", { "class": "wl-proto-prompt", "data-wallet-proto-prompt": "" }, [
      el("span", { text: "Hold deposits here? Paste your wallet or Safe 0x\u2026 to scan all held positions." })
    ]);
    var btn = el("button", { type: "button", "data-slot": "button", "data-variant": "outline", "data-size": "sm", "data-focus-wallet-scan": "", text: "Scan Wallet / Safe \u2191" });
    btn.addEventListener("click", function () {
      if (typeof pfFocusForWallet === "function") pfFocusForWallet();
    });
    bar.appendChild(btn);
    card.appendChild(bar);
  }
  function wlToneOf(st) {
    if (st === "DELTA") return { lbl: "FLAGGED", tone: "gap" };
    if (st === "UNRESOLVED" || st === "CHANGED RECENTLY" || st === "DOCS UPDATED") return { lbl: st, tone: "observed" };   // neutral, never a gap
    if (st === "PROTECTIVE") return { lbl: "PROTECTIVE", tone: "protective" };
    if (st === "ALIGNED") return { lbl: "ALIGNED", tone: "aligned" };
    return { lbl: "PINNED", tone: "observed" };
  }
  function walletExposureRender(out, r) {
    out.textContent = "";
    var sum = r.summary || {}, cust = r.custody || {}, blks = r.blocks || {}, pos = r.positions || [];
    var card = el("div", { "data-slot": "card", "class": "pf-card wl-res-card", "data-wallet-result": r.demoMode || "live" });

    var topRow = el("div", { "class": "wl-res-top" });
    var badges = el("div", { "class": "wl-badges" });
    if (cust.isSafe) {
      badges.appendChild(el("span", {
        "class": "pf-st-pill wl-safe-pill", "data-tone": "protective", "data-wallet-safe-badge": "",
        text: "Gnosis Safe " + cust.threshold + "-of-" + cust.ownerCount + " detected"
      }));
    } else {
      badges.appendChild(el("span", { "class": "pf-st-pill", "data-tone": "aligned", text: "Multicall3 Read-Only Scan" }));
    }
    var pinParts = [];
    if (blks.ethereum && blks.ethereum.number) pinParts.push("ETH #" + num(blks.ethereum.number));
    if (blks.base && blks.base.number) pinParts.push("Base #" + num(blks.base.number));
    if (pinParts.length) badges.appendChild(el("span", { "class": "wl-pin-meta mono", text: pinParts.join(" \u00b7 ") }));
    topRow.appendChild(badges);
    if (r.isDemo) {
      topRow.appendChild(el("span", { "class": "wl-demo-tag mono", text: "INSTANT DEMO \u00b7 PASTE YOUR 0x\u2026 ABOVE FOR LIVE SCAN" }));
    }
    card.appendChild(topRow);

    card.appendChild(el("h3", { "class": "wl-headline", "data-wallet-headline": "", text: String(sum.headline || "") }));

    var exitSec = sum.shortestExitWindowSec;
    var exitTxt = exitSec === null || exitSec === undefined ? "No timelock gap seen"
      : exitSec === 0 ? "0s (instant admin path)" : secs(exitSec);
    var metrics = el("dl", { "class": "pf-metrics wl-metrics" }, [
      el("div", {}, [el("dt", { text: "Portfolio Risk Score" }), el("dd", { "data-wallet-risk": "", text: String(sum.portfolioRiskScore || 0) + "/100 \u00b7 Grade " + String(sum.grade || "A") })]),
      el("div", {}, [el("dt", { text: "Shortest Exit Window" }), el("dd", { "class": exitSec === 0 ? "wl-warn-txt" : "", "data-wallet-exit": "", text: exitTxt })]),
      el("div", {}, [el("dt", { text: "Held Breakdown" }), el("dd", { text: (Number(sum.alignedCount || 0) + Number(sum.protectiveCount || 0)) + " Aligned \u00b7 " + Number(sum.adverseGapCount || 0) + " Flagged" })])
    ]);
    card.appendChild(metrics);

    if (pos.length > 0) {
      var ul = el("ul", { "class": "wl-pos-list", "data-wallet-positions": "", "aria-label": "Detected DeFi positions" });
      pos.forEach(function (p) {
        var meta = wlToneOf(p.status), chLbl = p.chain === "base" ? "Base" : "Ethereum";
        var li = el("li", { "class": "wl-pos-pill", "data-pos-slug": p.slug, "data-pos-status": p.status }, [
          protoLogoImg(p.slug, "rc-logo", 18),
          el("a", { "class": "wl-pos-name", href: siteUrl(p.scorecardUrl || ("https://pacta.wtf/protocols/" + p.slug + "/")), text: p.protocolName }),
          el("span", { "class": "rc-sym", text: p.symbol + (p.formattedBalance ? " \u00b7 " + p.formattedBalance : "") }),
          el("span", { "class": "rc-chain", text: chLbl }),
          el("span", { "class": "pf-st-pill", "data-tone": meta.tone, text: meta.lbl })
        ]);
        ul.appendChild(li);
      });
      card.appendChild(ul);
    } else {
      var emptyRow = el("div", { "class": "wl-empty-row" }, [
        el("span", { text: "No balances detected across 883 indexed Ethereum & Base receipt tokens/vaults on this address." })
      ]);
      var tryDemo = el("button", { type: "button", "data-slot": "button", "data-variant": "outline", "data-size": "sm", text: "Preview Demo Treasury Safe" });
      tryDemo.addEventListener("click", function () {
        var dChip = $('[data-wallet-demo="demo_safe_eth_base"]');
        if (dChip) dChip.click();
      });
      emptyRow.appendChild(tryDemo);
      card.appendChild(emptyRow);
    }

    var allGaps = Array.isArray(r.allGapBreakdowns) ? r.allGapBreakdowns.slice() : [];
    if (!allGaps.length) {
      if (r.topAdverseGapPreview) allGaps.push(r.topAdverseGapPreview);
      pos.forEach(function (p) {
        if ((p.status === "DELTA" || p.status === "OBSERVED") && (!r.topAdverseGapPreview || p.slug !== r.topAdverseGapPreview.slug)) {
          var uid0 = (p.baseEasUids && p.baseEasUids[0]) || null;
          allGaps.push({
            slug: p.slug, protocolName: p.protocolName, status: p.status, chain: p.chain,
            symbol: p.symbol, formattedBalance: p.formattedBalance, pinnedBlock: p.pinnedBlock,
            documentedDelaySeconds: p.documentedDelaySeconds, observedDelaySeconds: p.observedDelaySeconds,
            easScanUrl: uid0 ? "https://base.easscan.org/attestation/view/" + uid0 : null,
            scorecardUrl: p.scorecardUrl, summaryShort: "", whatDiffers: { changed: [], matched: [] }
          });
        }
      });
    }
    if (allGaps.length > 0) {
      var gapWrap = el("div", { "class": "wl-gaps-stack", "data-wallet-all-gaps": String(allGaps.length) });
      allGaps.forEach(function (tg, idxGap) {
        var isObs = tg.status === "OBSERVED";
        var boxAttrs = { "class": isObs ? "wl-top-gap wl-obs-gap" : "wl-top-gap", "data-wallet-gap-item": tg.slug };
        if (idxGap === 0 && !isObs) boxAttrs["data-wallet-top-gap"] = tg.slug;
        var gapBox = el("div", boxAttrs);
        var kLbl = isObs
          ? "HELD RPC-OBSERVED POSITION #" + (idxGap + 1) + " \u00b7 DOCS NOT YET ASSESSED"
          : "#" + (idxGap + 1) + " HELD DELTA \u00b7 100% FREE FULL BREAKDOWN";
        var gapHead = el("div", { "class": "wl-gap-head" }, [
          el("span", { "class": "wl-gap-k mono", text: kLbl }),
          el("span", { "class": "wl-gap-links" }, [
            tg.pinnedBlock ? el("span", { "class": "mono", text: (tg.chain === "base" ? "Base" : "Ethereum") + " #" + num(tg.pinnedBlock) }) : "",
            tg.easScanUrl ? arrowLink({ href: tg.easScanUrl, target: "_blank", rel: "noopener" }, "Base EAS", "up-right") : "",
            arrowLink({ href: siteUrl(tg.scorecardUrl || ("https://pacta.wtf/protocols/" + tg.slug + "/")) }, "Scorecard")
          ])
        ]);
        gapBox.appendChild(gapHead);
        gapBox.appendChild(el("p", { "class": "wl-gap-title" }, [
          el("b", { text: tg.protocolName + " (" + tg.symbol + (tg.formattedBalance ? " \u00b7 " + tg.formattedBalance : "") + ")" }),
          tg.summaryShort ? " \u2014 " + tg.summaryShort : ""
        ]));
        var wd = tg.whatDiffers || {};
        if (Array.isArray(wd.changed) && wd.changed.length) {
          wd.changed.slice(0, 2).forEach(function (c) {
            gapBox.appendChild(el("p", { "class": "wl-gap-line wl-gap-changed", "data-pf-changed": "", text: wdLine("Changed", c, wd) }));
          });
        } else if (typeof tg.documentedDelaySeconds === "number" || typeof tg.observedDelaySeconds === "number") {
          gapBox.appendChild(el("p", { "class": "wl-gap-line wl-gap-changed", text: "Observed delay: " + (tg.observedDelaySeconds !== null ? secs(tg.observedDelaySeconds) : "unverified") + (tg.documentedDelaySeconds !== null ? " vs " + secs(tg.documentedDelaySeconds) + " documented" : "") }));
        }
        if (Array.isArray(wd.matched) && wd.matched.length) {
          gapBox.appendChild(el("p", { "class": "wl-gap-line wl-gap-matched", text: wdLine("Matched", wd.matched[0], wd) }));
        }
        gapWrap.appendChild(gapBox);
      });
      card.appendChild(gapWrap);
    }

    if (pos.length > 0) {
      var shared = Array.isArray(r.sharedControllers) ? r.sharedControllers : [];
      var exitNote = cust.isSafe
        ? "Custody check: " + cust.threshold + "-of-" + cust.ownerCount + " Gnosis Safe signing coordination vs " + exitTxt + " shortest upstream protocol exit window."
        : "Custody check: single-key / EOA holder vs " + exitTxt + " shortest upstream protocol exit window.";
      var overlapNote = shared.length > 0
        ? " Shared controller overlap: " + shared.map(function (sc) { return short(sc.address, 6, 4) + " (" + sc.protocols.join(" + ") + ")"; }).join("; ") + "."
        : " No shared admin controller address detected across these " + pos.length + " held positions.";
      card.appendChild(el("div", { "class": "wl-contagion-row", "data-wallet-contagion": "" }, [
        el("b", { text: "Exit-Window & Signer Overlap: " }),
        el("span", { text: exitNote + overlapNote })
      ]));
    }

    card.appendChild(buildInlineWatchWidget(r.wallet));

    if (Number(sum.adverseGapCount || 0) > 0 || Number(sum.observedCount || 0) > 0) {
      var b2b = el("div", { "class": "wl-inline-b2b", "data-wallet-b2b": "" }, [
        el("span", { text: "Curate or maintain one of these vaults? " }),
        arrowLink({ href: siteUrl("https://pacta.wtf/bounties/#sponsor-pool") }, "Fund a Verification Pool"),
        el("span", { text: " \u00b7 " }),
        arrowLink({ href: siteUrl("https://pacta.wtf/request/?tier=community") }, "Free 7-Day Fix Re-Check"),
        el("span", { text: " \u00b7 " }),
        arrowLink({ href: siteUrl("https://pacta.wtf/curators/") }, "Curator Exposure Matrix")
      ]);
      card.appendChild(b2b);
    }

    out.appendChild(card);
    var prefChain = (cust.chains && cust.chains.indexOf("base") >= 0) ? "base" : (pos[0] && pos[0].chain === "base" ? "base" : "ethereum");
    notifyScanCheckComplete(prefChain, r.wallet);
  }
  var PROTO_SVG_SLUGS = { "drakewell-usddw": 1, "wintermute-confidential-wbtc-ethereum": 1 };
  // Item 20: a ticker slot shows a token symbol, never a product word ("Lista", "Liquid"): these protocols show exactly this ticker
  var PROTO_TICKER_FIXED = { "lista-lending": "LISTA", "ether-fi-liquid-veda-boringvault": "ETHFI", "usdt0": "USDT0", "concentrator": "CTR",
    "autofinance": "TOKE", "team-finance": "TEAM", "harvest-finance": "FARM", "gmx-governor-trajectory": "GMX", "stake-dao": "SDT" };
  var PROTO_EXTRA_SYMS = {
    "augur": "REP", "autofinance": "TOKE", "baseline-protocol": "B", "bedrock-unibtc": "BR", "bedrock-unieth": "BR",
    "concrete": "CT", "curve-dex-ethereum": "CRV", "debridge": "DBR", "defi-saver": "DFS", "dexfi-aggregator": "GDEX",
    "dolomite": "DOLO", "dxsale": "DX", "equilibria": "EQB", "ethena-usdtb": "ENA", "ether-fi-liquid-veda-boringvault": "ETHFI",
    "exactly": "EXA", "falcon-finance-usdf-susdf": "FF", "frax-ether-sfrxeth": "FRAX", "frax-usd-frxusd": "FRAX", "glif": "GLF",
    "gravity-by-galxe-bridge": "G", "hyperlane": "HYPER", "infinifi": "INFI", "kelp-dao-rseth": "KERNEL", "lombard-lbtc": "BARD",
    "mantle-liquid-staking-meth-cmeth": "COOK", "meta-pool-eth": "MPDAO", "metamorpho-re7-weth-vs-re7-usdt": "MORPHO",
    "morpheusai": "MOR", "multichain": "MULTI", "pancakeswap-amm-v3": "CAKE", "polygon-bridge": "POL", "quickswap-v4": "QUICK",
    "sierra-protocol": "SIERRA", "sonic-gateway": "S", "superform-v2-base": "UP", "sushiswap-v3": "SUSHI", "synfutures-v3": "F",
    "wormhole-core-ntt": "W"
  };
  var FEATURED_COMBO_SLUGS = [
    "inverse-finance-firm", "moonwell-lending-base", "stader-labs-ethx", "ethena-usde-susde",
    "fluid-instadapp", "curve-finance-crvusd", "sonic-gateway", "usual-money-usd0-usd0",
    "cian-yield-layer", "lagoon", "aave-v3-gho", "lido-steth-dual-governance",
    "pendle-finance-v2", "morpho-blue-core", "spark-sky", "uniswap-v4",
    "circle-usdc", "pancakeswap-amm-v3"
  ];
  function protoIconSrc(slug) {
    return BASE + "/assets/protocols/" + slug + (PROTO_SVG_SLUGS[slug] ? ".svg" : ".webp");
  }
  function protoLogoImg(slug, cls, sz, explicitSrc) {
    var src = explicitSrc || protoIconSrc(slug);
    var img = el("img", { "class": cls, src: src, alt: "", width: String(sz), height: String(sz) });
    img.addEventListener("error", function () {
      var cur = img.getAttribute("src") || "";
      if (/\.webp$/.test(cur)) img.setAttribute("src", cur.slice(0, -5) + ".svg");
    });
    return img;
  }
  function chainBadgeSvg(chain, sz) {
    var ns = "http://www.w3.org/2000/svg", s = document.createElementNS(ns, "svg"), c = document.createElementNS(ns, "circle");
    s.setAttribute("viewBox", "0 0 16 16"); s.setAttribute("width", String(sz || 14)); s.setAttribute("height", String(sz || 14));
    s.setAttribute("aria-hidden", "true");
    c.setAttribute("cx", "8"); c.setAttribute("cy", "8"); c.setAttribute("r", "8");
    if (chain === "base") {
      s.setAttribute("class", "ch-ico ch-base"); c.setAttribute("fill", "#0052FF"); s.appendChild(c);
      var pb = document.createElementNS(ns, "path");
      pb.setAttribute("d", "M8.15 12.4A4.4 4.4 0 1 0 3.76 8.5h5.19v-1H3.76A4.4 4.4 0 0 1 8.15 3.6a4.4 4.4 0 0 1 0 8.8Z");
      pb.setAttribute("fill", "#fff"); s.appendChild(pb);
    } else {
      s.setAttribute("class", "ch-ico ch-eth"); c.setAttribute("fill", "#627EEA"); s.appendChild(c);
      [["M8 2.5 4.6 8.1 8 6.55l3.4 1.55L8 2.5Z", "0.9"], ["M8 6.55 4.6 8.1 8 10.15l3.4-2.05L8 6.55Z", "0.65"],
       ["M8 10.9 4.6 8.85 8 13.5l3.4-4.65L8 10.9Z", "0.9"]].forEach(function (pair) {
        var pe = document.createElementNS(ns, "path");
        pe.setAttribute("d", pair[0]); pe.setAttribute("fill", "#fff"); pe.setAttribute("fill-opacity", pair[1]);
        s.appendChild(pe);
      });
    }
    return s;
  }
  function protoTickerText(x) {
    if (PROTO_TICKER_FIXED[x.slug]) return PROTO_TICKER_FIXED[x.slug];
    var it = x.it || {}, raw = (it.tokens || []).slice(), ex = PROTO_EXTRA_SYMS[x.slug];
    if (ex) raw.unshift(ex);
    var seen = {}, clean = [], nmLow = String(it.name || "").toLowerCase();
    raw.forEach(function (t) {
      var s = String(t || "").trim();
      if (!s || /\s/.test(s) || s.length > 10) return;
      if (s.toLowerCase() === nmLow && s.length > 5) return;
      var k = s.toUpperCase();
      if (!seen[k]) { seen[k] = 1; clean.push(s); }
    });
    return clean.slice(0, 2).join(" \u00b7 ");
  }
  function protoStatusMeta(x) {
    var g = x.card && x.card.grade ? x.card.grade : "", cl = (x.it && x.it.classification) || "";
    // Unresolved / Changed recently (the corrections registry): neutral, never a GAP, whatever the attested classification
    var ns = (g === "unresolved" || g === "recent_change" || g === "docs_updated") ? g : (x.it && x.it.scorecardStatus) || "";
    if (ns === "unresolved" || ns === "recent_change" || ns === "docs_updated")
      return { label: ({ unresolved: "UNRESOLVED", recent_change: "CHANGED RECENTLY", docs_updated: "DOCS UPDATED" })[ns], tone: "observed", rank: 3 };
    if (g === "delta" || cl === "parameter_delta" || cl === "mixed") return { label: "DELTA", tone: "gap", rank: 0 };
    if (g === "protective" || cl === "protective_delta") return { label: "PROTECTIVE", tone: "protective", rank: 1 };
    if (g === "aligned" || cl === "aligned_baseline") return { label: "ALIGNED", tone: "aligned", rank: 2 };
    return { label: "PINNED", tone: "observed", rank: 3 };
  }
  function comboSearch(data, q, maxN) {
    var protos = (data || []).filter(function (x) {
      return x.it && x.it.kind === "protocol" && x.it.preflightArgs && ADDR_RE.test(String(x.it.preflightArgs.address || ""));
    });
    q = String(q || "").trim().toLowerCase().slice(0, 80);
    if (!q) {
      var byS = {};
      protos.forEach(function (x) { byS[x.slug] = x; });
      var feat = [];
      FEATURED_COMBO_SLUGS.forEach(function (s) { if (byS[s]) feat.push(byS[s]); });
      return feat.length ? feat : protos.slice(0, maxN || 18);
    }
    var qSlug = q.replace(/\s+/g, "-");
    var scored = [];
    protos.forEach(function (x) {
      var toks = x.comboTokens || x.tokens || [], words = x.name.split(/[^a-z0-9.]+/).filter(Boolean), r = -1;
      var shortToks = toks.filter(function (t) { return !/\s/.test(t); });
      if (/^0x[0-9a-f]{2,}$/.test(q)) {
        if (x.addrs.indexOf(q) >= 0) r = 0;
        else if (x.addrs.some(function (a) { return a.indexOf(q) === 0; })) r = 2;
      } else if (shortToks.indexOf(q) >= 0 || x.name === q || x.slug === q || words[0] === q) {
        r = 0;
      } else if (x.name.indexOf(q) === 0 || shortToks.some(function (t) { return t.indexOf(q) === 0; })) {
        r = 1;
      } else if (words.some(function (w) { return w.indexOf(q) === 0; }) || toks.some(function (t) { return t.indexOf(q) === 0; })) {
        r = 2;
      } else if (x.slug.indexOf(qSlug) >= 0 || x.name.indexOf(q) >= 0
                 || (q.length >= 2 && ((x.catLow && x.catLow.indexOf(q) >= 0) || (x.chainLow && x.chainLow.indexOf(q) === 0)))
                 || (q.length >= 3 && x.search && x.search.indexOf(q) >= 0)) {
        r = 3;
      }
      if (r >= 0) scored.push({ x: x, r: r, feat: FEATURED_COMBO_SLUGS.indexOf(x.slug) >= 0 ? 0 : 1, sr: protoStatusMeta(x).rank });
    });
    scored.sort(function (a, b) {
      return a.r - b.r || a.feat - b.feat || a.sr - b.sr || (a.x.name < b.x.name ? -1 : a.x.name > b.x.name ? 1 : 0);
    });
    return scored.slice(0, maxN || 25).map(function (m) { return m.x; });
  }
  function renderComboOption(x, idPrefix, idx) {
    var it = x.it, pa = it.preflightArgs || {}, ch = pa.chain === "base" ? "base" : "ethereum";
    var sym = protoTickerText(x), st = protoStatusMeta(x);
    var ava = el("span", { "class": "pf-opt-ava" }, [
      protoLogoImg(x.slug, "pf-opt-logo", 28),
      el("span", { "class": "pf-opt-ch" }, [chainBadgeSvg(ch, 12)])
    ]);
    var topKids = [el("span", { "class": "pf-opt-name", text: it.name })];
    if (sym) topKids.push(el("span", { "class": "pf-opt-sym", text: sym }));
    var subTxt = (ch === "base" ? "Base" : "Ethereum") + " \u00b7 "
      + (x.card && x.card.summary_short ? String(x.card.summary_short) : String(it.category || it.targetLabel || ""));
    var main = el("span", { "class": "pf-opt-main" }, [
      el("span", { "class": "pf-opt-top" }, topKids),
      el("span", { "class": "pf-opt-sub", text: subTxt })
    ]);
    var right = el("span", { "class": "pf-opt-right" }, [
      el("span", { "class": "pf-st-pill", "data-tone": st.tone, text: st.label }),
      el("span", { "class": "pf-opt-addr", text: short(String(pa.address || ""), 6, 4) })
    ]);
    return el("div", {
      "class": "pf-opt", role: "option", id: idPrefix + "-" + idx,
      "aria-selected": "false", "data-pf-opt": x.slug
    }, [ava, main, right]);
  }

  // U3/A3: noValidate form; 0x + 40 hex validated on blur and submit; the error is a visible message the input points to
  // (aria-invalid + aria-describedby); the button is disabled with a spinner while the check runs
  function initPreflight() {
    var box = $(".pf"), form = $("#pf-form"), out = $("#pf-out");
    if (!box || !form || !out) return;
    var api = box.getAttribute("data-api") || "", chainSel = $('select[name="chain"]', form), addr = $('input[name="address"]', form);
    if (!chainSel || !addr || !/^https:\/\//.test(api)) return;
    var err = $("#pf-addr-error"), btn = $("#pf-submit"), spin = btn ? $(".spinner", btn) : null, lbl = btn ? $("[data-pf-label]", btn) : null;
    var combo = $("[data-pf-combo]", form), listbox = $("#pf-listbox"), selChip = $("#pf-sel-chip");
    var clearBtn = $("#pf-combo-clear"), toggleBtn = $("#pf-combo-toggle"), toggleLbl = toggleBtn ? $(".pf-toggle-lbl", toggleBtn) : null;
    var chainIco = $("[data-pf-chain-ico]", form);
    var idleLbl = lbl && lbl.textContent ? lbl.textContent : "Check protocol";
    var help = addr.getAttribute("aria-describedby") || "pf-help";
    var seq = 0, ctl = null, timer = null, PF_TIMEOUT_MS = 10000;
    var comboHits = [], comboOpts = [], activeOpt = -1;

    function syncChainIcon() {
      if (!chainIco) return;
      chainIco.textContent = "";
      chainIco.appendChild(chainBadgeSvg(chainSel.value === "base" ? "base" : "ethereum", 14));
    }
    chainSel.addEventListener("change", syncChainIcon);
    syncChainIcon();

    function applySelectedOverlay(meta) {
      pfSelectedMeta = meta || null;
      if (!selChip) return;
      if (!meta) {
        selChip.hidden = true; selChip.textContent = "";
        if (toggleLbl) toggleLbl.textContent = "Protocols";
        var hasV = !!val();
        if (clearBtn) clearBtn.hidden = !hasV;
        if (combo) combo.setAttribute("data-has-clear", hasV ? "1" : "0");
        return;
      }
      selChip.textContent = "";
      var ava = el("span", { "class": "pf-sel-ava" }, [
        protoLogoImg(meta.slug, "pf-sel-logo", 24, meta.icon || ""),
        el("span", { "class": "pf-sel-ch" }, [chainBadgeSvg(meta.chain, 11)])
      ]);
      selChip.appendChild(ava);
      selChip.appendChild(el("span", { "class": "pf-sel-name", "data-pf-sel-name": "", text: meta.name }));
      if (meta.sym) selChip.appendChild(el("span", { "class": "pf-sel-sym", text: meta.sym }));
      selChip.appendChild(el("span", { "class": "pf-sel-addr", text: short(meta.address, 6, 4) }));
      selChip.hidden = false;
      if (clearBtn) clearBtn.hidden = false;
      if (combo) combo.setAttribute("data-has-clear", "1");
      if (toggleLbl) toggleLbl.textContent = "Switch";
    }
    pfSelectFromChip = function (b, ch, a) {
      var slug = b.getAttribute("data-pf-slug") || "";
      if (!slug) { applySelectedOverlay(null); syncChainIcon(); return; }
      syncChainIcon();
      closeCombo();
      applySelectedOverlay({
        slug: slug,
        name: b.getAttribute("data-pf-disp") || b.getAttribute("data-r-name") || slug,
        sym: b.getAttribute("data-pf-sym") || "",
        chain: ch,
        address: a,
        icon: b.getAttribute("data-pf-icon") || ""
      });
    };

    function setActiveOpt(i) {
      activeOpt = i;
      comboOpts.forEach(function (o, k) { o.setAttribute("aria-selected", String(k === i)); });
      if (comboOpts[i]) {
        addr.setAttribute("aria-activedescendant", comboOpts[i].id);
        if (comboOpts[i].scrollIntoView) { try { comboOpts[i].scrollIntoView({ block: "nearest" }); } catch (e) { /* ignore */ } }
      } else {
        addr.removeAttribute("aria-activedescendant");
      }
    }
    function closeCombo() {
      if (!listbox || listbox.hidden) return;
      listbox.hidden = true;
      addr.setAttribute("aria-expanded", "false");
      addr.removeAttribute("aria-activedescendant");
      if (combo) combo.removeAttribute("data-open");
      activeOpt = -1;
    }
    function selectComboItem(x) {
      if (!x || !x.it || !x.it.preflightArgs) return;
      var pa = x.it.preflightArgs, a = String(pa.address || ""), ch = pa.chain === "base" ? "base" : "ethereum";
      if (!ADDR_RE.test(a)) return;
      chainSel.value = ch;
      syncChainIcon();
      addr.value = a; addr.setAttribute("value", a);
      invalid("");
      closeCombo();
      applySelectedOverlay({ slug: x.slug, name: x.it.name, sym: protoTickerText(x), chain: ch, address: a });
      syncScanUpgradeTarget(ch, a);
      run();
    }
    function renderCombo(data, queryOverride) {
      if (!listbox) return;
      var q = queryOverride !== undefined ? queryOverride : (pfSelectedMeta ? "" : val());
      listbox.textContent = ""; comboHits = []; comboOpts = []; activeOpt = -1;
      if (!data) {
        listbox.appendChild(el("p", { "class": "pf-dd-empty", text: "Protocol catalog unavailable offline. Paste any 0x\u2026 contract address above." }));
        return;
      }
      var hits = comboSearch(data, q, q ? 25 : 18);
      comboHits = hits;
      var totalProtos = data.filter(function (x) { return x.it && x.it.kind === "protocol"; }).length;
      listbox.appendChild(el("div", { "class": "pf-dd-head" }, [
        el("span", { text: q ? "Matching protocols & tokens (" + hits.length + ")" : "Featured gaps & top protocols" }),
        el("span", { text: totalProtos + " indexed" })
      ]));
      if (!hits.length) {
        listbox.appendChild(el("p", { "class": "pf-dd-empty", "data-pf-dd-empty": "", text: "No indexed protocol or ticker matches \u201c" + q.slice(0, 40) + "\u201d. Paste any 0x\u2026 contract address to run a live check." }));
      } else {
        hits.forEach(function (x, k) {
          var row = renderComboOption(x, "pf-opt", k);
          row.addEventListener("mousedown", function (ev) { ev.preventDefault(); selectComboItem(x); });
          row.addEventListener("click", function () { selectComboItem(x); });
          listbox.appendChild(row);
          comboOpts.push(row);
        });
      }
      listbox.appendChild(el("div", { "class": "pf-dd-foot" }, [
        el("span", { text: q ? "\u2191\u2193 navigate \u00b7 Enter to check live \u00b7 Esc close" : "Type to search all " + totalProtos + "+ protocols & token symbols (AAVE, stETH, WELL, USDC\u2026)" }),
        el("span", { text: "or paste 0x\u2026" })
      ]));
      setActiveOpt(q && hits.length ? 0 : -1);
    }
    function openCombo(queryOverride) {
      if (!listbox || addr.disabled) return;
      if (typeof window !== "undefined" && window.innerWidth && window.innerWidth < 640 && window.innerHeight && addr.getBoundingClientRect) {
        try {
          var rect = addr.getBoundingClientRect();
          if (rect && rect.bottom > window.innerHeight * 0.52) {
            var scTarget = (box.closest && box.closest("#free-check")) || form;
            if (scTarget && scTarget.scrollIntoView) scTarget.scrollIntoView({ behavior: "smooth", block: "start" });
          }
        } catch (e) { /* ignore */ }
      }
      listbox.hidden = false;
      addr.setAttribute("aria-expanded", "true");
      if (combo) combo.setAttribute("data-open", "1");
      if (LK) { renderCombo(LK, queryOverride); return; }
      listbox.textContent = "";
      listbox.appendChild(el("p", { "class": "pf-dd-empty", text: "Loading indexed protocols\u2026" }));
      lookupData().then(function (d) { if (!listbox.hidden) renderCombo(d, queryOverride); });
    }
    var sampleCard = $("[data-pf-sample]", out);
    if (sampleCard) {
      sampleCard.addEventListener("click", function () {
        var slug = sampleCard.getAttribute("data-pf-sample-slug") || "moonwell-lending-base";
        var chip = $('[data-receipt][data-pf-slug="' + slug + '"]');
        if (chip) chip.click();
      });
    }

    function busy(on) {
      if (!btn) return;
      btn.disabled = on; btn.setAttribute("aria-busy", String(on));
      if (spin) spin.hidden = !on;
      if (lbl) lbl.textContent = on ? "Checking…" : idleLbl;
    }
    function invalid(text) {
      if (text) {
        if (err) { err.textContent = text; err.hidden = false; }
        addr.setAttribute("aria-invalid", "true"); addr.setAttribute("aria-describedby", "pf-addr-error");
      } else {
        if (err) { err.textContent = ""; err.hidden = true; }
        addr.removeAttribute("aria-invalid"); addr.setAttribute("aria-describedby", help);
      }
    }
    function problem(a) {
      if (!a) return "Enter a contract address, or select a protocol above.";
      if (!/^0x/i.test(a)) return "A contract address starts with 0x.";
      if (!ADDR_RE.test(a)) return "Enter 0x followed by 40 hexadecimal characters (" + Math.max(0, a.length - 2) + " entered).";
      return "";
    }
    function val() { return String(addr.value || "").trim(); }
    function msg(t, kind) {
      out.textContent = "";
      var p = el("p", { "class": "pf-msg", id: "pf-msg", role: "status" }, [el("span", { text: t })]);
      if (kind) p.setAttribute("data-pf-state", kind);
      if (kind === "loading") p.insertBefore(el("span", { "class": "spinner", "aria-hidden": "true" }), p.firstChild);
      out.appendChild(p);
      if (kind && kind !== "loading") {
        var retry = el("button", { type: "button", "data-slot": "button", "data-variant": "outline", "data-size": "sm", "data-pf-retry": "", text: "Retry" });
        retry.addEventListener("click", function () { run(); });
        p.appendChild(retry);
      }
    }
    // v4.7 W3: only an address-shaped entry (0x…) is validated as an address; a name is looked up in the catalog instead
    function isName(a) { return !!a && !/^0x/i.test(a); }

    if (selChip) {
      selChip.addEventListener("click", function () {
        applySelectedOverlay(null);
        addr.value = ""; addr.setAttribute("value", "");
        if (combo) combo.setAttribute("data-is-hex", "0");
        syncScanUpgradeTarget();
        addr.focus();
        openCombo("");
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener("click", function () {
        applySelectedOverlay(null);
        addr.value = ""; addr.setAttribute("value", "");
        invalid("");
        if (combo) combo.setAttribute("data-is-hex", "0");
        syncScanUpgradeTarget();
        addr.focus();
        openCombo("");
      });
    }
    if (toggleBtn) {
      toggleBtn.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
      toggleBtn.addEventListener("click", function () {
        if (listbox && !listbox.hidden) { closeCombo(); return; }
        if (pfSelectedMeta) {
          applySelectedOverlay(null);
          addr.value = ""; addr.setAttribute("value", "");
          if (combo) combo.setAttribute("data-is-hex", "0");
        }
        addr.focus();
        openCombo(pfSelectedMeta ? "" : val());
      });
    }
    addr.addEventListener("focus", function () {
      if (!pfSelectedMeta && !ADDR_RE.test(val())) openCombo(val());
    });
    addr.addEventListener("click", function () {
      if (!pfSelectedMeta && listbox && listbox.hidden && !ADDR_RE.test(val())) openCombo(val());
    });
    addr.addEventListener("blur", function () {
      var a = val();
      invalid(a && !isName(a) ? problem(a) : "");
    });
    addr.addEventListener("keydown", function (ev) {
      if (!listbox) return;
      if (ev.key === "ArrowDown") {
        ev.preventDefault();
        if (listbox.hidden) { openCombo(pfSelectedMeta ? "" : val()); return; }
        if (comboOpts.length) setActiveOpt((activeOpt + 1) % comboOpts.length);
      } else if (ev.key === "ArrowUp") {
        ev.preventDefault();
        if (listbox.hidden) { openCombo(pfSelectedMeta ? "" : val()); return; }
        if (comboOpts.length) setActiveOpt((activeOpt - 1 + comboOpts.length) % comboOpts.length);
      } else if (ev.key === "Escape" && !listbox.hidden) {
        ev.preventDefault(); ev.stopPropagation(); closeCombo();
      } else if (ev.key === "Enter" && !listbox.hidden && comboHits.length && (activeOpt >= 0 || isName(val()))) {
        ev.preventDefault();
        selectComboItem(comboHits[activeOpt >= 0 ? activeOpt : 0]);
      }
    });
    // R2: a press on the submit button must not move it before the click lands (phones: the suggestions above it would
    // collapse, or the field's blur message would appear, between mousedown and click, so the first tap missed). Keep focus in
    // the field and the suggestions open through the press; the submit handler (run) picks or closes them.
    if (btn) btn.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
    document.addEventListener("mousedown", function (ev) {
      if (listbox && !listbox.hidden && combo && !combo.contains(ev.target) && !(btn && btn.contains(ev.target))) closeCombo();
    });

    addr.addEventListener("input", function () {
      var a = val();
      if (pfSelectedMeta && a.toLowerCase() !== String(pfSelectedMeta.address || "").toLowerCase()) applySelectedOverlay(null);
      if (combo) combo.setAttribute("data-is-hex", /^0x/i.test(a) ? "1" : "0");
      var showClr = !!a || !!pfSelectedMeta;
      if (clearBtn) clearBtn.hidden = !showClr;
      if (combo) combo.setAttribute("data-has-clear", showClr ? "1" : "0");
      if (addr.getAttribute("aria-invalid") === "true") invalid(a && !isName(a) ? problem(a) : "");
      if (ADDR_RE.test(a)) { closeCombo(); return; }
      if (!a && out.hasAttribute("data-pf-names")) { out.textContent = ""; out.removeAttribute("data-pf-names"); }
      openCombo(a);
    });
    function lookupNames(a) {
      var my = ++seq;
      if (ctl) { try { ctl.abort(); } catch (e) { /* settled */ } ctl = null; }
      busy(false); invalid("");
      out.textContent = "";   // R2: a new name query never shows the previous verdict while the catalog loads
      lookupData().then(function (d) {
        if (my !== seq) return;
        out.textContent = ""; out.setAttribute("data-pf-names", "");
        if (!d) { msg("The protocol catalog could not be loaded. Enter a 0x… contract address instead.", "http"); return; }
        var hits = lkFind(d, a, 5);
        if (!hits.length) {
          out.appendChild(el("p", { "class": "pf-msg", role: "status", "data-pf-nomatch": "" }, ["No indexed protocol or token matches \u201c" + a.slice(0, 40)
            + "\u201d. Enter a 0x\u2026 contract address to check any contract."]));
          return;
        }
        var ul = el("ul", { "class": "pf-matches", "aria-label": "Indexed protocols matching " + a.slice(0, 40) });
        hits.forEach(function (x) {
          var pa = x.it.preflightArgs || {}, brief = x.it.kind === "brief";
          var run_ = el("button", { type: "button", "data-slot": "button", "data-variant": "outline", "data-size": "sm", "data-pf-run": x.slug, text: "Run live check" });
          run_.addEventListener("click", function () {
            if (!ADDR_RE.test(String(pa.address || ""))) return;
            var cVal = pa.chain === "base" ? "base" : "ethereum";
            chainSel.value = cVal; syncChainIcon();
            addr.value = pa.address; addr.setAttribute("value", pa.address);
            applySelectedOverlay({ slug: x.slug, name: x.it.name, sym: protoTickerText(x), chain: cVal, address: pa.address });
            run();
          });
          ul.appendChild(el("li", { "data-pf-match-item": x.slug }, [
            el("span", { "class": "pm-n" }, [x.it.name, el("small", { text: lkSub(x) })]),
            arrowLink({ href: siteUrl(x.it.url), "data-slot": "button", "data-variant": "default", "data-size": "sm" }, brief ? "Open brief" : "Open scorecard"),
            run_]));
        });
        out.appendChild(el("p", { "class": "pf-msg", role: "status", text: hits.length + (hits.length === 1 ? " indexed match" : " indexed matches") + " for \u201c" + a.slice(0, 40) + "\u201d" }));
        out.appendChild(ul);
      });
    }
    function runSinglePreflight(ch, a, my) {
      var opts = { headers: { Accept: "application/json" } }, timedOut = false;
      if (typeof AbortController === "function") {
        ctl = new AbortController(); opts.signal = ctl.signal;
        var mine = ctl;
        timer = setTimeout(function () { timedOut = true; try { mine.abort(); } catch (e) { /* settled */ } }, PF_TIMEOUT_MS);
      }
      busy(true);
      var who = pfSelectedMeta && pfSelectedMeta.address.toLowerCase() === a.toLowerCase()
        ? pfSelectedMeta.name + " (" + short(a, 6, 4) + ")"
        : short(a, 6, 4);
      msg("Checking " + who + " on " + (ch === "base" ? "Base" : "Ethereum") + " at the latest block…", "loading");
      // optional free-tier attribution (non-personal): the browser demo names itself; no location, no personal data
      fetch(api + "/v1/check/preflight?chain=" + ch + "&address=" + a + "&caller_agent=" + checkerCallerAgent() + "&requester_role=individual_user&caller_purpose=general_research", opts)
        .then(function (res) { return res.json().then(function (b) { return { status: res.status, body: b }; }); })
        .then(function (x) {
          if (my !== seq) return;
          if (timer) { clearTimeout(timer); timer = null; }
          busy(false);
          var b = x.body || {}, r = b.verdict ? b : (b.result && b.result.verdict ? b.result : null);
          if (x.status === 200 && b.source === "pinned_catalog_fallback") pfFallback(out, b);
          else if (x.status === 200 && r) pfRender(out, r);
          else if (x.status === 429) msg("Rate limited: HTTP 429" + (b.error ? " (" + String(b.error) + ")" : "") + (b.detail ? ": " + String(b.detail) : "") + ". Wait a minute, then retry.", "ratelimit");
          else if (x.status === 400) { out.textContent = ""; invalid("The API rejected this address" + (b.detail ? ": " + String(b.detail) : ".")); }
          else msg("The API answered HTTP " + x.status + (b.error ? " (" + String(b.error) + ")" : "") + (b.detail ? ": " + String(b.detail) : "."), "http");
        })
        .catch(function () {
          if (my !== seq) return;
          if (timer) { clearTimeout(timer); timer = null; }
          busy(false);
          if (timedOut) msg("The check timed out after " + (PF_TIMEOUT_MS / 1000) + " s. The address is kept; retry, or use the cURL quickstart.", "timeout");
          else msg("Network error: could not reach the API. Retry, or use the cURL quickstart.", "network");
        });
    }
    function runWalletScan(a, my) {
      var opts = { headers: { Accept: "application/json" } }, timedOut = false;
      if (typeof AbortController === "function") {
        ctl = new AbortController(); opts.signal = ctl.signal;
        var mine = ctl;
        timer = setTimeout(function () { timedOut = true; try { mine.abort(); } catch (e) { /* settled */ } }, PF_TIMEOUT_MS);
      }
      busy(true);
      msg("Scanning " + short(a, 6, 4) + " across Ethereum & Base via Multicall3…", "loading");
      function fallbackMulticall() {
        return browserDirectWalletScan(a).then(function (res) {
          if (my !== seq) return;
          if (timer) { clearTimeout(timer); timer = null; }
          busy(false);
          walletExposureRender(out, res);
        });
      }
      fetch(api + "/v1/check/wallet-exposure?address=" + a + "&chain=all&caller_agent=" + checkerCallerAgent() + "&requester_role=individual_user&caller_purpose=general_research", opts)
        .then(function (res) {
          if (res.status === 404 || res.status === 501 || res.status === 502 || res.status === 503) {
            return { fallback: true };
          }
          return res.json().then(function (b) { return { status: res.status, body: b }; }).catch(function () { return { fallback: true }; });
        })
        .then(function (x) {
          if (my !== seq) return;
          if (x && x.fallback) return fallbackMulticall();
          if (timer) { clearTimeout(timer); timer = null; }
          busy(false);
          var b = (x && x.body) || {};
          if (x.status === 200 && b.schema === "pacta.wallet_exposure.v1") walletExposureRender(out, b);
          else if (x.status === 429) msg("Rate limited: HTTP 429" + (b.error ? " (" + String(b.error) + ")" : "") + ". Wait a minute, then retry.", "ratelimit");
          else if (x.status === 400) { out.textContent = ""; invalid("The API rejected this address" + (b.detail ? ": " + String(b.detail) : ".")); }
          else return fallbackMulticall();
        })
        .catch(function () {
          if (my !== seq) return;
          fallbackMulticall().catch(function () {
            if (my !== seq) return;
            if (timer) { clearTimeout(timer); timer = null; }
            busy(false);
            if (timedOut) msg("The wallet scan timed out after " + (PF_TIMEOUT_MS / 1000) + " s. Retry, or try an instant demo chip above.", "timeout");
            else msg("Network error: could not reach RPC or API endpoints. Retry, or try an instant demo chip above.", "network");
          });
        });
    }
    var walletScanner = box.getAttribute("data-wallet-scanner") === "1";
    pfFocusForWallet = function () {
      applySelectedOverlay(null);
      addr.value = ""; addr.setAttribute("value", "");
      invalid("");
      if (combo) combo.setAttribute("data-is-hex", "0");
      closeCombo();
      syncScanUpgradeTarget();
      addr.focus();
      if (box.scrollIntoView) { try { box.scrollIntoView({ behavior: "smooth", block: "start" }); } catch (e) { /* ignore */ } }
    };
    $$("[data-wallet-demo]", box).forEach(function (dBtn) {
      dBtn.addEventListener("click", function () {
        var mode = dBtn.getAttribute("data-wallet-demo") || "", dAddr = dBtn.getAttribute("data-demo-addr") || "";
        if (!mode) return;
        var my = ++seq;
        if (ctl) { try { ctl.abort(); } catch (e) { /* settled */ } ctl = null; }
        if (timer) { clearTimeout(timer); timer = null; }
        applySelectedOverlay(null);
        closeCombo();
        invalid("");
        out.removeAttribute("data-pf-names");
        if (ADDR_RE.test(dAddr)) {
          addr.value = dAddr; addr.setAttribute("value", dAddr);
          if (combo) combo.setAttribute("data-is-hex", "1");
          if (clearBtn) clearBtn.hidden = false;
          if (combo) combo.setAttribute("data-has-clear", "1");
        }
        $$("[data-wallet-demo]", box).forEach(function (o) { o.setAttribute("aria-pressed", String(o === dBtn)); });
        $$("[data-receipt]", box).forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
        if (typeof window.pactaBeacon === "function") { try { window.pactaBeacon("live_checker_submit", "demo:" + mode); } catch (e) { /* ignore */ } }
        xTrackLead();
        busy(true);
        walletTokensData().then(function (wt) {
          if (my !== seq) return;
          busy(false);
          var res = demoWalletExposure(mode, wt);
          if (!res) { msg("Demo portfolio data unavailable.", "http"); return; }
          walletExposureRender(out, res);
        }).catch(function () {
          if (my !== seq) return;
          busy(false);
          msg("Demo portfolio data could not be loaded.", "network");
        });
      });
    });
    function run() {
      // Every submit (valid or not) supersedes the previous one: bump seq and abort any in-flight request BEFORE the
      // input checks, so a stale response can never overwrite a later validation message.
      var my = ++seq;
      if (ctl) { try { ctl.abort(); } catch (e) { /* already settled */ } ctl = null; }
      if (timer) { clearTimeout(timer); timer = null; }
      var a = val(), ch = chainSel.value === "base" ? "base" : "ethereum", p = problem(a);
      if (isName(a)) {
        if (listbox && !listbox.hidden && comboHits.length) { selectComboItem(comboHits[activeOpt >= 0 ? activeOpt : 0]); return; }
        if (a.length >= 2) lookupNames(a);
        else { invalid("Type a protocol or token name, pick from the dropdown, or paste a 0x\u2026 contract address."); busy(false); out.textContent = ""; out.removeAttribute("data-pf-names"); addr.focus(); }
        return;
      }
      closeCombo();
      if (p) { invalid(p); busy(false); out.textContent = ""; addr.focus(); return; }
      out.removeAttribute("data-pf-names");
      invalid("");
      $$("[data-wallet-demo]", box).forEach(function (o) { o.setAttribute("aria-pressed", "false"); });
      if (typeof fetch !== "function") { msg("This browser cannot call the API; use the cURL quickstart.", "http"); return; }
      // First-party beacon hook (docs/b.js); optional: the checker works the same without it.
      if (typeof window.pactaBeacon === "function") { try { window.pactaBeacon("live_checker_submit", ch + ":" + a.toLowerCase()); } catch (e) { /* ignore */ } }
      xTrackLead();
      var selectedIsThis = !!(pfSelectedMeta && pfSelectedMeta.address.toLowerCase() === a.toLowerCase());
      if (!walletScanner || selectedIsThis) {
        runSinglePreflight(ch, a, my);
        return;
      }
      busy(true);
      msg("Resolving " + short(a, 6, 4) + "…", "loading");
      lookupData().catch(function () { return null; }).then(function (d) {
        if (my !== seq) return;
        var low = a.toLowerCase();
        var hitProto = (d || []).filter(function (x) {
          return x.it && x.it.kind === "protocol" && x.addrs && x.addrs.indexOf(low) >= 0;
        })[0];
        if (hitProto) {
          var pa = hitProto.it.preflightArgs || {};
          var pCh = pa.chain === "base" || hitProto.it.chain === "base" ? "base" : "ethereum";
          chainSel.value = pCh; syncChainIcon();
          applySelectedOverlay({ slug: hitProto.slug, name: hitProto.it.name, sym: protoTickerText(hitProto), chain: pCh, address: a });
          runSinglePreflight(pCh, a, my);
        } else {
          runWalletScan(a, my);
        }
      });
    }
    form.addEventListener("submit", function (ev) { ev.preventDefault(); run(); });
    // "Try:" examples ([data-receipt][data-pf-address]) fill this form and submit it from initReceipts (N1)
  }

  function initSealCombo() {
    var wrap = $("[data-seal-combo]"), inp = $("#co-target"), chainSel = $("#co-chain"), docsInp = $("#co-docs");
    var listbox = $("#co-target-listbox"), tog = wrap ? $("[data-seal-toggle]", wrap) : null;
    if (!wrap || !inp || !listbox) return;
    var hits = [], opts = [], active = -1;
    function setAct(i) {
      active = i;
      opts.forEach(function (o, k) { o.setAttribute("aria-selected", String(k === i)); });
    }
    function close() {
      if (listbox.hidden) return;
      listbox.hidden = true; inp.setAttribute("aria-expanded", "false"); wrap.removeAttribute("data-open"); active = -1;
    }
    function pick(x) {
      var pa = (x && x.it && x.it.preflightArgs) || {}, a = String(pa.address || "");
      if (!ADDR_RE.test(a)) return;
      if (chainSel) { chainSel.value = pa.chain === "base" ? "base" : "ethereum"; chainSel.dispatchEvent(new Event("change")); }
      inp.value = a; inp.setAttribute("value", a); inp.dispatchEvent(new Event("change"));
      if (docsInp && !String(docsInp.value || "").trim()) { docsInp.value = x.it.name; docsInp.setAttribute("value", x.it.name); }
      close();
    }
    function render(data) {
      var q = String(inp.value || "").trim();
      if (ADDR_RE.test(q)) q = "";
      listbox.textContent = ""; hits = []; opts = []; active = -1;
      if (!data) return;
      hits = comboSearch(data, q, q ? 20 : 14);
      hits.forEach(function (x, k) {
        var row = renderComboOption(x, "co-opt", k);
        row.addEventListener("mousedown", function (ev) { ev.preventDefault(); pick(x); });
        row.addEventListener("click", function () { pick(x); });
        listbox.appendChild(row); opts.push(row);
      });
      setAct(q && hits.length ? 0 : -1);
    }
    function open() {
      if (inp.disabled) return;
      listbox.hidden = false; inp.setAttribute("aria-expanded", "true"); wrap.setAttribute("data-open", "1");
      if (LK) { render(LK); return; }
      lookupData().then(function (d) { if (!listbox.hidden) render(d); });
    }
    if (tog) {
      tog.addEventListener("mousedown", function (ev) { ev.preventDefault(); });
      tog.addEventListener("click", function () { if (!listbox.hidden) close(); else { inp.focus(); open(); } });
    }
    inp.addEventListener("focus", function () { if (!ADDR_RE.test(String(inp.value || "").trim())) open(); });
    inp.addEventListener("input", function () {
      var v = String(inp.value || "").trim();
      if (ADDR_RE.test(v)) close(); else open();
    });
    inp.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && !listbox.hidden) { ev.preventDefault(); close(); }
      else if (ev.key === "ArrowDown") { ev.preventDefault(); if (listbox.hidden) open(); else if (opts.length) setAct((active + 1) % opts.length); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); if (listbox.hidden) open(); else if (opts.length) setAct((active - 1 + opts.length) % opts.length); }
      else if (ev.key === "Enter" && !listbox.hidden && hits.length && active >= 0) { ev.preventDefault(); pick(hits[active]); }
    });
    document.addEventListener("mousedown", function (ev) { if (!listbox.hidden && !wrap.contains(ev.target)) close(); });
  }

  // /protocols/: two independent, combinable filter groups (Status x Chain) intersected with the text search; "Clear all" resets
  // the three; 0 matches renders a one-click recovery prompt. Rows are only shown / hidden; every label is textContent.
  function initProtocolFilter() {
    var root = $("[data-pfilter-root]"), q = $("#proto-q"), count = $("#proto-count");
    if (!root || !q) return;
    var rows = $$("#proto-table tbody tr"), sBtns = $$("[data-pfilter-status]", root), cBtns = $$("[data-pfilter-chain]", root);
    var clear = $("#proto-clear"), active = $("#proto-active"), empty = $("#proto-empty"), st = "all", chn = "all", bkt = "all";
    var bBtns = $$("[data-pfilter-basket]", root);
    function label(btns, attr, v) {
      var b = btns.filter(function (x) { return x.getAttribute(attr) === v; })[0];
      var n = b && $(".num", b);
      return b ? String(b.textContent).slice(0, b.textContent.length - (n ? n.textContent.length : 0)).trim() : v;
    }
    function words() { return q.value.toLowerCase().split(" ").filter(Boolean); }
    function apply() {
      var w = words(), shown = 0;
      rows.forEach(function (tr) {
        var hay = tr.getAttribute("data-psearch") || "", ch = (tr.getAttribute("data-pchains") || "").split(" ");
        var bks = (tr.getAttribute("data-pbaskets") || "").split(" ");
        var ok = (st === "all" || tr.getAttribute("data-ptier") === st) && (chn === "all" || ch.indexOf(chn) >= 0) && (bkt === "all" || bks.indexOf(bkt) >= 0)
          && w.every(function (x) { return hay.indexOf(x) >= 0; });
        tr.hidden = !ok;
        if (ok) shown++;
      });
      sBtns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-pfilter-status") === st)); });
      cBtns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-pfilter-chain") === chn)); });
      bBtns.forEach(function (b) { b.setAttribute("aria-pressed", String(b.getAttribute("data-pfilter-basket") === bkt)); });
      if (count) count.textContent = shown + " of " + rows.length + " protocols shown";
      var parts = [];
      if (st !== "all") parts.push("Docs vs chain: " + label(sBtns, "data-pfilter-status", st));
      if (chn !== "all") parts.push("Chain: " + label(cBtns, "data-pfilter-chain", chn));
      if (bkt !== "all") parts.push("Basket: " + label(bBtns, "data-pfilter-basket", bkt));
      if (q.value.trim()) parts.push("Search: “" + q.value.trim() + "”");
      if (active) active.textContent = parts.length ? "Active filters · " + parts.join(" · ") : "";
      if (clear) clear.hidden = !parts.length;
      if (empty) {
        empty.textContent = "";
        empty.hidden = shown !== 0;
        if (!shown) {
          var who = (chn !== "all" ? label(cBtns, "data-pfilter-chain", chn) + " " : "") + (st !== "all" ? label(sBtns, "data-pfilter-status", st) + " " : "") + "protocols";
          empty.appendChild(el("span", { text: "No " + who + (q.value.trim() ? " match “" + q.value.trim() + "”" : " match these filters") + " —" }));
          if (chn !== "all") empty.appendChild(el("button", { type: "button", "class": "linkish", "data-precover": "chain", text: "Switch to All chains" }));
          if (st !== "all") empty.appendChild(el("button", { type: "button", "class": "linkish", "data-precover": "status", text: "All statuses" }));
          if (q.value.trim()) empty.appendChild(el("button", { type: "button", "class": "linkish", "data-precover": "search", text: "Clear search" }));
        }
      }
    }
    function reset(what) {
      if (what === "chain" || what === "all") chn = "all";
      if (what === "status" || what === "all") st = "all";
      if (what === "search" || what === "all") q.value = "";
      if (what === "basket" || what === "all") bkt = "all";
      apply();
    }
    sBtns.forEach(function (b) { b.addEventListener("click", function () { st = b.getAttribute("data-pfilter-status") || "all"; apply(); }); });
    cBtns.forEach(function (b) { b.addEventListener("click", function () { chn = b.getAttribute("data-pfilter-chain") || "all"; apply(); }); });
    bBtns.forEach(function (b) { b.addEventListener("click", function () { bkt = b.getAttribute("data-pfilter-basket") || "all"; apply(); }); });
    if (clear) clear.addEventListener("click", function () { reset("all"); });
    if (empty) empty.addEventListener("click", function (ev) {
      var t = ev.target && ev.target.closest ? ev.target.closest("[data-precover]") : null;
      if (t) reset(t.getAttribute("data-precover"));
    });
    q.addEventListener("input", apply);
    apply();
  }

  // pinned-snapshot ages: fills the empty [data-age="<unix ts>"] next to every observed UTC timestamp with "(Xh Ym ago)"
  function initAges() {
    var now = Math.floor(Date.now() / 1000);
    $$("[data-age]").forEach(function (n) {
      var t = parseInt(n.getAttribute("data-age"), 10);
      n.textContent = t && t <= now + 300 ? " (" + fmt(Math.max(0, now - t)) + " ago)" : "";
    });
    freshness();
  }
  // Freshness honesty: "Last live re-check" shows when the free live re-check last succeeded; when it has failed, or is older
  // than 15 minutes, the visible fallback says the page is showing the pinned historical snapshot.
  var LIVE_OK_AT = 0, LIVE_FAILED = false, STALE_S = 15 * 60;
  function freshness() {
    var now = Math.floor(Date.now() / 1000), stale = LIVE_FAILED || !LIVE_OK_AT || now - LIVE_OK_AT > STALE_S;
    $$("[data-last-recheck]").forEach(function (n) {
      var utcHm = LIVE_OK_AT ? new Date(LIVE_OK_AT * 1000).toISOString().slice(11, 16) + " UTC" : "";
      n.textContent = LIVE_OK_AT ? "Last live re-check: " + utcHm + " (" + fmt(Math.max(0, now - LIVE_OK_AT)) + " ago)" : (LIVE_FAILED ? "Last live re-check: failed" : "Last live re-check: not yet");
    });
    $$("[data-snapshot-fallback]").forEach(function (n) { n.hidden = !stale; });
  }

  var THEME_KEY = "pacta-theme";
  function themePref() {
    var t = null; try { t = localStorage.getItem(THEME_KEY); } catch (e) { /* private mode */ }
    if (t === "slate") t = "dark";
    if (t === "paper") t = "light";
    return t === "light" || t === "dark" ? t : "system";
  }

  function systemDark() { try { return window.matchMedia("(prefers-color-scheme: dark)").matches; } catch (e) { return false; } }

  // ---- R4: hamburger Sheet below 768 px (dialog: focus moves in, Tab is trapped, Escape / overlay / link closes) -------------
  function initSheet() {
    var sheet = $("#nav-sheet"), openBtn = $("[data-sheet-open]"); if (!sheet || !openBtn) return;
    var last = null;
    function focusables() { return $$("a[href],button:not([disabled])", sheet); }
    function open() {
      last = document.activeElement; sheet.hidden = false; document.body.classList.add("sheet-open");
      openBtn.setAttribute("aria-expanded", "true");
      var f = $('[data-slot="button"][data-sheet-close]', sheet) || focusables()[0]; if (f) f.focus();
    }
    function close() {
      if (sheet.hidden) return;
      sheet.hidden = true; document.body.classList.remove("sheet-open"); openBtn.setAttribute("aria-expanded", "false");
      if (last && last.focus) last.focus();
    }
    openBtn.addEventListener("click", open);
    sheet.addEventListener("click", function (ev) {
      var t = ev.target && ev.target.closest ? ev.target : null; if (!t) return;
      if (t.closest("[data-sheet-close]") || t.closest("a[href]")) close();
    });
    sheet.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") { ev.preventDefault(); close(); return; }
      if (ev.key !== "Tab") return;
      var f = focusables(); if (!f.length) return;
      if (ev.shiftKey && document.activeElement === f[0]) { ev.preventDefault(); f[f.length - 1].focus(); }
      else if (!ev.shiftKey && document.activeElement === f[f.length - 1]) { ev.preventDefault(); f[0].focus(); }
    });
    window.addEventListener("resize", function () { if (window.innerWidth >= 1024) close(); });   // v4.7: the Sheet serves < 1024 px
  }

  // ---- Tabs (MCP / cURL / Python): roving tabindex, arrow keys, Home / End; panels hidden only once JavaScript runs ---------
  function initTabs() {
    $$("[data-tabs]").forEach(function (root) {
      var tabs = $$('[role="tab"]', root);
      function select(t, focus) {
        tabs.forEach(function (x) {
          var on = x === t, p = document.getElementById(x.getAttribute("aria-controls") || "");
          x.setAttribute("aria-selected", String(on)); x.setAttribute("tabindex", on ? "0" : "-1");
          if (p) {
            if (on) { p.removeAttribute("data-inactive"); p.removeAttribute("inert"); p.removeAttribute("aria-hidden"); }
            else { p.setAttribute("data-inactive", ""); p.setAttribute("inert", ""); p.setAttribute("aria-hidden", "true"); }
          }
        });
        if (focus) t.focus();
      }
      var cur = tabs.filter(function (t) { return t.getAttribute("aria-selected") === "true"; })[0] || tabs[0];
      if (cur) select(cur, false);   // v4.7.1: the build's inactive panels get inert + aria-hidden as soon as JavaScript runs
      tabs.forEach(function (t, i) {
        t._select = function (focus) { select(t, focus); };
        t.addEventListener("click", function () { select(t, false); });
        t.addEventListener("keydown", function (ev) {
          var j = ev.key === "ArrowRight" ? i + 1 : ev.key === "ArrowLeft" ? i - 1 : ev.key === "Home" ? 0 : ev.key === "End" ? tabs.length - 1 : null;
          if (j === null) return;
          ev.preventDefault(); select(tabs[(j + tabs.length) % tabs.length], true);
        });
      });
    });
  }

  function openTab(id, scroll) {
    var t = id ? document.getElementById(id) : null;
    if (!t || t.getAttribute("role") !== "tab" || typeof t._select !== "function") return false;
    t._select(false);
    if (scroll && t.scrollIntoView) { try { t.scrollIntoView({ block: "center" }); } catch (e) { /* old browsers */ } }
    return true;
  }
  function initTabLinks() {
    $$("[data-tab-open]").forEach(function (a) {
      a.addEventListener("click", function (ev) { if (openTab(a.getAttribute("data-tab-open"), true)) { ev.preventDefault(); document.getElementById(a.getAttribute("data-tab-open")).focus(); } });
    });
    var h = String(location.hash || "").slice(1);
    if (/^[a-z0-9-]{1,40}$/.test(h)) openTab(h, false);
  }
  // v4.7 W4: a #fragment inside a collapsed <details> (the /bounties/ Wave 1 archive) opens it, so old links still land
  function initDetailsHash() {
    function go() {
      var h = String(location.hash || "").slice(1);
      if (!/^[A-Za-z0-9_-]{1,60}$/.test(h)) return;
      var t = document.getElementById(h); if (!t || !t.closest) return;
      var d = t.closest("details"), opened = false;
      while (d) { if (!d.open) { d.open = true; opened = true; } d = d.parentElement && d.parentElement.closest ? d.parentElement.closest("details") : null; }
      if (opened && t.scrollIntoView) { try { t.scrollIntoView({ block: "start" }); } catch (e) { /* old browsers */ } }
    }
    go();
    window.addEventListener("hashchange", go);
  }

  // ---- v4.7 W3: one search over protocols, tokens, briefs and 0x addresses (lookup.json + scorecards.json, fetched on first use) --
  var LK = null, LK_LOADING = null;
  function lookupData() {
    if (LK) return Promise.resolve(LK);
    if (LK_LOADING) return LK_LOADING;
    if (typeof fetch !== "function") return Promise.resolve(null);
    var root = BASE + "/", j = function (u) { return fetch(u, { headers: { Accept: "application/json" } }).then(function (r) { return r.json(); }); };
    LK_LOADING = Promise.all([j(root + "api/v1/lookup.json"), j(root + "api/v1/scorecards.json").catch(function () { return null; })]).then(function (x) {
      var items = x[0] && Array.isArray(x[0].items) ? x[0].items : [], cards = {};
      ((x[1] && x[1].protocols) || []).forEach(function (c) { if (c && c.slug) cards[c.slug] = c; });
      LK = items.filter(function (it) { return it && typeof it.slug === "string" && typeof it.name === "string"; }).map(function (it) {
        var c = cards[it.slug] || null, addrs = [it.primaryContract, it.controllerAddress].concat(it.aliasAddresses || []).concat(it.relatedContracts || [])
          .map(function (a) { return typeof a === "string" ? a : (a && typeof a.address === "string" ? a.address : ""); })
          .filter(function (a) { return ADDR_RE.test(a); }).map(function (a) { return a.toLowerCase(); });
        var baseToks = (it.tokens || []).map(function (t) { return String(t).toLowerCase(); });
        var cToks = PROTO_EXTRA_SYMS[it.slug] ? [PROTO_EXTRA_SYMS[it.slug].toLowerCase()].concat(baseToks) : baseToks;
        return { it: it, card: c, name: it.name.toLowerCase(), slug: it.slug, tokens: baseToks, comboTokens: cToks,
          catLow: String(it.category || "").toLowerCase(), chainLow: String(it.chain || "").toLowerCase(),
          addrs: addrs, search: c ? String(c.search || "").toLowerCase() : "" };
      });
      return LK;
    }).catch(function () { LK_LOADING = null; return null; });
    return LK_LOADING;
  }
  // rank: name / token prefix (0), word prefix (1), slug or name substring (2), contract address (3); -1 = no match
  function lkRank(x, q) {
    if (!q) return -1;
    if (/^0x[0-9a-f]{4,}$/.test(q)) {
      if (x.addrs.indexOf(q) >= 0) return 0;
      return x.addrs.some(function (a) { return a.indexOf(q) === 0; }) || x.search.indexOf(q) >= 0 ? 3 : -1;
    }
    if (x.name.indexOf(q) === 0 || x.tokens.indexOf(q) >= 0) return 0;
    if (x.tokens.some(function (t) { return t.indexOf(q) === 0; }) || x.name.split(/[^a-z0-9.]+/).some(function (w) { return w.indexOf(q) === 0; })) return 1;
    if (x.slug.indexOf(q.replace(/\s+/g, "-")) >= 0 || x.name.indexOf(q) >= 0) return 2;
    return x.search && q.length >= 3 && x.search.indexOf(q) >= 0 ? 2 : -1;
  }
  function lkFind(data, q, n) {
    q = String(q || "").trim().toLowerCase().slice(0, 80);
    return (data || []).map(function (x) { return { x: x, r: lkRank(x, q) }; }).filter(function (m) { return m.r >= 0; })
      .sort(function (a, b) { return a.r - b.r || (a.x.it.kind === "brief") - (b.x.it.kind === "brief") || (a.x.name < b.x.name ? -1 : a.x.name > b.x.name ? 1 : 0); })
      .slice(0, n).map(function (m) { return m.x; });
  }
  var GRADE_WORD = { delta: "Delta", recent_change: "Changed recently", docs_updated: "Docs updated", unresolved: "Unresolved", protective: "Protective", aligned: "Aligned", observed: "Observed" };
  function lkSub(x) {
    var it = x.it, ch = it.chain === "base" ? "Base" : "Ethereum";
    if (it.kind === "brief") return "Brief · " + ch + " · " + String(it.category || "");
    return [x.card && GRADE_WORD[x.card.grade] ? GRADE_WORD[x.card.grade] : "", ch, x.card ? String(x.card.summary_short || "") : String(it.targetLabel || "")]
      .filter(Boolean).join(" · ");
  }
  function initCmdk() {
    var openers = $$("[data-cmdk-open]"); if (!openers.length) return;
    var plat = (navigator && (navigator.platform || navigator.userAgent)) || "";
    if (/Mac|iPhone|iPad/.test(plat)) $$("[data-cmdk-kbd]").forEach(function (k) { k.textContent = "\u2318K"; });
    var dlg = null, input = null, list = null, foot = null, opts = [], active = -1, last = null, q = "";
    function setActive(i) {
      active = i;
      opts.forEach(function (o, k) { o.setAttribute("aria-selected", String(k === i)); });
      if (input) { if (opts[i]) input.setAttribute("aria-activedescendant", opts[i].id); else input.removeAttribute("aria-activedescendant"); }
      if (opts[i] && opts[i].scrollIntoView) { try { opts[i].scrollIntoView({ block: "nearest" }); } catch (e) { /* ignore */ } }
    }
    function render(data) {
      list.textContent = ""; opts = [];
      if (!q) { foot.textContent = "Type a protocol, a token (LBTC, ETHx, USDC, USDe, GHO), a brief or a 0x address."; setActive(-1); return; }
      if (!data) { foot.textContent = "Search is unavailable offline. Open the scorecards page instead."; setActive(-1); return; }
      var hits = lkFind(data, q, 8);
      hits.forEach(function (x, k) {
        var a = el("a", { href: siteUrl(x.it.url), role: "option", id: "cmdk-o-" + k, "aria-selected": "false", "data-cmdk-item": x.slug }, [
          el("span", { "class": "cmdk-t", text: x.it.name }), el("span", { "class": "cmdk-s", text: lkSub(x) })]);
        list.appendChild(a); opts.push(a);
      });
      foot.textContent = hits.length ? hits.length + (hits.length === 1 ? " match" : " matches") + " · \u2191 \u2193 to move · Enter to open · Esc to close"
        : "No indexed protocol, token or brief matches. Try a contract address on the homepage checker.";
      setActive(hits.length ? 0 : -1);
    }
    function refresh() {
      q = String(input.value || "").trim().toLowerCase();
      if (LK) { render(LK); return; }
      list.textContent = ""; opts = []; setActive(-1);
      foot.textContent = q ? "Loading the protocol catalog…" : "Type a protocol, a token (LBTC, ETHx, USDC, USDe, GHO), a brief or a 0x address.";
      lookupData().then(function (d) { if (dlg && !dlg.hidden) render(d); });
    }
    function build() {
      input = el("input", { type: "text", id: "cmdk-q", role: "combobox", "aria-expanded": "true", "aria-controls": "cmdk-list", "aria-autocomplete": "list",
        "aria-label": "Search protocols, tokens, briefs or 0x addresses", placeholder: "Search protocols, tokens or 0x…", autocomplete: "off", spellcheck: "false" });
      var closeBtn = el("button", { type: "button", "data-slot": "button", "data-variant": "ghost", "data-size": "sm", "data-cmdk-close": "", "aria-label": "Close search", text: "Esc" });
      list = el("div", { "class": "cmdk-list", id: "cmdk-list", role: "listbox", "aria-label": "Results" });
      foot = el("p", { "class": "cmdk-foot", role: "status" });
      var panel = el("div", { "class": "cmdk-panel" }, [el("div", { "class": "cmdk-head" }, [svgIcon("m21 21-4.3-4.3M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14z"), input, closeBtn]), list, foot]);
      dlg = el("div", { "class": "cmdk", role: "dialog", "aria-modal": "true", "aria-label": "Search Pacta", hidden: "", "data-cmdk": "" }, [panel]);
      document.body.appendChild(dlg);
      dlg.addEventListener("mousedown", function (ev) { if (ev.target === dlg) close(); });
      closeBtn.addEventListener("click", function () { close(); });
      input.addEventListener("input", refresh);
      dlg.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") { ev.preventDefault(); close(); }
        else if (ev.key === "ArrowDown" && opts.length) { ev.preventDefault(); setActive((active + 1) % opts.length); }
        else if (ev.key === "ArrowUp" && opts.length) { ev.preventDefault(); setActive((active - 1 + opts.length) % opts.length); }
        else if (ev.key === "Enter" && ev.target === input && opts[active]) { ev.preventDefault(); location.href = opts[active].getAttribute("href"); }
        else if (ev.key === "Tab") {   // focus stays inside the dialog
          var f = [input, closeBtn].concat(opts), i = f.indexOf(document.activeElement);
          ev.preventDefault(); f[(i + (ev.shiftKey ? -1 : 1) + f.length) % f.length].focus();
        }
      });
    }
    function open() {
      if (!dlg) build();
      if (!dlg.hidden) { input.focus(); return; }
      last = document.activeElement; dlg.hidden = false; document.body.classList.add("cmdk-open");
      openers.forEach(function (b) { b.setAttribute("aria-expanded", "true"); });
      input.value = ""; refresh(); input.focus();
    }
    function close() {
      if (!dlg || dlg.hidden) return;
      dlg.hidden = true; document.body.classList.remove("cmdk-open");
      openers.forEach(function (b) { b.setAttribute("aria-expanded", "false"); });
      if (last && last.focus) last.focus();
    }
    openers.forEach(function (b) { b.setAttribute("aria-expanded", "false"); b.addEventListener("click", function () { open(); }); });
    document.addEventListener("keydown", function (ev) {
      var t = ev.target || {}, tag = String(t.tagName || "").toLowerCase(), typing = tag === "input" || tag === "textarea" || tag === "select" || t.isContentEditable;
      if ((ev.metaKey || ev.ctrlKey) && !ev.altKey && String(ev.key).toLowerCase() === "k") { ev.preventDefault(); if (dlg && !dlg.hidden) close(); else open(); }
      else if (ev.key === "/" && !typing && !ev.metaKey && !ev.ctrlKey && !ev.altKey) { ev.preventDefault(); open(); }
    });
    window.pactaCmdk = { open: open, close: close };   // harness / QA hook (no data, no state outside this dialog)
  }

  // ---- Tooltip: any [data-tip] (rosette slices) shows its label on hover and on keyboard focus (A1) ---------------------------
  function initTooltips() {
    var tip = null;
    function show(t) {
      var label = t.getAttribute("data-tip"); if (!label) return;
      if (!tip) { tip = el("div", { "class": "tip", role: "tooltip", id: "pacta-tip" }); document.body.appendChild(tip); }
      tip.textContent = label; tip.hidden = false;
      var r = t.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
      var left = Math.max(8, Math.min(document.documentElement.clientWidth - w - 8, r.left + r.width / 2 - w / 2));
      var top = r.top - h - 8 < 8 ? r.bottom + 8 : r.top - h - 8;
      tip.style.left = Math.round(left + window.scrollX) + "px"; tip.style.top = Math.round(top + window.scrollY) + "px";
      t.setAttribute("aria-describedby", "pacta-tip");
    }
    function hide(t) { if (tip) tip.hidden = true; if (t && t.removeAttribute) t.removeAttribute("aria-describedby"); }
    function tgt(ev) { return ev.target && ev.target.closest ? ev.target.closest("[data-tip]") : null; }
    document.addEventListener("mouseover", function (ev) { var t = tgt(ev); if (t) show(t); });
    document.addEventListener("mouseout", function (ev) { var t = tgt(ev); if (t) hide(t); });
    document.addEventListener("focusin", function (ev) { var t = tgt(ev); if (t) show(t); });
    document.addEventListener("focusout", function (ev) { var t = tgt(ev); if (t) hide(t); });
    document.addEventListener("keydown", function (ev) { if (ev.key === "Escape") hide(null); });
  }

  // ---- A4: "Copied" is announced through the aria-live toaster (Sonner-style toast) ------------------------------------------
  function toast(text) {
    var host = $("#toaster"); if (!host) return;
    host.textContent = "";
    host.appendChild(el("div", { "data-slot": "toast" }, [text]));
    clearTimeout(host._t);
    host._t = setTimeout(function () { host.textContent = ""; }, 2400);
  }

  function svgIcon(d) {
    if (typeof document.createElementNS !== "function") return el("span", {});
    var s = document.createElementNS(SVG_NS, "svg");
    [["class", "i"], ["viewBox", "0 0 24 24"], ["aria-hidden", "true"]].forEach(function (a) { s.setAttribute(a[0], a[1]); });
    var p = document.createElementNS(SVG_NS, "path"); p.setAttribute("d", d); s.appendChild(p);
    return s;
  }

  function scEvidence(card) {
    var ev = card.evidence || {}, eas = card.easAttested !== false;
    return el("div", { "class": "sc-ev" }, [
      el("p", { "class": "sc-full" }, [el("b", { text: "Docs say: " }), plainText(ev.documented)]),
      el("p", { "class": "sc-full" }, [el("b", { text: eas ? "Chain says: " : "Chain (pinned; docs not compared): " }), plainText(ev.observed || card.finding)])]);
  }

  // T1: the radar's state badges stay skeletons until the live re-check settles (success, failure or timeout), then appear once
  function liveSettled(ok, blk) {
    $$("[data-live-pending]").forEach(function (n) { n.removeAttribute("data-live-pending"); });
    if (ok && blk) {   // v4.4 (F5): the footer pill and the "Next:" line follow the live read (v4.6: one block per chain)
      $$("[data-prov-pill]").forEach(function (n) { n.textContent = "Live-checked · " + blkPill(blk); n.setAttribute("data-live", "1"); });
      $$(".livebar .lb-asof").forEach(function (n) { n.hidden = true; });
    }
    $$("[data-live-status]").forEach(function (n) {
      var t = $("[data-live-status-text]", n), sp = $(".spinner", n); if (sp) sp.hidden = true;
      // N5 (v4.3): the radar header cites one block (the finalized read); the live block number goes on the provenance line
      if (t) t.textContent = ok ? "Live state confirmed" + (blk ? " at the latest block" : "") : "Live check unavailable: showing the pinned snapshot";
    });
  }

  function accItem(title, kids) {
    return el("details", { "class": "acc", "data-slot": "accordion-item" }, [el("summary", { "data-slot": "accordion-trigger", text: title }),
      el("div", { "data-slot": "accordion-content" }, kids)]);
  }

  // U6: the exact POST /v1/requests wire schema (the Worker rejects unknown keys): closed enums, bounded plain text, no PII outside
  // contact_handle. urgency_track follows the chosen track.
  var REQ_ENUMS = {
    requester_role: ["protocol_team", "risk_curator_analyst", "institutional_allocator", "defi_developer", "security_researcher", "individual_user", "autonomous_agent"],
    caller_purpose: ["collateral_due_diligence", "governance_monitoring", "security_audit", "pre_trade_safety", "yield_allocation", "integration_testing", "general_research"],
    request_type: ["doc_or_data_discrepancy", "missing_protocol", "missing_check_surface", "unsupported_chain", "mcp_or_api_feature"]
  };
  var URGENCY = { community: "community_queue_free", "wholesale-150": "active_due_diligence", clearance: "issuer_24h_clearance_5k",
    continuous: "active_due_diligence", api_sla: "api_high_volume_sla" };
  var REQ_API_RE = /^https:\/\/(?:api\.pacta\.wtf|pacta\.fractalneurons\.com|pacta-x402\.pacta\.workers\.dev)\/v1\/requests$/;
  var PILOT_API_RE = /^https:\/\/(?:api\.pacta\.wtf|pacta\.fractalneurons\.com|pacta-x402\.pacta\.workers\.dev)\/v1\/(?:pilot\/(?:watch|sponsor-pool)|requests)$/;
  var EMAIL_RE = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$/, TG_RE = /^@[A-Za-z0-9_]{3,32}$/, GH_RE = /^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})$/;
  var PII_RE = /[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}|(^|[\s(])@[A-Za-z0-9_]{2,}|\b\d{1,3}(?:\.\d{1,3}){3}\b|<[^>]*>/;
  var JUNK_CONTACT = /^(none|n\/?a|na|-+|null|user@example\.com|test@test\.com|email@example\.com)$/i;

  function cleanSubject(v) { return String(v || "").replace(/[:@<>]/g, " ").replace(BAD_CHARS, "").replace(/\s+/g, " ").trim(); }

  function cutWords(s, max) {
    s = String(s || "").replace(/\s+/g, " ").trim();
    if (s.length <= max) return s;
    var c = s.slice(0, max - 1), i = c.lastIndexOf(" ");
    return (i > 20 ? c.slice(0, i) : c).replace(/[\s,;:.(-]+$/, "") + "…";
  }

  // Command + Popover combobox (multi-select) for the protocols in scope: type to filter, arrows / Enter to toggle, chips to remove
  function initCombo(form, onChange) {
    var root = $("[data-combo]", form), none = { values: function () { return []; }, select: function () { return false; }, input: null };
    if (!root) return none;
    var input = $("#req-proto-q", root), list = $("#req-proto-list", root), chips = $("[data-combo-chips]", root);
    if (!input || !list || !chips) return none;
    var emptyLi = $('[data-slot="command-empty"]', list), items = $$('[role="option"]', list), active = -1, selected = [];
    function visible() { return $$('[role="option"]', list).filter(function (i) { return !i.hidden; }); }   // in ranked (DOM) order
    function setActive(i) {
      var v = visible(); items.forEach(function (x) { x.removeAttribute("data-active"); }); active = i;
      if (i >= 0 && v[i]) {
        v[i].setAttribute("data-active", "true"); input.setAttribute("aria-activedescendant", v[i].id);
        try { v[i].scrollIntoView({ block: "nearest" }); } catch (e) { /* old browsers */ }
      } else input.removeAttribute("aria-activedescendant");
    }
    function render() {
      chips.textContent = "";
      selected.forEach(function (it) {
        var name = it.getAttribute("data-name") || "";
        var x = el("button", { type: "button", "aria-label": "Remove " + name }, [svgIcon("M18 6 6 18M6 6l12 12")]);
        x.addEventListener("click", function () { toggle(it); input.focus(); });
        chips.appendChild(el("span", { "class": "chip-x" }, [el("span", { text: name }), x]));
      });
      items.forEach(function (it) { it.setAttribute("aria-selected", String(selected.indexOf(it) >= 0)); });
      onChange();
    }
    function toggle(it) { var i = selected.indexOf(it); if (i >= 0) selected.splice(i, 1); else selected.push(it); render(); }
    function open() { list.hidden = false; input.setAttribute("aria-expanded", "true"); }
    function close() { list.hidden = true; input.setAttribute("aria-expanded", "false"); setActive(-1); }
    // v4.5 G-P2-3: rank 0 = name or slug starts with the query, 1 = a word of the name does, 2 = substring, 3 = a contract address
    function rank(it, t) {
      var nm = String(it.getAttribute("data-name") || "").toLowerCase(), sl = String(it.getAttribute("data-slug") || "");
      if (nm.indexOf(t) === 0 || sl.indexOf(t) === 0) return 0;
      if ((" " + nm.replace(/[^a-z0-9]+/g, " ")).indexOf(" " + t) >= 0) return 1;
      if (nm.indexOf(t) >= 0 || sl.indexOf(t) >= 0) return 2;
      if (/^0x[0-9a-f]{4,40}$/.test(t) && (" " + String(it.getAttribute("data-q") || "")).indexOf(" " + t) >= 0) return 3;
      return -1;
    }
    function filter() {
      var t = String(input.value || "").trim().toLowerCase(), n = 0, order = [];
      items.forEach(function (it, i) {
        var r = t ? rank(it, t) : 0;
        it.hidden = r < 0; if (r >= 0) { n++; order.push([r, i, it]); }
      });
      order.sort(function (a, b) { return a[0] - b[0] || a[1] - b[1]; });
      order.forEach(function (x) { x[2].remove(); list.appendChild(x[2]); });
      if (emptyLi) emptyLi.hidden = n !== 0;
      setActive(n ? 0 : -1);
    }
    input.addEventListener("focus", function () { filter(); open(); });
    input.addEventListener("input", function () { filter(); open(); });
    input.addEventListener("keydown", function (ev) {
      var v = visible();
      if (ev.key === "ArrowDown") { ev.preventDefault(); open(); setActive(Math.min(v.length - 1, active + 1)); }
      else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive(Math.max(0, active - 1)); }
      else if (ev.key === "Enter") { ev.preventDefault(); if (!list.hidden && v[active]) toggle(v[active]); }
      else if (ev.key === "Escape") { if (!list.hidden) { ev.preventDefault(); close(); } }
      else if (ev.key === "Backspace" && !input.value && selected.length) toggle(selected[selected.length - 1]);
    });
    list.addEventListener("mousedown", function (ev) { ev.preventDefault(); });   // keep focus in the input
    list.addEventListener("click", function (ev) {
      var it = ev.target && ev.target.closest ? ev.target.closest('[role="option"]') : null; if (!it) return;
      toggle(it); input.value = ""; filter(); close();   // G-P2-3: a mouse pick closes the list (aria-expanded="false") and clears the query
    });
    document.addEventListener("click", function (ev) { if (!root.contains(ev.target)) close(); });
    return {
      input: input,
      values: function () { return selected.map(function (it) { return { name: it.getAttribute("data-name") || "", slug: it.getAttribute("data-slug") || "" }; }); },
      select: function (v) {
        var low = String(v).toLowerCase();
        var it = items.filter(function (x) { return x.getAttribute("data-slug") === v || String(x.getAttribute("data-name") || "").toLowerCase() === low; })[0];
        if (it && selected.indexOf(it) < 0) { selected.push(it); render(); }
        return !!it;
      }
    };
  }

  function postPilotEndpoint(url, payload) {
    if (!PILOT_API_RE.test(url) || typeof fetch !== "function") return Promise.reject(new Error("unavailable"));
    var init = { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify(payload) };
    try { if (typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") init.signal = AbortSignal.timeout(15000); } catch (e) { /* none */ }
    return fetch(url, init).then(function (r) {
      return r.json().then(function (j) { return { status: r.status, j: j }; }, function () { return { status: r.status, j: {} }; });
    });
  }

  function validWatchDestination(raw) {
    var d = String(raw || "").trim();
    if (!d || d.length > 240 || JUNK_CONTACT.test(d) || /^@handle$|^@telegram$/i.test(d)) return "";
    if (/^https?:\/\//i.test(d)) {
      try {
        var u = new URL(d);
        if (u.protocol !== "https:" || u.username || u.password || !u.hostname || /^(?:localhost|127\.|10\.|192\.168\.)/i.test(u.hostname)) return "";
        return "webhook";
      } catch (e) { return ""; }
    }
    if (d.charAt(0) === "@" || /^https?:\/\/t\.me\//i.test(d)) {
      var tg = d.replace(/^https?:\/\/t\.me\//i, "@");
      if (tg.charAt(0) !== "@") tg = "@" + tg;
      return TG_RE.test(tg) ? "telegram" : "";
    }
    if (EMAIL_RE.test(d) && !/@(?:example\.com|test\.com)$/i.test(d)) return "email";
    return "";
  }

  function bindWatchPilotRoot(root) {
    if (!root || root.getAttribute("data-wp-bound") === "1") return;
    root.setAttribute("data-wp-bound", "1");
    var form = $("[data-watch-pilot-form]", root), tIn = $("[data-wp-target]", root), dIn = $("[data-wp-dest]", root);
    var btn = $("[data-wp-submit]", root), spin = btn ? $(".spinner", btn) : null, lbl = btn ? $("[data-wp-btn-lbl]", btn) : null;
    var errEl = $("[data-wp-err]", root), stEl = $("[data-wp-status]", root), doneEl = $("[data-wp-done]", root), doneMsg = $("[data-wp-done-msg]", root);
    var api = root.getAttribute("data-api") || "https://api.pacta.wtf/v1/pilot/watch";
    var fbApi = root.getAttribute("data-fallback-api") || "https://api.pacta.wtf/v1/requests";
    if (!form || !tIn || !dIn) return;
    function setErr(inp, msg) {
      if (errEl) { errEl.textContent = msg || ""; errEl.hidden = !msg; }
      [tIn, dIn].forEach(function (x) { x.removeAttribute("aria-invalid"); });
      if (inp && msg) { inp.setAttribute("aria-invalid", "true"); if (inp.focus) inp.focus(); }
    }
    function setBusy(on) {
      if (btn) { btn.disabled = on; btn.setAttribute("aria-busy", String(on)); }
      if (spin) spin.hidden = !on;
      if (lbl) lbl.textContent = on ? "Enabling\u2026" : "Enable free alerts";
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (stEl) { stEl.textContent = ""; stEl.hidden = true; }
      var tVal = cleanText(tIn.value, 120), dVal = String(dIn.value || "").trim();
      var validTarget = ADDR_RE.test(tVal) || /^(?:ethereum|base):0x[0-9a-fA-F]{40}$/.test(tVal)
        || (tVal.length >= 2 && /^[A-Za-z0-9][A-Za-z0-9._()/ -]{1,119}$/.test(tVal) && !PII_RE.test(tVal));
      if (!validTarget) { setErr(tIn, "Enter a valid 0x Safe/wallet address or protocol name/slug."); return; }
      var ch = validWatchDestination(dVal);
      if (!ch) { setErr(dIn, "Enter a real email address, @Telegram handle, or https:// webhook URL."); return; }
      setErr(null, "");
      xTrackLead();
      setBusy(true);
      var payload = { target: tVal, channel: ch, destination: dVal };
      if (isInternalQa()) payload.internal = true;
      postPilotEndpoint(api, payload).then(function (res) {
        if (res.status === 404 && fbApi && ch !== "webhook") {
          return postPilotEndpoint(fbApi, {
            caller_agent: isInternalQa() ? "pacta-founder-qa" : "pacta-web",
            requester_role: "risk_curator_analyst",
            caller_purpose: "governance_monitoring",
            request_type: "mcp_or_api_feature",
            target_subject: cleanSubject(tVal).slice(0, 120) || "wallet-watch",
            requested_capability: "30-day free control-plane drift alert pilot (" + ch + ")",
            urgency_track: "active_due_diligence",
            contact_handle: dVal.slice(0, 120)
          });
        }
        return res;
      }).then(function (res) {
        setBusy(false);
        var j = res.j || {};
        if (res.status === 200 && (j.ok || j.request_id)) {
          var wid = j.watch_id || j.request_id || "WCH-2026";
          if (doneMsg) doneMsg.textContent = "30-day free alert pilot active (" + wid + ") for " + tVal + " via " + ch + ". Watch setup replies come from pacta@dri.network.";
          form.hidden = true;
          if (doneEl) { doneEl.hidden = false; if (doneEl.focus) { try { doneEl.focus(); } catch (e) { /* ignore */ } } }
          return;
        }
        if (stEl) {
          stEl.hidden = false;
          stEl.textContent = res.status === 429 ? "Rate limit reached — please wait a few minutes." : ("Could not enable alerts (HTTP " + res.status + (j.detail ? ": " + j.detail : "") + ").");
        }
      }).catch(function () {
        setBusy(false);
        if (stEl) { stEl.hidden = false; stEl.textContent = "Network error reaching Pacta API — please retry or write to pacta@dri.network."; }
      });
    });
  }

  function buildInlineWatchWidget(targetAddr) {
    var boxApi = ($(".pf") && $(".pf").getAttribute("data-api")) || "https://api.pacta.wtf";
    var sec = el("div", {
      "class": "watch-pilot-box wp-inline",
      "data-watch-pilot": "",
      "data-wallet-watch-inline": "",
      "data-api": boxApi + "/v1/pilot/watch",
      "data-fallback-api": boxApi + "/v1/requests"
    });
    sec.appendChild(el("div", { "class": "wp-head" }, [
      el("span", { "class": "step-k mono", text: "WATCH THIS SAFE / WALLET FREE \u00b7 30-DAY PILOT" }),
      el("h4", { text: "Get pre-execution alerts before held protocols upgrade or rotate Safe signers" })
    ]));
    var f = el("form", { "class": "wp-form", "data-watch-pilot-form": "", novalidate: "", autocomplete: "off" });
    var tInput = el("input", { type: "hidden", name: "target", value: String(targetAddr || ""), "data-wp-target": "" });
    var dInput = el("input", {
      type: "text", name: "destination", maxlength: "240", spellcheck: "false", autocapitalize: "off",
      placeholder: "Email, Telegram or webhook", "aria-label": "Email, Telegram or HTTPS webhook", "data-wp-dest": ""
    });
    var subBtn = el("button", {
      type: "submit", "data-slot": "button", "data-variant": "default", "data-size": "default", "data-wp-submit": ""
    }, [
      el("span", { "class": "spinner", "aria-hidden": "true", hidden: "" }),
      el("span", { "data-wp-btn-lbl": "", text: "Enable free alerts" })
    ]);
    f.appendChild(tInput);
    f.appendChild(el("div", { "class": "wp-inline-row" }, [dInput, subBtn]));
    var priv = el("p", { "class": "wp-privacy", "data-wp-privacy": "" }, [
      "Used only to deliver the alerts you ask for and opted-in setup replies from Pacta (",
      el("code", { text: "pacta@dri.network" }),
      "); never sold or used for cold marketing \u2014 see ",
      el("a", { href: siteUrl("https://pacta.wtf/privacy/#watch-pilot"), text: "Privacy" }),
      "."
    ]);
    f.appendChild(priv);
    f.appendChild(el("p", { "class": "form-message", "data-slot": "form-message", "data-wp-err": "", hidden: "" }));
    f.appendChild(el("p", { "class": "wp-status", role: "status", "aria-live": "polite", "data-wp-status": "", hidden: "" }));
    sec.appendChild(f);
    sec.appendChild(el("div", { "class": "wp-done", "data-wp-done": "", hidden: "", tabindex: "-1" }, [
      el("span", { "data-slot": "badge", "data-variant": "success", text: "30-Day Free Pilot Active" }),
      el("p", { "data-wp-done-msg": "", text: "Alert pilot enabled." })
    ]));
    bindWatchPilotRoot(sec);
    return sec;
  }

  function initWatchPilot() {
    $$("[data-watch-pilot]").forEach(function (r) { bindWatchPilotRoot(r); });
  }

  function initSponsorPool() {
    var form = $("[data-sponsor-pool-form]");
    if (!form) return;
    var sec = form.closest("[data-sponsor-pool]");
    if (sec && SPONSOR_POOL_ADDRESS === "") sec.setAttribute("data-sponsor-address", "");
    var tIn = $("[data-sp-target]", form), tierSel = $("[data-sp-tier-select]", form), setSel = $("[data-sp-settlement]", form);
    var attrIn = $("[data-sp-attr]", form), cIn = $("[data-sp-contact]", form);
    var btn = $("[data-sp-submit]", form), spin = btn ? $(".spinner", btn) : null, lbl = btn ? $("[data-sp-btn-lbl]", btn) : null;
    var errEl = $("[data-sp-err]", form), stEl = $("[data-sp-status]", form);
    var doneEl = sec ? $("[data-sp-done]", sec) : null, doneMsg = sec ? $("[data-sp-done-msg]", sec) : null;
    var api = form.getAttribute("data-api") || "https://api.pacta.wtf/v1/pilot/sponsor-pool";
    var fbApi = form.getAttribute("data-fallback-api") || "https://api.pacta.wtf/v1/requests";
    var pf = readPrefill(location.search);
    if (pf.protocol && tIn && !tIn.value) tIn.value = pf.protocol;
    function setErr(inp, msg) {
      if (errEl) { errEl.textContent = msg || ""; errEl.hidden = !msg; }
      [tIn, cIn].forEach(function (x) { if (x) x.removeAttribute("aria-invalid"); });
      if (inp && msg) { inp.setAttribute("aria-invalid", "true"); if (inp.focus) inp.focus(); }
    }
    function setBusy(on) {
      if (btn) { btn.disabled = on; btn.setAttribute("aria-busy", String(on)); }
      if (spin) spin.hidden = !on;
      if (lbl) lbl.textContent = on ? "Reserving\u2026" : "Reserve Verification Pool";
    }
    form.addEventListener("submit", function (ev) {
      ev.preventDefault();
      if (stEl) { stEl.textContent = ""; stEl.hidden = true; }
      var tVal = cleanText(tIn ? tIn.value : "", 160);
      var cVal = String(cIn ? cIn.value : "").trim();
      var tierVal = (tierSel && tierSel.value) ? tierSel.value : "pool-50";
      var setVal = (setSel && setSel.value) ? setSel.value : "safe_reserve";
      var attrVal = cleanText(attrIn ? attrIn.value : "", 80);
      if (tVal.length < 2 || PII_RE.test(tVal)) { setErr(tIn, "Enter the target protocol name/slug or 0x contract address (keep contact details in Contact)."); return; }
      var cClean = cVal.replace(/^github:/i, "");
      if (!cVal || JUNK_CONTACT.test(cVal) || cVal.length > 160 || !(EMAIL_RE.test(cClean) || TG_RE.test(cClean) || GH_RE.test(cClean))) {
        setErr(cIn, "Enter a valid work email, @Telegram handle, or GitHub username."); return;
      }
      setErr(null, "");
      xTrackLead();
      setBusy(true);
      var payload = { target: tVal, tier: tierVal, settlement: setVal, contact: cVal };
      if (attrVal) payload.attribution = attrVal;
      if (isInternalQa()) payload.internal = true;
      postPilotEndpoint(api, payload).then(function (res) {
        if (res.status === 404 && fbApi) {
          return postPilotEndpoint(fbApi, {
            caller_agent: isInternalQa() ? "pacta-founder-qa" : "pacta-web",
            requester_role: "risk_curator_analyst",
            caller_purpose: "collateral_due_diligence",
            request_type: "missing_protocol",
            target_subject: cleanSubject(tVal).slice(0, 120) || "sponsor-pool",
            requested_capability: "Sponsor Verification Pool (" + tierVal + ", " + setVal + (attrVal ? ", attribution: " + attrVal : "") + ")",
            urgency_track: "active_due_diligence",
            contact_handle: cVal.slice(0, 120)
          });
        }
        return res;
      }).then(function (res) {
        setBusy(false);
        var j = res.j || {};
        if (res.status === 200 && (j.ok || j.request_id)) {
          var pid = j.pool_id || j.request_id || "POOL-2026";
          var tierLbl = tierVal === "wholesale-150" ? "sweep, $150 per protocol for 20 or more" : "$50 minimum pool, $25 fixed verification fee";
          if (doneMsg) doneMsg.textContent = "Verification pool reserved (" + pid + ") for " + tVal + " (" + tierLbl + "). No payment now: we reply from Pacta (pacta@dri.network), and deposit instructions come only after the Sponsor Safe is deployed and verified.";
          form.hidden = true;
          if (doneEl) { doneEl.hidden = false; if (doneEl.focus) { try { doneEl.focus(); } catch (e) { /* ignore */ } } }
          return;
        }
        if (stEl) {
          stEl.hidden = false;
          stEl.textContent = res.status === 429 ? "Rate limit reached — please wait a few minutes." : ("Could not reserve pool (HTTP " + res.status + (j.detail ? ": " + j.detail : "") + ").");
        }
      }).catch(function () {
        setBusy(false);
        if (stEl) { stEl.hidden = false; stEl.textContent = "Network error reaching Pacta API — please retry or write to pacta@dri.network."; }
      });
    });
  }

  function syncScanUpgradeTarget(chOverride, addrOverride) {
    var pfChain = $("#pf-chain"), pfAddr = $("#pf-address");
    var ch = (chOverride || (pfChain && pfChain.value) || "ethereum") === "base" ? "base" : "ethereum";
    var a = String(addrOverride || (pfAddr && pfAddr.value) || "").trim();
    var wpTarget = $("#watch-pilot-target");
    if (wpTarget && ADDR_RE.test(a)) {
      var pSlug = pfSelectedMeta && String(pfSelectedMeta.address || "").toLowerCase() === a.toLowerCase() ? pfSelectedMeta.slug : "";
      wpTarget.value = pSlug || (ch + ":" + a);
    }
  }

  function notifyScanCheckComplete(chain, address) {
    syncScanUpgradeTarget(chain, address);
  }

  function initScanFunnel() {
    var pfChain = $("#pf-chain"), pfAddr = $("#pf-address");
    var q = {};
    try {
      var sp = new URLSearchParams(window.location.search || "");
      sp.forEach(function (v, k) { q[k] = v; });
    } catch (e) { /* ignore */ }
    var pf = readPrefill(window.location.search || "");
    if (pf.protocol) {
      var freeBtn = $("[data-seal-community-link]"), poolBtn = $("[data-seal-pool-link]"), dosBtn = $("[data-seal-dossier-link]");
      if (freeBtn) freeBtn.setAttribute("href", "../request/?tier=community&protocol=" + encodeURIComponent(pf.protocol));
      if (poolBtn) poolBtn.setAttribute("href", "../bounties/?protocol=" + encodeURIComponent(pf.protocol) + "#sponsor-pool");
      if (dosBtn) dosBtn.setAttribute("href", "../request/?tier=clearance&protocol=" + encodeURIComponent(pf.protocol));
    }
    if (pfChain) pfChain.addEventListener("change", function () { syncScanUpgradeTarget(); });
    if (pfAddr) pfAddr.addEventListener("input", function () { syncScanUpgradeTarget(); });
    if (ADDR_RE.test(String(q.address || "")) && pfAddr && !pfAddr.value) {
      if (pfChain && (q.chain === "base" || q.chain === "ethereum")) pfChain.value = q.chain;
      pfAddr.value = q.address;
      pfAddr.setAttribute("value", q.address);
      syncScanUpgradeTarget(q.chain, q.address);
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    // v4.3: every feature starts on its own, so one that throws can never leave a later one (the "Try:" examples, the
    // checker, the radar) unbound; the error is re-thrown asynchronously, so it still reaches the console
    [initTheme, initInternalQaBadge, initXPixel, initSheet, initTabs, initTabLinks, initDetailsHash, initCmdk, initTooltips, initCopy, initBeaconHooks, tick, initIndex, initRequest, initLauncher, initCheckout, initScanFunnel, initWatchPilot, initSponsorPool, initSealCombo, initMiniApp, initInspector, initPreflight,
     initLiveTimelocks, initProtocolFilter, initAges, initRefresh, initHeroCheck, initBadgeWidget, initScorecards, initReceipts].forEach(function (f) {
      try { f(); } catch (e) { setTimeout(function () { throw e; }, 0); }
    });
    setInterval(tick, 30000);
    setInterval(initAges, 60000);
    if ($("#insp-list")) loadData().catch(function () { /* static sheet and drawer links keep working */ });
  });
})();
