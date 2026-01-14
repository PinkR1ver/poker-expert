import sys
from PySide6.QtWidgets import QApplication
from ui.main_window import MainWindow

if __name__ == "__main__":
    # Fix for matplotlib numpy issue if numpy wasn't imported explicitly but needed for fill_between logic check
    import numpy as np
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
