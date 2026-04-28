(function () {
  "use strict";

  var LANG_KEY = "fc-lang";
  var DEFAULT_LANG = "zh-CN";
  var SUPPORTED = ["zh-CN", "zh-TW", "en", "de", "fr", "ja"];
  var LANG_LABELS = {
    "zh-CN": {
      "zh-CN": "简体中文",
      "zh-TW": "繁體中文",
      "en": "English",
      "de": "Deutsch",
      "fr": "Français",
      "ja": "日本語"
    },
    "zh-TW": {
      "zh-CN": "簡體中文",
      "zh-TW": "繁體中文",
      "en": "English",
      "de": "Deutsch",
      "fr": "Français",
      "ja": "日本語"
    },
    "en": {
      "zh-CN": "Simplified Chinese",
      "zh-TW": "Traditional Chinese",
      "en": "English",
      "de": "German",
      "fr": "French",
      "ja": "Japanese"
    },
    "de": {
      "zh-CN": "Vereinfachtes Chinesisch",
      "zh-TW": "Traditionelles Chinesisch",
      "en": "Englisch",
      "de": "Deutsch",
      "fr": "Französisch",
      "ja": "Japanisch"
    },
    "fr": {
      "zh-CN": "Chinois simplifié",
      "zh-TW": "Chinois traditionnel",
      "en": "Anglais",
      "de": "Allemand",
      "fr": "Français",
      "ja": "Japonais"
    },
    "ja": {
      "zh-CN": "簡体字中国語",
      "zh-TW": "繁体字中国語",
      "en": "英語",
      "de": "ドイツ語",
      "fr": "フランス語",
      "ja": "日本語"
    }
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

  var currentLang = DEFAULT_LANG;
  var localeData = { messages: {}, raw: {}, patterns: [] };
  var fallbackData = { messages: {}, raw: {}, patterns: [] };

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

  function translateRaw(rawText) {
    var src = String(rawText || "");
    if (!src) return src;
    var lead = (src.match(/^\s*/) || [""])[0];
    var tail = (src.match(/\s*$/) || [""])[0];
    var core = src.trim();
    if (!core) return src;

    var curRaw = (localeData && localeData.raw) || {};
    var fbRaw = (fallbackData && fallbackData.raw) || {};

    var out = "";
    if (Object.prototype.hasOwnProperty.call(curRaw, core)) out = String(curRaw[core] || "");
    if (!out && Object.prototype.hasOwnProperty.call(fbRaw, core)) out = String(fbRaw[core] || "");
    if (!out) out = translateByPatterns(core, localeData);
    if (!out) out = translateByPatterns(core, fallbackData);
    if (!out) return src;
    return lead + out + tail;
  }

  function t(key, params, fallback) {
    var v = getByPath(localeData.messages || {}, key);
    if (v == null) v = getByPath(fallbackData.messages || {}, key);
    if (v == null) v = fallback != null ? fallback : key;
    return fillTemplate(String(v), params || {});
  }

  function languageLabel(uiLang, langCode) {
    var ui = normalizeLang(uiLang);
    var code = normalizeLang(langCode);
    var byUi = LANG_LABELS[ui] || LANG_LABELS[DEFAULT_LANG] || {};
    return byUi[code] || code;
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

  function apply(root) {
    var target = root || document.body;
    if (!target) return;
    applyDepth += 1;
    try {
      applyDataAttrs(target);
      applyTextNodes(target);
      applyAttributes(target);
      try {
        document.documentElement.setAttribute("lang", currentLang);
      } catch (e) {
        // ignore
      }
    } finally {
      applyDepth = Math.max(0, applyDepth - 1);
    }
  }

  function hasActiveSelect() {
    try {
      var el = document.activeElement;
      return !!el && String(el.tagName || "").toUpperCase() === "SELECT";
    } catch (e) {
      return false;
    }
  }

  function ensureObserver() {
    if (mutationObserver || !window.MutationObserver) return;
    mutationObserver = new MutationObserver(function () {
      if (applyDepth > 0) return;
      if (observerTimer) return;
      observerTimer = window.setTimeout(function () {
        observerTimer = null;
        if (hasActiveSelect()) return;
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
    var d = await loadLocale(DEFAULT_LANG);
    d.__loaded = true;
    fallbackData = d;
  }

  function detectPreferredLang() {
    try {
      var v = localStorage.getItem(LANG_KEY);
      if (v) return normalizeLang(v);
    } catch (e) {
      // ignore
    }
    var langs = [];
    try {
      if (Array.isArray(navigator.languages)) langs = navigator.languages.slice();
      if (!langs.length && navigator.language) langs = [navigator.language];
    } catch (e) {
      // ignore
    }
    for (var i = 0; i < langs.length; i++) {
      var n = normalizeLang(langs[i]);
      if (isSupported(n)) return n;
    }
    return DEFAULT_LANG;
  }

  async function setLanguage(lang, opts) {
    var o = opts || {};
    var code = normalizeLang(lang);
    await ensureFallback();
    try {
      localeData = await loadLocale(code);
      localeData.__loaded = true;
      currentLang = code;
    } catch (e) {
      localeData = fallbackData;
      currentLang = DEFAULT_LANG;
    }

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
    for (var i = 0; i < SUPPORTED.length; i++) {
      var code = SUPPORTED[i];
      var opt = selectEl.querySelector('option[value="' + code + '"]');
      if (!opt) {
        opt = document.createElement("option");
        opt.value = code;
        selectEl.appendChild(opt);
      }
      opt.textContent = languageLabel(uiLang, code);
    }
    selectEl.value = currentLang;
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
    selectEl.addEventListener("change", function () {
      setLanguage(selectEl.value, { persist: true, apply: true, emit: true }).catch(function () {});
    });
  }

  async function initPage(opts) {
    var o = opts || {};
    await setLanguage(detectPreferredLang(), { persist: false, apply: true, emit: false });
    ensureObserver();
    var selectId = String(o.selectId || "").trim();
    if (selectId) {
      bindLanguageSelect(document.getElementById(selectId));
    }
    return currentLang;
  }

  window.fccI18n = {
    key: LANG_KEY,
    defaultLang: DEFAULT_LANG,
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
