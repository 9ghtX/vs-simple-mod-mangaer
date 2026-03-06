import os
import re
import zipfile
import shutil
from datetime import datetime

from domain import ModInfo, GameVersion, safe_read_json_bytes

class VersionService:
    def detect_game_version_from_base_dir(self, base_dir: str):
        # Требование: “по названию папки можно понимать версию”.
        # Делаем так: берём basename и парсим.
        folder = os.path.basename(os.path.normpath(base_dir))
        v = GameVersion.parse(folder)
        if v.major == 0 and v.minor == 0:
            # запасной вариант: попробовать прочитать client settings / dll name / и т.п. — пока пропускаем
            pass
        return v

class ModCompatibilityService:
    def is_compatible_minor(self, game_version: GameVersion, mod_game_versions_raw: list):
        """
        Требование: зелёным если "число после точки" совпадает
        У VS 1.21.6 → сравниваем minor=21
        """
        if game_version.major == 0 and game_version.minor == 0:
            return True

        # если в моде нет данных по версии игры — считаем “неизвестно”, но не красим в красный
        if not mod_game_versions_raw:
            return True

        for vraw in mod_game_versions_raw:
            v = GameVersion.parse(str(vraw))
            if v.major == 0 and v.minor == 0:
                continue
            if v.major == game_version.major and v.minor == game_version.minor:
                return True
        return False

    def last_major_minor(self, mod_game_versions_raw: list):
        # Требование: "#.##" (major + minor)
        best = GameVersion()
        for vraw in mod_game_versions_raw:
            v = GameVersion.parse(str(vraw))
            if (v.major, v.minor, v.patch) > (best.major, best.minor, best.patch):
                best = v
        if best.major == 0 and best.minor == 0:
            return ""
        return best.major_minor_str()

class ModScanner:
    def __init__(self):
        pass

    def _infer_type(self, mod: ModInfo):
        s = f"{mod.name} {mod.modid} {mod.description}".lower()
        if "shader" in s or "ssr" in s or "fog" in s or "god ray" in s:
            return "Shader"
        if mod.modid.endswith("lib") or " lib " in f" {s} ":
            return "Library"
        return "Content"

    def scan_mods_dir(self, mods_dir: str):
        result = {}
        if not mods_dir or not os.path.isdir(mods_dir):
            return result

        for fn in os.listdir(mods_dir):
            if not fn.lower().endswith(".zip"):
                continue

            path = os.path.join(mods_dir, fn)
            mi = self._read_modinfo_from_zip(path)
            if mi and mi.modid:
                result[mi.modid] = mi

        return result

    def _read_modinfo_from_zip(self, zip_path: str):
        try:
            with zipfile.ZipFile(zip_path, "r") as z:
                modinfo_name = None
                for n in z.namelist():
                    if n.lower().endswith("modinfo.json"):
                        modinfo_name = n
                        break
                if not modinfo_name:
                    return None

                raw = safe_read_json_bytes(z.read(modinfo_name))
                if not isinstance(raw, dict) or not raw:
                    return None

        except Exception:
            return None

        mod = ModInfo.from_raw(raw)
        mod.type_label = self._infer_type(mod)
        return mod

