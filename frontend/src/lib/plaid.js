const SCRIPT_URL = 'https://cdn.plaid.com/link/v2/stable/link-initialize.js'

let loading = null

function loadPlaid() {
  if (window.Plaid) return Promise.resolve(window.Plaid)
  if (!loading) {
    loading = new Promise((resolve, reject) => {
      const script = document.createElement('script')
      script.src = SCRIPT_URL
      script.async = true
      script.onload = () => resolve(window.Plaid)
      script.onerror = () => {
        loading = null
        script.remove()
        reject(new Error('Could not load the bank connection window. Check your internet connection and try again.'))
      }
      document.head.append(script)
    })
  }
  return loading
}

export async function openPlaidLink(linkToken) {
  const plaid = await loadPlaid()
  return new Promise((resolve, reject) => {
    const handler = plaid.create({
      token: linkToken,
      onSuccess: (publicToken) => {
        handler.destroy?.()
        resolve(publicToken)
      },
      onExit: (error) => {
        handler.destroy?.()
        if (error) reject(new Error(error.display_message || error.error_message || 'The bank connection did not finish.'))
        else resolve(null)
      },
    })
    handler.open()
  })
}
