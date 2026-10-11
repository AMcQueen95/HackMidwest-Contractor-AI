import { useEffect, useRef, useState } from 'react'
import { monthLabel } from '../lib/format'
import { GearIcon, Logo, UploadIcon } from './Icons'

export default function Header({ report, month, onMonth, theme, onTheme, onAddRecords, onClearBooks }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [confirming, setConfirming] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return
    const close = (event) => {
      if (!menuRef.current?.contains(event.target)) {
        setMenuOpen(false)
        setConfirming(false)
      }
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
          <div className="dataset-badge" title={report.is_sample ? 'Fictional demo company' : 'Records saved to this company'}>
            <span className="dataset-tag">{report.is_sample ? 'Demo company' : 'Your books'}</span>
            <span className="dataset-name">{report.business.name}</span>
          </div>
        )}

        <div className="topbar-actions">
          {report && report.months.length > 3 && (
            <select className="month-select" aria-label="Month" value={month} onChange={(event) => onMonth(event.target.value)}>
              {report.months.map((m) => (
                <option key={m} value={m}>{monthLabel(m)}</option>
              ))}
            </select>
          )}
          {report && report.months.length <= 3 && (
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
          {onAddRecords && <button type="button" className="button" onClick={onAddRecords}>
            <UploadIcon />
            <span className="button-label">Add records</span>
          </button>}
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
                {onClearBooks && (
                  <div className="menu-section">
                    <div className="menu-label">Company records</div>
                    {confirming ? (
                      <>
                        <p className="menu-warning">This removes every record and bank connection for this company. It can't be undone.</p>
                        <div className="menu-actions">
                          <button type="button" className="button button-quiet" onClick={() => setConfirming(false)}>Keep records</button>
                          <button type="button" className="button button-quiet button-danger"
                            onClick={() => { setMenuOpen(false); setConfirming(false); onClearBooks() }}>
                            Yes, clear them
                          </button>
                        </div>
                      </>
                    ) : (
                      <button type="button" className="button button-quiet" onClick={() => setConfirming(true)}>Clear company books</button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
