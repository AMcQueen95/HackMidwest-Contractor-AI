import { createContext, useContext } from 'react'

export const CHART_COLORS = {
  light: { previous: '#5F86C4', current: '#E8590C', grid: '#E6E8EC', text: '#5B6472', surface: '#FFFFFF' },
  dark: { previous: '#6C93D1', current: '#E8590C', grid: '#2A3140', text: '#A3ACBA', surface: '#171C26' },
}

const THEME_KEY = 'toolbelt-theme'

export function savedTheme() {
  try {
    return localStorage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'
  } catch {
    return 'light'
  }
}

export function applyTheme(theme) {
  document.documentElement.dataset.theme = theme
  try {
    localStorage.setItem(THEME_KEY, theme)
  } catch {
    return
  }
}

export const ThemeContext = createContext('light')
export const useChartColors = () => CHART_COLORS[useContext(ThemeContext)]
