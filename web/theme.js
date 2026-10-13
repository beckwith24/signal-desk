// Applies the saved colour theme before the page paints, so there is no light/dark flash.
// Dark unless this device picked Light or Auto (Auto follows the phone/computer setting).
(function () {
  "use strict";
  var pref = "dark";
  try { var v = JSON.parse(localStorage.getItem("sd.theme")); if (v === "light" || v === "auto" || v === "dark") pref = v; } catch (e) {}
  var mq = window.matchMedia ? window.matchMedia("(prefers-color-scheme: light)") : null;
  function current() { return pref === "auto" ? (mq && mq.matches ? "light" : "dark") : pref; }
  function apply() {
    var t = current();
    document.documentElement.setAttribute("data-theme", t);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute("content", t === "light" ? "#F0F3FA" : "#131722");
  }
  function changed() { apply(); try { document.dispatchEvent(new Event("sd-theme")); } catch (e) {} }
  apply();
  window.SDTheme = {
    pref: function () { return pref; },
    current: current,
    set: function (p) {
      if (p !== "light" && p !== "auto") p = "dark";
      pref = p;
      try { localStorage.setItem("sd.theme", JSON.stringify(p)); } catch (e) {}
      changed();
    },
  };
  if (mq) {
    var onSys = function () { if (pref === "auto") changed(); };
    if (mq.addEventListener) mq.addEventListener("change", onSys); else if (mq.addListener) mq.addListener(onSys);
  }
})();
