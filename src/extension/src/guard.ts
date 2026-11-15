// Runs at document_start, before YouTube registers its keyboard shortcuts, so this listener comes first.
// A key typed in a card field stops here; the field still receives the text.
for (const type of ["keydown", "keypress", "keyup"]) {
  window.addEventListener(
    type,
    (e) => {
      const target = e.target as Element | null;
      if (target instanceof HTMLInputElement && target.closest(".fc-layer")) e.stopImmediatePropagation();
    },
    true,
  );
}

// P pins the newest card on the player, unless the person is typing. YouTube never sees that key.
window.addEventListener(
  "keydown",
  (e) => {
    const target = e.target as HTMLElement;
    if (e.key.toLowerCase() !== "p" || e.ctrlKey || e.metaKey || e.altKey) return;
    if (target.matches?.("input, textarea") || target.isContentEditable) return;
    const pin = [...document.querySelectorAll<HTMLElement>('.fc-layer .fc-pin[data-pinned="false"]')].pop();
    if (!pin) return;
    e.stopImmediatePropagation();
    pin.click();
  },
  true,
);
