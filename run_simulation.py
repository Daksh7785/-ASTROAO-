import io
import time
import math
import random
import requests
import subprocess
import numpy as np
from PIL import Image

def generate_sh_wfs_frame(frame_w=512, frame_h=512, mla_x=16, mla_y=16, shifts=None) -> bytes:
    """Generates a synthetic spot grid image as a BMP byte string."""
    subap_w = frame_w // mla_x
    subap_h = frame_h // mla_y
    
    # Initialize blank grayscale frame
    frame = np.zeros((frame_h, frame_w), dtype=np.uint8)
    y_indices, x_indices = np.indices((frame_h, frame_w))
    
    # Generate spots
    for y_idx in range(mla_y):
        for x_idx in range(mla_x):
            ref_cx = (x_idx + 0.5) * subap_w
            ref_cy = (y_idx + 0.5) * subap_h
            
            # Apply shift if provided
            dx, dy = 0.0, 0.0
            if shifts is not None:
                subap_flat_idx = y_idx * mla_x + x_idx
                if subap_flat_idx < len(shifts):
                    dx, dy = shifts[subap_flat_idx]
            
            # Place Gaussian spot
            cx = ref_cx + dx
            cy = ref_cy + dy
            
            # Crop a small bounding region around spot center for fast render
            r_limit = 10
            x0 = max(0, int(cx - r_limit))
            y0 = max(0, int(cy - r_limit))
            x1 = min(frame_w, int(cx + r_limit))
            y1 = min(frame_h, int(cy + r_limit))
            
            dist2 = (x_indices[y0:y1, x0:x1] - cx)**2 + (y_indices[y0:y1, x0:x1] - cy)**2
            # Spot width (sigma) is ~2.0 pixels. Max brightness is 220 out of 255.
            spot = 220.0 * np.exp(-dist2 / (2.0 * 2.0**2))
            
            # Blend into frame
            frame[y0:y1, x0:x1] = np.maximum(frame[y0:y1, x0:x1], spot.astype(np.uint8))
            
    # Add random camera read noise
    noise = np.random.normal(5.0, 2.0, frame.shape).astype(np.int16)
    frame = np.clip(frame.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    
    # Save as BMP in memory
    img = Image.fromarray(frame)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='BMP')
    return img_byte_arr.getvalue()

def run():
    print("[AstroAO] Starting AstroAO Backend Subprocess...")
    # Run FastAPI uvicorn backend
    backend_proc = subprocess.Popen(
        ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
        cwd="./backend"
    )
    
    # Wait for backend startup
    time.sleep(3.0)
    
    # Setup observation session
    url = "http://127.0.0.1:8000/api/v1/sessions"
    session_payload = {
        "name": "Live Turbulence Screen",
        "description": "Simulation of Kolmogorov atmospheric turbulence",
        "target_name": "Sirius",
        "frame_rate_hz": 20.0
    }
    
    try:
        r = requests.post(url, json=session_payload)
        session_info = r.json()
        session_id = session_info["id"]
        print(f"[AstroAO] Created observation session. ID: {session_id}")
    except Exception as e:
        print(f"[AstroAO] Failed to connect to backend: {e}")
        backend_proc.terminate()
        return

    # Simulate loop
    frame_number = 1
    t_start = time.time()
    mla_x, mla_y = 16, 16
    n_subaps = mla_x * mla_y
    
    print("[AstroAO] Simulating Shack-Hartmann frames. Press Ctrl+C to stop.")
    try:
        while True:
            t = time.time() - t_start
            
            # Generate simulated turbulence shifts using sinusoidal fluctuations
            # Tips & tilts (global shifts) + local aberrations
            global_dx = 3.0 * math.sin(t * 1.5) + 1.2 * math.cos(t * 4.2)
            global_dy = 2.5 * math.cos(t * 1.2) + 1.5 * math.sin(t * 3.8)
            
            # Add some high-order turbulence fluctuations (Fried parameter fluctuations)
            # Occasional turbulence spikes
            turb_spike = 1.0
            if random.random() < 0.05:
                turb_spike = random.uniform(2.5, 4.0) # simulate sudden seeing degradation
                print("[AstroAO] Simulation: Atmospheric seeing spike!")
                
            shifts = []
            for y_idx in range(mla_y):
                for x_idx in range(mla_x):
                    # Random phase aberration per subaperture
                    local_dx = 1.5 * math.sin(t * 3.0 + x_idx * 0.5) * turb_spike
                    local_dy = 1.5 * math.cos(t * 3.0 + y_idx * 0.5) * turb_spike
                    
                    shifts.append((global_dx + local_dx, global_dy + local_dy))
            
            # Render frame
            bmp_bytes = generate_sh_wfs_frame(shifts=shifts)
            
            # Upload to backend
            upload_url = f"http://127.0.0.1:8000/api/v1/sessions/{session_id}/frames/upload"
            files = {'file': ('frame.bmp', bmp_bytes, 'image/bmp')}
            params = {
                'frame_number': frame_number,
                'timestamp': t
            }
            
            t_upload = time.perf_counter()
            resp = requests.post(upload_url, files=files, params=params)
            latency = (time.perf_counter() - t_upload) * 1000.0
            
            if resp.status_code == 200:
                data = resp.json()
                frame_data = data["frame"]
                print(f"Frame #{frame_number:04d} | RMS: {frame_data['wavefront_rms']:.1f}nm | r0: {frame_data['r0_meters']*100:.1f}cm | Strehl: {frame_data['strehl_estimate']*100:.1f}% | Latency: {latency:.1f}ms")
            else:
                print(f"[AstroAO] Error uploading frame: {resp.text}")
                
            frame_number += 1
            # Maintain ~20 Hz frame rate
            time.sleep(max(0.01, 0.05 - (time.time() - (t_start + t))))
            
    except KeyboardInterrupt:
        print("\nStopping simulation...")
    finally:
        backend_proc.terminate()
        print("Backend terminated. Done.")

if __name__ == "__main__":
    run()
