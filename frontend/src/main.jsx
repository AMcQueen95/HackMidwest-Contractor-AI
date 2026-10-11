import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import AccountGate from './components/AccountGate.jsx'
import './styles.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <AccountGate />
  </StrictMode>,
)
