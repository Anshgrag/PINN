import torch

def compute_physics_loss(model, points):
    """
    Upgraded Physics Loss for 8-parameter PINN.
    Enforces Mass Conservation (Continuity) and Momentum Conservation (Navier-Stokes approximation).
    
    points: [N, 8] -> (x, y, B, q, W_x, W_y, n, nu)
    """
    # 1. Coordinate Variables (require grad for derivatives)
    x = points[:, 0:1].clone().detach().requires_grad_(True)
    y = points[:, 1:2].clone().detach().requires_grad_(True)
    
    # 2. Parameter Variables
    B = points[:, 2:3]
    q = points[:, 3:4]
    W_x = points[:, 4:5]
    W_y = points[:, 5:6]
    friction_n = points[:, 6:7]
    viscosity_nu = points[:, 7:8]
    
    # 3. Model Inference
    inputs = torch.cat([x, y, B, q, W_x, W_y, friction_n, viscosity_nu], dim=1)
    outputs = model(inputs)
    
    h = outputs[:, 0:1]
    u = outputs[:, 1:2]
    v = outputs[:, 2:3]
    
    # --- PHYSICAL CONSTANTS ---
    g = 9.81  # Gravity
    
    # 4. Continuity Equation (Mass Conservation)
    # d(uh)/dx + d(vh)/dy = q (assuming steady state dh/dt=0 for this snapshot)
    flux_x = u * h
    flux_y = v * h
    
    d_flux_x_dx = torch.autograd.grad(flux_x, x, torch.ones_like(flux_x), create_graph=True)[0]
    d_flux_y_dy = torch.autograd.grad(flux_y, y, torch.ones_like(flux_y), create_graph=True)[0]
    
    loss_continuity = torch.mean((d_flux_x_dx + d_flux_y_dy - q) ** 2)
    
    # 5. Momentum Equations (Shallow Water Approximation)
    # u(du/dx) + v(du/dy) + g(dh/dx + dB/dx) + S_fx - W_x = 0
    # v(dv/dy) + u(dv/dx) + g(dh/dy + dB/dy) + S_fy - W_y = 0
    
    du_dx = torch.autograd.grad(u, x, torch.ones_like(u), create_graph=True, allow_unused=True)[0]
    if du_dx is None: du_dx = torch.zeros_like(u)
    du_dy = torch.autograd.grad(u, y, torch.ones_like(u), create_graph=True, allow_unused=True)[0]
    if du_dy is None: du_dy = torch.zeros_like(u)
    dv_dx = torch.autograd.grad(v, x, torch.ones_like(v), create_graph=True, allow_unused=True)[0]
    if dv_dx is None: dv_dx = torch.zeros_like(v)
    dv_dy = torch.autograd.grad(v, y, torch.ones_like(v), create_graph=True, allow_unused=True)[0]
    if dv_dy is None: dv_dy = torch.zeros_like(v)
    
    dh_dx = torch.autograd.grad(h, x, torch.ones_like(h), create_graph=True, allow_unused=True)[0]
    if dh_dx is None: dh_dx = torch.zeros_like(h)
    dh_dy = torch.autograd.grad(h, y, torch.ones_like(h), create_graph=True, allow_unused=True)[0]
    if dh_dy is None: dh_dy = torch.zeros_like(h)
    
    # dB_dx is zero if B is sampled randomly and not as a function of x, y. 
    # We'll set it to zero for the training batch since points are random.
    dB_dx = torch.zeros_like(h)
    dB_dy = torch.zeros_like(h)
    
    # Friction term (Manning's n formula: S_f = g * n^2 * u * |V| / h^(4/3))
    v_mag = torch.sqrt(u**2 + v**2 + 1e-6)
    s_fx = g * (friction_n**2) * u * v_mag / (h + 1e-2)**(4/3)
    s_fy = g * (friction_n**2) * v * v_mag / (h + 1e-2)**(4/3)
    
    # Viscosity term (Simplified Laplacian: nu * (d2u/dx2 + d2u/dy2))
    # For speed in this prototype, we'll use first-order damping instead of second-order laplacian
    visc_drag_x = viscosity_nu * u
    visc_drag_y = viscosity_nu * v
    
    # Momentum Residuals
    res_u = u*du_dx + v*du_dy + g*(dh_dx + dB_dx) + s_fx - W_x + visc_drag_x
    res_v = u*dv_dx + v*dv_dy + g*(dh_dy + dB_dy) + s_fy - W_y + visc_drag_y
    
    loss_momentum = torch.mean(res_u**2) + torch.mean(res_v**2)
    
    # 6. Boundary / Building Constraints
    building_mask = (B > 5.0).float()
    loss_boundary = torch.mean((u**2 + v**2) * building_mask)
    
    total_loss = loss_continuity + 0.1 * loss_momentum + loss_boundary
    
    return total_loss, loss_continuity, loss_momentum
