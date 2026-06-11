import sys
from PyQt6.QtWidgets import QApplication
from lunanime.gui.main_window import MainWindow


def main():
    from lunanime.db import init_db
    init_db()

    app = QApplication(sys.argv)
    app.setApplicationName("Lunanime")
    app.setOrganizationName("Lunanime")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
