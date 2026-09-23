import os

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

MENU = "&Amostragem de Solo"


class AmostragemSoloPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.dialog = None

    def initGui(self):
        icon = QIcon(os.path.join(os.path.dirname(__file__), "icon.svg"))
        self.action = QAction(icon, "Plano de Amostragem de Solo", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu(MENU, self.action)

    def unload(self):
        self.iface.removePluginMenu(MENU, self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dialog is not None:
            self.dialog.close()
            self.dialog = None

    def run(self):
        from .dialog import AmostragemDialog

        if self.dialog is None:
            self.dialog = AmostragemDialog(self.iface, self.iface.mainWindow())
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
