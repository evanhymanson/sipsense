"""
SipSense Model Training Script

Usage:
    cd backend
    python -m app.ml.train                         # train on real ratings (+ synthetic if < 500)
    python -m app.ml.train --synthetic-only         # train on synthetic data only
    python -m app.ml.train --epochs 30 --lr 0.002   # custom hyperparams

The script:
  1. Loads all UserRating rows from the database
  2. If fewer than 500 ratings exist, generates synthetic ratings to bootstrap
  3. Adds negative samples (unrated items scored low) to teach dislikes
  4. Builds user/item index mappings and item feature tensors
  5. Trains the NCF model with side features and saves to model.pt
  6. Exports ONNX model for lightweight inference (no PyTorch needed at runtime)
  7. Saves metadata (mappings, metrics) to model_meta.json
"""

import argparse
import json
import random
import shutil
import sys
import tempfile
from pathlib import Path

import torch
from torch.utils.data import DataLoader, TensorDataset

# -- Setup paths so we can import app modules
ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app import models
from app.ml.collaborative_filter import NCFModel

_SHARED_MODEL_DIR = Path(__file__).resolve().parent / "models"
_LOCAL_MODEL_DIR = Path(__file__).resolve().parent

MODEL_DIR = _SHARED_MODEL_DIR if _SHARED_MODEL_DIR.exists() else _LOCAL_MODEL_DIR
MODEL_PATH = MODEL_DIR / "model.pt"
META_PATH = MODEL_DIR / "model_meta.json"
ONNX_PATH = MODEL_DIR / "model.onnx"

# -- Item feature engineering

ITEM_FEATURE_CATEGORIES = [
    "bourbon", "scotch", "irish", "japanese",
    "rye", "canadian", "single malt", "blended",
]
N_ITEM_FEATURES = 13  # 5 numeric + 8 category one-hot


def build_item_features(
    db, item2idx: dict[int, int],
) -> torch.Tensor:
    """Build a (n_items, 13) feature tensor for all items in the index.

    Features: price(1) + abv(1) + age(1) + flavor_x(1) + flavor_y(1) + category_onehot(8) = 13
    """
    n_items = len(item2idx)
    features = torch.zeros(n_items, N_ITEM_FEATURES)

    whiskey_ids = [wid for wid in item2idx if isinstance(wid, int)]
    whiskeys = {}
    if whiskey_ids:
        whiskeys = {
            w.id: w
            for w in db.query(models.Whiskey)
            .filter(models.Whiskey.id.in_(whiskey_ids))
            .all()
        }

    for wid, idx in item2idx.items():
        w = whiskeys.get(wid) if isinstance(wid, int) else None
        if w is None:
            # Defaults for synthetic-only items
            features[idx, 0] = 50.0 / 300.0  # price
            features[idx, 1] = 40.0 / 70.0   # abv
            features[idx, 2] = 10.0 / 30.0   # age
            features[idx, 3] = 0.5            # flavor_x
            features[idx, 4] = 0.5            # flavor_y
            continue

        features[idx, 0] = min((w.price_usd or 50.0) / 300.0, 1.0)
        features[idx, 1] = min((w.abv or 40.0) / 70.0, 1.0)
        features[idx, 2] = min((w.age or 10) / 30.0, 1.0)
        features[idx, 3] = (w.flavor_x if w.flavor_x is not None else 50) / 100.0
        features[idx, 4] = (w.flavor_y if w.flavor_y is not None else 50) / 100.0

        cat = (w.category or "").lower()
        for ci, c in enumerate(ITEM_FEATURE_CATEGORIES):
            if cat == c:
                features[idx, 5 + ci] = 1.0

    return features


# -- Synthetic rating generation

# Flavor preferences for synthetic user archetypes
ARCHETYPES = [
    {"name": "bourbon_lover",   "cats": ["bourbon"],           "flavors": ["vanilla", "caramel", "oak", "sweet"],    "bias": 0.3, "price_range": (25, 80),  "abv_pref": 45.0, "age_pref": 8},
    {"name": "peat_head",       "cats": ["scotch"],            "flavors": ["smoky", "peaty"],                        "bias": 0.2, "price_range": (40, 120), "abv_pref": 46.0, "age_pref": 12},
    {"name": "smooth_sipper",   "cats": ["irish", "japanese"], "flavors": ["smooth", "fruity", "floral", "light"],   "bias": 0.1, "price_range": (20, 60),  "abv_pref": 40.0},
    {"name": "rye_fan",         "cats": ["rye"],               "flavors": ["spicy", "herbal", "pepper"],             "bias": 0.2, "price_range": (25, 70),  "abv_pref": 50.0},
    {"name": "sherry_cask",     "cats": ["scotch"],            "flavors": ["fruity", "chocolate", "nutty", "oak"],   "bias": 0.1, "price_range": (50, 150), "abv_pref": 43.0, "age_pref": 15},
    {"name": "budget_explorer", "cats": [],                    "flavors": [],                                        "bias": -0.3, "price_range": (15, 40)},
    {"name": "adventurer",      "cats": [],                    "flavors": [],                                        "bias": 0.0},
    {"name": "sweet_tooth",     "cats": ["bourbon", "irish"],  "flavors": ["sweet", "honey", "vanilla", "caramel"],  "bias": 0.2, "price_range": (20, 70),  "abv_pref": 43.0},
]


