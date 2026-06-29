import io
import time
import numpy as np
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from app.services import ao_algorithms as alg
from app.models import WFSFrame, DMCommand, TurbulenceStat, Anomaly, Instrument
from app.websocket.frame_stream import manager as ws_manager

class FrameProcessor:
    def __init__(self, instrument: Instrument):
        self.inst = instrument
        
        # Grid sizes and setup
        self.subap_w = int(self.inst.frame_width // self.inst.mla_lenslets_x)
        self.subap_h = int(self.inst.frame_height // self.inst.mla_lenslets_y)
        
        # Build lenslet center coordinates and reference centroids
        self.subap_positions = []
        self.ref_centroids_x = []
        self.ref_centroids_y = []
        
        for y_idx in range(self.inst.mla_lenslets_y):
            for x_idx in range(self.inst.mla_lenslets_x):
                # Subaperture bounding box coordinates
                cx_ref = (x_idx + 0.5) * self.subap_w
                cy_ref = (y_idx + 0.5) * self.subap_h
                self.subap_positions.append([cx_ref, cy_ref])
                self.ref_centroids_x.append(cx_ref)
                self.ref_centroids_y.append(cy_ref)
                
        self.subap_positions = np.array(self.subap_positions)
        self.ref_centroids_x = np.array(self.ref_centroids_x)
        self.ref_centroids_y = np.array(self.ref_centroids_y)
        self.n_subaps = len(self.subap_positions)
        
        # Zernike reconstructor settings
        self.n_modes = 22
        # Precompute the interaction matrix D and its pseudo-inverse
        self.pupil_radius_px = self.inst.pupil_diameter * (self.inst.frame_width / 2.0) / 100.0  # approximate scale
        if self.pupil_radius_px <= 0:
            self.pupil_radius_px = self.inst.frame_width / 2.0
            
        self.D = alg.build_interaction_matrix(
            self.subap_positions - (self.inst.frame_width/2.0),
            n_modes=self.n_modes,
            focal_length=self.inst.mla_focal_length,
            pixel_size=self.inst.pixel_size,
            pupil_radius_px=self.pupil_radius_px
        )
        self.D_pinv = np.linalg.pinv(self.D)
        
        # DM Actuator grid positions (Fried Geometry: Corners of lenslets)
        # For N lenslets along an axis, there are N+1 actuators
        self.act_positions = []
        act_x_count = self.inst.mla_lenslets_x + 1
        act_y_count = self.inst.mla_lenslets_y + 1
        
        for y_idx in range(act_y_count):
            for x_idx in range(act_x_count):
                ax = x_idx * self.subap_w
                ay = y_idx * self.subap_h
                self.act_positions.append([ax, ay])
                
        self.act_positions = np.array(self.act_positions)
        
        # Grid layout for Wavefront visualization (e.g. 64x64)
        self.wf_grid_size = 64
        self.wf_y, self.wf_x = np.indices((self.wf_grid_size, self.wf_grid_size))
        # Center of grid is at (32, 32)
        cx, cy = self.wf_grid_size / 2.0, self.wf_grid_size / 2.0
        self.norm_wf_x = (self.wf_x - cx) / (self.wf_grid_size / 2.0)
        self.norm_wf_y = (self.wf_y - cy) / (self.wf_grid_size / 2.0)
        self.pupil_mask = (self.norm_wf_x**2 + self.norm_wf_y**2) <= 1.0
        
        # Precompute Zernike basis on the 64x64 grid to accelerate reconstruction evaluation
        self.zernike_basis = []
        for idx in range(self.n_modes):
            z_mode, _, _ = alg.eval_zernike_mode(idx + 2, self.norm_wf_x, self.norm_wf_y)
            self.zernike_basis.append(z_mode)
        self.zernike_basis = np.array(self.zernike_basis)
        
        # Calibration defaults
        self.dark_frame = np.zeros((self.inst.frame_height, self.inst.frame_width), dtype=np.float32)
        self.flat_frame = np.ones((self.inst.frame_height, self.inst.frame_width), dtype=np.float32)
        
        # Turbulence time-series buffers
        self.zernike_history = []
        self.time_history = []
        self.prev_centroids_x = self.ref_centroids_x.copy()
        self.prev_centroids_y = self.ref_centroids_y.copy()

    async def process_frame(self, frame_bytes: bytes, frame_number: int, timestamp: float, session_id: str, db: AsyncSession) -> dict:
        t_start = time.perf_counter()
        
        # 1. Load BMP file using PIL
        img = Image.open(io.BytesIO(frame_bytes))
        raw_frame = np.array(img, dtype=np.float32)
        if len(raw_frame.shape) == 3:
            raw_frame = raw_frame[:, :, 0] # grayscale
            
        # 2. Preprocess
        calibrated = alg.preprocess_frame(raw_frame, self.dark_frame, self.flat_frame)
        
        # 3. Centroiding per subaperture
        cx_list, cy_list, snr_list = [], [], []
        threshold = np.mean(calibrated) + 2.0 * np.std(calibrated)
        
        for idx in range(self.n_subaps):
            px, py = self.subap_positions[idx]
            # Crop subaperture patch
            x0 = int(px - self.subap_w / 2.0)
            y0 = int(py - self.subap_h / 2.0)
            x1 = int(px + self.subap_w / 2.0)
            y1 = int(py + self.subap_h / 2.0)
            
            subap_patch = calibrated[y0:y1, x0:x1]
            
            # WCoG centered at previous spot positions to suppress noise
            pcx = self.prev_centroids_x[idx] - x0
            pcy = self.prev_centroids_y[idx] - y0
            cx, cy, snr = alg.centroid_wcog(subap_patch, pcx, pcy, sigma=2.0, threshold=threshold)
            
            # Convert subap patch coordinates back to frame coordinates
            cx_frame = cx + x0
            cy_frame = cy + y0
            
            cx_list.append(cx_frame)
            cy_list.append(cy_frame)
            snr_list.append(snr)
            
        cx_arr = np.array(cx_list)
        cy_arr = np.array(cy_list)
        self.prev_centroids_x = cx_arr.copy()
        self.prev_centroids_y = cy_arr.copy()
        
        # 4. Compute slopes (spot displacement relative to reference position)
        # Shift in pixels scaled to slope angle in radians
        # slope = deviation * pixel_size_microns / focal_length_mm
        pixel_scale = self.inst.pixel_size * 1e-6
        focal_scale = self.inst.mla_focal_length * 1e-3
        slopes_x = (cx_arr - self.ref_centroids_x) * pixel_scale / focal_scale
        slopes_y = (cy_arr - self.ref_centroids_y) * pixel_scale / focal_scale
        
        # 5. Wavefront Modal Reconstruction
        # a = D_pinv * Slopes
        flat_slopes = np.concatenate([slopes_x, slopes_y])
        zernike_coeffs = self.D_pinv @ flat_slopes
        
        # W(x,y) = sum(a_j * Z_j)
        wavefront_map = np.zeros((self.wf_grid_size, self.wf_grid_size))
        for idx in range(self.n_modes):
            wavefront_map += zernike_coeffs[idx] * self.zernike_basis[idx]
            
        # Standard deviation of reconstructed map yields RMS error
        rms_val = np.std(wavefront_map[self.pupil_mask])
        ptv_val = np.max(wavefront_map[self.pupil_mask]) - np.min(wavefront_map[self.pupil_mask])
        
        # Convert RMS from radians to nanometers
        rms_nm = float(rms_val * (self.inst.wavelength / (2.0 * np.pi)))
        ptv_nm = float(ptv_val * (self.inst.wavelength / (2.0 * np.pi)))
        
        # 6. DM Actuator Commands (Fried Geometry)
        dm_voltages, dm_strokes = alg.compute_dm_voltages(
            wavefront_map,
            self.act_positions / (self.inst.frame_width / self.wf_grid_size),  # scaled to wavefront map grid
            self.pupil_mask,
            coupling_coeff=self.inst.dm_coupling_coeff,
            lambda_reg=0.001
        )
        
        # Check DM saturation
        max_stroke = np.max(np.abs(dm_strokes))
        saturation = max_stroke > (self.inst.dm_actuators_x or 5.0)
        
        # 7. Turbulence stats estimator
        self.zernike_history.append(zernike_coeffs)
        self.time_history.append(timestamp)
        if len(self.zernike_history) > 200:
            self.zernike_history.pop(0)
            self.time_history.pop(0)
            
        r0, tau0, strehl = alg.estimate_turbulence_params(
            self.zernike_history,
            self.time_history,
            self.inst.pupil_diameter * 1e-3,  # convert mm to meters
            wavelength=self.inst.wavelength * 1e-9  # convert nm to meters
        )
        
        # Compute PSF map using 2D FFT
        psf_map = alg.compute_psf(wavefront_map, self.pupil_mask)
        
        # Estimate Wind Speed and Direction
        wind_speed, wind_direction = alg.estimate_wind_profile(
            self.zernike_history,
            self.time_history,
            self.inst.pupil_diameter * 1e-3
        )
        
        processing_time_ms = (time.perf_counter() - t_start) * 1000.0
        
        # Store objects in database
        db_frame = WFSFrame(
            session_id=session_id,
            frame_number=frame_number,
            timestamp=timestamp,
            centroids_x=cx_arr.tolist(),
            centroids_y=cy_arr.tolist(),
            slopes_x=slopes_x.tolist(),
            slopes_y=slopes_y.tolist(),
            zernike_coeffs=zernike_coeffs.tolist(),
            wavefront_rms=rms_nm,
            wavefront_ptv=ptv_nm,
            wavefront_map=wavefront_map.tolist(),
            processing_time_ms=processing_time_ms
        )
        db_dm = DMCommand(
            session_id=session_id,
            frame_number=frame_number,
            timestamp=timestamp,
            actuator_map=dm_voltages.reshape(self.inst.mla_lenslets_y + 1, self.inst.mla_lenslets_x + 1).tolist(),
            max_stroke_used=float(max_stroke),
            saturation_flag=bool(saturation),
            predicted_residual_rms=rms_nm * 0.15 # theoretical residual with simple correction
        )
        db_turb = TurbulenceStat(
            session_id=session_id,
            timestamp=timestamp,
            r0_meters=r0,
            tau0_ms=tau0,
            strehl_estimate=strehl,
            cn2_integrated=1.2e-15,
            wind_speed_eff=wind_speed
        )
        
        db.add(db_frame)
        db.add(db_dm)
        db.add(db_turb)
        
        # Check for anomalies
        if saturation:
            anom = Anomaly(
                session_id=session_id,
                frame_number=frame_number,
                anomaly_type="dm_saturation",
                severity="warning",
                confidence=1.0,
                description=f"Deformable Mirror saturation: maximum stroke requested is {max_stroke:.2f}um."
            )
            db.add(anom)
            
        if r0 < 0.05:
            anom = Anomaly(
                session_id=session_id,
                frame_number=frame_number,
                anomaly_type="turbulence_spike",
                severity="critical",
                confidence=0.9,
                description=f"Severe turbulence spike detected: Fried Parameter r0 is extremely low ({r0*100:.1f} cm)."
            )
            db.add(anom)
            
        # PUSH via WebSocket broadcast
        payload = {
            "frame_number": frame_number,
            "timestamp": timestamp,
            "wavefront_rms": rms_nm,
            "wavefront_ptv": ptv_nm,
            "wavefront_map": wavefront_map.tolist(),
            "psf_map": psf_map.tolist(),
            "dm_voltages": dm_voltages.tolist(),
            "dm_strokes": dm_strokes.tolist(),
            "zernike_coeffs": zernike_coeffs.tolist(),
            "r0_meters": r0,
            "tau0_ms": tau0,
            "strehl_estimate": strehl,
            "wind_speed": wind_speed,
            "wind_direction": wind_direction,
            "processing_time_ms": processing_time_ms
        }
        await ws_manager.broadcast_frame(session_id, payload)
        
        return payload
