import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QHBoxLayout,
    QLineEdit, QPushButton, QLabel, QSpinBox, QComboBox, QWidget,
    QFileDialog
)

from domain import AppConfig


class ConfigDialog(QDialog):
    def __init__(self, cfg: AppConfig, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuration")
        self._cfg = cfg

        self.base_edit = QLineEdit(cfg.base_dir)
        self.pack_edit = QLineEdit(cfg.pack_dir)
        self.server_edit = QLineEdit(cfg.server_dir)

        self.max_backups = QSpinBox()
        self.max_backups.setRange(0, 99)
        self.max_backups.setValue(int(cfg.max_backups))

        self.table_mode = QComboBox()
        self.table_mode.addItems(["compact", "expanded"])
        self.table_mode.setCurrentText(cfg.table_mode)

        self.lang = QComboBox()
        self.lang.addItems(["ru", "en"])
        self.lang.setCurrentText(cfg.language)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.addRow("Main folder:", self._path_row(self.base_edit))
        form.addRow("Installation folder:", self._path_row(self.pack_edit))
        form.addRow("Server folder (optional):", self._path_row(self.server_edit))
        form.addRow("Maximum backups:", self.max_backups)
        form.addRow("Table mode:", self.table_mode)
        form.addRow("Language:", self.lang)
        layout.addLayout(form)

        self.hint = QLabel("You must select a main folder and an installation folder.")
        layout.addWidget(self.hint)

        btns = QHBoxLayout()
        self.ok_btn = QPushButton("Save")
        self.cancel_btn = QPushButton("Cancel")
        btns.addWidget(self.ok_btn)
        btns.addWidget(self.cancel_btn)
        layout.addLayout(btns)

        self.ok_btn.clicked.connect(self._on_ok)
        self.cancel_btn.clicked.connect(self.reject)

    def _path_row(self, edit: QLineEdit):
        container = QWidget()
        w = QHBoxLayout(container)
        w.setContentsMargins(0, 0, 0, 0)

        browse = QPushButton("Browse…")
        browse.clicked.connect(lambda: self._browse_into(edit))

        w.addWidget(edit)
        w.addWidget(browse)

        return container

    def _browse_into(self, edit: QLineEdit):
        path = QFileDialog.getExistingDirectory(
            self,
            "Select folder",
            edit.text() or os.getcwd()
        )
        if path:
            edit.setText(path)

    def _on_ok(self):
        self._cfg.base_dir = self.base_edit.text().strip()
        self._cfg.pack_dir = self.pack_edit.text().strip()
        self._cfg.server_dir = self.server_edit.text().strip()
        self._cfg.max_backups = int(self.max_backups.value())
        self._cfg.table_mode = self.table_mode.currentText()
        self._cfg.language = self.lang.currentText()
        self.accept()