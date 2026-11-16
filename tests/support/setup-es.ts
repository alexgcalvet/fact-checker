// The tests of the slices before S26 read the Spanish texts: they run with a Spanish browser. A test sets its own
// language on navigator.language.
Object.defineProperty(navigator, "language", { value: "es-ES", configurable: true });

// jsdom has no ResizeObserver; the overlay only needs it to refit the layer, which jsdom never lays out.
globalThis.ResizeObserver ??= class { observe() {} disconnect() {} } as unknown as typeof ResizeObserver;
