import torch
import torch.nn as nn

class FloodMLP(nn.Module):
    """
    Vectorized MLP for point-by-point physics evaluation.
    Takes 4 inputs (x, y, Elevation B, Rainfall q).
    Outputs 3 values (depth h, velocity u, velocity v).
    """
    def __init__(self):
        super(FloodMLP, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(4, 64),
            nn.Tanh(),  # Tanh is crucial for smooth second-order derivatives in PINNs
            nn.Linear(64, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 3) # h, u, v
        )

    def forward(self, x):
        # x shape: [Batch_Size (e.g., 65536), 4]
        out = self.net(x)
        
        # Enforce physical reality: Water depth (h) cannot be negative
        h = torch.nn.functional.relu(out[:, 0:1])
        u = out[:, 1:2]
        v = out[:, 2:3]
        
        return torch.cat([h, u, v], dim=1)
