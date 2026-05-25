import numpy as np

def compute_resilience_metrics(h_grid, B_array):
    """
    Computes flood resilience metrics based on water depth and elevation.
    
    Args:
        h_grid (np.ndarray): 256x256 array of water depths (meters).
        B_array (np.ndarray): 256x256 array of elevations (meters).
        
    Returns:
        dict: Resilience metrics.
    """
    # 1. Define masks
    building_mask = B_array > 5.0
    # For synthetic city, land is where elevation is low but above 0
    land_mask = (B_array <= 5.0) & (B_array > 0.0) 
    
    # 2. Inundation Extent (Land area flooded > 0.3m)
    land_cells = np.sum(land_mask)
    if land_cells > 0:
        flooded_land_cells = np.sum((h_grid > 0.3) & land_mask)
        inundation_extent_pct = (flooded_land_cells / land_cells) * 100
    else:
        inundation_extent_pct = 0.0
        
    # 3. Building Exposure (Building area flooded > 0.05m)
    building_cells = np.sum(building_mask)
    if building_cells > 0:
        flooded_building_cells = np.sum((h_grid > 0.05) & building_mask)
        building_exposure_pct = (flooded_building_cells / building_cells) * 100
    else:
        building_exposure_pct = 0.0
        
    # 4. Resilience Score (0-100)
    resilience_score = 100 - (0.6 * inundation_extent_pct + 0.4 * building_exposure_pct)
    resilience_score = max(0.0, min(100.0, resilience_score))
    
    return {
        "resilience_score": float(resilience_score),
        "inundation_extent_pct": float(inundation_extent_pct),
        "building_exposure_pct": float(building_exposure_pct)
    }

def run_tsunami_simulation(B_array, model_fn, payload):
    """
    Simulates a rigorous multi-day event.
    Time steps increased for mathematical accuracy and user-requested "processing depth".
    """
    # Simulate 100 steps (every ~45 mins for 72 hours)
    timeline_steps = np.linspace(0, 72, 100)
    surge_curve = 8.0 * np.exp(-((timeline_steps - 36)**2) / (2 * 10**2))
    
    min_resilience = 100.0
    peak_inundation = 0.0
    peak_exposure = 0.0
    
    # Copy payload to mutate it during simulation steps
    step_payload = payload.model_copy()
    
    for q in surge_curve:
        step_payload.rainfall_intensity = float(q)
        # Add dynamic wind that peaks with the surge
        step_payload.wind_speed = payload.wind_speed * (q / 8.0)
        
        h_grid = model_fn(B_array, step_payload)
        metrics = compute_resilience_metrics(h_grid, B_array)
        
        min_resilience = min(min_resilience, metrics["resilience_score"])
        peak_inundation = max(peak_inundation, metrics["inundation_extent_pct"])
        peak_exposure = max(peak_exposure, metrics["building_exposure_pct"])
        
    # Final Grading
    passed = min_resilience > 65.0 # Slightly stricter
    grade = "A" if min_resilience > 85 else "B" if min_resilience > 70 else "C" if min_resilience > 55 else "D" if min_resilience > 35 else "F"
    
    return {
        "event_duration_hours": 72,
        "peak_surge_intensity": float(np.max(surge_curve)),
        "min_resilience_score": float(round(min_resilience, 2)),
        "peak_inundation_pct": float(round(peak_inundation, 2)),
        "peak_building_exposure_pct": float(round(peak_exposure, 2)),
        "passed": bool(passed),
        "grade": grade,
        "summary": "City defenses held against multi-parameter stress." if passed else "Catastrophic failure under combined wind/surge load."
    }
