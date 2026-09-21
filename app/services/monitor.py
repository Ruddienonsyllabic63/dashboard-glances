import threading
import time
import json
from datetime import datetime, timedelta
from sqlalchemy import text
from app.database import SessionLocal, Machine, MonitorLog, MonitorConfig
from app.services.glances import GlancesClient
from app.routers.alerts import send_threshold_alert


def collect_once():
    db = SessionLocal()
    try:
        config = db.query(MonitorConfig).first()
        if not config:
            config = MonitorConfig(interval_minutes=5, enabled=True, retention_months=3)
            db.add(config)
            db.commit()
        if not config.enabled:
            return

        selected = json.loads(config.selected_machines or "[]")
        machines = db.query(Machine).filter(Machine.enabled == True).all()

        for m in machines:
            if selected and m.id not in selected:
                continue

            client = GlancesClient(m.host, m.port)
            alive = client.is_alive()
            log = MonitorLog(
                machine_id=m.id,
                machine_name=m.name,
                status="online" if alive else "offline",
            )
            if alive:
                if config.collect_cpu:
                    cpu = client.get_cpu()
                    log.cpu_percent = cpu.get("total", 0) if cpu else 0

                if config.collect_mem:
                    mem = client.get_memory()
                    log.mem_percent = mem.get("percent", 0) if mem else 0
                    log.mem_used = mem.get("used", 0) if mem else 0
                    log.mem_total = mem.get("total", 0) if mem else 0

                if config.collect_load:
                    load = client.get_load()
                    log.load_1 = load.get("min1", 0) if load else 0
                    log.load_5 = load.get("min5", 0) if load else 0
                    log.load_15 = load.get("min15", 0) if load else 0

                if config.collect_disk:
                    disk = client.get_disk()
                    if disk and len(disk) > 0:
                        root = next((d for d in disk if d.get("mnt_point") == "/"), disk[0])
                        log.disk_root_percent = root.get("percent", 0)

                if config.collect_procs:
                    procs = client.get_processlist()
                    if procs:
                        log.process_count = len(procs)
                        cpu_count = client.get_cpu()
                        cores = cpu_count.get("cpucore", 1) if cpu_count else 1
                        top = sorted(procs, key=lambda p: p.get("cpu_percent", 0), reverse=True)[:5]
                        log.top_procs = json.dumps([
                            {"name": p.get("name", "?"), "cpu": round(p.get("cpu_percent", 0) / cores, 1), "mem": p.get("memory_percent", 0), "user": p.get("username", "-")}
                            for p in top
                        ])

                # Check CPU threshold
                if config.alert_cpu and config.cpu_threshold > 0 and log.cpu_percent >= config.cpu_threshold:
                    log.threshold_alert = True
                    try:
                        from app.routers.alerts import send_threshold_alert
                        send_threshold_alert(
                            db,
                            log.machine_name,
                            machine_id=m.id,
                            cpu_percent=log.cpu_percent,
                            threshold=config.cpu_threshold,
                            alert_type="cpu"
                        )
                    except Exception as e:
                        print(f"[Monitor] Erro ao enviar alerta CPU: {e}")

                # Check Memory threshold
                if config.alert_mem and config.mem_threshold > 0 and log.mem_percent >= config.mem_threshold:
                    log.threshold_alert = True
                    try:
                        from app.routers.alerts import send_threshold_alert
                        send_threshold_alert(
                            db,
                            log.machine_name,
                            machine_id=m.id,
                            mem_percent=log.mem_percent,
                            threshold=config.mem_threshold,
                            alert_type="mem"
                        )
                    except Exception as e:
                        print(f"[Monitor] Erro ao enviar alerta Memória: {e}")

                # Check Disk threshold
                if config.alert_disk and config.disk_threshold > 0 and log.disk_root_percent >= config.disk_threshold:
                    log.threshold_alert = True
                    try:
                        from app.routers.alerts import send_threshold_alert
                        send_threshold_alert(
                            db,
                            log.machine_name,
                            machine_id=m.id,
                            disk_percent=log.disk_root_percent,
                            threshold=config.disk_threshold,
                            alert_type="disk"
                        )
                    except Exception as e:
                        print(f"[Monitor] Erro ao enviar alerta Disco: {e}")

                # Check Process count threshold
                if config.alert_process and config.process_threshold > 0 and log.process_count >= config.process_threshold:
                    log.threshold_alert = True
                    try:
                        from app.routers.alerts import send_threshold_alert
                        send_threshold_alert(
                            db,
                            log.machine_name,
                            machine_id=m.id,
                            proc_count=log.process_count,
                            threshold=config.process_threshold,
                            alert_type="process"
                        )
                    except Exception as e:
                        print(f"[Monitor] Erro ao enviar alerta Processos: {e}")

                # Check per-user threshold
                if config.alert_per_user and config.per_user_threshold > 0:
                    per_users = json.loads(config.per_user_names or "[]")
                    if per_users and procs:
                        user_counts = {}
                        for p in procs:
                            u = p.get("username", "-")
                            if u in per_users:
                                user_counts[u] = user_counts.get(u, 0) + 1
                        alerted = [u for u, c in user_counts.items() if c >= config.per_user_threshold]
                        if alerted:
                            log.threshold_alert = True
                            log.per_user_alert = json.dumps(alerted)
                            try:
                                from app.routers.alerts import send_threshold_alert
                                send_threshold_alert(
                                    db,
                                    log.machine_name,
                                    machine_id=m.id,
                                    proc_count=log.process_count,
                                    threshold=config.per_user_threshold,
                                    user_alert=json.dumps(alerted),
                                    cpu_percent=log.cpu_percent,
                                    mem_percent=log.mem_percent,
                                    disk_percent=log.disk_root_percent,
                                    top_procs=json.loads(log.top_procs) if log.top_procs else []
                                )
                            except Exception as e:
                                print(f"[Monitor] Erro ao enviar alerta per-user: {e}")

            db.add(log)
        db.commit()
    except Exception as e:
        print(f"[Monitor] Erro na coleta: {e}")
    finally:
        db.close()


