import numpy as np
from scipy.linalg import pinv
from scipy.optimize import curve_fit

def preprocess_frame(raw_frame: np.ndarray, dark_frame: np.ndarray = None, flat_frame: np.ndarray = None) -> np.ndarray:
    """Dark subtraction and flat division."""
    processed = raw_frame.astype(np.float32)
    if dark_frame is not None:
        processed = processed - dark_frame
    if flat_frame is not None:
        # Avoid division by zero
        flat = np.where(flat_frame == 0, 1.0, flat_frame)
        processed = processed / flat
    return np.clip(processed, 0, None)

def centroid_cog(subap_data: np.ndarray, threshold: float = 0.0) -> tuple:
    """Center of Gravity centroiding."""
    h, w = subap_data.shape
    y_indices, x_indices = np.indices((h, w))
    
    # Apply background threshold
    data_thresh = subap_data - threshold
    data_thresh[data_thresh < 0] = 0.0
    
    total_intensity = np.sum(data_thresh)
    if total_intensity <= 0:
        return w / 2.0, h / 2.0, 0.0
        
    cx = np.sum(data_thresh * x_indices) / total_intensity
    cy = np.sum(data_thresh * y_indices) / total_intensity
    
    # Calculate SNR: mean of peak signal / std of background noise
    bg_noise = np.std(subap_data[subap_data < threshold]) if np.any(subap_data < threshold) else 1.0
    snr = np.max(subap_data) / max(bg_noise, 1e-3)
    
    return float(cx), float(cy), float(snr)

def centroid_wcog(subap_data: np.ndarray, prev_cx: float, prev_cy: float, sigma: float = 2.0, threshold: float = 0.0) -> tuple:
    """Weighted Center of Gravity centroiding using a Gaussian window centered at the previous spot position."""
    h, w = subap_data.shape
    y_indices, x_indices = np.indices((h, w))
    
    # Generate Gaussian weight window
    weight = np.exp(-((x_indices - prev_cx)**2 + (y_indices - prev_cy)**2) / (2.0 * sigma**2))
    
    # Apply background threshold
    data_thresh = subap_data - threshold
    data_thresh[data_thresh < 0] = 0.0
    
    weighted_data = data_thresh * weight
    total_intensity = np.sum(weighted_data)
    
    if total_intensity <= 0:
        return w / 2.0, h / 2.0, 0.0
        
    cx = np.sum(weighted_data * x_indices) / total_intensity
    cy = np.sum(weighted_data * y_indices) / total_intensity
    
    bg_noise = np.std(subap_data[subap_data < threshold]) if np.any(subap_data < threshold) else 1.0
    snr = np.max(subap_data) / max(bg_noise, 1e-3)
    
    return float(cx), float(cy), float(snr)

