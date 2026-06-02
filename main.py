import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from apumachi.gui.main_window import MainWindow


def main():
    from apumachi.db import init_db
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("ApuMachi")
    app.setOrganizationName("ApuMachi")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
