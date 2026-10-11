import { useEffect, useState } from 'react'
import { accountAction, createCompany, getAccount, getAuthConfig, refreshAccount, setWorkspace, signOut } from '../api'
import App from '../App'

let startup = null
function loadAccount() {
  if (!startup) startup = (async () => {
    const config = await getAuthConfig()
    if (!config.configured) return { config, account: null, recovery: false }
    const fragment = new URLSearchParams(window.location.hash.slice(1))
    const recovery = fragment.get('type') === 'recovery'
    const access = fragment.get('access_token')
    const refresh = fragment.get('refresh_token')
    const callbackError = fragment.get('error_description')
    if (access || callbackError) window.history.replaceState(null, '', window.location.pathname + window.location.search)
    if (callbackError) return { config, account: null, recovery: false, error: 'This sign-in link has expired or could not be used. Request a new one.' }
    if (access && refresh) {
      try { await accountAction('session', { access_token: access, refresh_token: refresh }) }
      catch (error) { return { config, account: null, recovery: false, error: error.message } }
    }
    let account = null
    if (config.configured) {
      try { account = await getAccount() } catch (error) {
        if (error.status !== 401) return { config, account: null, recovery: false, error: error.message }
        try { await refreshAccount(); account = await getAccount() } catch (refreshError) {
          if (refreshError.status !== 401) return { config, account: null, recovery: false, error: refreshError.message }
        }
      }
    }
    return { config, account, recovery }
  })()
  return startup
}

export default function AccountGate() {
  const [ready, setReady] = useState(false)
  const [configured, setConfigured] = useState(false)
  const [account, setAccount] = useState(null)
  const [company, setCompany] = useState(null)
  const [demo, setDemo] = useState(false)
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    let live = true
    loadAccount().then(({ config, account, recovery, error }) => {
      if (!live) return
      setConfigured(config.configured)
      if (error) setError(error)
      setAccount(account)
      if (recovery) setMode('password')
    }).catch((error) => { if (live) setError(error.message) })
      .finally(() => { if (live) setReady(true) })
    const expired = () => {
      setWorkspace({ demo: false, companyId: null })
      setAccount(null); setCompany(null); setDemo(false)
      setError('Your session expired. Please sign in again.')
    }
    window.addEventListener('toolbelt-signed-out', expired)
    return () => { live = false; window.removeEventListener('toolbelt-signed-out', expired) }
  }, [])

  function changeMode(next) { setMode(next); setError(''); setMessage(''); setPassword('') }
  function openCompany(selected) {
    setWorkspace({ demo: false, companyId: selected.id })
    setCompany(selected); setDemo(false)
  }
  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(''); setMessage('')
    try {
      const body = mode === 'recover' ? { email } : mode === 'password' ? { password } : { email, password }
      const result = await accountAction(mode === 'register' ? 'signup' : mode, body)
      setPassword('')
      if (mode === 'recover' || (mode === 'register' && !result.signed_in)) {
        setMessage(result.message)
      } else {
        setAccount(await getAccount()); setMode('login')
        if (mode === 'password') setMessage(result.message)
      }
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  async function addCompany(event) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const result = await createCompany(name)
      setAccount(await getAccount()); setName(''); openCompany(result.company)
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  async function logout() {
    setBusy(true); setError('')
    try {
      await signOut()
      setWorkspace({ demo: false, companyId: null })
      setCompany(null); setAccount(null); setPassword(''); setMessage(''); setMode('login')
    } catch (error) { setError(error.message) } finally { setBusy(false) }
  }
  function leaveDashboard() {
    setWorkspace({ demo: false, companyId: null })
    setCompany(null); setDemo(false)
  }

  if (!ready) return <main className="page"><p role="status">Opening Toolbelt CFO…</p></main>
  if (company || demo) return <>
    <nav className="account-bar" aria-label="Account">
      <span>{demo ? 'Read-only demo' : `${account.user.email} · ${company.name}`}</span>
      <button className="button" onClick={leaveDashboard}>{demo ? 'Back to welcome' : 'Switch company'}</button>
      {!demo && <button className="button" onClick={logout} disabled={busy}>Sign out</button>}
      {error && <p role="alert">{error}</p>}
    </nav>
    <App key={demo ? 'demo' : company.id} demo={demo} />
  </>

  const title = mode === 'register' ? 'Create your account' : mode === 'recover' ? 'Reset your password'
    : mode === 'password' ? 'Choose a new password' : 'Sign in to your company'
  return <main className="page account-page">
    <h1>Toolbelt CFO<span>Your business finances, in one place.</span></h1>
    {error && <p role="alert" className="is-bad">{error}</p>}
    {message && <p role="status">{message}</p>}
    {account && mode !== 'password' ? <section className="account-card">
      <h2>Your companies</h2>
      <p>Signed in as {account.user.email}</p>
      {account.companies.length ? <div className="company-list">{account.companies.map((item) =>
        <button key={item.id} className="button" onClick={() => openCompany(item)}>{item.name}</button>)}</div>
        : <p>Create a company to start. Your financial records will be kept separate from the demo.</p>}
      <form onSubmit={addCompany}>
        <label htmlFor="company-name">Company name</label>
        <input id="company-name" value={name} onChange={(e) => setName(e.target.value)} required maxLength={120} />
        <button className="button button-primary" disabled={busy}>{busy ? 'Creating…' : 'Create company'}</button>
      </form>
      <button className="button" onClick={logout} disabled={busy}>Sign out</button>
    </section> : <section className="account-card">
      <h2>{title}</h2>
      {!configured && <p>Sign-in is being set up. You can explore the demo while we get it ready.</p>}
      <form onSubmit={submit}>
        {mode !== 'password' && <><label htmlFor="account-email">Email</label>
          <input id="account-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required maxLength={254} /></>}
        {mode !== 'recover' && <><label htmlFor="account-password">Password</label>
          <input id="account-password" type="password" autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
            value={password} onChange={(e) => setPassword(e.target.value)} required minLength={mode === 'login' ? 1 : 12} maxLength={128} />
          {mode !== 'login' && <p className="footnote">Use at least 12 characters. A memorable passphrase works well.</p>}</>}
        <button className="button button-primary" disabled={busy || !configured}>
          {busy ? 'Please wait…' : mode === 'register' ? 'Create account' : mode === 'recover' ? 'Send reset link' : mode === 'password' ? 'Save password' : 'Sign in'}
        </button>
      </form>
      <div className="account-links">
        {mode !== 'login' && <button className="button" onClick={() => changeMode('login')}>Back to sign in</button>}
        {mode === 'login' && <><button className="button" onClick={() => changeMode('register')}>Create account</button>
          <button className="button" onClick={() => changeMode('recover')}>Forgot password?</button></>}
      </div>
    </section>}
    <section className="account-card"><h2>See how it works</h2>
      <p>Explore Ridgeline’s fictional books. Your company starts with your own records.</p>
      <button className="button" onClick={() => { setWorkspace({ demo: true, companyId: null }); setDemo(true) }}>Try the demo</button>
    </section>
  </main>
}