# Pre-defined analytical Zernike polynomials (Noll order j=2 to 22)
# returns: (Z_val, dZ/dx, dZ/dy)
def eval_zernike_mode(j: int, x: np.ndarray, y: np.ndarray) -> tuple:
    r2 = x**2 + y**2
    r = np.sqrt(r2)
    # Avoid division by zero for polar angle
    theta = np.arctan2(y, x)
    
    # Helper coefficients
    sq3 = np.sqrt(3.0)
    sq5 = np.sqrt(5.0)
    sq6 = np.sqrt(6.0)
    sq8 = np.sqrt(8.0)
    sq10 = np.sqrt(10.0)
    
    # Default outputs
    z = np.zeros_like(x)
    dz_dx = np.zeros_like(x)
    dz_dy = np.zeros_like(x)
    
    # We normalized pupil coordinates to [-1, 1] range inside pupil diameter.
    # Exclude coordinates outside pupil (r > 1) in evaluations if needed, but here we define the functional basis
    mask = r <= 1.0
    
    if j == 2:  # Tip (x)
        z = 2.0 * x
        dz_dx = 2.0 * np.ones_like(x)
    elif j == 3:  # Tilt (y)
        z = 2.0 * y
        dz_dy = 2.0 * np.ones_like(y)
    elif j == 4:  # Defocus
        z = sq3 * (2.0 * r2 - 1.0)
        dz_dx = sq3 * 4.0 * x
        dz_dy = sq3 * 4.0 * y
    elif j == 5:  # Astigmatism 45°
        z = sq6 * (2.0 * x * y)
        dz_dx = sq6 * 2.0 * y
        dz_dy = sq6 * 2.0 * x
    elif j == 6:  # Astigmatism 0°
        z = sq6 * (x**2 - y**2)
        dz_dx = sq6 * 2.0 * x
        dz_dy = sq6 * -2.0 * y
    elif j == 7:  # Coma x
        # sqrt(8)*(3r^2-2)*y
        z = sq8 * (3.0 * r2 - 2.0) * y
        dz_dx = sq8 * 6.0 * x * y
        dz_dy = sq8 * (3.0 * x**2 + 9.0 * y**2 - 2.0)
    elif j == 8:  # Coma y
        # sqrt(8)*(3r^2-2)*x
        z = sq8 * (3.0 * r2 - 2.0) * x
        dz_dx = sq8 * (9.0 * x**2 + 3.0 * y**2 - 2.0)
        dz_dy = sq8 * 6.0 * x * y
    elif j == 9:  # Trefoil x
        # sqrt(8) * (3x^2y - y^3)
        z = sq8 * (3.0 * x**2 * y - y**3)
        dz_dx = sq8 * 6.0 * x * y
        dz_dy = sq8 * (3.0 * x**2 - 3.0 * y**2)
    elif j == 10:  # Trefoil y
        # sqrt(8) * (x^3 - 3xy^2)
        z = sq8 * (x**3 - 3.0 * x * y**2)
        dz_dx = sq8 * (3.0 * x**2 - 3.0 * y**2)
        dz_dy = sq8 * -6.0 * x * y
    elif j == 11:  # Spherical primary
        z = sq5 * (6.0 * r2**2 - 6.0 * r2 + 1.0)
        dz_dx = sq5 * (24.0 * r2 - 12.0) * x
        dz_dy = sq5 * (24.0 * r2 - 12.0) * y
    elif j == 12: # Secondary Astigmatism 0°
        z = sq10 * (4.0 * r2 - 3.0) * (x**2 - y**2)
        dz_dx = sq10 * (12.0 * x**3 + 4.0 * x * y**2 - 6.0 * x)
        dz_dy = sq10 * (-4.0 * x**2 * y - 12.0 * y**3 + 6.0 * y)
    elif j == 13: # Secondary Astigmatism 45°
        z = sq10 * (4.0 * r2 - 3.0) * (2.0 * x * y)
        dz_dx = sq10 * (8.0 * x**2 * y + 24.0 * y**3 - 6.0 * y)
        dz_dy = sq10 * (24.0 * x**3 + 8.0 * x * y**2 - 6.0 * x)
    else:
        # Fallback to general low-order mode approximations or zero
        pass
        
    return z * mask, dz_dx * mask, dz_dy * mask

def build_interaction_matrix(subap_positions: np.ndarray, n_modes: int, focal_length: float, pixel_size: float, pupil_radius_px: float) -> np.ndarray:
    """
    Builds the wavefront interaction matrix D relating Zernike coefficients to slopes.
    subap_positions: coordinates of subaperture centers in pixels relative to pupil center.
    """
    n_subaps = len(subap_positions)
    # D size is [2 * n_subaps, n_modes]
    D = np.zeros((2 * n_subaps, n_modes))
    
    # Normalize positions to pupil coordinates [-1, 1]
    norm_positions = subap_positions / pupil_radius_px
    
    for idx_mode in range(n_modes):
        j = idx_mode + 2  # Start Zernikes from Noll mode 2 (Tip)
        for i, (x, y) in enumerate(norm_positions):
            _, dz_dx, dz_dy = eval_zernike_mode(j, x, y)
            # Slopes are scaled by pixel_size / focal_length to convert sensor displacements to physical slope angles
            # Normalization scaling factor 1 / pupil_radius_px for coordinate chain rule
            grad_scale = 1.0 / pupil_radius_px
            D[i, idx_mode] = dz_dx * grad_scale
            D[n_subaps + i, idx_mode] = dz_dy * grad_scale
            
    return D

