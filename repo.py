import os
import json
from domain import AppConfig

class ConfigRepository:
    def __init__(self, config_path: str):
        self.config_path = config_path

    def load(self):
        if not os.path.isfile(self.config_path):
            return AppConfig()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            cfg = AppConfig()
            cfg.base_dir = data.get("base_dir", "")
            cfg.pack_dir = data.get("pack_dir", "")
            cfg.server_dir = data.get("server_dir", "")
            cfg.max_backups = int(data.get("max_backups", 5))
            cfg.table_mode = data.get("table_mode", "compact")
            cfg.language = data.get("language", "ru")
            return cfg
        except Exception:
            return AppConfig()

    def save(self, cfg: AppConfig):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        data = {
            "base_dir": cfg.base_dir,
            "pack_dir": cfg.pack_dir,
            "server_dir": cfg.server_dir,
            "max_backups": int(cfg.max_backups),
            "table_mode": cfg.table_mode,
            "language": cfg.language,
        }
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)