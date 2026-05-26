from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel
import torch
import numpy as np
from model import FloodMLP
import io

app = FastAPI(title="Vectorized PINN Flood Backend")

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model = FloodMLP().to(device)

import os

# Get the directory of the current script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_PATH = os.path.join(BASE_DIR, "flood_mlp_weights.pth")

# Load pre-trained weights
try:
    model.load_state_dict(torch.load(WEIGHTS_PATH, map_location=device))
    model.eval()
    print(f"Successfully loaded pre-trained weights from {WEIGHTS_PATH}.")
except FileNotFoundError:
    print(f"Warning: Weights not found at {WEIGHTS_PATH}. Using untrained initialization.")

class TsunamiRequest(BaseModel):
    elevation_map: list      # MxN float array
    material_map: list       # MxN int array (0: None, 1: Wood, 2: Masonry, 3: Concrete)
    wave_height: float       # Wave height in meters
    wave_duration: float     # Surge duration in seconds
    debris_density: float    # Factor 0-1 for floating debris impact

def calculate_resilience(h_grid, u_grid, v_grid, B_array, M_array, debris_density):
    """
    Analyzes the flood simulation data to produce an engineering resilience report.
    """
    rows, cols = h_grid.shape
    
    # 1. Hydrodynamic Force Calculation (F = 0.5 * rho * v^2 * A + debris_momentum)
    velocity_sq = u_grid**2 + v_grid**2
    rho = 1025 # Seawater density kg/m^3
    
    # Pressure in Pascals (N/m^2)
    # Adding debris impact: 1 + debris_density * velocity factor
    dynamic_pressure = 0.5 * rho * velocity_sq * (1 + debris_density * 5.0)
    static_pressure = rho * 9.81 * h_grid
    total_pressure = dynamic_pressure + static_pressure
    
    # 2. Structural Integrity Pass
    # Failure thresholds in Pascals (Typical values for illustration)
    thresholds = {0: 1e10, 1: 15000, 2: 45000, 3: 150000} # Wood, Masonry, Concrete
    
    failures = np.zeros_like(h_grid)
    for m_type, thresh in thresholds.items():
        if m_type == 0: continue
        mask = (M_array == m_type)
        failures[mask & (total_pressure > thresh)] = 1
        
    # 3. Aggregating Metrics
    total_buildings = np.sum(M_array > 0)
    total_failures = np.sum(failures)
    survival_rate = (1 - total_failures / total_buildings) * 100 if total_buildings > 0 else 100
    
    # Bottleneck analysis: Identify zones where velocity is 2x the average due to narrowing
    avg_velocity = np.mean(np.sqrt(velocity_sq[h_grid > 0.1])) if np.any(h_grid > 0.1) else 1.0
    bottlenecks = np.sum(np.sqrt(velocity_sq) > avg_velocity * 2.5)
    
    # Final Reporting Logic
    permeability = 100 - (bottlenecks / (rows * cols) * 1000)
    permeability = max(0, min(100, permeability))
    
    design_quality = "POOR"
    if survival_rate > 90 and permeability > 80: design_quality = "OPTIMAL"
    elif survival_rate > 70 and permeability > 60: design_quality = "GOOD"
    elif survival_rate > 50: design_quality = "ADEQUATE"
    
    return {
        "resilience_score": round(survival_rate * 0.7 + permeability * 0.3, 1),
        "survival_rate": round(survival_rate, 1),
        "permeability": round(permeability, 1),
        "design_quality": design_quality,
        "critical_failure_count": int(total_failures),
        "max_pressure_kpa": round(np.max(total_pressure) / 1000, 1)
    }

def prepare_grid(B_array, q_scalar):
    """Flattens MxN image inputs into MLP data points."""
    rows, cols = B_array.shape
    x = np.linspace(-1, 1, cols)
    y = np.linspace(-1, 1, rows)
    X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
    
    X_flat = X_grid.flatten()
    Y_flat = Y_grid.flatten()
    B_flat = B_array.flatten()
    q_flat = np.full_like(X_flat, q_scalar)
    
    # Shape: [MxN, 4]
    points = np.stack([X_flat, Y_flat, B_flat, q_flat], axis=1)
    return torch.tensor(points, dtype=torch.float32).to(device)

