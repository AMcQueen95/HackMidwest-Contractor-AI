import { useEffect, useRef, useState } from 'react'
import { monthLabel } from '../lib/format'
import { GearIcon, Logo, UploadIcon } from './Icons'

export default function Header({ report, month, onMonth, theme, onTheme, onUpload }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (event) => {
      if (!menuRef.current?.contains(event.target)) setMenuOpen(false)
    }
    document.addEventListener('pointerdown', close)
    return () => document.removeEventListener('pointerdown', close)
  }, [menuOpen])

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <div className="brand">
          <Logo />
          <span className="brand-name">
            Toolbelt <span>CFO</span>
          </span>
        </div>

        {report && (
          <div className="dataset-badge" title="You are looking at the built-in sample books">
            {report.is_sample && <span className="dataset-tag">Sample data</span>}
            <span className="dataset-name">{report.business.name}</span>
          </div>
        )}

        <div className="topbar-actions">
          {report && (
            <div className="segmented" role="group" aria-label="Month">
              {report.months.map((m) => (
                <button
                  key={m}
                  type="button"
                  className={m === month ? 'is-active' : ''}
                  aria-pressed={m === month}
                  onClick={() => onMonth(m)}
                >
                  {monthLabel(m)}
                </button>
              ))}
            </div>
          )}
          <button type="button" className="button" onClick={onUpload}>
            <UploadIcon />
            <span className="button-label">Use your own books</span>
          </button>
          <div className="menu" ref={menuRef}>
            <button
              type="button"
              className="icon-button"
              aria-label="Settings"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen((open) => !open)}
            >
              <GearIcon />
            </button>
            {menuOpen && (
              <div className="menu-panel">
                <div className="menu-label">Appearance</div>
                <div className="segmented" role="group" aria-label="Appearance">
                  {['light', 'dark'].map((t) => (
                    <button
                      key={t}
                      type="button"
                      className={t === theme ? 'is-active' : ''}
                      aria-pressed={t === theme}
                      onClick={() => onTheme(t)}
                    >
                      {t === 'light' ? 'Light' : 'Dark'}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