def compute_dm_voltages(wavefront_map: np.ndarray, act_positions: np.ndarray, pupil_mask: np.ndarray, coupling_coeff: float = 0.135, lambda_reg: float = 0.001) -> tuple:
    """
    Compute actuator voltages with Tikhonov regularization.
    Fried geometry assumes actuators are positioned relative to the wavefront grid.
    act_positions: Nx2 array of actuator coordinates on the wavefront grid.
    """
    n_act = len(act_positions)
    grid_h, grid_w = wavefront_map.shape
    y_indices, x_indices = np.indices((grid_h, grid_w))
    
    # Flatten wavefront map inside pupil mask
    flat_wf = wavefront_map[pupil_mask]
    n_points = len(flat_wf)
    
    # 1. Build DM Influence Matrix F
    # F[i, j] is the mirror surface height at pixel point i when actuator j is poked
    # We use a Gaussian influence function: F_ij = exp(-d_ij^2 / (2 * sigma^2))
    # coupling_coeff = exp(-pitch^2 / (2 * sigma^2))
    # Assuming actuator pitch in grid pixels = 4
    pitch = 4.0
    sigma = np.sqrt(-pitch**2 / (2.0 * np.log(coupling_coeff))) if coupling_coeff > 0 else 1.0
    
    F = np.zeros((n_points, n_act))
    flat_x = x_indices[pupil_mask]
    flat_y = y_indices[pupil_mask]
    
    for j, (ax, ay) in enumerate(act_positions):
        dist2 = (flat_x - ax)**2 + (flat_y - ay)**2
        F[:, j] = np.exp(-dist2 / (2.0 * sigma**2))
        
    # We want DM surface to create conjugate wavefront: F * voltages = -wavefront/2
    target = -flat_wf / 2.0
    
    # Tikhonov regularization: voltages = (F.T * F + lambda * I)^-1 * F.T * target
    FtF = F.T @ F
    FtTarget = F.T @ target
    voltages = np.linalg.solve(FtF + lambda_reg * np.eye(n_act), FtTarget)
    
    # Calculate physical DM strokes (microns)
    # Voltage of 1.0 is mapped to stroke limit (e.g. 5 microns)
    strokes = voltages * 5.0
    
    return voltages, strokes

# Noll coefficients for variance tracking (modes 2 to 22)
NOLL_COEFF = {
    2: 0.449, 3: 0.449,           # Tip / Tilt
    4: 0.0232, 5: 0.0232,         # Astigmatism / Defocus
    6: 0.0232, 7: 0.00619,        # Coma
    8: 0.00619, 9: 0.00619,
    10: 0.00619, 11: 0.00619,
    12: 0.00232, 13: 0.00232,
    14: 0.00232, 15: 0.00232,
    16: 0.00232, 17: 0.00232,
    18: 0.000874, 19: 0.000874,
    20: 0.000874, 21: 0.000874,
    22: 0.000874
}

