(function () {
  if (window.__qiccGate) return;
  window.__qiccGate = true;

  var TOKEN_KEY = "qicc_gate_token";
  var SESSION_KEY = "qicc_gate_ok";

  function currentToken() {
    try { return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || ""; }
    catch (e) { return ""; }
  }

  function sessionUnlocked() {
    try { return sessionStorage.getItem(SESSION_KEY) === "1"; }
    catch (e) { return false; }
  }

  function markSessionUnlocked() {
    try { sessionStorage.setItem(SESSION_KEY, "1"); } catch (e) {}
  }

  function saveToken(token) {
    if (!token) return;
    try { localStorage.setItem(TOKEN_KEY, token); } catch (e) {}
    try { sessionStorage.setItem(TOKEN_KEY, token); } catch (e) {}
    markSessionUnlocked();
  }

  function isApiRequest(input) {
    var url = typeof input === "string" ? input : (input && input.url) || "";
    try {
      var parsed = new URL(url, window.location.href);
      return parsed.origin === window.location.origin && parsed.pathname.indexOf("/api/") === 0;
    } catch (e) {
      return url.indexOf("/api/") === 0;
    }
  }

  var origFetch = window.fetch;
  window.fetch = function (input, init) {
    init = Object.assign({}, init || {});
    if (isApiRequest(input)) {
      if (!init.credentials) init.credentials = "include";
      var headers = new Headers(init.headers || {});
      var token = currentToken();
      if (token && !headers.has("X-Qicc-Gate")) headers.set("X-Qicc-Gate", token);
      init.headers = headers;
    }
    return origFetch.call(this, input, init);
  };

  var html = document.documentElement;
  html.classList.add("qicc-locked");

  var style = document.createElement("style");
  style.textContent =
    "html.qicc-locked body{visibility:hidden!important}" +
    "html.qicc-locked #qicc-gate,html.qicc-locked #qicc-gate *{visibility:visible!important}" +
    "#qicc-gate{position:fixed;inset:0;z-index:2147483646;display:flex;align-items:center;justify-content:center;" +
    "background:#001a33;background-image:radial-gradient(ellipse at 20% 0%,rgba(0,120,212,.45),transparent 55%)," +
    "radial-gradient(ellipse at 90% 100%,rgba(80,230,255,.12),transparent 50%);" +
    "font-family:'Segoe UI',Inter,system-ui,sans-serif;color:#1b1b1b}" +
    "#qicc-gate .card{width:min(400px,92vw);background:#fff;border:1px solid #d0d5dd;border-radius:8px;" +
    "padding:22px 24px 20px;box-shadow:0 24px 64px rgba(0,26,51,.45)}" +
    "#qicc-gate .az-head{display:flex;align-items:center;gap:10px;margin:0 0 16px;padding-bottom:14px;" +
    "border-bottom:1px solid #e6e8eb}" +
    "#qicc-gate .az-head svg{width:28px;height:28px;flex-shrink:0;display:block}" +
    "#qicc-gate .az-head b{display:block;font-size:16px;font-weight:600;color:#201f1e;letter-spacing:.01em;line-height:1.15}" +
    "#qicc-gate .az-head span{display:block;font-size:12px;color:#605e5c;margin-top:2px}" +
    "#qicc-gate .brands{display:flex;align-items:center;justify-content:center;gap:12px;margin:0 0 14px;flex-wrap:wrap}" +
    "#qicc-gate .brands img{display:block;height:44px;width:auto}" +
    "#qicc-gate .brands .nx{height:22px}" +
    "#qicc-gate h1{margin:0 0 4px;font-size:20px;letter-spacing:.01em;color:#201f1e;text-align:center}" +
    "#qicc-gate p{margin:0 0 16px;color:#605e5c;font-size:14px;line-height:1.4;text-align:center}" +
    "#qicc-gate input{width:100%;box-sizing:border-box;padding:12px 14px;border-radius:4px;border:1.5px solid #8a8886;" +
    "background:#fff;color:#201f1e;font-size:22px;letter-spacing:.28em;text-align:center}" +
    "#qicc-gate input:focus{outline:none;border-color:#0078D4;box-shadow:0 0 0 1px #0078D4}" +
    "#qicc-gate button{width:100%;margin-top:12px;padding:12px 14px;border:0;border-radius:4px;" +
    "background:#0078D4;color:#fff;font-weight:600;font-size:15px;cursor:pointer}" +
    "#qicc-gate button:hover{background:#106EBE}" +
    "#qicc-gate button:disabled{opacity:.6;cursor:wait}" +
    "#qicc-gate .err{min-height:18px;margin:10px 0 0;color:#a4262c;font-size:13px;text-align:center}" +
    "#qicc-gate .hosted{margin:16px 0 0;padding-top:12px;border-top:1px solid #e6e8eb;display:flex;" +
    "align-items:center;justify-content:center;gap:8px;color:#605e5c;font-size:12px}" +
    "#qicc-gate .hosted svg{width:16px;height:16px;flex-shrink:0}";
  document.head.appendChild(style);

  function unlockUi() {
    html.classList.remove("qicc-locked");
    var el = document.getElementById("qicc-gate");
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  function checkGate() {
    return fetch("/api/gate", { credentials: "include", cache: "no-store" }).then(function (r) {
      return r.ok;
    }).catch(function () { return false; });
  }

  function waitForParent() {
    function tick() {
      checkGate().then(function (ok) {
        if (ok) { window.location.reload(); return; }
        setTimeout(tick, 500);
      });
    }
    tick();
  }

  function showPrompt() {
    if (document.getElementById("qicc-gate")) return;
    var wrap = document.createElement("div");
    wrap.id = "qicc-gate";
    var azMark =
      '<svg viewBox="0 0 18 18" aria-hidden="true">' +
        '<path fill="#0078D4" d="M6.44.5 0 16.7h4.22L16.05.5z"/>' +
        '<path fill="#50E6FF" d="M10.15 11.28 7.18 6.05 16.05.5 10.15 11.28z"/>' +
        '<path fill="#0078D4" d="M6.9 12.18h6.02L16.05 16.7H3.78z"/>' +
      "</svg>";
    wrap.innerHTML =
      '<div class="card">' +
        '<div class="az-head">' + azMark +
          "<div><b>Microsoft Azure</b><span>Static Web Apps</span></div>" +
        "</div>" +
        '<div class="brands">' +
          '<img class="nx" src="/nexans-logo.svg" alt="Nexans">' +
        "</div>" +
        "<h1>QICC Production</h1>" +
        "<p>Enter the site PIN to open the apps.</p>" +
        '<form id="qicc-gate-form">' +
          '<input id="qicc-gate-pin" type="password" inputmode="numeric" autocomplete="off" maxlength="12" autofocus>' +
          "<button type=\"submit\">Unlock</button>" +
        "</form>" +
        '<div class="err" id="qicc-gate-err"></div>' +
        '<div class="hosted">' + azMark + "<span>Hosted on Microsoft Azure</span></div>" +
      "</div>";
    (document.body || html).appendChild(wrap);
    var form = document.getElementById("qicc-gate-form");
    var input = document.getElementById("qicc-gate-pin");
    var err = document.getElementById("qicc-gate-err");
    var btn = form.querySelector("button");
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      var pin = (input.value || "").trim();
      if (!pin) { err.textContent = "Enter the PIN."; return; }
      btn.disabled = true;
      err.textContent = "";
      fetch("/api/unlock", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pin: pin }),
      }).then(function (r) {
        if (!r.ok) throw new Error("wrong");
        return r.json();
      }).then(function (data) {
        if (data && data.token) saveToken(data.token);
        else markSessionUnlocked();
        window.location.reload();
      }).catch(function () {
        err.textContent = "Wrong PIN.";
        input.value = "";
        input.focus();
      }).then(function () {
        btn.disabled = false;
      });
    });
    setTimeout(function () { try { input.focus(); } catch (e) {} }, 50);
  }

  function start() {
    var inFrame = window !== window.top;
    if (inFrame) {
      checkGate().then(function (ok) {
        if (ok) { unlockUi(); return; }
        waitForParent();
      });
      return;
    }
    if (sessionUnlocked()) {
      checkGate().then(function (ok) {
        if (ok) unlockUi();
        else showPrompt();
      });
      return;
    }
    showPrompt();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
