import torch
from typing import Tuple


# ---------------------------------------------------------------------------
# Gravity constant (m/s^2)
# ---------------------------------------------------------------------------
G = 9.81

# ---------------------------------------------------------------------------
# Loss weights — tune these if one term dominates and drives others to zero.
# A common failure mode: if lambda_momentum is too large it suppresses h,
# making continuity trivially satisfied with h=0. Start with equal weights
# and adjust based on the magnitude of each loss term during early training.
# ---------------------------------------------------------------------------
LAMBDA_CONTINUITY = 1.0
LAMBDA_MOMENTUM   = 1.0
LAMBDA_BOUNDARY   = 0.5


def compute_physics_loss(
    model: torch.nn.Module,
    points: torch.Tensor,
    building_elevation_threshold: float = 5.0,
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Computes the full Shallow Water Equations (SWE) physics loss:
        1. Continuity   (mass conservation)
        2. Momentum X   (x-direction force balance)
        3. Momentum Y   (y-direction force balance)
        4. Boundary     (zero velocity inside solid buildings)

    Args:
        model:   FloodMLP instance.
        points:  Tensor [N, 4] of (x, y, B, q) — normalized coordinates.
                 *** MUST be created with requires_grad=True ***
                 Do this in your training loop:
                     points = raw_points.clone().requires_grad_(True)
        building_elevation_threshold: Elevations (B) above this value (in
                 normalized units if you normalized B) are treated as solid
                 buildings. Adjust to match your normalization.

    Returns:
        total_loss, loss_continuity, loss_momentum, loss_boundary
    """

    # ------------------------------------------------------------------
    # CRITICAL: x and y must track gradients so autograd can differentiate
    # the network outputs w.r.t. spatial coordinates. This only works if
    # `points` itself has requires_grad=True before this slice.
    # ------------------------------------------------------------------
    x = points[:, 0:1]   # [N, 1]  — requires_grad inherited from points
    y = points[:, 1:2]   # [N, 1]
    B = points[:, 2:3]   # [N, 1]  — bathymetry / ground elevation
    q = points[:, 3:4]   # [N, 1]  — source term (rainfall / inflow)

    # ------------------------------------------------------------------
    # Forward pass
    # ------------------------------------------------------------------
    inputs = torch.cat([x, y, B, q], dim=1)   # [N, 4]
    outputs = model(inputs)                    # [N, 3]

    h = outputs[:, 0:1]   # water depth      [N, 1]
    u = outputs[:, 1:2]   # x-velocity       [N, 1]
    v = outputs[:, 2:3]   # y-velocity       [N, 1]

    # Free-surface elevation: η = h + B
    eta = h + B            # [N, 1]

    # ------------------------------------------------------------------
    # Helper: single autograd gradient call
    # ------------------------------------------------------------------
    def grad(output: torch.Tensor, var: torch.Tensor) -> torch.Tensor:
        return torch.autograd.grad(
            outputs=output,
            inputs=var,
            grad_outputs=torch.ones_like(output),
            create_graph=True,
            retain_graph=True,
        )[0]

    # ------------------------------------------------------------------
    # 1. CONTINUITY EQUATION  (mass conservation, steady-state dh/dt = 0)
    #    ∂(uh)/∂x + ∂(vh)/∂y = q
    # ------------------------------------------------------------------
    flux_x = u * h                          # discharge in x
    flux_y = v * h                          # discharge in y

    d_flux_x_dx = grad(flux_x, x)          # ∂(uh)/∂x
    d_flux_y_dy = grad(flux_y, y)          # ∂(vh)/∂y

    continuity_residual = d_flux_x_dx + d_flux_y_dy - q
    loss_continuity = torch.mean(continuity_residual ** 2)

    # ------------------------------------------------------------------
    # 2. MOMENTUM EQUATIONS
    #    Without these, u and v have no physics constraints and trivially
    #    collapse to zero, making continuity trivially satisfied at h=0.
    #
    #    X:  u·∂u/∂x + v·∂u/∂y + g·∂η/∂x = 0
    #    Y:  u·∂v/∂x + v·∂v/∂y + g·∂η/∂y = 0
    # ------------------------------------------------------------------
    du_dx   = grad(u,   x)     # ∂u/∂x
    du_dy   = grad(u,   y)     # ∂u/∂y
    dv_dx   = grad(v,   x)     # ∂v/∂x
    dv_dy   = grad(v,   y)     # ∂v/∂y
    d_eta_dx = grad(eta, x)    # ∂η/∂x  (free-surface slope)
    d_eta_dy = grad(eta, y)    # ∂η/∂y

    momentum_x_residual = u * du_dx + v * du_dy + G * d_eta_dx
    momentum_y_residual = u * dv_dx + v * dv_dy + G * d_eta_dy

    loss_momentum = (
        torch.mean(momentum_x_residual ** 2)
        + torch.mean(momentum_y_residual ** 2)
    )

    # ------------------------------------------------------------------
    # 3. BUILDING BOUNDARY CONDITION
    #    Enforce zero velocity at cells occupied by solid buildings.
    #    B > threshold  →  building mask = 1  →  penalize any velocity.
    #    Note: if you normalized B, adjust the threshold accordingly, e.g.
    #        threshold_normalized = (5.0 - B_mean) / B_std
    # ------------------------------------------------------------------
    building_mask = (B > building_elevation_threshold).float()   # {0, 1}

    velocity_mag_sq = u ** 2 + v ** 2
    loss_boundary = torch.mean(velocity_mag_sq * building_mask)

    # ------------------------------------------------------------------
    # 4. TOTAL LOSS  (weighted sum)
    # ------------------------------------------------------------------
    total_loss = (
        LAMBDA_CONTINUITY * loss_continuity
        + LAMBDA_MOMENTUM  * loss_momentum
        + LAMBDA_BOUNDARY  * loss_boundary
    )

    return total_loss, loss_continuity, loss_momentum, loss_boundary


# ---------------------------------------------------------------------------
# Input normalization helper
# Normalize your raw city-model coordinates ONCE before training and keep
# the statistics to denormalize outputs for visualization.
# ---------------------------------------------------------------------------

class InputNormalizer:
    """
    Computes per-channel mean and std from a dataset of points and applies
    z-score normalization: x_norm = (x - mean) / std.

    Usage:
        normalizer = InputNormalizer()
        normalizer.fit(all_points)          # call once on full dataset
        points_norm = normalizer.transform(batch_points)  # call each step

    The normalizer stores .mean and .std as plain tensors so they can be
    moved to the right device with .to(device).
    """

    def __init__(self):
        self.mean: torch.Tensor | None = None
        self.std:  torch.Tensor | None = None

    def fit(self, points: torch.Tensor, eps: float = 1e-8) -> "InputNormalizer":
        """
        Args:
            points: [N, 4] raw (x, y, B, q) tensor.
            eps:    small constant to avoid division by zero for constant channels.
        """
        self.mean = points.mean(dim=0, keepdim=True)          # [1, 4]
        self.std  = points.std(dim=0, keepdim=True) + eps      # [1, 4]
        return self

    def transform(self, points: torch.Tensor) -> torch.Tensor:
        assert self.mean is not None, "Call .fit() before .transform()"
        return (points - self.mean.to(points.device)) / self.std.to(points.device)

    def inverse_transform(self, points_norm: torch.Tensor) -> torch.Tensor:
        assert self.mean is not None, "Call .fit() before .inverse_transform()"
        return points_norm * self.std.to(points_norm.device) + self.mean.to(points_norm.device)