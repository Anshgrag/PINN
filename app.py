from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch
import numpy as np
from model import FloodMLP
from metrics import compute_resilience_metrics, run_tsunami_simulation
import io
import json
import os

app = FastAPI(title="Vectorized PINN Flood Backend")

# Enable CORS for all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Resilience-Score", "X-Inundation-Extent", "X-Building-Exposure"]
)

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
    elevation_map: list       # 256x256 float array
    rainfall_intensity: float  # Scalar
    wind_speed: float = 0.0
    wind_direction: float = 0.0 # Degrees
    viscosity: float = 0.01
    friction_base: float = 0.03 # Manning's n

def prepare_grid(B_array, payload: FloodRequest, size=256):
    """Flattens 256x256 image inputs into 65,536 MLP data points with 8 features."""
    x = np.linspace(-1, 1, size)
    y = np.linspace(-1, 1, size)
    X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
    
    X_flat = X_grid.flatten()
    Y_flat = Y_grid.flatten()
    B_flat = B_array.flatten()
    
    # Advanced Parameters
    q_flat = np.full_like(X_flat, payload.rainfall_intensity)
    
    # Wind Vectors
    rad = np.radians(payload.wind_direction)
    wx = payload.wind_speed * np.cos(rad)
    wy = payload.wind_speed * np.sin(rad)
    wx_flat = np.full_like(X_flat, wx)
    wy_flat = np.full_like(X_flat, wy)
    
    # Friction (Buildings have higher n)
    n_flat = np.full_like(X_flat, payload.friction_base)
    n_flat[B_flat > 5.0] = 0.1 # Very high friction for buildings
    
    # Viscosity
    nu_flat = np.full_like(X_flat, payload.viscosity)
    
    # Shape: [65536, 8]
    points = np.stack([X_flat, Y_flat, B_flat, q_flat, wx_flat, wy_flat, n_flat, nu_flat], axis=1)
    return torch.tensor(points, dtype=torch.float32).to(device)

def run_model_inference(B_array, payload: FloodRequest):
    """Helper for internal batch simulation."""
    points_tensor = prepare_grid(B_array, payload)
    with torch.no_grad():
        outputs = model(points_tensor)
    return outputs[:, 0].reshape(256, 256).cpu().numpy()

@app.post("/predict")
async def predict_flood(payload: FloodRequest):
    B_array = np.array(payload.elevation_map, dtype=np.float32)
    if B_array.shape != (256, 256):
        raise HTTPException(status_code=400, detail="Elevation map must be 256x256.")
    
    # 1. Flatten the city grid with advanced params
    points_tensor = prepare_grid(B_array, payload)
    
    # 2. Fast Vectorized Inference
    with torch.no_grad():
        outputs = model(points_tensor) # Shape: [65536, 3]
        
    # 3. Reshape back into 256x256 visual matrices
    h_grid = outputs[:, 0].reshape(256, 256).cpu().numpy()
    u_grid = outputs[:, 1].reshape(256, 256).cpu().numpy()
    v_grid = outputs[:, 2].reshape(256, 256).cpu().numpy()
    
    # 4. Compute Resilience Metrics
    metrics = compute_resilience_metrics(h_grid, B_array)
    
    # OPTIMIZATION: Return binary data to avoid JSON overhead
    # We pack (h, u, v) into a single (3, 256, 256) float32 array
    combined = np.stack([h_grid, u_grid, v_grid], axis=0).astype(np.float32)
    
    headers = {
        "X-Resilience-Score": str(round(metrics["resilience_score"], 2)),
        "X-Inundation-Extent": str(round(metrics["inundation_extent_pct"], 2)),
        "X-Building-Exposure": str(round(metrics["building_exposure_pct"], 2)),
        "Access-Control-Expose-Headers": "X-Resilience-Score, X-Inundation-Extent, X-Building-Exposure"
    }
    
    return Response(content=combined.tobytes(), media_type="application/octet-stream", headers=headers)

@app.post("/report")
async def generate_report(payload: FloodRequest):
    B_array = np.array(payload.elevation_map, dtype=np.float32)
    if B_array.shape != (256, 256):
        raise HTTPException(status_code=400, detail="Elevation map must be 256x256.")
    
    # run_tsunami_simulation needs to be updated in metrics.py to handle the payload
    report = run_tsunami_simulation(B_array, run_model_inference, payload)
    return report

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