class ModCopyService:
    def __init__(self):
        pass

    def backup_and_clear_server_mods(self, server_mods_dir: str, backups_dir: str, max_backups: int):
        os.makedirs(backups_dir, exist_ok=True)
        os.makedirs(server_mods_dir, exist_ok=True)

        # backup zip
        stamp = datetime.now().strftime("%d%m%Y-%H-%M")
        backup_name = f"mod_backup_{stamp}.zip"
        backup_path = os.path.join(backups_dir, backup_name)

        with zipfile.ZipFile(backup_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
            for root, _, files in os.walk(server_mods_dir):
                for f in files:
                    full = os.path.join(root, f)
                    rel = os.path.relpath(full, server_mods_dir)
                    z.write(full, rel)

        # clear server Mods
        for name in os.listdir(server_mods_dir):
            p = os.path.join(server_mods_dir, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    os.remove(p)
                except Exception:
                    pass

        # rotate backups
        self._rotate_backups(backups_dir, max_backups)

        return backup_path

    def _rotate_backups(self, backups_dir: str, max_backups: int):
        if max_backups <= 0:
            return
        files = []
        for fn in os.listdir(backups_dir):
            if fn.lower().endswith(".zip") and fn.startswith("mod_backup_"):
                path = os.path.join(backups_dir, fn)
                files.append((os.path.getmtime(path), path))
        files.sort(reverse=True)
        for i, (_, path) in enumerate(files):
            if i >= max_backups:
                try:
                    os.remove(path)
                except Exception:
                    pass

    def copy_server_required_mods(self, client_mods_dir: str, server_mods_dir: str, mods: list):
        """
        mods: list[ModInfo] — уже отсканированные моды (клиентские), из них копируем те, что required_on_server
        """
        os.makedirs(server_mods_dir, exist_ok=True)

        # Копируем zip-файлы по ModID: ищем соответствующий zip на клиенте
        # Более надёжно: сканировать client_mods_dir и строить map modid->zip path по modinfo, но чтобы не пересканировать:
        # делаем быстрый проход: zip->modid
        zip_map = self._build_zip_map_by_modid(client_mods_dir)

        copied = []
        missing = []
        for m in mods:
            if not m.required_on_server and not m.side == "server" and not m.side == "universal":
                continue
            zpath = zip_map.get(m.modid)
            if not zpath:
                missing.append(m.modid)
                continue
            shutil.copy2(zpath, os.path.join(server_mods_dir, os.path.basename(zpath)))
            copied.append(m.modid)

        return copied, missing

    def _build_zip_map_by_modid(self, mods_dir: str):
        from domain import safe_read_json_bytes
        import zipfile

        out = {}
        if not os.path.isdir(mods_dir):
            return out
        for fn in os.listdir(mods_dir):
            if not fn.lower().endswith(".zip"):
                continue
            path = os.path.join(mods_dir, fn)
            try:
                with zipfile.ZipFile(path, "r") as z:
                    modinfo_name = None
                    for n in z.namelist():
                        if n.lower().endswith("modinfo.json"):
                            modinfo_name = n
                            break
                    if not modinfo_name:
                        continue
                    raw = safe_read_json_bytes(z.read(modinfo_name))
                    modid = raw.get("modid", "")
                    if modid:
                        out[modid] = path
            except Exception:
                continue
        return out

class LocalizationService:
    RU = {
        "Name": "Название",
        "ModID": "ID мода",
        "Version": "Версия",
        "Description": "Описание",
        "Side": "Сторона",
        "RequiredOnClient": "Требуется на клиенте",
        "RequiredOnServer": "Требуется на сервере",
        "Dependencies": "Зависимости",
        "Tags": "Тэги",
        "GameVersions": "Версии игры",
    }

    EN = {
        "Name": "Name",
        "ModID": "Mod ID",
        "Version": "Version",
        "Description": "Description",
        "Side": "Side",
        "RequiredOnClient": "Required on client",
        "RequiredOnServer": "Required on server",
        "Dependencies": "Dependencies",
        "Tags": "Tags",
        "GameVersions": "Game versions",
    }

    def __init__(self, language: str):
        self.language = language if language in ("ru", "en") else "ru"

    def label_for_field(self, key: str):
        d = self.RU if self.language == "ru" else self.EN
        return d.get(key, key)

    def humanize_value(self, v):
        if isinstance(v, bool):
            return "Да" if v and self.language == "ru" else ("Yes" if v else ("Нет" if self.language == "ru" else "No"))
        if isinstance(v, list):
            return ", ".join(str(x) for x in v)
        if v is None:
            return ""
        return str(v)