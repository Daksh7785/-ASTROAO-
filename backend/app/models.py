import datetime
import uuid
from sqlalchemy import Column, String, Integer, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.database import Base

def generate_uuid():
    return str(uuid.uuid4())

class Instrument(Base):
    __tablename__ = "instruments"
    id = Column(String, primary_key=True, default=generate_uuid)
    name = Column(String, nullable=False)
    mla_lenslets_x = Column(Integer, nullable=False)
    mla_lenslets_y = Column(Integer, nullable=False)
    mla_focal_length = Column(Float, nullable=False)
    mla_lenslet_size = Column(Float, nullable=False)
    pixel_size = Column(Float, nullable=False)
    frame_width = Column(Integer, nullable=False)
    frame_height = Column(Integer, nullable=False)
    pupil_diameter = Column(Float, nullable=False)
    wavelength = Column(Float, default=500.0)
    dm_actuators_x = Column(Integer)
    dm_actuators_y = Column(Integer)
    dm_coupling_coeff = Column(Float, default=0.135)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(String, primary_key=True, default=generate_uuid)
    instrument_id = Column(String, ForeignKey("instruments.id"))
    name = Column(String, nullable=False)
    description = Column(String)
    target_name = Column(String)
    start_time = Column(DateTime, default=datetime.datetime.utcnow)
    end_time = Column(DateTime)
    frame_rate_hz = Column(Float, nullable=False)
    total_frames = Column(Integer, default=0)
    status = Column(String, default="active")  # active, completed, failed
    metadata_json = Column(JSON)

class WFSFrame(Base):
    __tablename__ = "wfs_frames"
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    centroids_x = Column(JSON)  # list of float
    centroids_y = Column(JSON)  # list of float
    slopes_x = Column(JSON)      # list of float
    slopes_y = Column(JSON)      # list of float
    zernike_coeffs = Column(JSON) # list of float
    wavefront_rms = Column(Float)
    wavefront_ptv = Column(Float)
    wavefront_map = Column(JSON)   # 2D list of float representing W(x,y)
    processing_time_ms = Column(Float)

class DMCommand(Base):
    __tablename__ = "dm_commands"
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    frame_number = Column(Integer, nullable=False)
    timestamp = Column(Float, nullable=False)
    actuator_map = Column(JSON) # 2D list of float representing actuator voltage
    max_stroke_used = Column(Float)
    saturation_flag = Column(Boolean, default=False)
    predicted_residual_rms = Column(Float)

class TurbulenceStat(Base):
    __tablename__ = "turbulence_stats"
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    timestamp = Column(Float, nullable=False)
    r0_meters = Column(Float)
    tau0_ms = Column(Float)
    strehl_estimate = Column(Float)
    cn2_integrated = Column(Float)
    wind_speed_eff = Column(Float)

class Anomaly(Base):
    __tablename__ = "ao_anomalies"
    id = Column(String, primary_key=True, default=generate_uuid)
    session_id = Column(String, ForeignKey("sessions.id"))
    frame_number = Column(Integer)
    detected_at = Column(DateTime, default=datetime.datetime.utcnow)
    anomaly_type = Column(String, nullable=False) # dm_saturation, turbulence_spike, etc
    severity = Column(String)                     # warning, critical
    confidence = Column(Float)
    description = Column(String)
