import { useState, useEffect } from 'react'

export default function InstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] = useState(null)
  const [showIosBanner, setShowIosBanner] = useState(false)
  const [dismissed, setDismissed] = useState(() => {
    try { return localStorage.getItem('sipsense_install_dismissed') === 'true' } catch { return false }
  })

  useEffect(() => {
    // Don't show if already installed or previously dismissed
    const isStandalone = window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone
    if (isStandalone || dismissed) return

    // Only show on mobile/tablet devices
    const isMobile = /android|iphone|ipad|ipod/i.test(navigator.userAgent)
      || (navigator.maxTouchPoints > 1 && window.innerWidth < 1024)
    if (!isMobile) return

    // Android/Chrome: capture the beforeinstallprompt event
    const handler = (e) => {
      e.preventDefault()
      setDeferredPrompt(e)
    }
    window.addEventListener('beforeinstallprompt', handler)

    // iOS Safari: show manual instructions
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent)
    const isSafari = /safari/i.test(navigator.userAgent) && !/chrome|crios/i.test(navigator.userAgent)
    if (isIos && isSafari) {
      setShowIosBanner(true)
    }

    return () => window.removeEventListener('beforeinstallprompt', handler)
  }, [])

  if (dismissed) return null
  if (!deferredPrompt && !showIosBanner) return null

  async function handleInstall() {
    if (deferredPrompt) {
      deferredPrompt.prompt()
      const { outcome } = await deferredPrompt.userChoice
      if (outcome === 'accepted') setDeferredPrompt(null)
    }
    setDismissed(true)
    try { localStorage.setItem('sipsense_install_dismissed', 'true') } catch { /* private browsing */ }
  }

  return (
    <div style={styles.banner}>
      <div style={styles.content}>
        <img src="/icons/icon-192.png" alt="" style={styles.icon} />
        <div>
          <strong style={styles.title}>Add SipSense to Home Screen</strong>
          <p style={styles.subtitle}>
            {showIosBanner
              ? 'Tap the share button, then "Add to Home Screen"'
              : 'Get the full app experience'}
          </p>
        </div>
      </div>
      <div style={styles.actions}>
        {!showIosBanner && (
          <button onClick={handleInstall} style={styles.installBtn}>Install</button>
        )}
        <button onClick={() => { setDismissed(true); try { localStorage.setItem('sipsense_install_dismissed', 'true') } catch { /* private browsing */ } }} style={styles.dismissBtn}>
          {showIosBanner ? 'Got it' : 'Not now'}
        </button>
      </div>
    </div>
  )
}

const styles = {
  banner: {
    position: 'fixed', bottom: 0, left: 0, right: 0, zIndex: 9999,
    background: '#2a1a0e', borderTop: '1px solid #d4a94b44',
    padding: '12px 16px', display: 'flex', alignItems: 'center',
    justifyContent: 'space-between', gap: 12,
    boxShadow: '0 -2px 12px rgba(0,0,0,0.4)',
  },
  content: { display: 'flex', alignItems: 'center', gap: 12 },
  icon: { width: 40, height: 40, borderRadius: 8 },
  title: { color: '#d4a94b', fontSize: 14, display: 'block' },
  subtitle: { color: '#bfa98a', fontSize: 12, margin: '2px 0 0' },
  actions: { display: 'flex', gap: 8, flexShrink: 0 },
  installBtn: {
    background: '#d4a94b', color: '#2a1a0e', border: 'none',
    borderRadius: 6, padding: '8px 16px', fontWeight: 600,
    fontSize: 13, cursor: 'pointer',
  },
  dismissBtn: {
    background: 'transparent', color: '#bfa98a', border: '1px solid #bfa98a44',
    borderRadius: 6, padding: '8px 12px', fontSize: 13, cursor: 'pointer',
  },
}
