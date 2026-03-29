import { useState, useEffect } from 'react'
import { Helmet } from 'react-helmet-async'
import { api, isLoggedIn } from '../api/client'

export default function Marketplace() {
  const [cart, setCart] = useState([])
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!isLoggedIn()) { setLoading(false); return }
    Promise.all([
      api.getCart().catch(() => []),
      api.getOrders().catch(() => []),
    ]).then(([c, o]) => {
      setCart(c)
      setOrders(o)
    }).finally(() => setLoading(false))
  }, [])

  const removeItem = async (itemId) => {
    try {
      await api.removeFromCart(itemId)
      setCart(prev => prev.filter(i => i.id !== itemId))
    } catch { /* ignore */ }
  }

  return (
    <div className="page marketplace-page">
      <Helmet>
        <title>Marketplace | SipSense</title>
        <meta name="description" content="Browse and purchase whiskeys directly through SipSense." />
      </Helmet>
      <h1>Marketplace</h1>

      <div className="coming-soon-banner">
        <h2>Coming Soon</h2>
        <p>We're building a curated marketplace where you can purchase whiskeys directly through SipSense. Add items to your cart now and be first to know when we launch.</p>
      </div>

      {isLoggedIn() && !loading && (
        <>
          <div className="marketplace-cart">
            <h2>Your Cart ({cart.length})</h2>
            {cart.length === 0 ? (
              <p className="status">Your cart is empty. Browse whiskeys and add bottles you're interested in.</p>
            ) : (
              <div className="cart-items">
                {cart.map(item => (
                  <div key={item.id} className="cart-item">
                    <div className="cart-item-info">
                      <strong>{item.whiskey_name}</strong>
                      <span className="cart-qty">Qty: {item.quantity}</span>
                    </div>
                    <button className="btn-sm btn-danger" onClick={() => removeItem(item.id)}>Remove</button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {orders.length > 0 && (
            <div className="marketplace-orders">
              <h2>Order History</h2>
              {orders.map(order => (
                <div key={order.id} className="order-card">
                  <div className="order-header">
                    <span>Order #{order.id}</span>
                    <span className={`order-status status-${order.status}`}>{order.status}</span>
                  </div>
                  <span className="order-date">{new Date(order.created_at).toLocaleDateString()}</span>
                </div>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  )
}
