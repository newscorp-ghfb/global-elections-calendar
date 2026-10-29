// Keyboard and ARIA helpers both renderers share (P146): the tabs' state and keys, and keyboard
// focus across a redraw. Browser-bound (it reads the document), so it is not a pure module.

// The tab a key moves to from `current`, or null when the key is not a tab key (or `current` is
// not one of `tabs`). ArrowLeft and ArrowRight wrap.
export function tabTarget(key, tabs, current) {
  const at = tabs.indexOf(current);
  if (at < 0) return null;
  if (key === "ArrowRight") return tabs[(at + 1) % tabs.length];
  if (key === "ArrowLeft") return tabs[(at + tabs.length - 1) % tabs.length];
  if (key === "Home") return tabs[0];
  if (key === "End") return tabs[tabs.length - 1];
  return null;
}

// The shown tab is selected and in the tab order; the others are reachable by the arrow keys. The
// list panel is named by the selected tab.
export function syncTabs(tabs, filter) {
  for (const t of tabs) {
    const on = t.dataset.filter === filter;
    t.classList.toggle("active", on);
    t.setAttribute("aria-selected", String(on));
    t.tabIndex = on ? 0 : -1;
    if (on) document.getElementById("listPanel").setAttribute("aria-labelledby", t.id);
  }
}

// Calls `redraw()`. When a control with a data-focus key had focus, the visible control with the
// same key is focused afterwards, or #listPanel when there is none. A control without a key inside
// #listPanel (the legacy Open icon) that the redraw removed also sends focus to #listPanel. Focus
// anywhere else without a key (the search box, Refresh, the month arrows) is left alone.
export function keepFocus(redraw) {
  const held = document.activeElement;
  const panel = document.getElementById("listPanel");
  const key = held instanceof HTMLElement && held.dataset.focus !== undefined ? held.dataset.focus : null;
  const inPanel = held instanceof HTMLElement && held !== panel && panel.contains(held);
  redraw();
  if (key === null) {
    // defensive: no current renderer keeps a keyless control in the panel connected across a redraw
    if (inPanel && !held.isConnected) panel.focus();
    return;
  }
  const again = [...document.querySelectorAll("[data-focus]")]
    .find((el) => el.dataset.focus === key && el.getClientRects().length > 0);
  (again ?? document.getElementById("listPanel")).focus();
}
