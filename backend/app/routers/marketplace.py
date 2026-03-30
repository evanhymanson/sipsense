"""Gap 13: E-Commerce marketplace scaffolding — cart and order infrastructure."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..auth import get_current_user

router = APIRouter(prefix="/marketplace", tags=["marketplace"])


@router.get("/cart")
def get_cart(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's shopping cart."""
    items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.username)
        .all()
    )
    result = []
    for item in items:
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == item.whiskey_id).first()
        if whiskey:
            result.append({
                "id": item.id,
                "whiskey": schemas.WhiskeyRead.model_validate(whiskey),
                "quantity": item.quantity,
                "added_at": item.added_at,
            })
    total = sum((r["whiskey"].price_usd or 0) * r["quantity"] for r in result)
    return {"items": result, "total_usd": round(total, 2), "item_count": len(result)}


@router.post("/cart", status_code=201)
def add_to_cart(
    body: schemas.CartItemCreate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Add a whiskey to the cart (or update quantity if already in cart)."""
    whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == body.whiskey_id).first()
    if not whiskey:
        raise HTTPException(status_code=404, detail="Whiskey not found")

    existing = (
        db.query(models.CartItem)
        .filter(
            models.CartItem.user_id == current_user.username,
            models.CartItem.whiskey_id == body.whiskey_id,
        )
        .first()
    )
    if existing:
        existing.quantity = body.quantity
        db.commit()
        return {"message": "Cart updated", "quantity": existing.quantity}

    item = models.CartItem(
        user_id=current_user.username,
        whiskey_id=body.whiskey_id,
        quantity=body.quantity,
    )
    db.add(item)
    db.commit()
    return {"message": "Added to cart", "quantity": body.quantity}


@router.delete("/cart/{item_id}", status_code=204)
def remove_from_cart(
    item_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Remove an item from the cart."""
    item = (
        db.query(models.CartItem)
        .filter(
            models.CartItem.id == item_id,
            models.CartItem.user_id == current_user.username,
        )
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")
    db.delete(item)
    db.commit()


@router.post("/checkout")
def create_order(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Convert cart to order. Marketplace is coming soon — this creates a pending order."""
    items = (
        db.query(models.CartItem)
        .filter(models.CartItem.user_id == current_user.username)
        .all()
    )
    if not items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    total = 0.0
    order = models.Order(user_id=current_user.username, status="pending")
    db.add(order)
    db.flush()  # get order.id

    for cart_item in items:
        whiskey = db.query(models.Whiskey).filter(models.Whiskey.id == cart_item.whiskey_id).first()
        price = (whiskey.price_usd or 0) if whiskey else 0
        order_item = models.OrderItem(
            order_id=order.id,
            whiskey_id=cart_item.whiskey_id,
            quantity=cart_item.quantity,
            price_usd=price,
        )
        db.add(order_item)
        total += price * cart_item.quantity
        db.delete(cart_item)

    order.total_usd = round(total, 2)
    db.commit()

    return {
        "order_id": order.id,
        "status": "pending",
        "total_usd": order.total_usd,
        "message": "Order created! Marketplace fulfillment coming soon.",
    }


@router.get("/orders")
def get_orders(
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get user's order history."""
    orders = (
        db.query(models.Order)
        .filter(models.Order.user_id == current_user.username)
        .order_by(models.Order.created_at.desc())
        .limit(50)
        .all()
    )
    result = []
    for order in orders:
        items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order.id).all()
        result.append({
            "id": order.id,
            "status": order.status,
            "total_usd": order.total_usd,
            "item_count": len(items),
            "created_at": order.created_at,
        })
    return result