def _score_whiskey(whiskey: models.Whiskey, archetype: dict) -> float:
    """Generate a plausible synthetic rating for a (user_archetype, whiskey) pair."""
    base = 3.0

    # Category match bonus
    cat = (whiskey.category or "").lower()
    if archetype["cats"] and cat in archetype["cats"]:
        base += 0.8
    elif archetype["cats"] and cat not in archetype["cats"]:
        base -= 0.3

    # Flavor overlap bonus
    profile_tags = {t.strip().lower() for t in (whiskey.flavor_profile or "").split(",")}
    matches = sum(1 for f in archetype["flavors"] if f in profile_tags)
    base += matches * 0.25

    # Price range preference
    if "price_range" in archetype:
        lo, hi = archetype["price_range"]
        price = whiskey.price_usd or 50.0
        if lo <= price <= hi:
            base += 0.3
        elif price > hi * 1.5:
            base -= 0.3

    # ABV preference (closer to target = higher score)
    if "abv_pref" in archetype:
        abv = whiskey.abv or 40.0
        diff = abs(abv - archetype["abv_pref"])
        if diff < 5:
            base += 0.2
        elif diff > 15:
            base -= 0.2

    # Age preference
    if "age_pref" in archetype and whiskey.age:
        if abs(whiskey.age - archetype["age_pref"]) < 5:
            base += 0.15

    # Archetype bias
    base += archetype["bias"]

    # Add noise for realism
    base += random.gauss(0, 0.4)

    return round(max(1.0, min(5.0, base)), 1)


def generate_synthetic_ratings(
    db, n_users: int = 80, ratings_per_user: int = 15
) -> list[tuple[str, int, float]]:
    """Create synthetic (username, whiskey_id, score) triples.

    Each synthetic user is assigned an archetype that determines their
    flavor preferences, then rates a random sample of whiskeys according
    to that profile.
    """
    whiskeys = db.query(models.Whiskey).all()
    if not whiskeys:
        print("No whiskeys in DB -- cannot generate synthetic ratings.")
        return []

    ratings = []
    for i in range(n_users):
        username = f"synth_user_{i:04d}"
        archetype = ARCHETYPES[i % len(ARCHETYPES)]
        sample_size = min(ratings_per_user, len(whiskeys))
        sample = random.sample(whiskeys, sample_size)
        for w in sample:
            score = _score_whiskey(w, archetype)
            ratings.append((username, w.id, score))

    print(f"Generated {len(ratings)} synthetic ratings "
          f"({n_users} users x ~{ratings_per_user} ratings each)")
    return ratings


# -- Negative sampling

def augment_with_negatives(
    ratings: list[tuple[str, int, float]],
    all_item_ids: set[int],
    neg_ratio: float = 0.5,
    neg_score: float = 2.0,
) -> list[tuple[str, int, float]]:
    """Add implicit negative samples: randomly sampled unrated items scored low.

    For each user, sample neg_ratio * num_rated unrated items.  This teaches
    the model what users do NOT like, improving recommendation quality.
    """
    user_rated: dict[str, set[int]] = {}
    for user, item, _ in ratings:
        user_rated.setdefault(user, set()).add(item)

    negatives = []
    all_items_list = list(all_item_ids)
    for user, rated_set in user_rated.items():
        n_neg = max(1, int(len(rated_set) * neg_ratio))
        unrated = [i for i in all_items_list if i not in rated_set]
        if not unrated:
            continue
        sampled = random.sample(unrated, min(n_neg, len(unrated)))
        for item in sampled:
            negatives.append((user, item, neg_score))

    print(f"Added {len(negatives)} negative samples ({neg_ratio:.0%} ratio, score={neg_score})")
    return ratings + negatives


