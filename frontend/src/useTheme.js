import { useEffect, useState } from 'react'

const STORAGE_KEY = 'spotter-theme'

function readInitialTheme() {
  if (typeof window === 'undefined') return 'light'
  const stored = window.localStorage?.getItem(STORAGE_KEY)
  if (stored === 'dark' || stored === 'light') return stored
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

/**
 * Colour theme, seeded from localStorage and falling back to the OS setting.
 *
 * The value is mirrored onto `<html>` rather than a local wrapper so the custom
 * properties cascade everywhere.
 */
export function useTheme() {
  const [theme, setTheme] = useState(readInitialTheme)

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    window.localStorage?.setItem(STORAGE_KEY, theme)
  }, [theme])

  return [theme, setTheme]
}
