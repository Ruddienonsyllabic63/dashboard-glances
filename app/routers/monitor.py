from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta
from typing import Optional, List
import json
from app.database import get_db, MonitorLog, MonitorConfig, Machine
from app.auth import get_current_user, require_admin
from app.services.monitor import start_scheduler, stop_scheduler, collect_once

router = APIRouter(prefix="/api/monitor", tags=["monitor"])


class ConfigUpdate(BaseModel):
    interval_minutes: Optional[int] = None
    enabled: Optional[bool] = None
    retention_months: Optional[int] = None
    collect_cpu: Optional[bool] = None
    collect_mem: Optional[bool] = None
    collect_disk: Optional[bool] = None
    collect_load: Optional[bool] = None
    collect_procs: Optional[bool] = None
    selected_machines: Optional[List[int]] = None
    process_threshold: Optional[int] = None
    per_user_threshold: Optional[int] = None
    per_user_names: Optional[List[str]] = None
    cpu_threshold: Optional[int] = None
    mem_threshold: Optional[int] = None
    disk_threshold: Optional[int] = None
    alert_cpu: Optional[bool] = None
    alert_mem: Optional[bool] = None
    alert_disk: Optional[bool] = None
    alert_process: Optional[bool] = None
    alert_per_user: Optional[bool] = None


@router.get("/config")
def get_config(user=Depends(get_current_user), db: Session = Depends(get_db)):
    config = db.query(MonitorConfig).first()
    if not config:
        config = MonitorConfig(interval_minutes=5, enabled=True, retention_months=3)
        db.add(config)
        db.commit()
    return {
        "interval_minutes": config.interval_minutes,
        "enabled": config.enabled,
        "retention_months": config.retention_months,
        "collect_cpu": config.collect_cpu,
        "collect_mem": config.collect_mem,
        "collect_disk": config.collect_disk,
        "collect_load": config.collect_load,
        "collect_procs": config.collect_procs,
        "selected_machines": config.selected_machines,
        "process_threshold": config.process_threshold,
        "per_user_threshold": config.per_user_threshold,
        "per_user_names": json.loads(config.per_user_names or "[]"),
        "cpu_threshold": config.cpu_threshold,
        "mem_threshold": config.mem_threshold,
        "disk_threshold": config.disk_threshold,
        "alert_cpu": config.alert_cpu,
        "alert_mem": config.alert_mem,
        "alert_disk": config.alert_disk,
        "alert_process": config.alert_process,
        "alert_per_user": config.alert_per_user,
    }


@router.put("/config")
def update_config(req: ConfigUpdate, user=Depends(require_admin), db: Session = Depends(get_db)):
    config = db.query(MonitorConfig).first()
    if not config:
        config = MonitorConfig()
        db.add(config)
    if req.interval_minutes is not None:
        if req.interval_minutes < 1:
            raise HTTPException(status_code=400, detail="Intervalo mínimo: 1 minuto")
        config.interval_minutes = req.interval_minutes
    if req.enabled is not None:
        config.enabled = req.enabled
    if req.retention_months is not None:
        if req.retention_months < 1:
            raise HTTPException(status_code=400, detail="Retenção mínima: 1 mês")
        config.retention_months = req.retention_months
    if req.collect_cpu is not None:
        config.collect_cpu = req.collect_cpu
    if req.collect_mem is not None:
        config.collect_mem = req.collect_mem
    if req.collect_disk is not None:
        config.collect_disk = req.collect_disk
    if req.collect_load is not None:
        config.collect_load = req.collect_load
    if req.collect_procs is not None:
        config.collect_procs = req.collect_procs
    if req.selected_machines is not None:
        config.selected_machines = str(req.selected_machines)
    if req.process_threshold is not None:
        config.process_threshold = req.process_threshold
    if req.per_user_threshold is not None:
        config.per_user_threshold = req.per_user_threshold
    if req.per_user_names is not None:
        config.per_user_names = json.dumps(req.per_user_names)
    if req.cpu_threshold is not None:
        config.cpu_threshold = req.cpu_threshold
    if req.mem_threshold is not None:
        config.mem_threshold = req.mem_threshold
    if req.disk_threshold is not None:
        config.disk_threshold = req.disk_threshold
    if req.alert_cpu is not None:
        config.alert_cpu = req.alert_cpu
    if req.alert_mem is not None:
        config.alert_mem = req.alert_mem
    if req.alert_disk is not None:
        config.alert_disk = req.alert_disk
    if req.alert_process is not None:
        config.alert_process = req.alert_process
    if req.alert_per_user is not None:
        config.alert_per_user = req.alert_per_user
    db.commit()
    if req.enabled is not None:
        if req.enabled:
            start_scheduler()
        else:
            stop_scheduler()
    return {"message": "Configuração atualizada"}


