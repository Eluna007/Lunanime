import sys
import traceback

from PyQt6.QtWidgets import QApplication
from lunanime.gui.main_window import MainWindow


def _excepthook(exc_type, exc_value, exc_tb):
    """PyQt6 aborts the whole app on unhandled exceptions in slots.
    Log them instead so a single bad result can't take Lunanime down."""
    traceback.print_exception(exc_type, exc_value, exc_tb)


def main():
    from lunanime.db import init_db
    init_db()

    sys.excepthook = _excepthook

    app = QApplication(sys.argv)
    app.setApplicationName("Lunanime")
    app.setOrganizationName("Lunanime")

    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
