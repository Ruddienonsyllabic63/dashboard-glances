import requests
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from pathlib import Path
from app.database import get_db, SystemConfig, MonitorLog, Machine
from app.auth import get_current_user, require_admin

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


def get_config_val(db: Session, key: str, default: str = "") -> str:
    cfg = db.query(SystemConfig).filter(SystemConfig.key == key).first()
    return cfg.value if cfg else default


def render_template(template_name: str, **kwargs) -> str:
    from jinja2 import Environment, FileSystemLoader
    from pathlib import Path
    
    template_dir = Path(__file__).parent.parent / "templates" / "email"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template(template_name)
    return template.render(**kwargs)


def send_email(db: Session, to_email: str, subject: str, html_content: str) -> bool:
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart
    
    host = get_config_val(db, "smtp_host")
    port = int(get_config_val(db, "smtp_port", "587"))
    user_smtp = get_config_val(db, "smtp_user")
    pwd = get_config_val(db, "smtp_password")
    from_addr = get_config_val(db, "smtp_from", user_smtp)
    use_tls = get_config_val(db, "smtp_use_tls") == "true"
    
    if not host or not user_smtp:
        return False
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = from_addr
    msg['To'] = to_email
    msg.attach(MIMEText(html_content, 'html'))
    
    try:
        server = smtplib.SMTP(host, port, timeout=10)
        if use_tls:
            server.starttls()
        server.login(user_smtp, pwd)
        server.sendmail(from_addr, [to_email], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"[Alerts] Erro ao enviar email: {e}")
        return False


def send_telegram(db: Session, message: str) -> bool:
    token = get_config_val(db, "telegram_bot_token")
    enabled = get_config_val(db, "telegram_enabled")
    allowed = get_config_val(db, "telegram_allowed_users", "[]")
    if not token or enabled != "true":
        return False
    import json
    try:
        allowed_ids = json.loads(allowed)
    except Exception:
        allowed_ids = []
    if not allowed_ids:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for uid in allowed_ids:
        try:
            requests.post(url, json={"chat_id": int(uid), "text": message, "parse_mode": "HTML"}, timeout=10)
        except Exception:
            pass
    return True


def send_threshold_alert(db: Session, machine_name: str, proc_count=None, user_alert=None, cpu_percent=0, mem_percent=0, disk_percent=0, threshold=0, top_procs=None, alert_type="process"):
    import json
    from app.database import User
    
    # Preparar mensagem baseada no tipo de alerta
    if alert_type == "cpu":
        subject = f"⚠ Alerta de CPU - {machine_name}"
        msg = f"<b>⚠ Alerta de CPU</b>\n\n"
        msg += f"🖥 <b>Máquina:</b> {machine_name}\n"
        msg += f"📊 <b>CPU:</b> {cpu_percent}%\n"
        msg += f"🎯 <b>Limite:</b> {threshold}%\n"
        msg += f"\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        email_subject = subject
        html_template = "alert_cpu.html"
        
    elif alert_type == "mem":
        subject = f"⚠ Alerta de Memória - {machine_name}"
        msg = f"<b>⚠ Alerta de Memória</b>\n\n"
        msg += f"🖥 <b>Máquina:</b> {machine_name}\n"
        msg += f"💾 <b>Memória:</b> {mem_percent}%\n"
        msg += f"🎯 <b>Limite:</b> {threshold}%\n"
        msg += f"\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        email_subject = subject
        html_template = "alert_mem.html"
        
    elif alert_type == "disk":
        subject = f"⚠ Alerta de Disco - {machine_name}"
        msg = f"<b>⚠ Alerta de Disco</b>\n\n"
        msg += f"🖥 <b>Máquina:</b> {machine_name}\n"
        msg += f"💿 <b>Disco:</b> {disk_percent}%\n"
        msg += f"🎯 <b>Limite:</b> {threshold}%\n"
        msg += f"\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        email_subject = subject
        html_template = "alert_disk.html"
        
    elif alert_type == "process":
        subject = f"⚠ Alerta de Processos - {machine_name}"
        msg = f"<b>⚠ Alerta de Processos</b>\n\n"
        msg += f"🖥 <b>Máquina:</b> {machine_name}\n"
        msg += f"📊 <b>Processos total:</b> {proc_count}\n"
        msg += f"🎯 <b>Limite:</b> {threshold}\n"
        if top_procs and len(top_procs) > 0:
            p = top_procs[0]
            msg += f"🔝 <b>Top Processo:</b> {p.get('user', '?')} → {p.get('name', '?')} ({p.get('cpu', 0)}%)\n"
        msg += f"📈 <b>CPU:</b> {cpu_percent}%\n"
        msg += f"💾 <b>Mem:</b> {mem_percent}%\n"
        msg += f"💿 <b>Disco:</b> {disk_percent}%\n"
        msg += f"\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        email_subject = subject
        html_template = "alert_template.html"
        
    elif alert_type == "per_user":
        users_list = json.loads(user_alert) if user_alert else []
        subject = f"⚠ Alerta de Processos por Usuário - {machine_name}"
        msg = f"<b>⚠ Alerta de Processos por Usuário</b>\n\n"
        msg += f"🖥 <b>Máquina:</b> {machine_name}\n"
        msg += f"👤 <b>Usuários:</b> {', '.join(users_list)}\n"
        msg += f"📊 <b>Processos total:</b> {proc_count}\n"
        msg += f"🎯 <b>Limite por usuário:</b> {threshold}\n"
        if top_procs and len(top_procs) > 0:
            p = top_procs[0]
            msg += f"🔝 <b>Top Processo:</b> {p.get('user', '?')} → {p.get('name', '?')} ({p.get('cpu', 0)}%)\n"
        msg += f"📈 <b>CPU:</b> {cpu_percent}%\n"
        msg += f"💾 <b>Mem:</b> {mem_percent}%\n"
        msg += f"💿 <b>Disco:</b> {disk_percent}%\n"
        msg += f"\n📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        email_subject = subject
        html_template = "alert_template.html"
        
    else:
        return
    
    # Enviar Telegram
    send_telegram(db, msg)
    
    # Preparar dados para email
    users_list = json.loads(user_alert) if user_alert else []
    
    # Enviar email para usuários do dashboard que têm alertas habilitados
    dashboard_users = db.query(User).filter(
        User.receive_alerts_email == True
    ).all()
    
    html = render_template(html_template,
        machine_name=machine_name,
        users=users_list,
        process_count=proc_count,
        threshold=threshold,
        cpu_percent=cpu_percent,
        mem_percent=mem_percent,
        disk_percent=disk_percent,
        timestamp=datetime.now().strftime('%d/%m/%Y %H:%M'),
        top_process=top_procs[0] if top_procs and len(top_procs) > 0 else None,
        top_processes=top_procs or [],
        alert_type=alert_type
    )
    
    sent_count = 0
    for u in dashboard_users:
        if u.email:
            if send_email(db, u.email, email_subject, html):
                sent_count += 1
                print(f"[Alerts] Email enviado para {u.email}")
    
    print(f"[Alerts] Emails enviados: {sent_count}/{len(dashboard_users)}")