@router.post("/collect")
def force_collect(user=Depends(require_admin)):
    collect_once()
    return {"message": "Coleta executada"}


@router.get("/logs")
def list_logs(
    machine_id: Optional[int] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    alerts_only: Optional[bool] = None,
    search: Optional[str] = None,
    page: Optional[int] = 1,
    per_page: Optional[int] = 150,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MonitorLog)
    if machine_id:
        query = query.filter(MonitorLog.machine_id == machine_id)
    if date_from:
        try:
            dt = datetime.fromisoformat(date_from)
            query = query.filter(MonitorLog.timestamp >= dt)
        except ValueError:
            pass
    if date_to:
        try:
            dt = datetime.fromisoformat(date_to) + timedelta(days=1)
            query = query.filter(MonitorLog.timestamp < dt)
        except ValueError:
            pass
    if alerts_only:
        query = query.filter(MonitorLog.threshold_alert == True)
    if search:
        like = f"%{search}%"
        query = query.filter(
            (MonitorLog.machine_name.ilike(like)) |
            (MonitorLog.top_procs.ilike(like)) |
            (MonitorLog.status.ilike(like))
        )
    total = query.count()
    offset = (page - 1) * per_page
    logs = query.order_by(MonitorLog.timestamp.desc()).offset(offset).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    return {
        "logs": [{
            "id": l.id, "machine_id": l.machine_id, "machine_name": l.machine_name,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
            "cpu_percent": l.cpu_percent, "mem_percent": l.mem_percent,
            "mem_used": l.mem_used, "mem_total": l.mem_total,
            "disk_root_percent": l.disk_root_percent,
            "load_1": l.load_1, "load_5": l.load_5, "load_15": l.load_15,
            "top_procs": l.top_procs, "status": l.status,
            "process_count": l.process_count, "threshold_alert": l.threshold_alert,
            "per_user_alert": l.per_user_alert,
        } for l in logs],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
    }


@router.get("/machines")
def list_monitor_machines(user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Machine).filter(Machine.enabled == True).all()


@router.delete("/logs")
def clear_logs(user=Depends(require_admin), db: Session = Depends(get_db)):
    count = db.query(MonitorLog).delete()
    db.commit()
    return {"message": f"{count} logs removidos"}


@router.get("/stats")
def get_stats(machine_id: Optional[int] = None, user=Depends(get_current_user), db: Session = Depends(get_db)):
    from sqlalchemy import func
    query = db.query(MonitorLog)
    if machine_id:
        query = query.filter(MonitorLog.machine_id == machine_id)
    total = query.count()
    alerts = db.query(MonitorLog).filter(MonitorLog.threshold_alert == True)
    if machine_id:
        alerts = alerts.filter(MonitorLog.machine_id == machine_id)
    alert_count = alerts.count()
    if total == 0:
        return {"total": 0, "avg_cpu": 0, "avg_mem": 0, "max_cpu": 0, "max_mem": 0, "alerts": 0}
    stats = query.with_entities(
        func.avg(MonitorLog.cpu_percent),
        func.avg(MonitorLog.mem_percent),
        func.max(MonitorLog.cpu_percent),
        func.max(MonitorLog.mem_percent),
    ).first()
    return {
        "total": total,
        "avg_cpu": round(stats[0] or 0, 1),
        "avg_mem": round(stats[1] or 0, 1),
        "max_cpu": round(stats[2] or 0, 1),
        "max_mem": round(stats[3] or 0, 1),
        "alerts": alert_count,
    }


@router.get("/detected-users")
def get_detected_users(db: Session = Depends(get_db)):
    logs = db.query(MonitorLog).order_by(MonitorLog.timestamp.desc()).limit(100).all()
    users = {}
    for log in logs:
        try:
            procs = json.loads(log.top_procs or "[]")
            for p in procs:
                u = p.get("user", "-")
                if u and u != "-" and u not in users:
                    users[u] = 1
        except Exception:
            pass
    return sorted(users.keys())
