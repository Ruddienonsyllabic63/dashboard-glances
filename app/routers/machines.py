from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
from app.database import get_db, Machine, User
from app.auth import get_current_user, require_admin
from app.services.glances import GlancesClient

router = APIRouter(prefix="/api/machines", tags=["machines"])


class MachineCreate(BaseModel):
    name: str
    host: str
    port: int = 61208
    is_local: bool = False
    tags: str = ""


class MachineUpdate(BaseModel):
    name: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    enabled: Optional[bool] = None
    tags: Optional[str] = None


@router.get("/")
def list_machines(user=Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(Machine).all()
    result = []
    for m in machines:
        client = GlancesClient(m.host, m.port)
        alive = client.is_alive()
        if alive:
            m.last_seen = datetime.now(timezone.utc)
            db.commit()
        result.append({
            "id": m.id, "name": m.name, "host": m.host, "port": m.port,
            "is_local": m.is_local, "enabled": m.enabled, "tags": m.tags,
            "status": "online" if alive else "offline",
            "last_seen": m.last_seen.isoformat() if m.last_seen else None,
            "created_at": m.created_at.isoformat() if m.created_at else None,
        })
    return result


@router.post("/")
def create_machine(req: MachineCreate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    machine = Machine(name=req.name, host=req.host, port=req.port, is_local=req.is_local, tags=req.tags)
    db.add(machine)
    db.commit()
    db.refresh(machine)
    client = GlancesClient(machine.host, machine.port)
    status = "online" if client.is_alive() else "offline"
    return {"id": machine.id, "name": machine.name, "status": status, "message": "Máquina adicionada"}


@router.put("/{machine_id}")
def update_machine(machine_id: int, req: MachineUpdate, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    for field, value in req.dict(exclude_unset=True).items():
        setattr(machine, field, value)
    db.commit()
    return {"message": "Máquina atualizada"}


@router.delete("/{machine_id}")
def delete_machine(machine_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    db.delete(machine)
    db.commit()
    return {"message": "Máquina removida"}


@router.get("/{machine_id}/data")
def get_machine_data(machine_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    client = GlancesClient(machine.host, machine.port)
    data = client.get_all()
    data["machine"] = {"id": machine.id, "name": machine.name, "host": machine.host}
    return data


@router.get("/{machine_id}/cpu")
def get_machine_cpu(machine_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    client = GlancesClient(machine.host, machine.port)
    return client.get_cpu() or {"error": "Não foi possível obter dados"}


@router.get("/{machine_id}/memory")
def get_machine_memory(machine_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    client = GlancesClient(machine.host, machine.port)
    return client.get_memory() or {"error": "Não foi possível obter dados"}


@router.get("/{machine_id}/disk")
def get_machine_disk(machine_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    client = GlancesClient(machine.host, machine.port)
    return client.get_disk() or {"error": "Não foi possível obter dados"}


@router.get("/{machine_id}/processes")
def get_machine_processes(machine_id: int, user=Depends(get_current_user), db: Session = Depends(get_db)):
    machine = db.query(Machine).filter(Machine.id == machine_id).first()
    if not machine:
        raise HTTPException(status_code=404, detail="Máquina não encontrada")
    client = GlancesClient(machine.host, machine.port)
    return client.get_processlist() or []


@router.post("/test")
def test_connection(req: MachineCreate, user: User = Depends(require_admin)):
    import requests as req_lib
    client = GlancesClient(req.host, req.port)
    try:
        alive = client.is_alive()
        if alive:
            data = client.get_system()
            return {"alive": True, "system": data}
        else:
            return {"alive": False, "error": "Glances não respondeu"}
    except req_lib.exceptions.ConnectionError:
        return {"alive": False, "error": f"Conexão recusada em {req.host}:{req.port}"}
    except req_lib.exceptions.Timeout:
        return {"alive": False, "error": "Timeout - máquina não respondeu em 3s"}
    except Exception as e:
        return {"alive": False, "error": str(e)}
