import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from app.database import get_db, User, PasswordResetToken, SystemConfig
from app.auth import hash_password, verify_password, create_access_token, get_current_user, require_admin

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"
    full_name: str = ""
    email: str = ""
    telegram_username: str = ""


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str
    confirm_password: str


class ChangeRoleRequest(BaseModel):
    user_id: int
    role: str


@router.post("/login")
def login(req: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Credenciais inválidas")
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer", "username": user.username, "role": user.role}


@router.post("/register")
def register(req: RegisterRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.query(User).filter(User.username == req.username).first():
        raise HTTPException(status_code=400, detail="Usuário já existe")
    if req.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Role inválida")
    new_user = User(
        username=req.username,
        hashed_password=hash_password(req.password),
        role=req.role,
        full_name=req.full_name,
        email=req.email,
        telegram_username=req.telegram_username,
    )
    db.add(new_user)
    db.commit()
    return {"message": "Usuário criado com sucesso"}


@router.get("/me")
def get_me(user: User = Depends(get_current_user)):
    return {"username": user.username, "id": user.id, "role": user.role}


@router.get("/users")
def list_users(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).all()
    return [{"id": u.id, "username": u.username, "role": u.role, "created_at": u.created_at.isoformat() if u.created_at else None} for u in users]


@router.put("/users/role")
def change_role(req: ChangeRoleRequest, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if req.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="Role inválida")
    target = db.query(User).filter(User.id == req.user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    target.role = req.role
    db.commit()
    return {"message": "Role atualizada"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Usuário não encontrado")
    if target.username == "admin":
        raise HTTPException(status_code=400, detail="Não é possível remover o admin")
    db.delete(target)
    db.commit()
    return {"message": "Usuário removido"}


@router.post("/change-password")
def change_password(req: ChangePasswordRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(req.old_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Senha atual incorreta")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="As senhas novas não conferem")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="A nova senha deve ter no mínimo 4 caracteres")
    user.hashed_password = hash_password(req.new_password)
    db.commit()
    return {"message": "Senha alterada com sucesso"}


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == req.username).first()
    if not user:
        return {"message": "Se o usuário existir, um token foi gerado. Verifique com o administrador."}
    old_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used == False
    ).all()
    for t in old_tokens:
        t.used = True
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=1)
    reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
    db.add(reset)
    db.commit()

    # Send reset link via email
    smtp_enabled = db.query(SystemConfig).filter(SystemConfig.key == "smtp_enabled").first()
    if smtp_enabled and smtp_enabled.value == "true":
        try:
            from app.routers.alerts import send_email
            reset_url = f"{req.base_url}reset-password?token={token}"
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Redefinição de Senha</h2>
                <p>Olá <strong>{user.full_name or user.username}</strong>,</p>
                <p>Você solicitou a redefinição da sua senha. Clique no link abaixo para criar uma nova senha:</p>
                <p><a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px;">Redefinir Senha</a></p>
                <p>Este link expira em 1 hora.</p>
                <p style="color: #666; font-size: 12px;">Se você não solicitou, ignore esta mensagem.</p>
            </body>
            </html>
            """
            send_email(db, user.email, "Redefinição de Senha - Glances Dashboard", html)
            return {"message": "Link de redefinição enviado para o e-mail: " + user.email}
        except Exception:
            pass

    if not user.email:
        return {"message": "Usuário não possui e-mail configurado. Entre em contato com o administrador."}

    return {"message": "Token gerado. Verifique o e-mail do usuário."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    reset = db.query(PasswordResetToken).filter(
        PasswordResetToken.token == req.token, PasswordResetToken.used == False
    ).first()
    if not reset:
        raise HTTPException(status_code=400, detail="Token inválido ou já utilizado")
    if datetime.now() > reset.expires_at:
        raise HTTPException(status_code=400, detail="Token expirado. Solicite um novo.")
    if req.new_password != req.confirm_password:
        raise HTTPException(status_code=400, detail="As senhas não conferem")
    if len(req.new_password) < 4:
        raise HTTPException(status_code=400, detail="A nova senha deve ter no mínimo 4 caracteres")
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        raise HTTPException(status_code=400, detail="Usuário não encontrado")
    user.hashed_password = hash_password(req.new_password)
    reset.used = True
    db.commit()
    return {"message": "Senha redefinida com sucesso"}
