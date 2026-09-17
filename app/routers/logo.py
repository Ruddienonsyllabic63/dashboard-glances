from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pathlib import Path
from app.database import get_db, SystemConfig
from app.auth import require_admin

router = APIRouter(prefix="/api/logo", tags=["logo"])

UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_EXT = {".svg", ".png", ".jpg", ".jpeg", ".ico", ".webp"}
MAX_SIZE = 2 * 1024 * 1024


@router.post("/upload")
async def upload_logo(file: UploadFile = File(...), user=Depends(require_admin), db=Depends(get_db)):
    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail=f"Formato não permitido: {ext}. Use: {', '.join(ALLOWED_EXT)}")
    content = await file.read()
    if len(content) > MAX_SIZE:
        raise HTTPException(status_code=400, detail="Arquivo muito grande (máx 2MB)")
    filename = f"logo{ext}"
    filepath = UPLOAD_DIR / filename
    filepath.write_bytes(content)
    cfg = db.query(SystemConfig).filter(SystemConfig.key == "logo_file").first()
    if cfg:
        cfg.value = filename
    else:
        db.add(SystemConfig(key="logo_file", value=filename))
    db.commit()
    return {"message": "Logo atualizada", "filename": filename, "url": f"/static/uploads/{filename}"}
