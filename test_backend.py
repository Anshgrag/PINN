import pytest
import torch
import numpy as np
from fastapi.testclient import TestClient
from app import app
from model import FloodMLP
from physics_loss import compute_physics_loss
import time

client = TestClient(app)

def test_model_output_shape():
    model = FloodMLP()
    test_input = torch.randn(10, 4)
    output = model(test_input)
    assert output.shape == (10, 3)
    # Check depth h is non-negative
    assert torch.all(output[:, 0] >= 0)

def test_physics_loss_computation():
    model = FloodMLP()
    points = torch.randn(10, 4, requires_grad=True)
    loss, loss_c, loss_b = compute_physics_loss(model, points)
    assert isinstance(loss, torch.Tensor)
    assert loss.dim() == 0 # Scalar

def test_api_predict_optimized():
    # Mock elevation map 256x256
    elevation_map = np.random.rand(256, 256).tolist()
    payload = {
        "elevation_map": elevation_map,
        "rainfall_intensity": 5.0
    }
    
    # Warmup
    client.post("/predict", json=payload)
    
    start_time = time.time()
    response = client.post("/predict", json=payload)
    end_time = time.time()
    
    latency_ms = (end_time - start_time) * 1000
    print(f"Optimized Inference Latency: {latency_ms:.2f}ms")
    
    assert response.status_code == 200
    
    # Unpack binary data
    data_bytes = response.content
    combined = np.frombuffer(data_bytes, dtype=np.float32).reshape(3, 256, 256)
    
    h_grid = combined[0]
    u_grid = combined[1]
    v_grid = combined[2]
    
    assert h_grid.shape == (256, 256)
    assert u_grid.shape == (256, 256)
    assert v_grid.shape == (256, 256)

if __name__ == "__main__":
    test_api_predict_optimized()
