from fastapi import FastAPI, Request, Depends, Form
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pathlib import Path
import secrets
from datetime import datetime, timedelta
from app.database import init_db, SessionLocal, User, SystemConfig, PasswordResetToken
from app.auth import hash_password, verify_password, create_access_token, decode_token
from app.routers import auth, machines, dashboard, backup, monitor, system, logo, alerts
from app.services.monitor import start_scheduler
from app.i18n import get_translations, detect_language, SUPPORTED_LANGS

app = FastAPI(title="Glances Dashboard", version="1.0.0")

BASE = Path(__file__).resolve().parent.parent
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE / "app" / "templates"))


def render_template(template_name: str, request: Request, context: dict = None):
    ctx = context or {}
    ctx["request"] = request
    # Detect language from request
    from app.i18n import detect_language
    lang = detect_language(request)
    ctx["translations"] = get_translations(lang)
    ctx["current_lang"] = lang
    ctx["supported_langs"] = SUPPORTED_LANGS
    return templates.TemplateResponse(request, template_name, ctx)


def get_system_config(request: Request):
    try:
        db = SessionLocal()
        rows = db.query(SystemConfig).all()
        cfg = {r.key: r.value for r in rows}
        db.close()
        return cfg
    except Exception:
        return {}


app.include_router(auth.router)
app.include_router(machines.router)
app.include_router(dashboard.router)
app.include_router(backup.router)
app.include_router(monitor.router)
app.include_router(system.router)
app.include_router(logo.router)
app.include_router(alerts.router)


@app.on_event("startup")
def startup():
    init_db()
    db = SessionLocal()
    if not db.query(User).first():
        admin = User(username="admin", hashed_password=hash_password("admin"), full_name="Administrador", role="admin")
        db.add(admin)
        db.commit()
    db.close()
    start_scheduler()


def get_user_from_cookie(request: Request):
    token = request.cookies.get("token")
    if not token:
        return None
    try:
        payload = decode_token(token)
        db = SessionLocal()
        user = db.query(User).filter(User.username == payload.get("sub")).first()
        db.close()
        return user
    except Exception:
        return None


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("dashboard.html", request, {"user": user, "config": cfg})


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    user = get_user_from_cookie(request)
    if user:
        return RedirectResponse("/", status_code=302)
    cfg = get_system_config(request)
    return render_template("login.html", request, {"error": None, "config": cfg})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    user = db.query(User).filter(User.username == username).first()
    db.close()
    if not user or not verify_password(password, user.hashed_password):
        cfg = get_system_config(request)
        return render_template("login.html", request, {"error": "Credenciais inválidas", "config": cfg})
    token = create_access_token({"sub": user.username, "role": user.role})
    response = RedirectResponse("/", status_code=302)
    response.set_cookie("token", token, httponly=False, max_age=28800)
    response.set_cookie("lang", "pt", httponly=False, max_age=31536000)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie("token")
    return response


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("settings.html", request, {"user": user, "config": cfg})


@app.get("/logs", response_class=HTMLResponse)
def logs_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("logs.html", request, {"user": user, "config": cfg})


@app.get("/admin/setup", response_class=HTMLResponse)
def admin_setup_page(request: Request):
    user = get_user_from_cookie(request)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("admin_setup.html", request, {"user": user, "config": cfg})


@app.get("/admin/alerts", response_class=HTMLResponse)
def admin_alerts_page(request: Request):
    user = get_user_from_cookie(request)
    if not user or user.role != "admin":
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("admin_alerts.html", request, {"user": user, "config": cfg})


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    user = get_user_from_cookie(request)
    if not user:
        return RedirectResponse("/login", status_code=302)
    cfg = get_system_config(request)
    return render_template("profile.html", request, {"user": user, "config": cfg})


@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request):
    cfg = get_system_config(request)
    return render_template("forgot_password.html", request, {"config": cfg, "error": None, "token": None})


