import { createContext, useContext } from 'react'

// Chart colors live in JS because Recharts takes them as props. Both pairs
// pass the dataviz palette validator against their own card surface.
export const CHART_COLORS = {
  light: { previous: '#5F86C4', current: '#E8590C', grid: '#E6E8EC', text: '#5B6472', surface: '#FFFFFF' },
  dark: { previous: '#6C93D1', current: '#E8590C', grid: '#2A3140', text: '#A3ACBA', surface: '#171C26' },
}

export const ThemeContext = createContext('light')
export const useChartColors = () => CHART_COLORS[useContext(ThemeContext)]
