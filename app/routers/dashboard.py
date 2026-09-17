from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db, DashboardLayout, Machine
from app.auth import get_current_user, User
from app.services.glances import GlancesClient

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


class LayoutSave(BaseModel):
    name: str
    config: str


@router.get("/all")
def get_all_data(user=Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(Machine).filter(Machine.enabled == True).all()
    result = []
    for m in machines:
        client = GlancesClient(m.host, m.port)
        data = client.get_all()
        data["machine"] = {"id": m.id, "name": m.name, "host": m.host}
        alive = client.is_alive()
        data["status"] = "online" if alive else "offline"
        result.append(data)
    return {"machines": result}


@router.get("/overview")
def get_overview(user=Depends(get_current_user), db: Session = Depends(get_db)):
    machines = db.query(Machine).filter(Machine.enabled == True).all()
    overview = {"total": len(machines), "online": 0, "offline": 0, "machines": []}
    for m in machines:
        client = GlancesClient(m.host, m.port)
        alive = client.is_alive()
        info = {"id": m.id, "name": m.name, "host": m.host, "status": "online" if alive else "offline"}
        if alive:
            overview["online"] += 1
            cpu = client.get_cpu()
            mem = client.get_memory()
            info["cpu_percent"] = cpu.get("total", 0) if cpu else 0
            info["mem_percent"] = mem.get("percent", 0) if mem else 0
        else:
            overview["offline"] += 1
            info["cpu_percent"] = 0
            info["mem_percent"] = 0
        overview["machines"].append(info)
    return overview


@router.get("/layouts")
def list_layouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    layouts = db.query(DashboardLayout).filter(
        (DashboardLayout.user_id == user.id) | (DashboardLayout.is_default == True)
    ).all()
    return [{"id": l.id, "name": l.name, "config": l.config, "is_default": l.is_default} for l in layouts]


@router.post("/layouts")
def save_layout(req: LayoutSave, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = db.query(DashboardLayout).filter(
        DashboardLayout.user_id == user.id, DashboardLayout.name == req.name
    ).first()
    if existing:
        existing.config = req.config
        db.commit()
        return {"id": existing.id, "message": "Layout atualizado"}
    custom_count = db.query(DashboardLayout).filter(
        DashboardLayout.user_id == user.id, DashboardLayout.is_default == False
    ).count()
    if custom_count >= 3:
        raise HTTPException(status_code=400, detail="Máximo de 3 layouts personalizados. Exclua um antes de criar outro.")
    layout = DashboardLayout(user_id=user.id, name=req.name, config=req.config)
    db.add(layout)
    db.commit()
    db.refresh(layout)
    return {"id": layout.id, "message": "Layout salvo"}


@router.put("/layouts/{layout_id}")
def update_layout(layout_id: int, req: LayoutSave, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    layout = db.query(DashboardLayout).filter(DashboardLayout.id == layout_id).first()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout não encontrado")
    if layout.is_default:
        raise HTTPException(status_code=400, detail="Não é possível alterar o layout padrão")
    if layout.user_id != user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    if req.name:
        layout.name = req.name
    layout.config = req.config
    db.commit()
    return {"message": "Layout atualizado"}


@router.delete("/layouts/{layout_id}")
def delete_layout(layout_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    layout = db.query(DashboardLayout).filter(DashboardLayout.id == layout_id).first()
    if not layout:
        raise HTTPException(status_code=404, detail="Layout não encontrado")
    if layout.is_default:
        raise HTTPException(status_code=400, detail="Não é possível excluir o layout padrão")
    if layout.user_id != user.id:
        raise HTTPException(status_code=403, detail="Sem permissão")
    db.delete(layout)
    db.commit()
    return {"message": "Layout removido"}
