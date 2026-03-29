import { useState, useEffect } from 'react'
import { api, isLoggedIn } from '../api/client'

const DEFER_COUNT = 3
const DISMISSED_KEY = 'sipsense_push_dismissed'
const SUBSCRIBED_KEY = 'sipsense_push_subscribed'
const VISIT_KEY = 'sipsense_visit_count'

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = window.atob(base64)
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

async function doSubscribe(key) {
  try {
    const reg = await navigator.serviceWorker.ready
    const sub = await reg.pushManager.subscribe({
      userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(key),
    })
    await api.subscribePush(sub, navigator.userAgent)
    localStorage.setItem(SUBSCRIBED_KEY, 'true')
  } catch {
    // Silent failure
  }
}

export default function PushPermissionBanner() {
  const [show, setShow] = useState(false)
  const [vapidKey, setVapidKey] = useState(null)

  useEffect(() => {
    if (!isLoggedIn()) return
    if (!('serviceWorker' in navigator) || !('PushManager' in window)) return
    if (Notification.permission === 'denied') return
    if (localStorage.getItem(SUBSCRIBED_KEY) === 'true') return
    if (localStorage.getItem(DISMISSED_KEY) === 'true') return

    // Defer until user has visited a few times
    const count = parseInt(localStorage.getItem(VISIT_KEY) || '0', 10) + 1
    localStorage.setItem(VISIT_KEY, String(count))
    if (count < DEFER_COUNT) return

    // Already granted? Subscribe silently if we have permission
    if (Notification.permission === 'granted') {
      api.getPushStatus().then((status) => {
        if (!status.subscribed && status.vapid_public_key) {
          doSubscribe(status.vapid_public_key)
        } else if (status.subscribed) {
          localStorage.setItem(SUBSCRIBED_KEY, 'true')
        }
      }).catch(() => {})
      return
    }

    // Need to ask — show the banner
    api.getPushStatus().then((status) => {
      if (status.subscribed) {
        localStorage.setItem(SUBSCRIBED_KEY, 'true')
        return
      }
      if (status.vapid_public_key) {
        setVapidKey(status.vapid_public_key)
        setShow(true)
      }
    }).catch(() => {})
  }, [])

  async function handleEnable() {
    try {
      const permission = await Notification.requestPermission()
      if (permission !== 'granted') {
        setShow(false)
        return
      }
      const reg = await navigator.serviceWorker.ready
      const sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidKey),
      })
      await api.subscribePush(sub, navigator.userAgent)
      localStorage.setItem(SUBSCRIBED_KEY, 'true')
    } catch (err) {
      console.error('Push subscription failed:', err)
    }
    setShow(false)
  }

  function handleDismiss() {
    localStorage.setItem(DISMISSED_KEY, 'true')
    setShow(false)
  }

  if (!show) return null

  return (
    <div style={styles.banner}>
      <div style={styles.content}>
        <span style={{ fontSize: 24 }}>&#x1f514;</span>
        <div>
          <strong style={styles.title}>Get instant notifications</strong>
          <p style={styles.subtitle}>
            Know when someone follows you, comments, or a price drops
          </p>
        </div>
      </div>
      <div style={styles.actions}>
        <button onClick={handleEnable} style={styles.enableBtn}>
          Enable
        </button>
        <button onClick={handleDismiss} style={styles.dismissBtn}>
          Not now
        </button>
      </div>
    </div>
  )
}

const styles = {
  banner: {
    position: 'fixed',
    bottom: 0,
    left: 0,
    right: 0,
    zIndex: 9998,
    background: '#2a1a0e',
    borderTop: '1px solid #d4a94b44',
    padding: '12px 16px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    boxShadow: '0 -2px 12px rgba(0,0,0,0.4)',
  },
  content: { display: 'flex', alignItems: 'center', gap: 12 },
  title: { color: '#d4a94b', fontSize: 14, display: 'block' },
  subtitle: { color: '#bfa98a', fontSize: 12, margin: '2px 0 0' },
  actions: { display: 'flex', gap: 8, flexShrink: 0 },
  enableBtn: {
    background: '#d4a94b',
    color: '#2a1a0e',
    border: 'none',
    borderRadius: 6,
    padding: '8px 16px',
    fontWeight: 600,
    fontSize: 13,
    cursor: 'pointer',
  },
  dismissBtn: {
    background: 'transparent',
    color: '#bfa98a',
    border: '1px solid #bfa98a44',
    borderRadius: 6,
    padding: '8px 12px',
    fontSize: 13,
    cursor: 'pointer',
  },
}
