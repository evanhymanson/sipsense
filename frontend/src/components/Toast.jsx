import { useState, useEffect, useCallback, createContext, useContext } from 'react'

const ToastContext = createContext(null)

// eslint-disable-next-line react-refresh/only-export-components
export function useToast() {
  return useContext(ToastContext)
}

function ToastItem({ toast, onRemove }) {
  useEffect(() => {
    const t = setTimeout(() => onRemove(toast.id), toast.duration || 3500)
    return () => clearTimeout(t)
  }, [toast, onRemove])

  return (
    <div className={`toast-notification toast-notification--${toast.type || 'info'}`}>
      <span className="toast-notification-msg">{toast.message}</span>
      <button className="toast-notification-close" onClick={() => onRemove(toast.id)}>×</button>
    </div>
  )
}

let toastId = 0

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'error', duration = 3500) => {
    const id = ++toastId
    setToasts(prev => [...prev, { id, message, type, duration }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  return (
    <ToastContext.Provider value={addToast}>
      {children}
      {toasts.length > 0 && (
        <div className="toast-container">
          {toasts.map(t => (
            <ToastItem key={t.id} toast={t} onRemove={removeToast} />
          ))}
        </div>
      )}
    </ToastContext.Provider>
  )
}
