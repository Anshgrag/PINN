import numpy as np
import torch
from scipy.ndimage import gaussian_filter

def generate_synthetic_city(size=256, num_buildings=40):
    """
    Generates a physically plausible synthetic city elevation map.
    - Smooth terrain (slopes)
    - Buildings (blocks)
    - A river or drainage channel
    """
    # 1. Base Terrain (sloped plane)
    x = np.linspace(0, 5, size)
    y = np.linspace(0, 5, size)
    X, Y = np.meshgrid(x, y)
    elevation = 0.5 * X + 0.2 * Y # Gentle slope towards top-left
    
    # 2. Add a River/Channel (low elevation)
    river_mask = (Y > 2.2) & (Y < 2.8)
    elevation[river_mask] -= 1.5
    
    # 3. Add Buildings
    buildings = np.zeros((size, size))
    for _ in range(num_buildings):
        bx, by = np.random.randint(20, size-20, 2)
        bw, bh = np.random.randint(10, 30, 2)
        b_height = np.random.uniform(5, 15)
        
        # Ensure buildings don't sit in the middle of the river for this simple model
        if not (by > 2.0 * size/5 and by < 3.0 * size/5):
            buildings[bx:bx+bw, by:by+bh] = b_height
            
    # 4. Final Map
    final_map = elevation + buildings
    # Apply slight smoothing to terrain but keep buildings sharp
    final_map = gaussian_filter(final_map, sigma=0.5)
    
    return final_map

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    city = generate_synthetic_city()
    plt.imshow(city, cmap='terrain')
    plt.colorbar(label='Elevation (m)')
    plt.title("Synthetic City Model for PINN Training")
    plt.show()
