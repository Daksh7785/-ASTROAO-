from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from typing import List

from app.config import settings
from app.database import init_db, close_db, get_db, async_session
from app.models import Instrument, Session, WFSFrame, DMCommand, TurbulenceStat, Anomaly
from app.services.frame_processor import FrameProcessor
from app.websocket.frame_stream import router as ws_router

# Session-based active frame processors
active_processors = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize Database
    await init_db()
    
    # Pre-seed a default instrument configuration
    async with async_session() as session:
        result = await session.execute(select(Instrument))
        instruments = result.scalars().all()
        if not instruments:
            default_inst = Instrument(
                name="AstroAO Default SH-WFS",
                mla_lenslets_x=16,
                mla_lenslets_y=16,
                mla_focal_length=40.0,    # mm
                mla_lenslet_size=0.3,     # mm
                pixel_size=4.65,          # microns
                frame_width=512,
                frame_height=512,
                pupil_diameter=4.8,       # mm
                wavelength=632.8,         # nm (HeNe laser)
                dm_actuators_x=16,
                dm_actuators_y=16,
                dm_coupling_coeff=0.135
            )
            session.add(default_inst)
            await session.commit()
            
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="AstroAO — Adaptive Optics Intelligence Platform",
    version="1.0.0",
    lifespan=lifespan
)

# Apply CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include WebSocket stream router
app.include_router(ws_router)

# ----------------- REST ENDPOINTS -----------------

@app.get("/api/v1/instruments", response_model=list)
async def get_instruments(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Instrument))
    instruments = result.scalars().all()
    return [
        {
            "id": i.id,
            "name": i.name,
            "mla_lenslets_x": i.mla_lenslets_x,
            "mla_lenslets_y": i.mla_lenslets_y,
            "mla_focal_length": i.mla_focal_length,
            "pixel_size": i.pixel_size,
            "frame_width": i.frame_width,
            "frame_height": i.frame_height,
            "pupil_diameter": i.pupil_diameter,
            "wavelength": i.wavelength,
        }
        for i in instruments
    ]

@app.post("/api/v1/sessions")
async def create_session(session_data: dict, db: AsyncSession = Depends(get_db)):
    # Find instrument or use the default one
    result = await db.execute(select(Instrument))
    inst = result.scalars().first()
    if not inst:
        raise HTTPException(status_code=500, detail="No instruments configured.")
        
    new_session = Session(
        instrument_id=inst.id,
        name=session_data.get("name", "New Observation Session"),
        description=session_data.get("description", "Lab turbulence screen run"),
        target_name=session_data.get("target_name", "Target Star"),
        frame_rate_hz=session_data.get("frame_rate_hz", 30.0),
        status="active"
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    
    # Initialize the FrameProcessor for this session
    active_processors[new_session.id] = FrameProcessor(inst)
    
    return {
        "id": new_session.id,
        "name": new_session.name,
        "instrument_id": new_session.instrument_id,
        "frame_rate_hz": new_session.frame_rate_hz,
        "status": new_session.status
    }

@app.post("/api/v1/sessions/{session_id}/frames/upload")
async def upload_frame(
    session_id: str,
    frame_number: int,
    timestamp: float,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    # Ensure active session
    res = await db.execute(select(Session).filter(Session.id == session_id))
    obs_session = res.scalars().first()
    if not obs_session:
        raise HTTPException(status_code=404, detail="Session not found")
        
    if session_id not in active_processors:
        # Load instrument configuration
        res_inst = await db.execute(select(Instrument).filter(Instrument.id == obs_session.instrument_id))
        inst = res_inst.scalars().first()
        active_processors[session_id] = FrameProcessor(inst)
        
    processor = active_processors[session_id]
    frame_bytes = await file.read()
    
    # Run the processing pipeline
    payload = await processor.process_frame(
        frame_bytes,
        frame_number=frame_number,
        timestamp=timestamp,
        session_id=session_id,
        db=db
    )
    
    # Increment total frames in the session
    obs_session.total_frames = max(obs_session.total_frames, frame_number)
    db.add(obs_session)
    await db.commit()
    
    return {"success": True, "frame": payload}

@app.get("/api/v1/sessions/{session_id}/stats")
async def get_session_stats(session_id: str, db: AsyncSession = Depends(get_db)):
    # Retrieve recent telemetry data
    res_frames = await db.execute(
        select(WFSFrame).filter(WFSFrame.session_id == session_id).order_by(WFSFrame.frame_number.desc()).limit(50)
    )
    frames = res_frames.scalars().all()
    
    res_turb = await db.execute(
        select(TurbulenceStat).filter(TurbulenceStat.session_id == session_id).order_by(TurbulenceStat.timestamp.desc()).limit(50)
    )
    turb_stats = res_turb.scalars().all()
    
    res_anom = await db.execute(
        select(Anomaly).filter(Anomaly.session_id == session_id).order_by(Anomaly.detected_at.desc()).limit(10)
    )
    anomalies = res_anom.scalars().all()
    
    if not frames:
        return {"success": False, "message": "No frame telemetry recorded yet."}
        
    avg_rms = sum(f.wavefront_rms for f in frames) / len(frames)
    avg_latency = sum(f.processing_time_ms for f in frames) / len(frames)
    
    r0_vals = [t.r0_meters for t in turb_stats if t.r0_meters]
    avg_r0 = sum(r0_vals) / len(r0_vals) if r0_vals else 0.15
    
    tau_vals = [t.tau0_ms for t in turb_stats if t.tau0_ms]
    avg_tau = sum(tau_vals) / len(tau_vals) if tau_vals else 10.0
    
    strehl_vals = [t.strehl_estimate for t in turb_stats if t.strehl_estimate is not None]
    avg_strehl = sum(strehl_vals) / len(strehl_vals) if strehl_vals else 0.8
    
    return {
        "success": True,
        "stats": {
            "avg_wavefront_rms_nm": avg_rms,
            "avg_latency_ms": avg_latency,
            "avg_r0_cm": avg_r0 * 100.0,
            "avg_tau0_ms": avg_tau,
            "avg_strehl": avg_strehl,
            "total_frames_processed": len(frames)
        },
        "anomalies": [
            {
                "id": a.id,
                "frame_number": a.frame_number,
                "anomaly_type": a.anomaly_type,
                "severity": a.severity,
                "description": a.description,
                "detected_at": a.detected_at.isoformat()
            }
            for a in anomalies
        ]
    }
