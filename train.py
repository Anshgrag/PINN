import torch
import torch.optim as optim
import numpy as np
from model import FloodMLP
from physics_loss import compute_physics_loss
from city_generator import generate_synthetic_city
import time

def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training on: {device}")

    # 1. Initialize Model and Optimizer
    model = FloodMLP().to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    
    # 2. Generate Training Data (Synthetic City)
    city_map = generate_synthetic_city(size=128) # Smaller for faster initial training
    B_flat = city_map.flatten()
    
    # Create coordinate grid
    x = np.linspace(-1, 1, 128)
    y = np.linspace(-1, 1, 128)
    X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
    X_flat = X_grid.flatten()
    Y_flat = Y_grid.flatten()
    
    # Training Loop
    epochs = 2000
    batch_size = 4096 # Sample points randomly for PINN
    
    print("Starting Training...")
    start_time = time.time()
    
    for epoch in range(epochs):
        # Regenerate city map every 100 epochs for generalization
        if epoch % 100 == 0:
            city_map = generate_synthetic_city(size=128)
            B_flat = city_map.flatten()
            x = np.linspace(-1, 1, 128)
            y = np.linspace(-1, 1, 128)
            X_grid, Y_grid = np.meshgrid(x, y, indexing='ij')
            X_flat = X_grid.flatten()
            Y_flat = Y_grid.flatten()
            if epoch > 0:
                print(f"--- Epoch {epoch}: Regenerated Synthetic City Layout ---")

        # Sample random points from the grid
        indices = np.random.choice(len(X_flat), batch_size, replace=False)
        
        # Prepare batch tensors
        x_t = torch.tensor(X_flat[indices], requires_grad=True, dtype=torch.float32).to(device).unsqueeze(1)
        y_t = torch.tensor(Y_flat[indices], requires_grad=True, dtype=torch.float32).to(device).unsqueeze(1)
        B_t = torch.tensor(B_flat[indices], dtype=torch.float32).to(device).unsqueeze(1)
        q_t = torch.full_like(x_t, 0.05) # Constant rainfall for training
        
        points = torch.cat([x_t, y_t, B_t, q_t], dim=1)
        
        # Compute Physics Loss
        optimizer.zero_grad()
        total_loss, loss_cont, loss_bound = compute_physics_loss(model, points)
        
        # Backprop
        total_loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch:4d} | Loss: {total_loss.item():.6f} | Continuity: {loss_cont.item():.6f} | Boundary: {loss_bound.item():.6f}")

    end_time = time.time()
    print(f"Training Complete in {end_time - start_time:.2f} seconds.")
    
    # Save the 'AI Physics Brain'
    torch.save(model.state_dict(), "flood_mlp_weights.pth")
    print("Model weights saved to flood_mlp_weights.pth")

if __name__ == "__main__":
    train()