@app.post("/predict")
async def predict_tsunami(payload: TsunamiRequest):
    B_array = np.array(payload.elevation_map, dtype=np.float32)
    M_array = np.array(payload.material_map, dtype=np.int32)
    rows, cols = B_array.shape
    
    # 1. Flatten the city grid for PINN
    # We use wave_height as the 'surge intensity' input for the model
    points_tensor = prepare_grid(B_array, payload.wave_height)
    
    # 2. Fast Vectorized Inference
    with torch.no_grad():
        outputs = model(points_tensor)
        
    # 3. Reshape back into MxN visual matrices
    h_grid = outputs[:, 0].reshape(rows, cols).cpu().numpy()
    u_grid = outputs[:, 1].reshape(rows, cols).cpu().numpy()
    v_grid = outputs[:, 2].reshape(rows, cols).cpu().numpy()
    
    # 4. Resilience Analysis
    report = calculate_resilience(h_grid, u_grid, v_grid, B_array, M_array, payload.debris_density)
    
    # Pack (h, u, v) into a single (3, rows, cols) float32 array for the frontend
    # Note: We append the report as metadata in the response headers or a multipart response
    # For simplicity, we'll pack the report metrics into the first few pixels of a hidden channel 
    # or just return as a JSON with binary data as base64 (less efficient) or custom header.
    
    response_content = np.stack([h_grid, u_grid, v_grid], axis=0).astype(np.float32).tobytes()
    
    # We'll use custom headers for the report data
    headers = {
        "X-Resilience-Score": str(report["resilience_score"]),
        "X-Survival-Rate": str(report["survival_rate"]),
        "X-Permeability": str(report["permeability"]),
        "X-Design-Quality": report["design_quality"],
        "X-Failure-Count": str(report["critical_failure_count"]),
        "X-Max-Pressure": str(report["max_pressure_kpa"])
    }
    
    return Response(content=response_content, media_type="application/octet-stream", headers=headers)

@app.post("/analyze_full_scenario")
async def analyze_full_scenario(payload: TsunamiRequest):
    """
    Runs a multi-step time-integrated simulation to assess cumulative damage.
    """
    B_array = np.array(payload.elevation_map, dtype=np.float32)
    M_array = np.array(payload.material_map, dtype=np.int32)
    rows, cols = B_array.shape
    
    # We simulate 10 key time steps of the surge
    num_steps = 10
    max_h = np.zeros_like(B_array)
    max_p = np.zeros_like(B_array)
    
    # Dynamic surge intensity based on wave duration
    # This simulates the wave rising, peaking, and receding
    for step in range(num_steps):
        # Surge profile: Sinusoidal rise and fall
        intensity = payload.wave_height * np.sin(np.pi * (step / num_steps))
        
        points_tensor = prepare_grid(B_array, intensity)
        with torch.no_grad():
            outputs = model(points_tensor)
            
        h = outputs[:, 0].reshape(rows, cols).cpu().numpy()
        u = outputs[:, 1].reshape(rows, cols).cpu().numpy()
        v = outputs[:, 2].reshape(rows, cols).cpu().numpy()
        
        # Calculate instantaneous pressure
        v_sq = u**2 + v**2
        rho = 1025
        p = 0.5 * rho * v_sq * (1 + payload.debris_density * 5.0) + rho * 9.81 * h
        
        # Track maximums
        max_h = np.maximum(max_h, h)
        max_p = np.maximum(max_p, p)

    # Run resilience calculation on integrated maximums
    # Thresholds (Wood, Masonry, Concrete)
    thresholds = {0: 1e10, 1: 15000, 2: 45000, 3: 150000}
    failures = np.zeros_like(max_h)
    for m_type, thresh in thresholds.items():
        if m_type == 0: continue
        mask = (M_array == m_type)
        failures[mask & (max_p > thresh)] = 1
        
    total_buildings = np.sum(M_array > 0)
    total_failures = np.sum(failures)
    survival_rate = (1 - total_failures / total_buildings) * 100 if total_buildings > 0 else 100
    
    return {
        "resilience_score": round(survival_rate * 0.8, 1), # Integration penalty
        "survival_rate": round(survival_rate, 1),
        "total_failures": int(total_failures),
        "max_inundation": round(np.max(max_h), 2),
        "max_pressure_kpa": round(np.max(max_p) / 1000, 1),
        "duration_analyzed": payload.wave_duration
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
