# Real-Time 2D Flood Prediction Backend (Vectorized PINN)

## Architectural Concept
To achieve sub-50ms inference for an interactive 2.5D science exhibition dashboard, we are using a **Vectorized Multi-Layer Perceptron (MLP)**. 

Instead of blurring the physics through 2D convolutions (U-Net), the system flattens the 256x256 city grid into 65,536 individual points. The PyTorch MLP processes these points simultaneously. This guarantees mathematically perfect spatial derivatives via `torch.autograd.grad` while maintaining lightning-fast speed. The output is then reshaped back into a 256x256 image matrix for the frontend to render.

## 1. Project Structure
- `app.py`: FastAPI server that handles flattening the image, running inference, and reshaping the output.
- `model.py`: The core PyTorch MLP architecture.
- `physics_loss.py`: The Continuous Autograd engine enforcing the Shallow Water Equations.

---

## 2. Implementation Code Draft

### A. The Neural Network (`model.py`)
```python
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
```

### B. The Physics Regularization (`physics_loss.py`)
```python
import torch

def compute_physics_loss(model, points):
    """
    Enforces Mass Conservation and Boundary constraints using PyTorch Autograd.
    points: Tensor of shape [N, 4] -> (x, y, B, q) with requires_grad=True
    """
    # Extract independent coordinate variables
    x = points[:, 0:1]
    y = points[:, 1:2]
    B = points[:, 2:3]
    q = points[:, 3:4]
    
    # Forward pass
    inputs = torch.cat([x, y, B, q], dim=1)
    outputs = model(inputs)
    
    h = outputs[:, 0:1]
    u = outputs[:, 1:2]
    v = outputs[:, 2:3]
    
    # 1. Autograd Gradients for Continuity Equation
    flux_x = u * h
    flux_y = v * h
    
    # Clean, direct spatial derivatives without convolution blurring
    d_flux_x_dx = torch.autograd.grad(
        outputs=flux_x, inputs=x, 
        grad_outputs=torch.ones_like(flux_x), 
        create_graph=True, retain_graph=True
    )[0]
    
    d_flux_y_dy = torch.autograd.grad(
        outputs=flux_y, inputs=y, 
        grad_outputs=torch.ones_like(flux_y), 
        create_graph=True, retain_graph=True
    )[0]
    
    # Mass Conservation (Steady State dh/dt = 0): d(uh)/dx + d(vh)/dy - q = 0
    continuity_residual = d_flux_x_dx + d_flux_y_dy - q
    loss_continuity = torch.mean(continuity_residual ** 2)
    
    # 2. Boundary Wall Restrictions (Building Mask)
    # Treat extreme elevations (e.g., B > 900) as solid city buildings
    building_mask = (B > 900.0).float()
    
    # Penalize any non-zero velocity where there is a building (water flows around, not through)
    velocity_mag_squared = (u ** 2) + (v ** 2)
    loss_boundary = torch.mean(velocity_mag_squared * building_mask)
    
    total_physics_loss = loss_continuity + loss_boundary
    
    return total_physics_loss, loss_continuity, loss_boundary
```

### C. Live Inference API (`app.py`)
```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import torch
import numpy as np

app = FastAPI(title="Vectorized PINN Flood Backend")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = FloodMLP().to(device)

# Load pre-trained weights
try:
    model.load_state_dict(torch.load("flood_mlp_weights.pth", map_location=device))
    model.eval()
except FileNotFoundError:
    print("Warning: Weights not found. Using untrained initialization.")

class FloodRequest(BaseModel):
    elevation_map: list      # 256x256 float array
    rainfall_intensity: float # Scalar in mm/hr

def prepare_grid(B_array, q_scalar, size=256):
    """Flattens 256x256 image inputs into 65,536 MLP data points."""
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
    
    X_flat = X_grid.flatten()
    Y_flat = Y_grid.flatten()
    B_flat = B_array.flatten()
    q_flat = np.full_like(X_flat, q_scalar)
    
    # Shape: [65536, 4]
    points = np.stack([X_flat, Y_flat, B_flat, q_flat], axis=1)
    return torch.tensor(points, dtype=torch.float32).to(device)

@app.post("/predict")
async def predict_flood(payload: FloodRequest):
    B_array = np.array(payload.elevation_map, dtype=np.float32)
    if B_array.shape != (256, 256):
        raise HTTPException(status_code=400, detail="Elevation map must be 256x256.")
    
    # 1. Flatten the city grid
    points_tensor = prepare_grid(B_array, payload.rainfall_intensity)
    
    # 2. Fast Vectorized Inference
    with torch.no_grad():
        outputs = model(points_tensor) # Shape: [65536, 3]
        
    # 3. Reshape back into 256x256 visual matrices
    h_grid = outputs[:, 0].reshape(256, 256).cpu().numpy().tolist()
    u_grid = outputs[:, 1].reshape(256, 256).cpu().numpy().tolist()
    v_grid = outputs[:, 2].reshape(256, 256).cpu().numpy().tolist()
    
    return {
        "water_depth_map": h_grid,
        "velocity_vectors": {
            "u": u_grid,
            "v": v_grid
        }
    }
```