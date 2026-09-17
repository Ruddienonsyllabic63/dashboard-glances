import json
import shutil
from pathlib import Path
from datetime import datetime, timezone
from config import BACKUP_DIR, DATABASE_URL


def _parse_dates(row: dict) -> dict:
    """Convert ISO date strings back to datetime objects for SQLAlchemy."""
    for k, v in row.items():
        if isinstance(v, str) and len(v) >= 10 and v[4] == '-' and v[7] == '-':
            try:
                row[k] = datetime.fromisoformat(v)
            except (ValueError, TypeError):
                pass
    return row


def create_backup(db_session) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_name = f"gd_{ts}"
    backup_dir = BACKUP_DIR / backup_name
    backup_dir.mkdir(parents=True, exist_ok=True)

    db_path = DATABASE_URL.replace("sqlite:///", "")
    if Path(db_path).exists():
        shutil.copy2(db_path, backup_dir / "dashboard.db")

    tables_data = {}
    from app.database import User, Machine, DashboardLayout, FilterPreset

    for model, name in [(User, "users"), (Machine, "machines"),
                         (DashboardLayout, "layouts"), (FilterPreset, "filters")]:
        rows = db_session.query(model).all()
        tables_data[name] = [
            {c.name: getattr(row, c.name) for c in model.__table__.columns}
            for row in rows
        ]
        for row in tables_data[name]:
            for k, v in row.items():
                if hasattr(v, "isoformat"):
                    row[k] = v.isoformat()

    (backup_dir / "data.json").write_text(json.dumps(tables_data, indent=2, ensure_ascii=False))

    return {"path": str(backup_dir), "timestamp": backup_name}


def list_backups() -> list:
    backups = []
    if BACKUP_DIR.exists():
        for d in sorted(BACKUP_DIR.iterdir(), reverse=True):
            if d.is_dir() and (d / "data.json").exists():
                backups.append({
                    "path": str(d),
                    "name": d.name,
                    "files": [f.name for f in d.iterdir()],
                })
    return backups


def restore_backup(backup_path: str, db_session) -> bool:
    backup_dir = Path(backup_path)
    data_file = backup_dir / "data.json"
    if not data_file.exists():
        return False

    data = json.loads(data_file.read_text())
    from app.database import User, Machine, DashboardLayout, FilterPreset

    model_map = {"users": User, "machines": Machine, "layouts": DashboardLayout, "filters": FilterPreset}

    for table_name, rows in data.items():
        model = model_map.get(table_name)
        if not model:
            continue
        db_session.query(model).delete()
        for row in rows:
            if table_name == "users" and "hashed_password" not in row:
                continue
            row = _parse_dates(dict(row))
            obj = model(**{k: v for k, v in row.items() if hasattr(model, k)})
            db_session.add(obj)
    db_session.commit()
    return True
