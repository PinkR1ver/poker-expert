"""
Import 页面 - 导入手牌历史文件
"""
import os

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QPushButton,
    QFileDialog, QProgressBar
)
from PySide6.QtCore import Qt, QThread, Signal

from poker_parser import parse_file
from db_manager import DBManager


class ImportWorker(QThread):
    """后台导入线程"""
    
    progress = Signal(str)
    finished = Signal(int, int)  # added, duplicates

    def __init__(self, file_paths, db_path="poker_tracker.db"):
        super().__init__()
        self.file_paths = file_paths
        self.db_path = db_path

    def run(self):
        db = DBManager(self.db_path)
        added_count = 0
        duplicate_count = 0
        
        for path in self.file_paths:
            self.progress.emit(f"Parsing {os.path.basename(path)}...")
            try:
                hands = parse_file(path)
                for hand in hands:
                    if db.add_hand(hand):
                        added_count += 1
                    else:
                        duplicate_count += 1
            except Exception as e:
                print(f"Error parsing {path}: {e}")
        
        db.close()
        self.finished.emit(added_count, duplicate_count)


class ImportPage(QWidget):
    """导入页面"""
    
    data_changed = Signal()

    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        center_container = QWidget()
        center_layout = QVBoxLayout(center_container)
        
        lbl_title = QLabel("Import Hand History")
        lbl_title.setAlignment(Qt.AlignCenter)
        lbl_title.setStyleSheet("font-size: 24px; font-weight: bold; margin-bottom: 20px;")
        
        lbl_desc = QLabel("Select GGPoker text files to import hands into the database.")
        lbl_desc.setAlignment(Qt.AlignCenter)
        lbl_desc.setStyleSheet("color: #aaaaaa; margin-bottom: 30px;")

        self.btn_import = QPushButton("Select Files...")
        self.btn_import.setFixedSize(200, 50)
        self.btn_import.setStyleSheet("font-size: 16px;")
        self.btn_import.clicked.connect(self.import_files)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.lbl_status = QLabel("")
        self.lbl_status.setAlignment(Qt.AlignCenter)

        center_layout.addWidget(lbl_title)
        center_layout.addWidget(lbl_desc)
        center_layout.addWidget(self.btn_import, 0, Qt.AlignCenter)
        center_layout.addWidget(self.progress_bar)
        center_layout.addWidget(self.lbl_status)
        center_layout.addStretch()

        layout.addStretch()
        layout.addWidget(center_container)
        layout.addStretch()

    def import_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Hand History Files", "", "Text Files (*.txt);;All Files (*)"
        )
        if files:
            self.btn_import.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)
            
            self.worker = ImportWorker(files)
            self.worker.progress.connect(self.update_status)
            self.worker.finished.connect(self.import_finished)
            self.worker.start()

    def update_status(self, msg):
        self.lbl_status.setText(msg)

    def import_finished(self, added, duplicates):
        self.lbl_status.setText(f"Import Complete.\nNew Hands: {added} | Duplicates: {duplicates}")
        self.progress_bar.setVisible(False)
        self.btn_import.setEnabled(True)
        self.data_changed.emit()