@router.post("/test-telegram")
def test_telegram(user=Depends(require_admin), db:Session=Depends(get_db)):
    token = get_config_val(db, "telegram_bot_token")
    if not token:
        return {"success": False, "error": "Token do bot não configurado"}
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        r = requests.get(url, timeout=10).json()
        if r.get("ok"):
            return {"success": True, "bot_name": r["result"].get("username", "?"), "bot_id": r["result"].get("id")}
        return {"success": False, "error": r.get("description", "Erro desconhecido")}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/test-email")
def test_email(user=Depends(require_admin), db:Session=Depends(get_db)):
    smtp_enabled = get_config_val(db, "smtp_enabled")
    if smtp_enabled != "true":
        return {"success": False, "error": "Envio de e-mail não está ativado"}
    
    user_smtp = get_config_val(db, "smtp_user")
    if not user_smtp:
        return {"success": False, "error": "Usuário SMTP não configurado"}
    
    from app.database import User
    current_user = db.query(User).filter(User.username == user.username).first()
    
    if not current_user or not current_user.email:
        return {"success": False, "error": "Você não tem e-mail cadastrado no perfil. Cadastre seu e-mail em Configurações → Meu Perfil"}
    
    try:
        html = render_template('test_template.html',
            from_email=get_config_val(db, "smtp_from", user_smtp),
            to_email=current_user.email,
            timestamp=datetime.now().strftime('%d/%m/%Y %H:%M')
        )
        
        if send_email(db, current_user.email, "Teste de E-mail - Glances Dashboard", html):
            return {"success": True}
        return {"success": False, "error": "Falha ao enviar e-mail"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@router.get("/stats")
def alert_stats(user=Depends(get_current_user), db:Session=Depends(get_db)):
    from sqlalchemy import func
    total_logs = db.query(MonitorLog).count()
    alerts = db.query(MonitorLog).filter(MonitorLog.threshold_alert == True).count()
    offline = db.query(MonitorLog).filter(MonitorLog.status == "offline").count()
    machines = db.query(Machine).filter(Machine.enabled == True).count()
    return {"total_logs": total_logs, "alerts": alerts, "offline": offline, "machines": machines}
