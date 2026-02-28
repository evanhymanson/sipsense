"""
Neural Collaborative Filtering (NCF) for SipSense

A PyTorch embedding model that learns user–whiskey interactions from ratings.
Based on the NCF paper (He et al., 2017) but simplified to a clean GMF + MLP
hybrid that's easy to understand and extend.

Architecture:
    User ID  →  user_embedding (dim=32)  ─┐
                                           ├─ concat → MLP(64→32→16) → 1
    Whiskey ID → item_embedding (dim=32)  ─┘

The MLP path learns non-linear interaction patterns beyond simple dot-product
similarity.  Bias terms let the model capture "this user rates high" and
"this whiskey is generally liked" independently.

Training uses MSE loss on observed ratings, with optional negative sampling
to learn from unobserved pairs.
"""

import torch
import torch.nn as nn


class NCFModel(nn.Module):
    """Neural Collaborative Filtering model.

    Args:
        n_users:       Number of unique users in the dataset.
        n_items:       Number of unique whiskeys.
        embedding_dim: Dimensionality of user/item embeddings (default 32).
        mlp_layers:    Sizes of MLP hidden layers after concatenation.
    """

    def __init__(
        self,
        n_users: int,
        n_items: int,
        embedding_dim: int = 32,
        mlp_layers: tuple[int, ...] = (64, 32, 16),
    ):
        super().__init__()

        # Embedding tables
        self.user_embedding = nn.Embedding(n_users, embedding_dim)
        self.item_embedding = nn.Embedding(n_items, embedding_dim)

        # Per-entity bias (captures "user X rates high" / "whiskey Y is popular")
        self.user_bias = nn.Embedding(n_users, 1)
        self.item_bias = nn.Embedding(n_items, 1)

        # Global bias (mean rating)
        self.global_bias = nn.Parameter(torch.zeros(1))

        # MLP tower: input is concat of user + item embeddings
        layers = []
        in_size = embedding_dim * 2
        for out_size in mlp_layers:
            layers.append(nn.Linear(in_size, out_size))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(0.2))
            in_size = out_size
        layers.append(nn.Linear(in_size, 1))
        self.mlp = nn.Sequential(*layers)

        self._init_weights()

    def _init_weights(self):
        """Xavier initialization for stable training."""
        for emb in (self.user_embedding, self.item_embedding):
            nn.init.xavier_uniform_(emb.weight)
        for emb in (self.user_bias, self.item_bias):
            nn.init.zeros_(emb.weight)
        for layer in self.mlp:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)

    def forward(
        self, user_ids: torch.Tensor, item_ids: torch.Tensor
    ) -> torch.Tensor:
        """Predict ratings for (user, item) pairs.

        Args:
            user_ids: LongTensor of shape (batch_size,)
            item_ids: LongTensor of shape (batch_size,)

        Returns:
            Predicted ratings of shape (batch_size,).
            During inference, call .clamp(1, 5) on the output.
        """
        u_emb = self.user_embedding(user_ids)       # (B, D)
        i_emb = self.item_embedding(item_ids)        # (B, D)
        u_bias = self.user_bias(user_ids).squeeze(-1)  # (B,)
        i_bias = self.item_bias(item_ids).squeeze(-1)  # (B,)

        # MLP interaction
        x = torch.cat([u_emb, i_emb], dim=-1)       # (B, 2D)
        mlp_out = self.mlp(x).squeeze(-1)            # (B,)

        # Combine: global bias + user bias + item bias + learned interaction
        return self.global_bias + u_bias + i_bias + mlp_out

    def predict_top_n(
        self,
        user_idx: int,
        all_item_indices: torch.Tensor,
        exclude: set[int] | None = None,
        top_n: int = 10,
    ) -> list[tuple[int, float]]:
        """Return top-N item indices + predicted scores for a single user.

        Args:
            user_idx:         Internal user index.
            all_item_indices: Tensor of all valid item indices.
            exclude:          Set of item indices to skip (already rated).
            top_n:            Number of results.

        Returns:
            List of (item_index, predicted_score) sorted by score descending.
        """
        self.eval()
        with torch.no_grad():
            user_t = torch.full_like(all_item_indices, user_idx)
            scores = self.forward(user_t, all_item_indices).clamp(1.0, 5.0)

        results = []
        for idx, score in zip(all_item_indices.tolist(), scores.tolist()):
            if exclude and idx in exclude:
                continue
            results.append((idx, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_n]
