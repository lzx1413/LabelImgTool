from PyQt4 import QtGui, QtCore
import socket
import re


class SettingDialog(QtGui.QDialog):
    enable_color_map = False

    def __init__(self, parent):
        QtGui.QDialog.__init__(self, parent)
        self.resize(320, 240)
        self.init_UI()

    def init_UI(self):
        main_v_layout = QtGui.QVBoxLayout()
        grid = QtGui.QGridLayout()
        self.enable_color_map_cb = QtGui.QCheckBox('enable color map')
        if self.__class__.enable_color_map:
            self.enable_color_map_cb.toggle()
        self.enable_color_map_cb.stateChanged.connect(
            self.change_color_enable_state)
        grid.addWidget(self.enable_color_map_cb, 0, 0, 1, 1)
        buttonBox = QtGui.QDialogButtonBox(parent=self)
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(
            QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        main_v_layout.addLayout(grid)
        spacerItem = QtGui.QSpacerItem(
            20, 48, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        main_v_layout.addItem(spacerItem)
        main_v_layout.addWidget(buttonBox)
        self.setLayout(main_v_layout)

    def change_color_enable_state(self, state):
        if state == QtCore.Qt.Checked:
            self.__class__.enable_color_map = True
        else:
            self.__class__.enable_color_map = False

    def get_color_map_state(self):
        return self.__class__.enable_color_map
