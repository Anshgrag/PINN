import torch
import torch.optim as optim
import numpy as np
from model import FloodMLP
from physics_loss import compute_physics_loss, InputNormalizer
from city_generator import generate_synthetic_city
import time
import os

def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # 1. Initialize Model
    model = FloodMLP(input_dim=4, hidden_dim=128, output_dim=3).to(device)
    optimizer = optim.Adam(model.parameters(), lr=5e-4) # Slightly higher LR for Tanh
    
    # 2. Normalization Setup
    # We'll use a large sample of synthetic cities to fit our normalizer once
    print("Fitting Input Normalizer...")
    normalizer = InputNormalizer()
    sample_cities = []
    for _ in range(3): # Fewer samples to fit faster
        elev, mats = generate_synthetic_city()
        rows, cols = elev.shape
        x = np.linspace(-1, 1, cols)
        y = np.linspace(-1, 1, rows)
        X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
        q = np.random.uniform(0.01, 0.5, size=elev.shape)
        pts = np.stack([X_grid.flatten(), Y_grid.flatten(), elev.flatten(), q.flatten()], axis=1)
        sample_cities.append(torch.tensor(pts, dtype=torch.float32))
    
    normalizer.fit(torch.cat(sample_cities, dim=0))
    
    # Save normalizer stats for app.py
    torch.save({'mean': normalizer.mean, 'std': normalizer.std}, "normalizer_stats.pth")
    print("Normalizer stats saved to normalizer_stats.pth")

    # 3. Training Loop
    epochs = 2000
    batch_size = 16384 # Significantly larger batches for speed on large city grid
    
    print("Starting Training...")
    start_time = time.time()
    
    # Initial city map
    current_elev, current_mats = generate_synthetic_city()
    rows, cols = current_elev.shape
    
    for epoch in range(epochs):
        # Regenerate city map occasionally
        if epoch % 200 == 0 and epoch > 0:
            current_elev, current_mats = generate_synthetic_city()
            rows, cols = current_elev.shape
            print(f"--- Epoch {epoch}: Regenerated Synthetic City Layout ---")

        # Prepare Batch
        x = np.linspace(-1, 1, cols)
        y = np.linspace(-1, 1, rows)
        X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
        
        # Randomly sample points
        indices = np.random.choice(rows*cols, batch_size, replace=False)
        
        raw_x = X_grid.flatten()[indices]
        raw_y = Y_grid.flatten()[indices]
        raw_B = current_elev.flatten()[indices]
        raw_q = np.random.uniform(0.01, 0.2, size=batch_size) # Random rainfall/surge intensity
        
        raw_points = torch.tensor(np.stack([raw_x, raw_y, raw_B, raw_q], axis=1), dtype=torch.float32).to(device)
        
        # Normalize inputs
        norm_points = normalizer.transform(raw_points)
        
        # Flag for autograd
        norm_points.requires_grad_(True)
        
        # Compute Physics Loss
        optimizer.zero_grad()
        
        # The new compute_physics_loss returns 4 values!
        # Note: threshold 5.0m matches our city_generator's building heights
        total_loss, loss_cont, loss_mom, loss_bound = compute_physics_loss(
            model, norm_points, building_elevation_threshold=5.0
        )
        
        # Backprop
        total_loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch:4d} | Loss: {total_loss.item():.6f} | Cont: {loss_cont.item():.6f} | Mom: {loss_mom.item():.6f} | Bound: {loss_bound.item():.6f}")

    end_time = time.time()
    print(f"Training Complete in {end_time - start_time:.2f} seconds.")
    
    # Save weights
    torch.save(model.state_dict(), "flood_mlp_weights.pth")
    print("Model weights saved to flood_mlp_weights.pth")

if __name__ == "__main__":
    train()
