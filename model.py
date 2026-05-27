import torch
import torch.nn as nn


class FloodMLP(nn.Module):
    """
    Vectorized MLP for point-by-point physics evaluation.
    Takes 4 inputs (x, y, Elevation B, Rainfall q) — all should be normalized
    to approximately [-1, 1] before being passed in.
    Outputs 3 values: water depth (h), x-velocity (u), y-velocity (v).

    Key design decisions:
    - Tanh activations throughout: smooth, bounded, supports clean second-order
      autograd derivatives required by the SWE physics loss.
    - Softplus (NOT ReLU) for enforcing h >= 0: ReLU has zero gradient for
      negative inputs, which causes the network to get stuck at h=0 and never
      recover. Softplus is smooth everywhere and always passes gradients.
    - Xavier (Glorot) uniform initialization: prevents vanishing/exploding
      gradients at the start of training, critical for deep PINNs.
    """

    def __init__(self, input_dim: int = 4, hidden_dim: int = 128, output_dim: int = 3):
        super(FloodMLP, self).__init__()

        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.Tanh(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.Tanh(),
            nn.Linear(hidden_dim // 2, output_dim),
        )

        # Xavier uniform initialization for all Linear layers
        # This keeps activations in the linear regime of Tanh at init,
        # ensuring healthy gradient flow from the first step.
        self._initialize_weights()

    def _initialize_weights(self):
        for layer in self.net:
            if isinstance(layer, nn.Linear):
                nn.init.xavier_uniform_(layer.weight)
                nn.init.zeros_(layer.bias)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: Tensor of shape [N, 4] — normalized (x, y, B, q) coordinates.
               MUST have requires_grad=True for physics loss autograd to work.

        Returns:
            Tensor of shape [N, 3] — (h, u, v) at each point.
        """
        # x shape: [N, 4]
        out = self.net(x)  # [N, 3]

        # --- Enforce h >= 0 using softplus ---
        # softplus(z) = log(1 + exp(z)) — smooth approximation of ReLU.
        # Unlike ReLU, its gradient is sigmoid(z) which is NEVER zero,
        # so the network can always learn to increase h from a negative init.
        # beta=5 sharpens the transition toward 0 (closer to ReLU shape)
        # without completely killing gradients in the negative region.
        h = torch.nn.functional.softplus(out[:, 0:1], beta=5)

        u = out[:, 1:2]
        v = out[:, 2:3]

        return torch.cat([h, u, v], dim=1)  # [N, 3]