@app.post("/forgot-password", response_class=HTMLResponse)
def forgot_password_submit(request: Request, username: str = Form(...)):
    db = SessionLocal()
    cfg = {r.key: r.value for r in db.query(SystemConfig).all()}
    user = db.query(User).filter(User.username == username).first()
    if not user:
        db.close()
        return render_template("forgot_password.html", request, {"config": cfg, "error": None, "success": "Se o usuário existir, um link foi enviado."})
    
    user_email = user.email
    user_name = user.full_name or user.username
    
    if not user_email:
        db.close()
        return render_template("forgot_password.html", request, {"config": cfg, "error": None, "success": "Este usuário não possui e-mail configurado. Entre em contato com o administrador."})
    
    # Mark old tokens as used
    old_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.used == False
    ).all()
    for t in old_tokens:
        t.used = True
    
    # Generate token
    token = secrets.token_urlsafe(32)
    expires = datetime.now() + timedelta(hours=1)
    reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires)
    db.add(reset)
    db.commit()
    
    # Send reset link via email
    smtp_enabled = cfg.get('smtp_enabled', '') == 'true'
    email_sent = False
    if smtp_enabled:
        try:
            from app.routers.alerts import send_email
            reset_url = f"{request.url.scheme}://{request.url.netloc}/reset-password?token={token}"
            html = f"""
            <html>
            <body style="font-family: Arial, sans-serif; padding: 20px;">
                <h2>Redefinição de Senha</h2>
                <p>Olá <strong>{user_name}</strong>,</p>
                <p>Você solicitou a redefinição da sua senha. Clique no link abaixo para criar uma nova senha:</p>
                <p><a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background: #3b82f6; color: white; text-decoration: none; border-radius: 8px;">Redefinir Senha</a></p>
                <p>Este link expira em 1 hora.</p>
                <p style="color: #666; font-size: 12px;">Se você não solicitou, ignore este e-mail.</p>
            </body>
            </html>
            """
            email_sent = send_email(db, user_email, "Redefinição de Senha - Glances Dashboard", html)
            if email_sent:
                print(f"[Auth] Email de redefinição enviado para {user_email}")
            else:
                print(f"[Auth] Falha ao enviar email para {user_email}")
        except Exception as e:
            print(f"[Auth] Erro ao enviar email: {e}")
    
    db.close()
    
    if not email_sent:
        return render_template("forgot_password.html", request, {"config": cfg, "error": None, "success": "O e-mail não pôde ser enviado. Verifique a configuração SMTP ou entre em contato com o administrador."})
    
    return render_template("forgot_password.html", request, {"config": cfg, "error": None, "success": "Um link de redefinição foi enviado para o e-mail do usuário."})


@app.get("/reset-password", response_class=HTMLResponse)
def reset_password_page(request: Request):
    cfg = get_system_config(request)
    return render_template("reset_password.html", request, {"config": cfg, "error": None, "success": None})


@app.get("/api/lang")
def get_language(request: Request):
    """Get current language."""
    from app.i18n import detect_language
    return {"lang": detect_language(request)}


@app.post("/api/lang")
def set_language(request: Request):
    """Set language via cookie."""
    from fastapi import Cookie
    lang = request.cookies.get("lang", "pt")
    response = JSONResponse({"lang": lang})
    response.set_cookie("lang", lang, httponly=False, max_age=31536000)
    return response


@app.post("/reset-password", response_class=HTMLResponse)
def reset_password_submit(request: Request, token: str = Form(...), new_password: str = Form(...), confirm_password: str = Form(...)):
    db = SessionLocal()
    cfg = {r.key: r.value for r in db.query(SystemConfig).all()}
    reset = db.query(PasswordResetToken).filter(PasswordResetToken.token == token, PasswordResetToken.used == False).first()
    if not reset:
        db.close()
        return render_template("reset_password.html", request, {"config": cfg, "error": "Token inválido ou já utilizado", "success": None})
    if datetime.now() > reset.expires_at:
        db.close()
        return render_template("reset_password.html", request, {"config": cfg, "error": "Token expirado. Solicite um novo.", "success": None})
    if new_password != confirm_password:
        db.close()
        return render_template("reset_password.html", request, {"config": cfg, "error": "As senhas não conferem", "success": None})
    if len(new_password) < 4:
        db.close()
        return render_template("reset_password.html", request, {"config": cfg, "error": "A senha deve ter no mínimo 4 caracteres", "success": None})
    user = db.query(User).filter(User.id == reset.user_id).first()
    if not user:
        db.close()
        return render_template("reset_password.html", request, {"config": cfg, "error": "Usuário não encontrado", "success": None})
    user.hashed_password = hash_password(new_password)
    reset.used = True
    db.commit()
    db.close()
    return render_template("reset_password.html", request, {"config": cfg, "error": None, "success": "Senha redefinida com sucesso! Faça login."})
