import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from domain import AppConfig
from repo import ConfigRepository
from services import (
    VersionService, ModScanner, ModCompatibilityService, ModCopyService, LocalizationService
)
from ui_main import MainWindow
from ui_config import ConfigDialog
from table_model import ModTableModel

class MainController:
    def __init__(self, window: MainWindow, repo: ConfigRepository):
        self.w = window
        self.repo = repo
        self.cfg = repo.load()

        self.version_svc = VersionService()
        self.scan_svc = ModScanner()
        self.compat_svc = ModCompatibilityService()
        self.copy_svc = ModCopyService()

        self.model = ModTableModel()
        self.w.table.setModel(self.model)

        self._all_mods = []

        # wire UI
        self.w.act_exit.triggered.connect(self._exit)
        self.w.act_config.triggered.connect(self.open_config)
        self.w.btn_reload.clicked.connect(self.reload_mods)
        self.w.btn_copy_server.clicked.connect(self.copy_to_server)
        self.w.mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self.w.search_edit.textChanged.connect(self._apply_filter)
        self.w.table.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # apply config
        self.w.mode_combo.setCurrentText(self.cfg.table_mode)
        self.model.set_mode(self.cfg.table_mode)

        self._refresh_block_state()
        if self.cfg.is_ready():
            self.reload_mods()

    def _exit(self):
        QApplication.instance().quit()

    def _on_mode_changed(self, mode: str):
        self.cfg.table_mode = mode
        self.model.set_mode(mode)
        self.repo.save(self.cfg)

    def open_config(self):
        dlg = ConfigDialog(self.cfg, self.w)
        if dlg.exec():
            self.repo.save(self.cfg)
            self._refresh_block_state()
            if self.cfg.is_ready():
                self.reload_mods()
            else:
                self.model.set_mods([])
                self.w.details.clear()

    def _refresh_block_state(self):
        ready = self.cfg.is_ready()
        server_enabled = bool(self.cfg.server_dir)
        self.model.set_server_enabled(server_enabled)

        if not ready:
            self.w.show_blocked("Need to choose: main folder and installation folder. Open: File → Config.")
        else:
            self.w.hide_blocked()

        self.w.set_actions_enabled(ready, server_enabled)

    def _mods_dir_from_pack(self):
        # обычно Mods лежит в pack_dir/Mods
        return os.path.join(self.cfg.pack_dir, "Mods")

    def _mods_dir_from_server(self):
        if not self.cfg.server_dir:
            return ""
        return os.path.join(self.cfg.server_dir, "Mods")

    def reload_mods(self):
        if not self.cfg.is_ready():
            return

        game_v = self.version_svc.detect_game_version_from_base_dir(self.cfg.base_dir)
        client_mods_dir = self._mods_dir_from_pack()
        server_mods_dir = self._mods_dir_from_server()

        client_map = self.scan_svc.scan_mods_dir(client_mods_dir)
        server_map = self.scan_svc.scan_mods_dir(server_mods_dir) if server_mods_dir else {}

        mods = []
        compat = self.compat_svc

        # объединяем по ModID
        all_ids = set(client_map.keys()) | set(server_map.keys())
        for modid in sorted(all_ids):
            m = client_map.get(modid) or server_map.get(modid)
            m.present_on_client = modid in client_map
            m.present_on_server = modid in server_map

            m.last_game_version_major_minor = compat.last_major_minor(m.game_versions_raw)
            m.compatible_minor = compat.is_compatible_minor(game_v, m.game_versions_raw)

            mods.append(m)

        self._all_mods = mods
        self._apply_filter()
        self.w.details.clear()

    def _apply_filter(self):
        text = (self.w.search_edit.text() or "").strip().lower()

        filtered = []
        for m in self._all_mods:

            if text:
                if text not in f"{m.name} {m.modid}".lower():
                    continue

            if self.w.chk_incompatible.isChecked() and m.compatible_minor:
                continue

            if self.w.chk_server.isChecked():
                # серверные и универсальные
                if not (m.required_on_server or (m.required_on_client and m.required_on_server)):
                    continue

            if self.w.chk_missing_server.isChecked() and m.present_on_server:
                continue

            filtered.append(m)

        self.model.set_mods(filtered)

    def _on_selection_changed(self, *_):
        idxs = self.w.table.selectionModel().selectedRows()
        if not idxs:
            self.w.details.clear()
            return
        row = idxs[0].row()
        mods = self.model.mods()
        if row < 0 or row >= len(mods):
            return
        m = mods[row]
        self._render_details(m)

    def _render_details(self, m):
        loc = LocalizationService(self.cfg.language)
        # показываем “человеческие” ключи для основных полей + весь raw внизу
        keys_priority = [
            "Name", "ModID", "Version", "Description", "Side",
            "RequiredOnClient", "RequiredOnServer", "Dependencies", "Tags", "GameVersions"
        ]
        raw = m.raw or {}
        lines = []
        for k in keys_priority:
            # raw может хранить в разных регистрах
            val = raw.get(k)
            if val is None:
                # пробуем варианты
                alt = k.lower()
                val = raw.get(alt)
            if val is None:
                continue
            lines.append(f"{loc.label_for_field(k)}: {loc.humanize_value(val)}")

        lines.append("")
        lines.append("— Calculated —")
        lines.append(f"Type: {m.type_label}")
        lines.append(f"Compatibility minor: {'OK' if m.compatible_minor else 'NOT COMPATABLE'}")
        lines.append(f"On client: {'Yes' if m.present_on_client else 'No'}")
        if self.cfg.server_dir:
            lines.append(f"On server: {'Yes' if m.present_on_server else 'No'}")
        lines.append("")
        lines.append("— Raw JSON (for debug) —")
        import json
        lines.append(json.dumps(raw, ensure_ascii=False, indent=2))
        self.w.details.setPlainText("\n".join(lines))

    def copy_to_server(self):
        if not (self.cfg.is_ready() and self.cfg.server_dir):
            return

        client_mods_dir = self._mods_dir_from_pack()
        server_mods_dir = self._mods_dir_from_server()
        backups_dir = os.path.join(self.cfg.server_dir, "ModBackups")

        # backup + clear
        try:
            backup_path = self.copy_svc.backup_and_clear_server_mods(
                server_mods_dir=server_mods_dir,
                backups_dir=backups_dir,
                max_backups=int(self.cfg.max_backups),
            )
        except Exception as e:
            QMessageBox.critical(self.w, "Error", f"Didn't make a backup/cleaning servers' mods folder:\n{e}")
            return

        # copy server mods
        try:
            copied, missing = self.copy_svc.copy_server_required_mods(
                client_mods_dir=client_mods_dir,
                server_mods_dir=server_mods_dir,
                mods=self._all_mods,
            )
        except Exception as e:
            QMessageBox.critical(self.w, "Error", f"Didn't copy mods on server:\n{e}")
            return

        msg = [
            f"Backup: {backup_path}",
            f"Copied: {len(copied)}",
        ]
        if missing:
            msg.append(f"Couldn't find a zip for ModID: {', '.join(missing)}")
        QMessageBox.information(self.w, "Done!", "\n".join(msg))

        self.reload_mods()

def build_config_path():
    # простой вариант: рядом со скриптом/EXE
    base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "vs_mod_manager_config.json")

def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    repo = ConfigRepository(build_config_path())
    _ = MainController(w, repo)
    w.resize(1200, 700)
    w.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()