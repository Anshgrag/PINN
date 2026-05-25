import torch
import torch.optim as optim
import numpy as np
from model import FloodMLP
from physics_loss import compute_physics_loss
from city_generator import generate_synthetic_city
import time

def train():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Training Advanced Physics PINN on: {device}")

    # 1. Initialize Model and Optimizer
    model = FloodMLP().to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-4)
    
    # 2. Training Hyperparameters
    epochs = 1500 # Slightly fewer epochs for faster turnaround
    batch_size = 4096
    size = 128
    
    print("Starting Training with Wind, Friction, and Viscosity...")
    start_time = time.time()
    
    for epoch in range(epochs):
        # Sample random coordinates and parameters
        x_raw = np.random.uniform(-1, 1, batch_size)
        y_raw = np.random.uniform(-1, 1, batch_size)
        
        # Randomly generate environment for each batch to ensure wide physics coverage
        # Rainfall / Surge q
        q_raw = np.random.uniform(0.0, 5.0, batch_size)
        # Wind Vectors
        wx_raw = np.random.uniform(-2.0, 2.0, batch_size)
        wy_raw = np.random.uniform(-2.0, 2.0, batch_size)
        # Friction n (Manning's n: 0.01 to 0.1)
        n_raw = np.random.uniform(0.01, 0.1, batch_size)
        # Viscosity nu
        nu_raw = np.random.uniform(0.0, 0.5, batch_size)
        
        # Elevation (B) - Use city generator logic for building/land distribution
        # In a real training, we'd sample from a variety of DEMs
        # Here we use a simpler building/river threshold logic for the batch
        B_raw = np.zeros(batch_size)
        building_prob = np.random.rand(batch_size)
        # 30% buildings, 10% river, 60% land
        B_raw[building_prob < 0.3] = np.random.uniform(5.0, 15.0, np.sum(building_prob < 0.3))
        B_raw[(building_prob >= 0.3) & (building_prob < 0.4)] = -1.5 # River
        B_raw[building_prob >= 0.4] = np.random.uniform(0.0, 2.0, np.sum(building_prob >= 0.4))

        # Convert to Tensors
        x_t = torch.tensor(x_raw, requires_grad=True, dtype=torch.float32).to(device).unsqueeze(1)
        y_t = torch.tensor(y_raw, requires_grad=True, dtype=torch.float32).to(device).unsqueeze(1)
        B_t = torch.tensor(B_raw, dtype=torch.float32).to(device).unsqueeze(1)
        q_t = torch.tensor(q_raw, dtype=torch.float32).to(device).unsqueeze(1)
        wx_t = torch.tensor(wx_raw, dtype=torch.float32).to(device).unsqueeze(1)
        wy_t = torch.tensor(wy_raw, dtype=torch.float32).to(device).unsqueeze(1)
        n_t = torch.tensor(n_raw, dtype=torch.float32).to(device).unsqueeze(1)
        nu_t = torch.tensor(nu_raw, dtype=torch.float32).to(device).unsqueeze(1)
        
        # Final Point Vector [Batch, 8]
        points = torch.cat([x_t, y_t, B_t, q_t, wx_t, wy_t, n_t, nu_t], dim=1)
        
        # Compute Physics Loss
        optimizer.zero_grad()
        total_loss, loss_cont, loss_mom = compute_physics_loss(model, points)
        
        # Backprop
        total_loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch:4d} | Loss: {total_loss.item():.6f} | Continuity: {loss_cont.item():.6f} | Momentum: {loss_mom.item():.6f}")

    end_time = time.time()
    print(f"Training Complete in {end_time - start_time:.2f} seconds.")
    
    # Save the 'AI Physics Brain'
    torch.save(model.state_dict(), "flood_mlp_weights.pth")
    print("Model weights saved to flood_mlp_weights.pth")

if __name__ == "__main__":
    train()
