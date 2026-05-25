import torch
import torch.nn as nn

class FloodMLP(nn.Module):
    """
    Upgraded Vectorized MLP for advanced physics simulation.
    Takes 8 inputs:
    1-2: x, y (Coordinates)
    3: B (Elevation)
    4: q (Rainfall/Surge)
    5-6: W_x, W_y (Wind Velocity Vectors)
    7: n (Manning's Friction Coefficient)
    8: nu (Viscosity)
    
    Outputs 3 values (depth h, velocity u, velocity v).
    """
    def __init__(self):
        super(FloodMLP, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(8, 64),
            nn.Tanh(),
            nn.Linear(64, 128),
            nn.Tanh(),
            nn.Linear(128, 128),
            nn.Tanh(),
            nn.Linear(128, 64),
            nn.Tanh(),
            nn.Linear(64, 3) # h, u, v
        )

    def forward(self, x):
        # x shape: [Batch_Size, 8]
        out = self.net(x)
        
        # Physical constraints
        h = torch.nn.functional.relu(out[:, 0:1]) # Depth must be non-negative
        u = out[:, 1:2]
        v = out[:, 2:3]
        
        return torch.cat([h, u, v], dim=1)
