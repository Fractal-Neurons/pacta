// Pacta site v2: theme toggle, zero-wallet control-plane inspector, radar countdowns, matrix filter.
// No wallet, no trackers, no third-party requests: data comes from this site's own /api/v1/*.json files.
// All record text is inserted with textContent (never innerHTML).
(function () {
  "use strict";
  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  function el(tag, attrs, kids) {
    var n = document.createElement(tag);
    Object.keys(attrs || {}).forEach(function (k) { if (k === "text") n.textContent = attrs[k]; else n.setAttribute(k, attrs[k]); });
    (kids || []).forEach(function (c) { if (c) n.appendChild(typeof c === "string" ? document.createTextNode(c) : c); });
    return n;
  }

  // ---- theme ----------------------------------------------------------------------------------------
  function applyTheme(t) {
    if (t === "paper") document.documentElement.setAttribute("data-theme", "paper");
    else document.documentElement.removeAttribute("data-theme");
    $$(".theme-toggle span").forEach(function (s) { s.classList.toggle("on", s.getAttribute("data-t") === (t === "paper" ? "paper" : "slate")); });
    var b = $(".theme-toggle"); if (b) b.setAttribute("aria-label", "Theme: " + (t === "paper" ? "Paper" : "Slate") + " (switch)");
  }
  function initTheme() {
    var t = null; try { t = localStorage.getItem("pacta-theme"); } catch (e) {}
    applyTheme(t);
    var b = $(".theme-toggle");
    if (b) b.addEventListener("click", function () {
      var next = document.documentElement.getAttribute("data-theme") === "paper" ? "slate" : "paper";
      try { localStorage.setItem("pacta-theme", next); } catch (e) {}
      applyTheme(next);
    });
  }

  // ---- countdowns -------------------------------------------------------------------------------------
  function fmt(sec) {
    var d = Math.floor(sec / 86400), h = Math.floor(sec % 86400 / 3600), m = Math.floor(sec % 3600 / 60);
    return (d ? d + "d " : "") + h + "h " + m + "m";
  }
  function tick() {
    var now = Math.floor(Date.now() / 1000);
    $$("[data-eta]").forEach(function (n) {
      var eta = parseInt(n.getAttribute("data-eta"), 10);
      if (!eta) return;
      n.textContent = eta > now ? "Execution window opens in " + fmt(eta - now) : "Window open — verify execution state";
    });
  }

  // ---- matrix filter ----------------------------------------------------------------------------------
  function initMatrix() {
    var q = $("#matrix-q"), rows = $$("#matrix tbody tr"), count = $("#matrix-count"), cls = "all";
    if (!rows.length) return;
    function apply() {
      var t = (q && q.value || "").trim().toLowerCase(), shown = 0;
      rows.forEach(function (r) {
        var ok = (cls === "all" || r.getAttribute("data-class") === cls) && (!t || r.getAttribute("data-search").indexOf(t) >= 0);
        r.hidden = !ok; if (ok) shown++;
      });
      if (count) count.textContent = shown + " of " + rows.length + " records shown";
    }
    if (q) q.addEventListener("input", apply);
    $$(".chip[data-class]").forEach(function (c) {
      c.addEventListener("click", function () {
        cls = c.getAttribute("data-class");
        $$(".chip[data-class]").forEach(function (o) { o.setAttribute("aria-pressed", String(o === c)); });
        apply();
      });
    });
    apply();
  }

  // ---- inspector --------------------------------------------------------------------------------------
  var DATA = null, FINAL = 0;
  function secs(s) {
    if (s === null || s === undefined) return "not documented";
    var d = s / 86400; return (d >= 1 && Number.isInteger(d) ? d + "d" : (s / 3600) + "h") + " (" + Number(s).toLocaleString("en-US") + "s)";
  }
  function multisig(text) {
    var m = text.match(/\b\d+-of-\d+\b/g) || [];
    var seen = []; m.forEach(function (x) { if (seen.indexOf(x) < 0) seen.push(x); });
    var guard = /\bguard\b/i.test(text) ? "Safe guard referenced in record" : (/\bmodule\b/i.test(text) ? "Safe module referenced in record" : "Safe modules / guard: not probed in this record");
    return { quorum: seen.length ? seen.join(" · ") : "no Safe quorum in this record", guard: guard };
  }
  function proxyAdmin(text) {
    var m = text.match(/ProxyAdmin \((0x[0-9a-fA-F]{40})\)/) || text.match(/admin\(\) = [A-Za-z ]*\((0x[0-9a-fA-F]{40})\)/);
    return m ? m[1] : null;
  }
  function roles(text) {
    var m = text.match(/(PROPOSER_ROLE[^;.)]*|EXECUTOR_ROLE[^;.)]*|DEFAULT_ADMIN_ROLE[^;.)]*)/g);
    return m ? m.slice(0, 2).join("; ") : "roles not enumerated in this record";
  }
  // Runnable as-is: full signature + every argument (call_signature / call_args in /api/v1/index.json);
  // repro_calldata is the exact ABI-encoded calldata for raw eth_call users.
  function castCmd(e) {
    var rpc = '--rpc-url "$ETH_RPC_URL"';
    var first = e.check_type === "eth_getStorageAt"
      ? "cast storage " + e.target_contract + " " + e.selector_or_slot + " --block " + e.block_number + " " + rpc
      : "cast call " + e.target_contract + ' "' + (e.call_signature || e.selector_or_slot) + '"' +
        (e.call_args && e.call_args.length ? " " + e.call_args.join(" ") : "") + " --block " + e.block_number + " " + rpc;
    return first + "\ncast block " + e.block_number + " --field hash " + rpc + "   # expect " + e.block_hash;
  }
  function cell(title, kids) { return el("div", { "class": "cell" }, [el("h3", { text: title })].concat(kids)); }
  function render(e) {
    var panel = $("#insp-panel"); if (!panel || !e) return;
    panel.textContent = "";
    var fin = FINAL && e.block_number <= FINAL;
    var ms = multisig(e.onchain_observed || ""), pa = proxyAdmin(e.onchain_observed || "");
    var differs = e.documented_delay_seconds !== null && e.observed_delay_seconds !== null && e.documented_delay_seconds !== e.observed_delay_seconds;
    var cls = e.classification === "parameter_delta" ? "delta" : (e.classification === "protective_delta" ? "protect" : "ok");
    panel.appendChild(el("div", {}, [el("b", { text: e.protocol + " " }), el("span", { "class": "badge " + cls, text: e.classification.replace("_", " ") }),
      el("span", { "class": "count", text: "  Sprint " + e.sprint + " · " + e.surface })]));
    panel.appendChild(cell("(a) Pinned block & canonical hash", [el("p", {}, ["#" + Number(e.block_number).toLocaleString("en-US") + " ",
      el("span", { "class": "badge" + (fin ? " ok" : ""), text: fin ? "Scanner-pinned (L1 finalized)" : "Scanner-pinned (finality: check head)" })]), el("p", { "class": "addr", text: e.block_hash })]));
    panel.appendChild(cell("(b) Multisig / Safe posture", [el("p", { text: ms.quorum }), el("p", { "class": "count", text: ms.guard })]));
    panel.appendChild(cell("(c) Timelock & proxy control plane", [
      el("p", {}, ["minDelay observed " + secs(e.observed_delay_seconds) + " vs docs " + secs(e.documented_delay_seconds) + " ",
        differs ? el("span", { "class": "badge delta", text: "differs from docs" }) : null]),
      el("p", { "class": "count", text: "Roles: " + roles(e.onchain_observed || "") }),
      el("p", { "class": "count", text: "EIP-1967 ProxyAdmin: " + (pa || "not applicable / not in this record") })]));
    var cmd = castCmd(e);
    var copy = el("button", { "class": "copy", type: "button", text: "Copy" });
    copy.addEventListener("click", function () { if (navigator.clipboard) navigator.clipboard.writeText(cmd).then(function () { copy.textContent = "Copied"; setTimeout(function () { copy.textContent = "Copy"; }, 1500); }); });
    var eas = e.base_eas_uid
      ? el("a", { href: "https://base.easscan.org/attestation/view/" + e.base_eas_uid, target: "_blank", rel: "noopener", text: "Base EAS attestation ↗" })
      : el("span", { "class": "count", text: "Base EAS: pending batch attestation — pinned by block hash + SHA-256 " + String(e.summary_sha256).slice(0, 18) + "…" });
    panel.appendChild(cell("(d) Reproduce it yourself", [el("div", { "class": "cmd" }, [el("pre", { text: cmd }), copy]), el("p", {}, [eas])]));
    panel.appendChild(el("p", { "class": "count", text: e.onchain_observed }));
  }
  function pick(key) {
    if (!DATA) return;
    var list = DATA.entries.filter(function (e) { return e.protocol.toLowerCase().indexOf(key.toLowerCase()) >= 0; })
      .sort(function (a, b) { return b.sprint - a.sprint; });
    $$(".pill").forEach(function (p) { p.setAttribute("aria-pressed", String(p.getAttribute("data-key") === key)); });
    showResults(list); render(list[0]);
  }
  function showResults(list) {
    var box = $("#insp-results"); if (!box) return;
    box.textContent = "";
    list.slice(0, 12).forEach(function (e) {
      var b = el("button", { type: "button", text: e.protocol + " · S" + e.sprint + " · " + e.target_label });
      b.addEventListener("click", function () { render(e); });
      box.appendChild(b);
    });
  }
  function initInspector() {
    var search = $("#insp-q");
    Promise.all([fetch("api/v1/index.json").then(function (r) { return r.json(); }),
                 fetch("api/v1/radar.json").then(function (r) { return r.json(); }).catch(function () { return null; })])
      .then(function (res) {
        DATA = res[0]; FINAL = res[1] && res[1].refreshed_at ? res[1].refreshed_at.block_number : 0;
        $$(".pill").forEach(function (p) { p.addEventListener("click", function () { pick(p.getAttribute("data-key")); }); });
        if (search) search.addEventListener("input", function () {
          var t = search.value.trim().toLowerCase(); if (!t) return;
          var list = DATA.entries.filter(function (e) { return JSON.stringify(e).toLowerCase().indexOf(t) >= 0; });
          showResults(list); if (list.length) render(list[0]);
        });
        pick("Ethena");
      }).catch(function () { /* static fallback stays visible */ });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initTheme(); initMatrix(); initInspector(); tick(); setInterval(tick, 30000);
  });
})();
