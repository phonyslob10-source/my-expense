export const FONT_SIZE_KEY = 'expense-font-size'
export const FONT_SIZE_OPTIONS = [
  { value: 'small', label: '小号', scale: 0.8125 },
  { value: 'medium', label: '适中', scale: 0.875 },
  { value: 'original', label: '原字号', scale: 1 },
] as const
export type FontSize = typeof FONT_SIZE_OPTIONS[number]['value']

export function readFontSize(): FontSize {
  try {
    const saved = localStorage.getItem(FONT_SIZE_KEY)
    return FONT_SIZE_OPTIONS.find(option => option.value === saved)?.value ?? 'medium'
  } catch {
    return 'medium'
  }
}

export function applyFontSize(value: FontSize) {
  const option = FONT_SIZE_OPTIONS.find(option => option.value === value)!
  document.documentElement.style.setProperty('--font-scale', String(option.scale))
  try {
    localStorage.setItem(FONT_SIZE_KEY, value)
  } catch {
    // The current session still works when browser storage is unavailable.
  }
}