# -- Data loading

def load_ratings(db, synthetic_only: bool = False) -> list[tuple[str, int, float]]:
    """Load ratings from DB, optionally augmented with synthetic and negative data."""
    real_ratings = []
    if not synthetic_only:
        rows = db.query(models.UserRating).all()
        real_ratings = [(r.user_id, r.whiskey_id, r.score) for r in rows]
        print(f"Loaded {len(real_ratings)} real ratings from database")

    # Generate synthetic to reach a minimum of ~500 ratings
    if len(real_ratings) < 500:
        needed_users = max(80, (500 - len(real_ratings)) // 15)
        synthetic = generate_synthetic_ratings(db, n_users=needed_users)
        all_ratings = real_ratings + synthetic
    else:
        all_ratings = real_ratings

    # Add negative samples (unrated items scored low) to teach dislikes
    all_item_ids = {r[1] for r in all_ratings}
    all_ratings = augment_with_negatives(all_ratings, all_item_ids)

    print(f"Total training ratings: {len(all_ratings)}")
    return all_ratings


def build_index_maps(
    ratings: list[tuple[str, int, float]],
) -> tuple[dict[str, int], dict[int, int], dict[int, int]]:
    """Build bidirectional mappings: username <-> user_idx, whiskey_id <-> item_idx."""
    users = sorted(set(r[0] for r in ratings))
    items = sorted(set(r[1] for r in ratings))

    user2idx = {u: i for i, u in enumerate(users)}
    item2idx = {item_id: i for i, item_id in enumerate(items)}
    idx2item = {i: item_id for item_id, i in item2idx.items()}

    return user2idx, item2idx, idx2item


# -- Training loop

def train(
    epochs: int = 30,
    lr: float = 0.001,
    batch_size: int = 256,
    embedding_dim: int = 32,
    synthetic_only: bool = False,
):
    """Full training pipeline: load data -> build model -> train -> save."""
    db = SessionLocal()
    try:
        # 1. Load data
        ratings = load_ratings(db, synthetic_only=synthetic_only)
        if len(ratings) < 10:
            print("Not enough ratings to train. Add whiskeys and ratings first.")
            return

        user2idx, item2idx, idx2item = build_index_maps(ratings)
        n_users = len(user2idx)
        n_items = len(item2idx)
        print(f"Index space: {n_users} users, {n_items} items")

        # Build item feature tensor
        item_features_all = build_item_features(db, item2idx)
        print(f"Item features: {item_features_all.shape}")

        # 2. Train/val split (80/20) for honest evaluation
        random.shuffle(ratings)
        split = int(len(ratings) * 0.8)
        train_ratings = ratings[:split]
        val_ratings = ratings[split:]
        print(f"Split: {len(train_ratings)} train, {len(val_ratings)} val")

        # Build tensors for train set
        train_users = torch.LongTensor([user2idx[r[0]] for r in train_ratings])
        train_items = torch.LongTensor([item2idx[r[1]] for r in train_ratings])
        train_scores = torch.FloatTensor([r[2] for r in train_ratings])

        dataset = TensorDataset(train_users, train_items, train_scores)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        # Build tensors for val set
        val_users = torch.LongTensor([user2idx[r[0]] for r in val_ratings])
        val_items = torch.LongTensor([item2idx[r[1]] for r in val_ratings])
        val_scores = torch.FloatTensor([r[2] for r in val_ratings])

        # 3. Build model with side features
        model = NCFModel(
            n_users=n_users,
            n_items=n_items,
            embedding_dim=embedding_dim,
            n_item_features=N_ITEM_FEATURES,
        )

        # Initialize global bias to mean rating for faster convergence
        mean_rating = train_scores.mean().item()
        with torch.no_grad():
            model.global_bias.fill_(mean_rating)
        print(f"Global bias initialized to mean rating: {mean_rating:.2f}")

        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
        criterion = torch.nn.MSELoss()
        lr_scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode="min", factor=0.5, patience=3, min_lr=1e-6,
        )

        # 4. Train with early stopping
        print(f"\nTraining NCF model ({epochs} epochs, lr={lr}, batch_size={batch_size})")
        print("-" * 50)

        best_val_loss = float("inf")
        patience = 7
        patience_counter = 0
        best_state = None

        for epoch in range(1, epochs + 1):
            model.train()
            epoch_loss = 0.0
            n_batches = 0

            for u_batch, i_batch, s_batch in loader:
                optimizer.zero_grad()
                feat_batch = item_features_all[i_batch]
                preds = model(u_batch, i_batch, item_features=feat_batch)
                loss = criterion(preds, s_batch)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            avg_train_loss = epoch_loss / n_batches

            # Validation loss
            model.eval()
            with torch.no_grad():
                val_feat = item_features_all[val_items]
                val_preds = model(val_users, val_items, item_features=val_feat)
                val_loss = criterion(val_preds, val_scores).item()

            lr_scheduler.step(val_loss)

            if epoch % 5 == 0 or epoch == 1:
                current_lr = optimizer.param_groups[0]["lr"]
                print(f"  Epoch {epoch:3d}/{epochs}  train_loss={avg_train_loss:.4f}  val_loss={val_loss:.4f}  lr={current_lr:.1e}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                best_state = {k: v.clone() for k, v in model.state_dict().items()}
            else:
                patience_counter += 1
                if patience_counter >= patience:
                    print(f"  Early stopping at epoch {epoch} (no val improvement for {patience} epochs)")
                    break

        # Restore best model
        if best_state:
            model.load_state_dict(best_state)

        # 5. Evaluate on both sets
        model.eval()
        with torch.no_grad():
            train_feat = item_features_all[train_items]
            train_preds = model(train_users, train_items, item_features=train_feat)
            train_rmse = torch.sqrt(criterion(train_preds, train_scores)).item()
            val_feat = item_features_all[val_items]
            val_preds = model(val_users, val_items, item_features=val_feat)
            val_rmse = torch.sqrt(criterion(val_preds, val_scores)).item()
            val_mae = torch.mean(torch.abs(val_preds - val_scores)).item()

        rmse = val_rmse
        mae = val_mae
        print(f"\nFinal metrics: train_RMSE={train_rmse:.4f}, val_RMSE={val_rmse:.4f}, val_MAE={val_mae:.4f}")

        # 6. Save model (combined checkpoint with item features)
        checkpoint = {
            "model_state": model.state_dict(),
            "item_features": item_features_all,
        }
        # Atomic write to avoid partial reads during auto-retrain
        with tempfile.NamedTemporaryFile(dir=MODEL_DIR, delete=False, suffix=".pt") as tmp:
            torch.save(checkpoint, tmp.name)
            shutil.move(tmp.name, MODEL_PATH)
        print(f"Model saved to {MODEL_PATH}")

        # 7. Save metadata (mappings + hyperparams)
        meta = {
            "n_users": n_users,
            "n_items": n_items,
            "embedding_dim": embedding_dim,
            "n_item_features": N_ITEM_FEATURES,
            "user2idx": user2idx,
            "item2idx": {str(k): v for k, v in item2idx.items()},
            "idx2item": {str(k): v for k, v in idx2item.items()},
            "rmse": round(rmse, 4),
            "train_rmse": round(train_rmse, 4),
            "mae": round(mae, 4),
            "n_ratings": len(ratings),
            "epochs": epochs,
        }
        with tempfile.NamedTemporaryFile(dir=MODEL_DIR, delete=False, suffix=".json", mode="w") as tmp:
            json.dump(meta, tmp, indent=2)
            tmp_name = tmp.name
        shutil.move(tmp_name, META_PATH)
        print(f"Metadata saved to {META_PATH}")

        # 8. Export ONNX model for lightweight inference (no PyTorch needed at runtime)
        try:
            dummy_users = torch.LongTensor([0])
            dummy_items = torch.LongTensor([0])
            dummy_features = torch.zeros(1, N_ITEM_FEATURES)
            torch.onnx.export(
                model,
                (dummy_users, dummy_items, dummy_features),
                ONNX_PATH,
                input_names=["user_ids", "item_ids", "item_features"],
                output_names=["scores"],
                dynamic_axes={
                    "user_ids": {0: "batch"},
                    "item_ids": {0: "batch"},
                    "item_features": {0: "batch"},
                    "scores": {0: "batch"},
                },
                opset_version=17,
            )
            print(f"ONNX model exported to {ONNX_PATH}")
        except Exception as e:
            print(f"ONNX export failed (non-fatal): {e}")

    finally:
        db.close()


# -- CLI

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SipSense NCF recommender model")
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--embedding-dim", type=int, default=32)
    parser.add_argument("--synthetic-only", action="store_true",
                        help="Train only on synthetic data (skip real ratings)")
    args = parser.parse_args()

    train(
        epochs=args.epochs,
        lr=args.lr,
        batch_size=args.batch_size,
        embedding_dim=args.embedding_dim,
        synthetic_only=args.synthetic_only,
    )
