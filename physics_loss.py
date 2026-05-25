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
