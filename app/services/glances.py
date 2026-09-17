import requests
import json
from datetime import datetime, timezone
from typing import Optional


class GlancesClient:
    def __init__(self, host: str, port: int = 61208, timeout: int = 5):
        self.base_url = f"http://{host}:{port}"
        self.timeout = timeout
        self.session = requests.Session()

    def _get(self, endpoint: str) -> Optional[dict]:
        try:
            resp = self.session.get(
                f"{self.base_url}/api/4/{endpoint}",
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception:
            return None

    def get_system(self) -> Optional[dict]:
        return self._get("system")

    def get_cpu(self) -> Optional[dict]:
        return self._get("cpu")

    def get_memory(self) -> Optional[dict]:
        return self._get("mem")

    def get_disk(self) -> Optional[dict]:
        return self._get("fs")

    def get_network(self) -> Optional[dict]:
        return self._get("network")

    def get_processlist(self) -> Optional[list]:
        return self._get("processlist")

    def get_load(self) -> Optional[dict]:
        return self._get("load")

    def get_uptime(self) -> Optional[dict]:
        return self._get("uptime")

    def get_alert(self) -> Optional[list]:
        return self._get("alert")

    def get_sensors(self) -> Optional[list]:
        return self._get("sensors")

    def get_all(self) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        return {
            "timestamp": now,
            "system": self.get_system(),
            "cpu": self.get_cpu(),
            "memory": self.get_memory(),
            "disk": self.get_disk(),
            "network": self.get_network(),
            "processlist": self.get_processlist(),
            "load": self.get_load(),
            "uptime": self.get_uptime(),
            "sensors": self.get_sensors(),
        }

    def is_alive(self) -> bool:
        try:
            resp = self.session.get(f"{self.base_url}/api/4/version", timeout=3)
            return resp.status_code == 200
        except requests.exceptions.ConnectionError:
            return False
        except requests.exceptions.Timeout:
            return False
        except Exception:
            return False
