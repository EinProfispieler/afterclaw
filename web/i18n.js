(function () {
  "use strict";

  var LANG_KEY = "fc-lang";
  var DEFAULT_LANG = "en";
  var FALLBACK_LANG = "zh-CN";
  var SUPPORTED = ["zh-CN", "zh-TW", "en", "de", "fr", "ja"];
  var LANG_ENDONYMS = {
    "zh-CN": "简体中文",
    "zh-TW": "繁體中文",
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "ja": "日本語"
  };
  var LANG_SELECT_TITLE = {
    "zh-CN": "语言",
    "zh-TW": "語言",
    "en": "Language",
    "de": "Sprache",
    "fr": "Langue",
    "ja": "言語"
  };
  var TEXT_NODE_RAW = new WeakMap();
  var TEXT_NODE_LAST_APPLIED = new WeakMap();
  var mutationObserver = null;
  var observerTimer = null;
  var applyDepth = 0;
  var boundLanguageSelects = [];
  var ATTR_RAW = {
    title: "data-fcc-raw-title",
    placeholder: "data-fcc-raw-placeholder",
    "aria-label": "data-fcc-raw-aria-label",
  };
  var OPTION_RAW_ATTR = "data-fcc-raw-option-text";

  var currentLang = DEFAULT_LANG;
  var localeData = { messages: {}, raw: {}, patterns: [] };
  var fallbackData = { messages: {}, raw: {}, patterns: [] };
  var englishData = { messages: {}, raw: {}, patterns: [] };
  var revealGuardTimer = null;
  var initPagePromise = null;
  var langMenuBusyUntil = 0;

  function isSupported(lang) {
    return SUPPORTED.indexOf(lang) >= 0;
  }

  function normalizeLang(raw) {
    var v = String(raw || "").trim();
    if (!v) return DEFAULT_LANG;
    var low = v.toLowerCase();
    if (low === "zh" || low === "zh-cn" || low === "zh-hans") return "zh-CN";
    if (low === "zh-tw" || low === "zh-hk" || low === "zh-mo" || low === "zh-hant") return "zh-TW";
    if (low.indexOf("en") === 0) return "en";
    if (low.indexOf("de") === 0) return "de";
    if (low.indexOf("fr") === 0) return "fr";
    if (low.indexOf("ja") === 0) return "ja";
    return isSupported(v) ? v : DEFAULT_LANG;
  }

  function getByPath(obj, path) {
    if (!obj || !path) return undefined;
    var segs = String(path).split(".");
    var cur = obj;
    for (var i = 0; i < segs.length; i++) {
      if (cur == null || typeof cur !== "object" || !(segs[i] in cur)) return undefined;
      cur = cur[segs[i]];
    }
    return cur;
  }

  function fillTemplate(text, params) {
    var src = String(text || "");
    var p = params || {};
    return src.replace(/\{([a-zA-Z0-9_]+)\}/g, function (_, key) {
      return Object.prototype.hasOwnProperty.call(p, key) ? String(p[key]) : "";
    });
  }

  function translateByPatterns(rawText, data) {
    var src = String(rawText || "");
    var rows = (data && Array.isArray(data.patterns)) ? data.patterns : [];
    for (var i = 0; i < rows.length; i++) {
      var row = rows[i] || {};
      var reText = String(row.re || "");
      var to = String(row.to || "");
      if (!reText || !to) continue;
      try {
        var re = new RegExp(reText);
        if (re.test(src)) {
          return src.replace(re, to);
        }
      } catch (e) {
        // ignore bad regex
      }
    }
    return "";
  }

  function translateWithData(rawText, data) {
    var src = String(rawText || "");
    if (!src) return "";
    var rawMap = (data && data.raw) || {};
    if (Object.prototype.hasOwnProperty.call(rawMap, src)) {
      return String(rawMap[src] || "");
    }
    return translateByPatterns(src, data);
  }

  function translateWithChain(rawText, data, maxDepth) {
    var src = String(rawText || "");
    if (!src) return "";
    var depth = Number(maxDepth);
    if (!Number.isFinite(depth) || depth < 1) depth = 3;
    var seen = {};
    seen[src] = true;
    var cur = src;
    var changed = false;
    for (var i = 0; i < depth; i++) {
      var next = translateWithData(cur, data);
      if (!next || next === cur) break;
      changed = true;
      if (seen[next]) {
        cur = next;
        break;
      }
      seen[next] = true;
      cur = next;
    }
    return changed ? cur : "";
  }

  function shouldPreferEnglishFallback() {
    return currentLang !== "zh-CN" && currentLang !== "zh-TW";
  }

  function hasCjk(text) {
    return /[\u3400-\u9FFF]/.test(String(text || ""));
  }

  function translateRaw(rawText) {
    var src = String(rawText || "");
    if (!src) return src;
    var lead = (src.match(/^\s*/) || [""])[0];
    var tail = (src.match(/\s*$/) || [""])[0];
    var core = src.trim();
    if (!core) return src;

    var out = "";
    out = translateWithChain(core, localeData, 4);
    if (!out && shouldPreferEnglishFallback()) {
      var enOut = translateWithChain(core, englishData, 4);
      if (enOut) {
        // Bridge: source text may be zh-CN, enOut is English key, then map to current locale directly.
        if (currentLang !== "en") {
          out = translateWithChain(enOut, localeData, 4) || enOut;
        } else {
          out = enOut;
        }
      }
    }
    if (!out && hasCjk(core)) out = translateWithChain(core, fallbackData, 4);
    if (!out) return src;
    return lead + out + tail;
  }

  function t(key, params, fallback) {
    var v = getByPath(localeData.messages || {}, key);
    if (v == null && shouldPreferEnglishFallback()) v = getByPath(englishData.messages || {}, key);
    if (v == null) v = getByPath(fallbackData.messages || {}, key);
    if (v == null) v = fallback != null ? fallback : key;
    return fillTemplate(String(v), params || {});
  }

  function languageLabel(uiLang, langCode) {
    var code = normalizeLang(langCode);
    return LANG_ENDONYMS[code] || code;
  }

  function applyDataAttrs(root) {
    if (!root || !root.querySelectorAll) return;
    var nodes = root.querySelectorAll("[data-i18n]");
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var key = el.getAttribute("data-i18n");
      var fb = el.getAttribute("data-i18n-fallback") || "";
      var txt = t(key, {}, fb);
      if (el.getAttribute("data-i18n-html") === "1") el.innerHTML = txt;
      else el.textContent = txt;
    }
    var attrs = ["placeholder", "title", "aria-label"];
    for (var ai = 0; ai < attrs.length; ai++) {
      var attr = attrs[ai];
      var sel = "[data-i18n-" + attr + "]";
      var els = root.querySelectorAll(sel);
      for (var j = 0; j < els.length; j++) {
        var e = els[j];
        var k = e.getAttribute("data-i18n-" + attr);
        if (!k) continue;
        e.setAttribute(attr, t(k, {}, e.getAttribute(attr) || ""));
      }
    }
  }

  function applyTextNodes(root) {
    if (!root || !document.createTreeWalker) return;
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        if (!node || !node.parentNode) return NodeFilter.FILTER_REJECT;
        var p = node.parentNode;
        var c = p;
        while (c) {
          if (String((c.tagName || "")).toUpperCase() === "SELECT") return NodeFilter.FILTER_REJECT;
          c = c.parentNode;
        }
        var tag = String((p.tagName || "")).toUpperCase();
        if (tag === "SCRIPT" || tag === "STYLE" || tag === "NOSCRIPT") return NodeFilter.FILTER_REJECT;
        if (p.getAttribute && p.getAttribute("data-i18n-no-raw") === "1") return NodeFilter.FILTER_REJECT;
        var raw = String(node.nodeValue || "");
        return raw.trim() ? NodeFilter.FILTER_ACCEPT : NodeFilter.FILTER_REJECT;
      }
    });

    var collected = [];
    while (walker.nextNode()) collected.push(walker.currentNode);
    for (var i = 0; i < collected.length; i++) {
      var n = collected[i];
      var currentText = String(n.nodeValue || "");
      if (!TEXT_NODE_RAW.has(n)) {
        TEXT_NODE_RAW.set(n, currentText);
      } else {
        var lastApplied = TEXT_NODE_LAST_APPLIED.has(n) ? String(TEXT_NODE_LAST_APPLIED.get(n) || "") : null;
        if (lastApplied !== null && currentText !== lastApplied) {
          TEXT_NODE_RAW.set(n, currentText);
        }
      }
      var src = TEXT_NODE_RAW.get(n) || "";
      var out = translateRaw(src);
      if (out !== n.nodeValue) n.nodeValue = out;
      TEXT_NODE_LAST_APPLIED.set(n, out);
    }
  }

  function applyAttributes(root) {
    if (!root || !root.querySelectorAll) return;
    var attrs = Object.keys(ATTR_RAW);
    for (var i = 0; i < attrs.length; i++) {
      var attr = attrs[i];
      var all = root.querySelectorAll("[" + attr + "]");
      for (var j = 0; j < all.length; j++) {
        var el = all[j];
        if (String((el.tagName || "")).toUpperCase() === "SELECT") continue;
        if (String((el.tagName || "")).toUpperCase() === "OPTION") continue;
        var rawAttr = ATTR_RAW[attr];
        if (!el.hasAttribute(rawAttr)) {
          el.setAttribute(rawAttr, el.getAttribute(attr) || "");
        }
        var src = el.getAttribute(rawAttr) || "";
        var out = translateRaw(src);
        if (out !== src) el.setAttribute(attr, out);
      }
    }
  }

  function applySelectOptions(root) {
    if (!root || !root.querySelectorAll) return;
    var options = root.querySelectorAll("option");
    for (var i = 0; i < options.length; i++) {
      var opt = options[i];
      var selectEl = null;
      try { selectEl = opt.closest ? opt.closest("select") : null; } catch (e) { selectEl = null; }
      if (!selectEl) continue;
      // Language menu should always use endonyms rendered by renderLanguageSelect.
      if ((selectEl.id || "") === "langSelect" || (selectEl.classList && selectEl.classList.contains("lang-select"))) {
        continue;
      }
      if (opt.getAttribute && opt.getAttribute("data-i18n")) continue;
      if (!opt.hasAttribute(OPTION_RAW_ATTR)) {
        opt.setAttribute(OPTION_RAW_ATTR, opt.textContent || "");
      }
      var src = opt.getAttribute(OPTION_RAW_ATTR) || "";
      var out = translateRaw(src);
      if (out !== opt.textContent) opt.textContent = out;
    }
  }

  function apply(root) {
    var target = root || document.body;
    if (!target) return;
    applyDepth += 1;
    try {
      applyDataAttrs(target);
      applyTextNodes(target);
      applyAttributes(target);
      applySelectOptions(target);
      try {
        document.documentElement.setAttribute("lang", currentLang);
      } catch (e) {
        // ignore
      }
    } finally {
      applyDepth = Math.max(0, applyDepth - 1);
    }
  }

  function ensureObserver() {
    if (mutationObserver || !window.MutationObserver) return;
    mutationObserver = new MutationObserver(function () {
      if (Date.now() < langMenuBusyUntil) return;
      if (applyDepth > 0) return;
      if (observerTimer) return;
      observerTimer = window.setTimeout(function () {
        observerTimer = null;
        if (Date.now() < langMenuBusyUntil) return;
        apply(document.body);
      }, 0);
    });
    var root = document.body || document.documentElement;
    if (!root) return;
    mutationObserver.observe(root, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["title", "placeholder", "aria-label"]
    });
  }

  async function loadLocale(lang) {
    var code = normalizeLang(lang);
    var res = await fetch("/locales/" + encodeURIComponent(code) + ".json", {
      cache: "no-store",
      credentials: "same-origin"
    });
    if (!res.ok) throw new Error("locale load failed: " + code);
    return await res.json();
  }

  async function ensureFallback() {
    if (fallbackData && fallbackData.__loaded) return;
    var d = await loadLocale(FALLBACK_LANG);
    d.__loaded = true;
    fallbackData = d;
  }

  async function ensureEnglish() {
    if (englishData && englishData.__loaded) return;
    var d = await loadLocale("en");
    d.__loaded = true;
    englishData = d;
  }

  function detectPreferredLang() {
    try {
      var v = localStorage.getItem(LANG_KEY);
      if (v) return normalizeLang(v);
    } catch (e) {
      // ignore
    }
    return DEFAULT_LANG;
  }

  function markPendingBeforeInit() {
    try {
      // Always hide until i18n is ready to avoid first-paint mixed language flash.
      document.documentElement.setAttribute("data-i18n-pending", "1");
    } catch (e) {
      // ignore
    }
  }

  function clearPendingAfterInit() {
    try { document.documentElement.removeAttribute("data-i18n-pending"); } catch (e) {}
    if (revealGuardTimer) {
      try { window.clearTimeout(revealGuardTimer); } catch (e) {}
      revealGuardTimer = null;
    }
  }

  markPendingBeforeInit();
  try {
    revealGuardTimer = window.setTimeout(function () {
      clearPendingAfterInit();
    }, 4500);
  } catch (e) {
    // ignore
  }

  async function setLanguage(lang, opts) {
    var o = opts || {};
    var code = normalizeLang(lang);
    await ensureFallback();
    try {
      await ensureEnglish();
    } catch (e) {
      englishData = fallbackData;
    }
    try {
      localeData = await loadLocale(code);
      localeData.__loaded = true;
      currentLang = code;
    } catch (e) {
      localeData = fallbackData;
      currentLang = DEFAULT_LANG;
    }

    clearPendingAfterInit();

    if (o.persist !== false) {
      try { localStorage.setItem(LANG_KEY, currentLang); } catch (e) {}
    }
    if (o.apply !== false) apply(document.body);
    refreshBoundLanguageSelects();
    if (o.emit !== false) {
      try {
        document.dispatchEvent(new CustomEvent("fcc:lang-changed", { detail: { lang: currentLang } }));
      } catch (e) {
        // ignore
      }
    }
    return currentLang;
  }

  function renderLanguageSelect(selectEl) {
    if (!selectEl) return;
    try {
      selectEl.disabled = false;
      selectEl.removeAttribute("disabled");
    } catch (e) {
      // ignore
    }
    var uiLang = normalizeLang(currentLang);
    if (document.activeElement === selectEl) {
      try { selectEl.setAttribute("title", LANG_SELECT_TITLE[uiLang] || "Language"); } catch (e) {}
      return;
    }
    var selectedCode = normalizeLang(currentLang);
    var frag = document.createDocumentFragment();
    for (var i = 0; i < SUPPORTED.length; i++) {
      var code = SUPPORTED[i];
      var opt = document.createElement("option");
      opt.value = code;
      opt.textContent = languageLabel(uiLang, code);
      frag.appendChild(opt);
    }
    while (selectEl.firstChild) selectEl.removeChild(selectEl.firstChild);
    selectEl.appendChild(frag);
    selectEl.value = selectedCode;
    try { selectEl.setAttribute("title", LANG_SELECT_TITLE[uiLang] || "Language"); } catch (e) {}
  }

  function refreshBoundLanguageSelects() {
    if (!boundLanguageSelects.length) return;
    for (var i = boundLanguageSelects.length - 1; i >= 0; i--) {
      var el = boundLanguageSelects[i];
      if (!el || !el.isConnected) {
        boundLanguageSelects.splice(i, 1);
        continue;
      }
      renderLanguageSelect(el);
    }
  }

  function bindLanguageSelect(selectEl) {
    if (!selectEl) return;
    if (selectEl.__fccLangBound) {
      renderLanguageSelect(selectEl);
      return;
    }
    selectEl.__fccLangBound = true;
    boundLanguageSelects.push(selectEl);
    renderLanguageSelect(selectEl);
    var hold = function () {
      langMenuBusyUntil = Math.max(langMenuBusyUntil, Date.now() + 12000);
    };
    ["mousedown", "click", "focus", "touchstart", "pointerdown", "keydown"].forEach(function (evt) {
      selectEl.addEventListener(evt, hold, { passive: true });
    });
    selectEl.addEventListener("blur", function () {
      langMenuBusyUntil = Math.max(langMenuBusyUntil, Date.now() + 800);
    });
    selectEl.addEventListener("change", function () {
      setLanguage(selectEl.value, { persist: true, apply: true, emit: true }).catch(function () {});
    });
  }

  async function initPage(opts) {
    var o = opts || {};
    var selectId = String(o.selectId || "").trim();
    if (!initPagePromise) {
      initPagePromise = (async function () {
        await setLanguage(detectPreferredLang(), { persist: false, apply: true, emit: false });
        ensureObserver();
        return currentLang;
      })();
    }
    await initPagePromise;
    if (selectId) bindLanguageSelect(document.getElementById(selectId));
    return currentLang;
  }

  window.fccI18n = {
    key: LANG_KEY,
    defaultLang: DEFAULT_LANG,
    fallbackLang: FALLBACK_LANG,
    supported: SUPPORTED.slice(),
    normalizeLang: normalizeLang,
    getLanguage: function () { return currentLang; },
    t: t,
    translateRaw: translateRaw,
    apply: apply,
    setLanguage: setLanguage,
    initPage: initPage,
  };

  // Fallback auto-init: if page script fails to call initPage, keep #langSelect usable.
  if (document && document.addEventListener) {
    var autoInitOnce = function () {
      if (window.__fccLangAutoInitDone) return;
      var el = document.getElementById("langSelect");
      if (!el) return;
      window.__fccLangAutoInitDone = true;
      initPage({ selectId: "langSelect" }).catch(function () {});
    };
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", autoInitOnce, { once: true });
    } else {
      autoInitOnce();
    }
  }
})();
