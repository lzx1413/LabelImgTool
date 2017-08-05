from PyQt4 import QtGui, QtCore
import socket
import re


class SettingDialog(QtGui.QDialog):
    enable_color_map = False

    def __init__(self, parent):
        QtGui.QDialog.__init__(self, parent)
        self.resize(320, 240)
        self.init_UI()
    def createModeGroup(self):
        '''
        set the trask mode setting group
        :return: mode group
        '''
        self.modegroupBox = QtGui.QGroupBox("& Task Mode")
        self.modegroupBox.setCheckable(True)
        self.modegroupBox.setChecked(True)
        self.CLS_mode_rb = QtGui.QRadioButton("CLS Mode")
        self.CLS_mode_rb.clicked.connect(self.CLS_model_selected)
        self.DET_mode_rb = QtGui.QRadioButton("DET Mode")
        self.DET_mode_rb.clicked.connect(self.DET_model_selected)
        self.SEG_mode_rb = QtGui.QRadioButton("SEG Mode")
        self.SEG_mode_rb.clicked.connect(self.SEG_model_selected)

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.CLS_mode_rb)
        vbox.addWidget(self.DET_mode_rb)
        vbox.addWidget(self.SEG_mode_rb)
        vbox.addStretch(True)
        self.modegroupBox.setLayout(vbox)
        return self.modegroupBox

    def createDEToptGroup(self):
        self.detgroupBox = QtGui.QGroupBox("& DET options")
        self.detgroupBox.setCheckable(True)
        self.detgroupBox.setChecked(False)
        self.enable_show_label_cb = QtGui.QCheckBox('enable show label name')
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.enable_show_label_cb)
        vbox.addStretch()
        self.detgroupBox.setLayout(vbox)
        return self.detgroupBox

    def createCLSoptGroup(self):
        self.clsgroupBox = QtGui.QGroupBox("& CLS options")
        self.clsgroupBox.setCheckable(True)
        self.clsgroupBox.setChecked(False)
        self.single_label_rb = QtGui.QRadioButton("single label")
        self.multi_label_rb = QtGui.QRadioButton("multi label")
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.single_label_rb)
        vbox.addWidget(self.multi_label_rb)
        vbox.addStretch(True)
        self.clsgroupBox.setLayout(vbox)
        return self.clsgroupBox

    def createSEGoptGroup(self):
        self.seggroupBox = QtGui.QGroupBox("& SEG options")
        self.seggroupBox.setCheckable(True)
        self.seggroupBox.setChecked(False)
        self.enable_color_map_cb = QtGui.QCheckBox('enable color map')
        if self.__class__.enable_color_map:
            self.enable_color_map_cb.toggle()
        self.enable_color_map_cb.stateChanged.connect(
            self.change_color_enable_state)
        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(self.enable_color_map_cb)
        vbox.addStretch(True)
        self.seggroupBox.setLayout(vbox)
        return self.seggroupBox


    def init_UI(self):
        main_v_layout = QtGui.QVBoxLayout()

        grid = QtGui.QGridLayout()
        grid.addWidget(self.createModeGroup(),0,0)
        grid.addWidget(self.createDEToptGroup(),1,0)
        grid.addWidget(self.createCLSoptGroup(),2,0)
        grid.addWidget(self.createSEGoptGroup(),3,0)
        self.DET_mode_rb.setChecked(True)
        self.DET_model_selected()
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

    def CLS_model_selected(self):
        self.clsgroupBox.setDisabled(False)
        self.detgroupBox.setDisabled(True)
        self.seggroupBox.setDisabled(True)

    def DET_model_selected(self):
        self.detgroupBox.setDisabled(False)
        self.clsgroupBox.setDisabled(True)
        self.seggroupBox.setDisabled(True)

    def SEG_model_selected(self):
        self.seggroupBox.setDisabled(False)
        self.detgroupBox.setDisabled(True)
        self.clsgroupBox.setDisabled(True)
    def change_color_enable_state(self, state):
        if state == QtCore.Qt.Checked:
            self.__class__.enable_color_map = True
        else:
            self.__class__.enable_color_map = False

    def get_color_map_state(self):
        return self.__class__.enable_color_map