def rotate_logs():
    db = SessionLocal()
    try:
        config = db.query(MonitorConfig).first()
        months = config.retention_months if config else 3
        cutoff = datetime.now() - timedelta(days=months * 30)
        deleted = db.query(MonitorLog).filter(MonitorLog.timestamp < cutoff).delete()
        if deleted:
            print(f"[Monitor] Rotação: {deleted} logs antigos removidos (> {months} meses)")
            db.execute(text("VACUUM"))
        db.commit()
    except Exception as e:
        print(f"[Monitor] Erro na rotação: {e}")
    finally:
        db.close()


_scheduler_thread = None
_stop_event = threading.Event()
_scheduler_id = None  # Identificador único do scheduler


def _scheduler_loop():
    global _scheduler_id
    import time
    my_id = id(threading.current_thread())
    _scheduler_id = my_id
    print(f"[Monitor] Scheduler iniciado (thread {my_id})")
    
    while not _stop_event.is_set():
        try:
            db = SessionLocal()
            try:
                config = db.query(MonitorConfig).first()
                interval = config.interval_minutes if config else 5
                enabled = config.enabled if config else True
            finally:
                db.close()

            if enabled:
                collect_once()
                rotate_logs()
                print(f"[Monitor] Coleta realizada - próxima em {interval} minutos")
            else:
                print("[Monitor] Monitor desabilitado, aguardando...")

        except Exception as e:
            print(f"[Monitor] Erro na coleta: {e}")
        
        # Aguardar o intervalo antes da próxima coleta
        _stop_event.wait(interval * 60)
    
    print(f"[Monitor] Scheduler parado (thread {my_id})")


def start_scheduler():
    global _scheduler_thread, _stop_event, _scheduler_id
    import time
    
    # Verificar se já existe um scheduler rodando no MESMO processo
    if _scheduler_thread and _scheduler_thread.is_alive():
        current_id = id(threading.current_thread())
        if _scheduler_id == current_id:
            print("[Monitor] Scheduler já está rodando neste processo")
            return
        # Se for thread diferente, pode ser reload - parar o antigo
        print(f"[Monitor] Detectado reload - parando scheduler antigo ({_scheduler_id})")
        try:
            _stop_event.set()
            time.sleep(1)  # Aguardar parada
        except:
            pass
    
    # Criar novo evento e thread
    _stop_event = threading.Event()
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    print("[Monitor] Agendador iniciado")


def stop_scheduler():
    global _scheduler_thread, _stop_event
    if _stop_event:
        _stop_event.set()
    if _scheduler_thread:
        _scheduler_thread.join(timeout=2)
    print("[Monitor] Agendador parado")
