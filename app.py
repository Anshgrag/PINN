from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import torch
import numpy as np
from model import FloodMLP
import io

app = FastAPI(title="Vectorized PINN Flood Backend")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = FloodMLP().to(device)

# Load pre-trained weights
try:
    model.load_state_dict(torch.load("flood_mlp_weights.pth", map_location=device))
    model.eval()
    print("Successfully loaded pre-trained weights.")
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
    h_grid = outputs[:, 0].reshape(256, 256).cpu().numpy()
    u_grid = outputs[:, 1].reshape(256, 256).cpu().numpy()
    v_grid = outputs[:, 2].reshape(256, 256).cpu().numpy()
    
    # OPTIMIZATION: Return binary data to avoid JSON overhead
    # We pack (h, u, v) into a single (3, 256, 256) float32 array
    combined = np.stack([h_grid, u_grid, v_grid], axis=0).astype(np.float32)
    
    return Response(content=combined.tobytes(), media_type="application/octet-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
