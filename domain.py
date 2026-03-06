import os
import json
import re
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class GameVersion:
    major: int = 0
    minor: int = 0
    patch: int = 0

    @staticmethod
    def parse(text: str):
        # Ищем первое похожее на X.Y.Z или X.Y
        # text может быть "v1.21.6" или "VintageStory_1.21.6"
        import re
        m = re.search(r'(\d+)\.(\d+)(?:\.(\d+))?', text)
        if not m:
            return GameVersion()
        major = int(m.group(1))
        minor = int(m.group(2))
        patch = int(m.group(3) or 0)
        return GameVersion(major, minor, patch)

    def major_minor_str(self):
        return f"{self.major}.{self.minor:02d}"

    def full_str(self):
        return f"{self.major}.{self.minor}.{self.patch}"

@dataclass
class AppConfig:
    base_dir: str = ""       # где лежит exe клиента/сервера (и/или по названию понимаем версию)
    pack_dir: str = ""       # папка сборки (где Mods, конфиги и т.д.)
    server_dir: str = ""     # опционально

    max_backups: int = 5
    table_mode: str = "compact"  # compact | expanded
    language: str = "ru"         # ru | en

    def is_ready(self):
        return bool(self.base_dir) and bool(self.pack_dir)

from dataclasses import dataclass, field

@dataclass
class ModInfo:
    name: str = ""
    author: str = ""
    modid: str = ""
    version: str = ""
    description: str = ""
    side: str = ""  # "Client"/"Server"/"Universal"
    tags: list = field(default_factory=list)

    required_on_client: bool = False
    required_on_server: bool = False

    # оставим как есть, но лучше dict (VS dependencies обычно dict)
    dependencies: object = field(default_factory=dict)

    game_versions_raw: list = field(default_factory=list)
    game_version: str = ""

    type_label: str = ""
    compatible_minor: bool = True
    present_on_client: bool = False
    present_on_server: bool = False

    raw: dict = field(default_factory=dict)

    @classmethod
    def from_raw(cls, raw):
        raw = _lower_keys(raw)

        side, roc, ros = infer_side_and_requirements(raw)

        name = raw.get("name", "")
        author = raw.get("author", "") or raw.get("authors", "")
        modid = raw.get("modid", "")
        version = raw.get("version", "")
        description = raw.get("description", "")

        deps = raw.get("dependencies", {})
        if not isinstance(deps, (dict, list)):
            deps = {}

        tags = raw.get("tags", [])
        if not isinstance(tags, list):
            tags = []

        gv = raw.get("gameversions") or raw.get("gameversion")
        if isinstance(gv, list):
            game_versions_raw = gv
        elif isinstance(gv, str):
            game_versions_raw = [gv]
        else:
            game_versions_raw = []

        return cls(
            name=name,
            author=author,
            modid=modid,
            version=version,
            description=description,
            side=side,
            required_on_client=roc,
            required_on_server=ros,
            dependencies=deps,
            tags=tags,
            game_versions_raw=game_versions_raw,
            raw=raw,
        )

def _lower_keys(raw):
    if not isinstance(raw, dict):
        return {}
    out = {}
    for k, v in raw.items():
        try:
            kk = str(k).lower()
        except Exception:
            continue
        out[kk] = v
    return out

def _norm_side(value):
    if not isinstance(value, str):
        return ""
    s = value.strip().lower()
    if s in ("universal", "client", "server"):
        return s
    return ""

def _get_bool(raw, key):
    if key not in raw:
        return False, False
    v = raw.get(key)

    if isinstance(v, bool):
        return True, v

    if isinstance(v, str):
        t = v.strip().lower()
        if t in ("true", "1", "yes", "y", "on"):
            return True, True
        if t in ("false", "0", "no", "n", "off", ""):
            return True, False
        return True, False

    if isinstance(v, int):
        return True, v != 0

    return True, False

def infer_side_and_requirements(raw):
    side_hint = _norm_side(raw.get("side", ""))

    roc_present, roc = _get_bool(raw, "requiredonclient")
    ros_present, ros = _get_bool(raw, "requiredonserver")

    # Флаги приоритетнее (реально чаще помогают)
    if roc_present or ros_present:
        if roc_present and ros_present:
            if roc and ros:
                inferred = "universal"
            elif roc and not ros:
                inferred = "client"
            elif ros and not roc:
                inferred = "server"
            else:
                inferred = "universal"
        elif ros_present:
            # только requiredOnServer
            inferred = "client" if ros is False else "universal"
        else:
            # только requiredOnClient
            inferred = "server" if roc is False else "universal"

    elif side_hint:
        inferred = side_hint
    else:
        inferred = "universal"

    if inferred == "client":
        return "Client", True, False
    if inferred == "server":
        return "Server", False, True
    return "Universal", True, True

def _normalize_keys(obj):
    if isinstance(obj, dict):
        return {
            str(k).lower(): _normalize_keys(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize_keys(x) for x in obj]
    return obj

def safe_read_json_bytes(data: bytes):
    import re

    text = data.decode("utf-8-sig", errors="replace")

    # удаление trailing commas
    text = re.sub(r",\s*(\}|\])", r"\1", text)

    raw = json.loads(text)

    # КЛЮЧЕВОЕ — нормализуем регистр
    return _normalize_keys(raw)