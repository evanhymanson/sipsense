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
  3. Builds user/item index mappings and saves them alongside the model
  4. Trains the NCF model and saves to  backend/app/ml/model.pt
  5. Saves metadata (mappings, metrics) to  backend/app/ml/model_meta.json
"""

import argparse
import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader, TensorDataset

# ── Setup paths so we can import app modules ─────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent  # backend/
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app import models
from app.ml.collaborative_filter import NCFModel

MODEL_DIR = Path(__file__).resolve().parent
MODEL_PATH = MODEL_DIR / "model.pt"
META_PATH = MODEL_DIR / "model_meta.json"

# ── Synthetic rating generation ──────────────────────────────────────────

# Flavor preferences for synthetic user archetypes
ARCHETYPES = [
    {"name": "bourbon_lover",   "cats": ["bourbon"],         "flavors": ["vanilla", "caramel", "oak", "sweet"],     "bias": 0.3},
    {"name": "peat_head",       "cats": ["scotch"],          "flavors": ["smoky", "peaty"],                         "bias": 0.2},
    {"name": "smooth_sipper",   "cats": ["irish", "japanese"], "flavors": ["smooth", "fruity", "floral", "light"],  "bias": 0.1},
    {"name": "rye_fan",         "cats": ["rye"],             "flavors": ["spicy", "herbal", "pepper"],              "bias": 0.2},
    {"name": "sherry_cask",     "cats": ["scotch"],          "flavors": ["fruity", "chocolate", "nutty", "oak"],    "bias": 0.1},
    {"name": "budget_explorer", "cats": [],                  "flavors": [],                                         "bias": -0.3},
    {"name": "adventurer",      "cats": [],                  "flavors": [],                                         "bias": 0.0},
    {"name": "sweet_tooth",     "cats": ["bourbon", "irish"],"flavors": ["sweet", "honey", "vanilla", "caramel"],   "bias": 0.2},
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

    # Budget archetype penalizes expensive bottles
    if archetype["name"] == "budget_explorer" and whiskey.price_usd and whiskey.price_usd > 60:
        base -= 0.5

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
        print("No whiskeys in DB — cannot generate synthetic ratings.")
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


# ── Data loading ─────────────────────────────────────────────────────────

def load_ratings(db, synthetic_only: bool = False) -> list[tuple[str, int, float]]:
    """Load ratings from DB, optionally augmented with synthetic data."""
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

    print(f"Total training ratings: {len(all_ratings)}")
    return all_ratings


def build_index_maps(
    ratings: list[tuple[str, int, float]],
) -> tuple[dict[str, int], dict[int, int], dict[int, int]]:
    """Build bidirectional mappings: username ↔ user_idx, whiskey_id ↔ item_idx."""
    users = sorted(set(r[0] for r in ratings))
    items = sorted(set(r[1] for r in ratings))

    user2idx = {u: i for i, u in enumerate(users)}
    item2idx = {item_id: i for i, item_id in enumerate(items)}
    idx2item = {i: item_id for item_id, i in item2idx.items()}

    return user2idx, item2idx, idx2item


# ── Training loop ────────────────────────────────────────────────────────

def train(
    epochs: int = 20,
    lr: float = 0.001,
    batch_size: int = 256,
    embedding_dim: int = 32,
    synthetic_only: bool = False,
):
    """Full training pipeline: load data → build model → train → save."""
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

        # Build tensors for val set (only for ratings where user+item exist in maps)
        val_users = torch.LongTensor([user2idx[r[0]] for r in val_ratings])
        val_items = torch.LongTensor([item2idx[r[1]] for r in val_ratings])
        val_scores = torch.FloatTensor([r[2] for r in val_ratings])

        # 3. Build model
        model = NCFModel(
            n_users=n_users,
            n_items=n_items,
            embedding_dim=embedding_dim,
        )

        # Initialize global bias to mean rating for faster convergence
        mean_rating = train_scores.mean().item()
        with torch.no_grad():
            model.global_bias.fill_(mean_rating)
        print(f"Global bias initialized to mean rating: {mean_rating:.2f}")

        optimizer = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=1e-5)
        criterion = torch.nn.MSELoss()

        # 4. Train with early stopping
        print(f"\nTraining NCF model ({epochs} epochs, lr={lr}, batch_size={batch_size})")
        print("-" * 50)

        best_val_loss = float("inf")
        patience = 5
        patience_counter = 0
        best_state = None

        for epoch in range(1, epochs + 1):
            model.train()
            epoch_loss = 0.0
            n_batches = 0

            for u_batch, i_batch, s_batch in loader:
                optimizer.zero_grad()
                preds = model(u_batch, i_batch)
                loss = criterion(preds, s_batch)
                loss.backward()
                optimizer.step()
                epoch_loss += loss.item()
                n_batches += 1

            avg_train_loss = epoch_loss / n_batches

            # Validation loss
            model.eval()
            with torch.no_grad():
                val_preds = model(val_users, val_items)
                val_loss = criterion(val_preds, val_scores).item()

            if epoch % 5 == 0 or epoch == 1:
                print(f"  Epoch {epoch:3d}/{epochs}  train_loss={avg_train_loss:.4f}  val_loss={val_loss:.4f}")

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
            train_preds = model(train_users, train_items)
            train_rmse = torch.sqrt(criterion(train_preds, train_scores)).item()
            val_preds = model(val_users, val_items)
            val_rmse = torch.sqrt(criterion(val_preds, val_scores)).item()
            val_mae = torch.mean(torch.abs(val_preds - val_scores)).item()

        rmse = val_rmse
        mae = val_mae
        print(f"\nFinal metrics: train_RMSE={train_rmse:.4f}, val_RMSE={val_rmse:.4f}, val_MAE={val_mae:.4f}")

        # 6. Save model
        torch.save(model.state_dict(), MODEL_PATH)
        print(f"Model saved to {MODEL_PATH}")

        # 7. Save metadata (mappings + hyperparams)
        meta = {
            "n_users": n_users,
            "n_items": n_items,
            "embedding_dim": embedding_dim,
            "user2idx": user2idx,
            "item2idx": {str(k): v for k, v in item2idx.items()},  # JSON needs string keys
            "idx2item": {str(k): v for k, v in idx2item.items()},
            "rmse": round(rmse, 4),
            "mae": round(mae, 4),
            "n_ratings": len(ratings),
            "epochs": epochs,
        }
        META_PATH.write_text(json.dumps(meta, indent=2))
        print(f"Metadata saved to {META_PATH}")

    finally:
        db.close()


# ── CLI ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train SipSense NCF recommender model")
    parser.add_argument("--epochs", type=int, default=20)
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
