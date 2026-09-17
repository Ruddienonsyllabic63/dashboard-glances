import shutil
import tempfile
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.database import get_db, User
from app.auth import get_current_user, require_admin
from app.services.backup import create_backup, list_backups, restore_backup

router = APIRouter(prefix="/api/backup", tags=["backup"])


@router.post("/create")
def backup_create(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    result = create_backup(db)
    return {"message": "Backup criado", **result}


@router.get("/list")
def backup_list(user=Depends(get_current_user)):
    return {"backups": list_backups()}


@router.get("/download")
def backup_download(name: str, user=Depends(require_admin)):
    from config import BACKUP_DIR
    backup_dir = BACKUP_DIR / name
    if not backup_dir.exists() or not (backup_dir / "data.json").exists():
        raise HTTPException(status_code=404, detail="Backup não encontrado")
    zip_path = shutil.make_archive(
        str(Path(tempfile.gettempdir()) / f"{name}"),
        "zip", str(backup_dir)
    )
    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{name}.zip",
        headers={"Content-Disposition": f'attachment; filename="{name}.zip"'}
    )


@router.post("/restore")
def backup_restore(backup_path: str, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    success = restore_backup(backup_path, db)
    if not success:
        raise HTTPException(status_code=400, detail="Falha ao restaurar backup")
    return {"message": "Backup restaurado com sucesso"}
