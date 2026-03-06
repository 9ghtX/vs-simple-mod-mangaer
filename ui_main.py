from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableView, QTextEdit, QComboBox, QLineEdit,
    QSplitter, QCheckBox, QHeaderView
)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VS Mod Manager")

        # actions
        self.btn_reload = QPushButton("Reload list")
        self.btn_copy_server = QPushButton("Copy on server")
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["compact", "expanded"])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Find by title/ID…")

        self.banner = QLabel("")
        self.banner.setStyleSheet("padding: 6px; background: #3b1d1d; color: #ffd0d0; border-radius: 6px;")
        self.banner.hide()

        self.table = QTableView()
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setSortingEnabled(True)
        self.table.setWordWrap(True)
        self.table.resizeRowsToContents()
        self.table.verticalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.ResizeToContents
        )

        self.details = QTextEdit()
        self.details.setReadOnly(True)

        self.chk_incompatible = QCheckBox("Not compatible")
        self.chk_server = QCheckBox("Only server ")
        self.chk_missing_server = QCheckBox("Not in server")

        left = QWidget()
        left_l = QVBoxLayout(left)
        top = QHBoxLayout()
        top.addWidget(self.btn_reload)
        top.addWidget(self.btn_copy_server)
        top.addWidget(QLabel("Mode:"))
        top.addWidget(self.mode_combo)
        top.addStretch(1)
        top.addWidget(self.search_edit)
        top.addWidget(self.chk_incompatible)
        top.addWidget(self.chk_server)
        top.addWidget(self.chk_missing_server)

        left_l.addLayout(top)
        left_l.addWidget(self.banner)
        left_l.addWidget(self.table)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(self.details)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

        central = QWidget()
        c_l = QVBoxLayout(central)
        c_l.addWidget(splitter)
        self.setCentralWidget(central)

        # menu
        menu = self.menuBar()
        m_file = menu.addMenu("File")
        self.act_config = m_file.addAction("Config…")
        self.act_exit = m_file.addAction("Exit")

    def show_blocked(self, text: str):
        self.banner.setText(text)
        self.banner.show()

    def hide_blocked(self):
        self.banner.hide()

    def set_actions_enabled(self, enabled: bool, server_enabled: bool):
        self.btn_reload.setEnabled(enabled)
        self.mode_combo.setEnabled(enabled)
        self.search_edit.setEnabled(enabled)
        self.btn_copy_server.setEnabled(enabled and server_enabled)