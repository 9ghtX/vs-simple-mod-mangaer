from PyQt6.QtCore import Qt, QAbstractTableModel, QModelIndex
from PyQt6.QtGui import QColor
from domain import ModInfo

class ModTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._mods = []
        self._mode = "compact"  # compact|expanded
        self._server_enabled = False

    def set_mode(self, mode: str):
        new_mode = mode if mode in ("compact", "expanded") else "compact"
        if new_mode == self._mode:
            return

        self.beginResetModel()
        self._mode = new_mode
        self.endResetModel()

    def set_server_enabled(self, enabled: bool):
        new_value = bool(enabled)
        if new_value == self._server_enabled:
            return

        self.beginResetModel()
        self._server_enabled = new_value
        self.endResetModel()

    def set_mods(self, mods: list):
        self.beginResetModel()
        self._mods = list(mods or [])
        self.endResetModel()

    def mods(self):
        return self._mods

    def rowCount(self, parent=QModelIndex()):
        return len(self._mods)

    def columnCount(self, parent=QModelIndex()):
        return len(self._columns())

    def _columns(self):
        if self._mode == "compact":
            cols = [
                "name",
                "author",
                "game_version",
                "version",
                "type",
                "on_client"
            ]
            if self._server_enabled:
                cols.append("on_server")
            return cols

        # expanded
        cols = [
            "name",
            "author",
            "modid",
            "version",
            "type",
            "description",
            "game_version",
            "side",
            "dependencies",
            "on_client",
        ]
        if self._server_enabled:
            cols.append("on_server")
        return cols

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        key = self._columns()[section]
        headers = {
            "name": "Title",
            "author": "Author",
            "game_version": "Game version",
            "version": "Mod version",
            "type": "Tags/Type",
            "on_client": "Client",
            "on_server": "Server",
            "modid": "Mod ID",
            "description": "Description",
            "side": "Side",
            "dependencies": "Dependencies",
        }
        return headers.get(key, key)

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        mod = self._mods[index.row()]
        col = self._columns()[index.column()]

        if role == Qt.ItemDataRole.DisplayRole:
            return self._display(mod, col)

        if role == Qt.ItemDataRole.ForegroundRole:
            # зелёный/красный для колонки "game_version" в compact
            if col == "game_version":
                return QColor("green") if mod.compatible_minor else QColor("red")
        return None

    def _display(self, m: ModInfo, col: str):
        if col == "name":
            return m.name or m.modid
        if col == "author":
            return m.author or ""
        if col == "modid":
            return m.modid or ""
        if col == "version":
            return m.version or ""
        if col == "type":
            if m.tags:
                return ", ".join(str(x) for x in m.tags)
            return m.type_label or ""
        if col == "description":
            return (m.description or "").strip()
        if col == "game_version":
            return m.game_version or "?"
        if col == "side":
            return self._side_label(m)
        if col == "dependencies":
            return self._deps_label(m.dependencies)
        if col == "on_client":
            return "Yes" if m.present_on_client else "No"
        if col == "on_server":
            return "Yes" if m.present_on_server else "No"
        return ""

    def _side_label(self, m: ModInfo):
        s = (m.side or "").strip().lower()
        # если ты нормализуешь side на "Client/Server/Universal", это тоже отработает
        if (m.required_on_client and m.required_on_server) or s == "universal":
            return "Universal"
        if (m.required_on_client and not m.required_on_server) or s == "client":
            return "Client"
        if (m.required_on_server and not m.required_on_client) or s == "server":
            return "Server"
        return "?"

    def _deps_label(self, deps):
        if not deps:
            return ""

        if isinstance(deps, dict):
            items = [f"{k}:{v}" for k, v in deps.items()]
            return ", ".join(items)

        if isinstance(deps, list):
            return ", ".join(str(x) for x in deps)

        return str(deps)

    def sort(self, column, order):
        cols = self._columns()
        if column < 0 or column >= len(cols):
            return

        key = cols[column]
        reverse = order == Qt.SortOrder.DescendingOrder

        def sort_key(m: ModInfo):
            if key == "name":
                return (m.name or m.modid or "").lower()
            if key == "author":
                return (m.author or "").lower()
            if key == "modid":
                return (m.modid or "").lower()
            if key == "version":
                return (m.version or "")
            if key == "game_version":
                # можно улучшить до (major, minor), но хотя бы строка будет работать
                return (m.game_version or "")
            if key == "type":
                # единая логика как в _display
                if m.tags:
                    return ", ".join(str(x) for x in m.tags).lower()
                return (m.type_label or "").lower()
            if key == "description":
                return (m.description or "").strip().lower()
            if key == "side":
                return self._side_label(m).lower()
            if key == "dependencies":
                return self._deps_label(m.dependencies).lower()
            if key == "on_client":
                return 1 if m.present_on_client else 0
            if key == "on_server":
                return 1 if m.present_on_server else 0
            return ""

        self.layoutAboutToBeChanged.emit()
        self._mods.sort(key=sort_key, reverse=reverse)
        self.layoutChanged.emit()