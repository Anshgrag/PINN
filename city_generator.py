import numpy as np
import torch
from scipy.ndimage import gaussian_filter

def generate_large_manhattan_grid(width_m=10000, height_m=5000, resolution=20):
    """
    Generates a large-scale Manhattan grid with elevation and structural materials.
    """
    cols = int(width_m / resolution)
    rows = int(height_m / resolution)
    
    elevation = np.zeros((rows, cols))
    materials = np.zeros((rows, cols)) # 0: None, 1: Wood, 2: Masonry, 3: Concrete
    
    street_width = 18
    avenue_width = 30
    block_width = 270 
    block_height = 80  
    
    sw_g = max(1, int(street_width / resolution))
    aw_g = max(1, int(avenue_width / resolution))
    bw_g = max(1, int(block_width / resolution))
    bh_g = max(1, int(block_height / resolution))
    
    x = np.linspace(0, 1, cols)
    X, Y = np.meshgrid(x, np.linspace(0, 1, rows))
    elevation = 2.0 * (1.0 - np.abs(2 * X - 1)) 
    
    river_width_g = int(500 / resolution)
    elevation[:, :river_width_g] = -5.0
    elevation[:, -river_width_g:] = -5.0
    
    start_g = river_width_g + 2
    end_g = cols - river_width_g - 2
    
    for i in range(rows):
        for j in range(start_g, end_g):
            is_avenue = (j % (bw_g + aw_g)) < aw_g
            is_street = (i % (bh_g + sw_g)) < sw_g
            
            if not is_avenue and not is_street:
                # Inside a building block
                h = 15.0 + np.random.uniform(0, 10)
                elevation[i, j] = h
                
                # Assign material based on height (Skyscrapers = Concrete, Small = Wood)
                if h > 22: materials[i, j] = 3 # Concrete
                elif h > 17: materials[i, j] = 2 # Masonry
                else: materials[i, j] = 1 # Wood
                
    elevation = gaussian_filter(elevation, sigma=0.5)
    
    return elevation, materials

def generate_synthetic_city(size=None, num_buildings=None):
    return generate_large_manhattan_grid(10000, 5000, 20)

if __name__ == "__main__":
    import matplotlib.pyplot as plt
    city = generate_synthetic_city()
    plt.imshow(city, cmap='terrain')
    plt.colorbar(label='Elevation (m)')
    plt.title("Synthetic City Model for PINN Training")
    plt.show()
