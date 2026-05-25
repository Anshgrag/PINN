# Real-Time 2D Flood Prediction Backend (Vectorized PINN)

This backend implements a Physics-Informed Neural Network (PINN) for sub-50ms flood prediction on a 256x256 grid.

## Architecture
- **Vectorized MLP**: Flattens the city grid into points for simultaneous processing.
- **Continuous Autograd**: Enforces the Shallow Water Equations (Mass Conservation) without grid blurring.
- **High-Performance API**: Uses binary octet-streams to bypass JSON serialization bottlenecks.

## Files
- `model.py`: PyTorch MLP architecture.
- `physics_loss.py`: Autograd engine for physics-informed training.
- `train.py`: Training script to generate `flood_mlp_weights.pth`.
- `app.py`: FastAPI server for optimized inference.
- `test_backend.py`: Unit tests and latency benchmarks.

## Setup & Running
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Train the model (optional if weights exist):
   ```bash
   python train.py
   ```
3. Start the server:
   ```bash
   python app.py
   ```

## API Usage
**Endpoint**: `POST /predict`
**Payload**:
```json
{
  "elevation_map": [[...]], // 256x256 list
  "rainfall_intensity": 5.0
}
```
**Response**: `application/octet-stream`
- Returns a raw binary buffer of shape `(3, 256, 256)` in `float32`.
- Index 0: Water Depth (h)
- Index 1: Velocity U
- Index 2: Velocity V

## Performance
- **CPU Inference**: ~70-80ms (includes preprocessing and data transfer).
- **GPU Inference**: Expected <20ms (with CUDA-enabled hardware).