def estimate_turbulence_params(zernike_history: list, time_history: list, pupil_diameter: float, wavelength: float = 500e-9) -> tuple:
    """
    Estimate Fried parameter r0 from Zernike variance (Noll 1976)
    and coherence timescale tau0 from temporal autocorrelation.
    """
    if len(zernike_history) < 10:
        return 0.15, 10.0, 0.8  # Defaults: r0=15cm, tau0=10ms, strehl=80%
        
    z_array = np.array(zernike_history)  # Shape [N, n_modes]
    variances = np.var(z_array, axis=0)
    
    # 1. Estimate r0
    r0_estimates = []
    k = 2.0 * np.pi / wavelength
    
    for idx, mode_j in enumerate(range(2, 2 + len(variances))):
        if mode_j in NOLL_COEFF and variances[idx] > 0:
            Cj = NOLL_COEFF[mode_j]
            # var = Cj * (D/r0)^(5/3) * k^2 (in rad)
            ratio_D_r0 = (variances[idx] / (Cj * k**2))**(3/5) if variances[idx] > 0 else 0
            if ratio_D_r0 > 0:
                r0_estimates.append(pupil_diameter / ratio_D_r0)
                
    r0 = np.median(r0_estimates) if r0_estimates else 0.15
    r0 = max(min(r0, 1.0), 0.02)  # Clamp to reasonable values (2cm to 1m)
    
    # 2. Estimate tau0 from Tip/Tilt temporal structure function/correlation
    dt = np.mean(np.diff(time_history)) if len(time_history) > 1 else 0.01
    
    # Autocorrelation of Tip mode (idx 0)
    tip_signal = z_array[:, 0]
    tip_norm = tip_signal - np.mean(tip_signal)
    acf = np.correlate(tip_norm, tip_norm, mode='full')[len(tip_norm)-1:]
    if acf[0] > 0:
        acf /= acf[0]
        # Find time where correlation drops to 1/e (~0.368)
        decay_idx = np.where(acf < 0.368)[0]
        tau0 = decay_idx[0] * dt if len(decay_idx) > 0 else 0.01
    else:
        tau0 = 0.01
        
    tau0 = max(min(tau0 * 1000.0, 100.0), 1.0) # convert to ms (1ms to 100ms)
    
    # 3. Strehl ratio estimate: S ≈ exp(-sigma_residual^2)
    # Approximate residual wavefront error from high-order modes (excluding defocus/astigmatism)
    high_order_var = np.sum(variances[3:]) if len(variances) > 3 else 0.05
    strehl = np.exp(-high_order_var)
    strehl = max(min(strehl, 1.0), 0.0)
    
    return float(r0), float(tau0), float(strehl)

def compute_psf(wavefront_map: np.ndarray, pupil_mask: np.ndarray) -> np.ndarray:
    """
    Compute the Point Spread Function (PSF) from the wavefront phase map using 2D FFT.
    Returns a normalized 2D intensity grid representing starlight focus quality.
    """
    grid_size = wavefront_map.shape[0]
    complex_field = np.zeros((grid_size, grid_size), dtype=np.complex128)
    
    # E(x,y) = A(x,y) * exp(i * phi(x,y))
    # where A(x,y) is the circular pupil mask and phi is the phase in radians
    complex_field[pupil_mask] = np.exp(1j * wavefront_map[pupil_mask])
    
    # 2D Fourier Transform
    field_fft = np.fft.fft2(complex_field)
    field_shift = np.fft.fftshift(field_fft)
    psf = np.abs(field_shift)**2
    
    # Normalize to peak intensity
    psf_max = np.max(psf)
    if psf_max > 0:
        psf = psf / psf_max
        
    return psf

def estimate_wind_profile(zernike_history: list, time_history: list, pupil_diameter: float) -> tuple:
    """
    Estimate effective wind speed (m/s) and wind direction (degrees)
    using the temporal fluctuations of Tip & Tilt Zernike modes.
    """
    if len(zernike_history) < 20:
        return 8.5, 225.0  # default values
        
    z_array = np.array(zernike_history)
    dt = np.mean(np.diff(time_history)) if len(time_history) > 1 else 0.05
    if dt <= 0:
        dt = 0.05
        
    # Calculate velocities of Tip (mode 2) and Tilt (mode 3)
    vx = np.diff(z_array[:, 0]) / dt
    vy = np.diff(z_array[:, 1]) / dt
    
    speed_rms = np.sqrt(np.mean(vx**2 + vy**2))
    
    # Scale wind speed based on pupil diameter and rms fluctuations
    wind_speed = float(speed_rms * pupil_diameter * 0.15)
    wind_speed = max(min(wind_speed, 45.0), 0.5)  # clamp 0.5 m/s to 45 m/s
    
    # Compute principal direction of the wind
    wind_dir = float(np.arctan2(np.mean(vy), np.mean(vx)) * 180.0 / np.pi) % 360.0
    
    return wind_speed, wind_dir
