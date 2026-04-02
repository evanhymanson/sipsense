"""
SipSense Model Inference

Loads the trained model and provides recommendation functions.
Prefers ONNX Runtime for inference (~50MB vs ~500MB PyTorch), falling back
to PyTorch if the ONNX model is not available.

Usage from application code:
    from app.ml.inference import get_ncf_recommendations

    results = get_ncf_recommendations(username="evan", db=db, top_n=10)
    # returns list of (Whiskey, score) or None if model not available
"""

import json
import logging
import threading
from pathlib import Path

import numpy as np
from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)

_SHARED_MODEL_DIR = Path(__file__).resolve().parent / "models"
_LOCAL_MODEL_DIR = Path(__file__).resolve().parent

MODEL_DIR = _SHARED_MODEL_DIR if _SHARED_MODEL_DIR.exists() else _LOCAL_MODEL_DIR
MODEL_PATH = MODEL_DIR / "model.pt"
META_PATH = MODEL_DIR / "model_meta.json"
ONNX_PATH = MODEL_DIR / "model.onnx"

# Module-level cache so we don't reload the model on every request
_cached_session = None  # ONNX InferenceSession or PyTorch model
_cached_meta: dict | None = None
_cached_item_features = None  # numpy array for ONNX, torch tensor for PyTorch
_use_onnx = False
_model_lock = threading.Lock()


def _load_model():
    """Load model + metadata from disk. Returns (None, None) if not available.
    Prefers ONNX Runtime for lightweight inference, falls back to PyTorch."""
    global _cached_session, _cached_meta, _cached_item_features, _use_onnx

    if _cached_session is not None:
        return _cached_session, _cached_meta

    with _model_lock:
        # Double-check after acquiring lock
        if _cached_session is not None:
            return _cached_session, _cached_meta

        if not META_PATH.exists():
            return None, None

        try:
            meta = json.loads(META_PATH.read_text())

            # Try ONNX Runtime first (much lighter than PyTorch)
            if ONNX_PATH.exists():
                try:
                    import onnxruntime as ort
                    session = ort.InferenceSession(
                        str(ONNX_PATH),
                        providers=["CPUExecutionProvider"],
                    )

                    # Load item features from the PyTorch checkpoint as numpy
                    if MODEL_PATH.exists():
                        import torch
                        checkpoint = torch.load(MODEL_PATH, weights_only=False)
                        if isinstance(checkpoint, dict) and "item_features" in checkpoint:
                            _cached_item_features = checkpoint["item_features"].numpy()
                        del checkpoint  # free the PyTorch objects
                    else:
                        _cached_item_features = None

                    _cached_session = session
                    _cached_meta = meta
                    _use_onnx = True
                    logger.info(
                        "ONNX model loaded: %d users, %d items, %d features, RMSE=%.4f",
                        meta["n_users"], meta["n_items"],
                        meta.get("n_item_features", 0), meta.get("rmse", 0),
                    )
                    return session, meta
                except ImportError:
                    logger.info("onnxruntime not installed, falling back to PyTorch")
                except Exception as e:
                    logger.warning("ONNX load failed, falling back to PyTorch: %s", e)

            # Fall back to PyTorch
            if not MODEL_PATH.exists():
                return None, None

            import torch
            from .collaborative_filter import NCFModel

            checkpoint = torch.load(MODEL_PATH, weights_only=False)
            if isinstance(checkpoint, dict) and "model_state" in checkpoint:
                state_dict = checkpoint["model_state"]
                _cached_item_features = checkpoint.get("item_features")
            else:
                state_dict = checkpoint
                _cached_item_features = None

            model = NCFModel(
                n_users=meta["n_users"],
                n_items=meta["n_items"],
                embedding_dim=meta.get("embedding_dim", 32),
                n_item_features=meta.get("n_item_features", 0),
            )
            model.load_state_dict(state_dict)
            model.eval()

            _cached_session = model
            _cached_meta = meta
            _use_onnx = False
            logger.info(
                "PyTorch NCF model loaded: %d users, %d items, %d features, RMSE=%.4f",
                meta["n_users"], meta["n_items"],
                meta.get("n_item_features", 0), meta.get("rmse", 0),
            )
            return model, meta

        except Exception as e:
            logger.warning("Failed to load NCF model: %s", e)
            return None, None


