"use strict";
(() => {
  // src/guard.ts
  for (const type of ["keydown", "keypress", "keyup"]) {
    window.addEventListener(
      type,
      (e) => {
        const target = e.target;
        if (target instanceof HTMLInputElement && target.closest(".fc-layer")) e.stopImmediatePropagation();
      },
      true
    );
  }
  window.addEventListener(
    "keydown",
    (e) => {
      const target = e.target;
      if (e.key.toLowerCase() !== "p" || e.ctrlKey || e.metaKey || e.altKey) return;
      if (target.matches?.("input, textarea") || target.isContentEditable) return;
      const pin = [...document.querySelectorAll('.fc-layer .fc-pin[data-pinned="false"]')].pop();
      if (!pin) return;
      e.stopImmediatePropagation();
      pin.click();
    },
    true
  );
})();
