(function () {
  if (window.__qiccGate) return;
  window.__qiccGate = true;

  var TOKEN_KEY = "qicc_gate_token";

  function currentToken() {
    try { return localStorage.getItem(TOKEN_KEY) || sessionStorage.getItem(TOKEN_KEY) || ""; }
    catch (e) { return ""; }
  }

  function saveToken(token) {
    if (!token) return;
    try { localStorage.setItem(TOKEN_KEY, token); } catch (e) {}
    try { sessionStorage.setItem(TOKEN_KEY, token); } catch (e) {}
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
    "background:#14161a;font-family:Inter,Segoe UI,system-ui,sans-serif;color:#f4f4f5}" +
    "#qicc-gate .card{width:min(360px,92vw);background:#1c1f26;border:1px solid #2e3340;border-radius:16px;" +
    "padding:28px 24px 24px;box-shadow:0 18px 50px rgba(0,0,0,.45)}" +
    "#qicc-gate h1{margin:0 0 6px;font-size:20px;letter-spacing:.02em}" +
    "#qicc-gate p{margin:0 0 16px;color:#9aa3b2;font-size:14px;line-height:1.4}" +
    "#qicc-gate input{width:100%;box-sizing:border-box;padding:12px 14px;border-radius:10px;border:1.5px solid #3a4150;" +
    "background:#14161a;color:#fff;font-size:22px;letter-spacing:.28em;text-align:center}" +
    "#qicc-gate input:focus{outline:none;border-color:#E60000}" +
    "#qicc-gate button{width:100%;margin-top:12px;padding:12px 14px;border:0;border-radius:10px;" +
    "background:#E60000;color:#fff;font-weight:700;font-size:15px;cursor:pointer}" +
    "#qicc-gate button:disabled{opacity:.6;cursor:wait}" +
    "#qicc-gate .err{min-height:18px;margin:10px 0 0;color:#ff8a80;font-size:13px;text-align:center}";
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
    var wrap = document.createElement("div");
    wrap.id = "qicc-gate";
    wrap.innerHTML =
      '<div class="card">' +
        "<h1>QICC Production</h1>" +
        "<p>Enter the site PIN to open the apps.</p>" +
        '<form id="qicc-gate-form">' +
          '<input id="qicc-gate-pin" type="password" inputmode="numeric" autocomplete="off" maxlength="12" autofocus>' +
          "<button type=\"submit\">Unlock</button>" +
        "</form>" +
        '<div class="err" id="qicc-gate-err"></div>' +
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
    checkGate().then(function (ok) {
      if (ok) { unlockUi(); return; }
      if (inFrame) waitForParent();
      else showPrompt();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
