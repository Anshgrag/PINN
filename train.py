import torch
import torch.optim as optim
import numpy as np
from model import FloodMLP
from physics_loss import compute_physics_loss

def train(epochs=1000, batch_size=4096):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = FloodMLP().to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-3)
    
    print(f"Starting training on {device}...")
    
    for epoch in range(epochs):
        optimizer.zero_grad()
        
        # Generate random points for training
        # x, y in [-1, 1], B in [0, 1000], q in [0, 10]
        x = (torch.rand(batch_size, 1, device=device) * 2 - 1).requires_grad_(True)
        y = (torch.rand(batch_size, 1, device=device) * 2 - 1).requires_grad_(True)
        B = torch.rand(batch_size, 1, device=device) * 1000
        q = torch.rand(batch_size, 1, device=device) * 10
        
        points = torch.cat([x, y, B, q], dim=1)
        
        loss, loss_c, loss_b = compute_physics_loss(model, points)
        
        loss.backward()
        optimizer.step()
        
        if epoch % 100 == 0:
            print(f"Epoch {epoch}: Loss {loss.item():.6f} (Cont: {loss_c.item():.6f}, Bound: {loss_b.item():.6f})")
            
    torch.save(model.state_dict(), "flood_mlp_weights.pth")
    print("Training complete. Weights saved to flood_mlp_weights.pth")

if __name__ == "__main__":
    train()
