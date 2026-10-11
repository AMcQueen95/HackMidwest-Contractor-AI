import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AccountGate from './components/AccountGate.jsx'
import { applyTheme, savedTheme } from './lib/theme'
import './styles.css'

applyTheme(savedTheme())

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AccountGate />
  </StrictMode>,
)
