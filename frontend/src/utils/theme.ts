export type Theme = "light" | "dark";

const THEME_KEY = "revia-theme-preference";

/**
 * Returns initial theme. By default, always opens in "light" mode.
 * Cleans up legacy keys that may have defaulted to dark mode via OS matchMedia.
 */
export function getInitialTheme(): Theme {
  try {
    // Clear old legacy key that was automatically set based on OS dark mode
    if (localStorage.getItem("revia-theme")) {
      localStorage.removeItem("revia-theme");
    }
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") {
      return saved;
    }
  } catch {}
  // Default is LIGHT mode per user requirement
  return "light";
}

/**
 * Applies theme to DOM documentElement and saves user preference.
 */
export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute("data-theme", theme);
  try {
    localStorage.setItem(THEME_KEY, theme);
  } catch {}

  const metaThemeColor = document.querySelector('meta[name="theme-color"]');
  if (metaThemeColor) {
    metaThemeColor.setAttribute("content", theme === "dark" ? "#080C14" : "#F5F0E8");
  }

  // Dispatch event for any non-React or cross-component listeners
  window.dispatchEvent(new CustomEvent("revia-theme-change", { detail: theme }));
}

/**
 * Quick query for current DOM theme state.
 */
export function isDarkMode(): boolean {
  return document.documentElement.getAttribute("data-theme") === "dark";
}