def reload_model():
    """Force-reload the model from disk (e.g. after retraining)."""
    global _cached_session, _cached_meta, _cached_item_features, _use_onnx
    with _model_lock:
        _cached_session = None
        _cached_meta = None
        _cached_item_features = None
        _use_onnx = False
    return _load_model()


def model_available() -> bool:
    """Check if a trained model exists on disk."""
    return META_PATH.exists() and (ONNX_PATH.exists() or MODEL_PATH.exists())


def _predict_all_onnx(session, user_idx: int, n_items: int, item_features) -> list[tuple[int, float]]:
    """Run ONNX inference for all items for a given user."""
    user_ids = np.full(n_items, user_idx, dtype=np.int64)
    item_ids = np.arange(n_items, dtype=np.int64)

    feeds = {"user_ids": user_ids, "item_ids": item_ids}
    if item_features is not None:
        feeds["item_features"] = item_features.astype(np.float32)

    scores = session.run(None, feeds)[0]
    scores = np.clip(scores, 1.0, 5.0)

    return [(int(i), float(scores[i])) for i in range(n_items)]


def get_ncf_recommendations(
    username: str,
    db: Session,
    top_n: int = 10,
) -> list[tuple[models.Whiskey, float]] | None:
    """Get NCF recommendations for a user.

    Returns:
        List of (Whiskey, predicted_score) tuples, or None if the model
        isn't available or the user isn't in the model's index.
    """
    session_or_model, meta = _load_model()
    if session_or_model is None or meta is None:
        return None

    user2idx = meta["user2idx"]
    item2idx = meta["item2idx"]
    idx2item = meta["idx2item"]

    # Check if this user exists in the model's training data
    if username not in user2idx:
        return None

    user_idx = user2idx[username]

    # Get whiskey IDs this user already rated (to exclude)
    rated = (
        db.query(models.UserRating.whiskey_id)
        .filter(models.UserRating.user_id == username)
        .all()
    )
    rated_whiskey_ids = {r[0] for r in rated}

    # Convert rated whiskey IDs -> item indices to exclude
    exclude_indices = set()
    for wid in rated_whiskey_ids:
        str_wid = str(wid)
        if str_wid in item2idx:
            exclude_indices.add(item2idx[str_wid])

    # Get predictions
    if _use_onnx:
        all_results = _predict_all_onnx(
            session_or_model, user_idx, meta["n_items"], _cached_item_features,
        )
        # Filter excluded and sort
        all_results = [(idx, s) for idx, s in all_results if idx not in exclude_indices]
        all_results.sort(key=lambda x: x[1], reverse=True)
        top_items = all_results[:top_n]
    else:
        # PyTorch path
        import torch
        all_item_indices = torch.arange(meta["n_items"], dtype=torch.long)
        top_items = session_or_model.predict_top_n(
            user_idx=user_idx,
            all_item_indices=all_item_indices,
            all_item_features=_cached_item_features,
            exclude=exclude_indices,
            top_n=top_n,
        )

    # Batch load all candidate whiskeys in a single query (avoids N+1)
    whiskey_ids_to_load = []
    for item_idx, score in top_items:
        str_idx = str(item_idx)
        if str_idx in idx2item:
            whiskey_ids_to_load.append(int(idx2item[str_idx]))

    whiskeys_map = {
        w.id: w
        for w in db.query(models.Whiskey)
        .filter(models.Whiskey.id.in_(whiskey_ids_to_load))
        .all()
    } if whiskey_ids_to_load else {}

    results = []
    for item_idx, score in top_items:
        str_idx = str(item_idx)
        if str_idx not in idx2item:
            continue
        whiskey_id = int(idx2item[str_idx])
        whiskey = whiskeys_map.get(whiskey_id)
        if whiskey:
            # Clamp score to expected [1, 5] range then normalize to [0, 1]
            clamped = max(1.0, min(5.0, score))
            normalized = (clamped - 1.0) / 4.0
            results.append((whiskey, round(normalized, 4)))

    return results
