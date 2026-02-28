"""
SipSense Model Inference

Loads the trained NCF model and provides recommendation functions
that the API router can call.

Usage from application code:
    from app.ml.inference import get_ncf_recommendations

    results = get_ncf_recommendations(username="evan", db=db, top_n=10)
    # returns list of (Whiskey, score) or None if model not available
"""

import json
import logging
from pathlib import Path

import torch
from sqlalchemy.orm import Session

from .. import models
from .collaborative_filter import NCFModel

logger = logging.getLogger(__name__)

MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "model.pt"
META_PATH = MODEL_DIR / "model_meta.json"

# Module-level cache so we don't reload the model on every request
_cached_model: NCFModel | None = None
_cached_meta: dict | None = None


def _load_model() -> tuple[NCFModel | None, dict | None]:
    """Load model + metadata from disk. Returns (None, None) if not available."""
    global _cached_model, _cached_meta

    if _cached_model is not None:
        return _cached_model, _cached_meta

    if not MODEL_PATH.exists() or not META_PATH.exists():
        return None, None

    try:
        meta = json.loads(META_PATH.read_text())
        model = NCFModel(
            n_users=meta["n_users"],
            n_items=meta["n_items"],
            embedding_dim=meta.get("embedding_dim", 32),
        )
        model.load_state_dict(torch.load(MODEL_PATH, weights_only=True))
        model.eval()

        _cached_model = model
        _cached_meta = meta
        logger.info(
            "NCF model loaded: %d users, %d items, RMSE=%.4f",
            meta["n_users"], meta["n_items"], meta.get("rmse", 0),
        )
        return model, meta

    except Exception as e:
        logger.warning("Failed to load NCF model: %s", e)
        return None, None


def reload_model():
    """Force-reload the model from disk (e.g. after retraining)."""
    global _cached_model, _cached_meta
    _cached_model = None
    _cached_meta = None
    return _load_model()


def model_available() -> bool:
    """Check if a trained model exists on disk."""
    return MODEL_PATH.exists() and META_PATH.exists()


def get_ncf_recommendations(
    username: str,
    db: Session,
    top_n: int = 10,
) -> list[tuple[models.Whiskey, float]] | None:
    """Get PyTorch NCF recommendations for a user.

    Returns:
        List of (Whiskey, predicted_score) tuples, or None if the model
        isn't available or the user isn't in the model's index.
    """
    model, meta = _load_model()
    if model is None or meta is None:
        return None

    user2idx = meta["user2idx"]
    item2idx = meta["item2idx"]  # str(whiskey_id) → item_idx
    idx2item = meta["idx2item"]  # str(item_idx) → whiskey_id

    # Check if this user exists in the model's training data
    if username not in user2idx:
        return None  # Unknown user — caller should fall back to content-based

    user_idx = user2idx[username]

    # Get whiskey IDs this user already rated (to exclude)
    rated = (
        db.query(models.UserRating.whiskey_id)
        .filter(models.UserRating.user_id == username)
        .all()
    )
    rated_whiskey_ids = {r[0] for r in rated}

    # Convert rated whiskey IDs → item indices to exclude
    exclude_indices = set()
    for wid in rated_whiskey_ids:
        str_wid = str(wid)
        if str_wid in item2idx:
            exclude_indices.add(item2idx[str_wid])

    # Build tensor of all item indices
    all_item_indices = torch.arange(meta["n_items"], dtype=torch.long)

    # Get predictions
    top_items = model.predict_top_n(
        user_idx=user_idx,
        all_item_indices=all_item_indices,
        exclude=exclude_indices,
        top_n=top_n,
    )

    # Convert item indices back to Whiskey DB objects
    results = []
    for item_idx, score in top_items:
        str_idx = str(item_idx)
        if str_idx not in idx2item:
            continue
        whiskey_id = idx2item[str_idx]
        whiskey = db.query(models.Whiskey).get(whiskey_id)
        if whiskey:
            # Normalize score to 0-1 range for consistency with cosine similarity
            normalized = (score - 1.0) / 4.0
            results.append((whiskey, round(normalized, 4)))

    return results
