try:
    from PyQt5.QtGui import *
    from PyQt5.QtCore import *
    from PyQt5.QtWidgets import *
except:
    from PyQt4.QtGui import *
    from PyQt4.QtCore import *
import socket
import re


class SettingDialog(QDialog):
    enable_color_map = True
    label_font_size = 10
    task_mode = 0 #0=det, 1=seg, 2=cls
    instance_seg_flag = False


    def __init__(self, parent,config):
        QDialog.__init__(self, parent)
        self.resize(320, 240)
        self.__class__.task_mode = config['task_mode']
        self.__class__.label_font_size = config['label_font_size']
        self.init_UI()
    def createModeGroup(self):
        '''
        set the trask mode setting group
        :return: mode group
        '''
        self.modegroupBox = QGroupBox("& Task Mode")
        self.modegroupBox.setCheckable(True)
        self.modegroupBox.setChecked(True)
        self.CLS_mode_rb = QRadioButton("CLS Mode")
        self.CLS_mode_rb.clicked.connect(self.CLS_model_selected)
        self.DET_mode_rb = QRadioButton("DET Mode")
        self.DET_mode_rb.clicked.connect(self.DET_model_selected)
        self.SEG_mode_rb = QRadioButton("SEG Mode")
        self.SEG_mode_rb.clicked.connect(self.SEG_model_selected)
        self.BRU_mode_rb = QRadioButton("BRU Mode")
        self.BRU_mode_rb.clicked.connect(self.BRU_model_selected)

        vbox = QVBoxLayout()
        vbox.addWidget(self.CLS_mode_rb)
        vbox.addWidget(self.DET_mode_rb)
        vbox.addWidget(self.SEG_mode_rb)
        vbox.addWidget(self.BRU_mode_rb)
        vbox.addStretch(True)
        self.modegroupBox.setLayout(vbox)
        return self.modegroupBox

    def createDEToptGroup(self):
        self.detgroupBox = QGroupBox("& DET options")
        self.enable_show_label_cb = QCheckBox('enable show label name')


        self.label_font_size_sl = QSlider(Qt.Horizontal)
        self.label_font_size_sl.setRange(5,50)
        self.label_font_size_sp = QSpinBox()
        self.label_font_size_sp.setRange(5,50)
        self.label_font_size_sl.valueChanged.connect(self.label_font_size_sp.setValue)
        '''
        QObject.connect(self.label_font_size_sl, SIGNAL("valueChanged(int)"),

                               self.label_font_size_sp, SLOT("setValue(int)"))
        '''
        self.label_font_size_sl.valueChanged.connect(self.change_label_font_size)
        self.label_font_size_sl.setValue(self.__class__.label_font_size)
        vbox = QVBoxLayout()
        vbox.addWidget(self.enable_show_label_cb)
        vbox.addWidget(QLabel('label font size'))
        vbox.addWidget(self.label_font_size_sl)
        vbox.addWidget(self.label_font_size_sp)
        vbox.addStretch()
        self.detgroupBox.setLayout(vbox)
        return self.detgroupBox

    def createCLSoptGroup(self):
        self.clsgroupBox = QGroupBox("& CLS options")
        #self.single_label_rb = QtGui.QRadioButton("single label")
        #self.multi_label_rb = QtGui.QRadioButton("multi label")
        vbox = QVBoxLayout()
        #vbox.addWidget(self.single_label_rb)
        #vbox.addWidget(self.multi_label_rb)
        vbox.addStretch(True)
        self.clsgroupBox.setLayout(vbox)
        return self.clsgroupBox
    def createBRUoptGroup(self):
        self.brugroupBox = QGroupBox("& Brush options")
        #self.single_label_rb = QtGui.QRadioButton("single label")
        #self.multi_label_rb = QtGui.QRadioButton("multi label")
        vbox = QVBoxLayout()
        #vbox.addWidget(self.single_label_rb)
        #vbox.addWidget(self.multi_label_rb)
        vbox.addStretch(True)
        self.brugroupBox.setLayout(vbox)
        return self.brugroupBox

    def createSEGoptGroup(self):
        self.seggroupBox = QGroupBox("& SEG options")
        self.enable_color_map_cb = QCheckBox('enable color map')
        self.instance_seg_label_cb = QCheckBox('set instance seg')
        self.instance_seg_label_cb.setChecked(self.__class__.instance_seg_flag)
        self.instance_seg_label_cb.stateChanged.connect(self.change_instance_seg_label)
        if self.__class__.enable_color_map:
            self.enable_color_map_cb.toggle()
        self.enable_color_map_cb.stateChanged.connect(
            self.change_color_enable_state)
        if self.__class__.enable_color_map:
            self.enable_color_map_cb.setChecked(True)
        vbox = QVBoxLayout()
        vbox.addWidget(self.enable_color_map_cb)
        vbox.addWidget(self.instance_seg_label_cb)
        vbox.addStretch(True)
        self.seggroupBox.setLayout(vbox)
        return self.seggroupBox


    def init_UI(self):
        main_v_layout = QVBoxLayout()

        grid = QGridLayout()
        grid.addWidget(self.createModeGroup(),0,0)
        grid.addWidget(self.createDEToptGroup(),1,0)
        grid.addWidget(self.createCLSoptGroup(),2,0)
        grid.addWidget(self.createSEGoptGroup(),3,0)
        grid.addWidget(self.createBRUoptGroup(),4,0)
        if self.__class__.task_mode == 0:
            self.DET_mode_rb.setChecked(True)
            self.DET_model_selected()
        elif self.__class__.task_mode == 1:
            self.SEG_mode_rb.setChecked(True)
            self.SEG_model_selected()
        elif self.__class__.task_mode == 2:
            self.CLS_mode_rb.setChecked(True)
            self.CLS_model_selected()
        elif self.__class__.task_mode == 3:
            self.BRU_mode_rb.setChecked(True)
            self.BRU_model_selected()
        buttonBox = QDialogButtonBox(parent=self)
        buttonBox.setOrientation(Qt.Horizontal)
        buttonBox.setStandardButtons(
            QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        main_v_layout.addLayout(grid)
        spacerItem = QSpacerItem(
            20, 48, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_v_layout.addItem(spacerItem)
        main_v_layout.addWidget(buttonBox)
        self.setLayout(main_v_layout)

    def CLS_model_selected(self):
        self.__class__.task_mode = 2
        self.clsgroupBox.setDisabled(False)
        self.detgroupBox.setDisabled(True)
        self.seggroupBox.setDisabled(True)
        self.brugroupBox.setDisabled(True)

    def DET_model_selected(self):
        self.__class__.task_mode = 0
        self.detgroupBox.setDisabled(False)
        self.clsgroupBox.setDisabled(True)
        self.seggroupBox.setDisabled(True)
        self.brugroupBox.setDisabled(True)

    def SEG_model_selected(self):
        self.__class__.task_mode = 1
        self.seggroupBox.setDisabled(False)
        self.detgroupBox.setDisabled(True)
        self.clsgroupBox.setDisabled(True)
        self.brugroupBox.setDisabled(True)

    def BRU_model_selected(self):
        self.__class__.task_mode = 3
        self.brugroupBox.setDisabled(False)
        self.seggroupBox.setDisabled(True)
        self.detgroupBox.setDisabled(True)
        self.clsgroupBox.setDisabled(True)

    def change_color_enable_state(self, state):
        if state == Qt.Checked:
            self.__class__.enable_color_map = True
        else:
            self.__class__.enable_color_map = False
    def change_instance_seg_label(self,state):
        if state == Qt.Checked:
            self.__class__.instance_seg_flag = True
        else:
            self.__class__.instance_seg_flag = False
    def change_label_font_size(self,value):
        self.__class__.label_font_size = value

    def get_color_map_state(self):
        return self.__class__.enable_color_map

    def get_setting_state(self):
        if self.__class__.task_mode == 0:
            return {'mode': 0,'enable_color_map':self.__class__.enable_color_map,'label_font_size': self.__class__.label_font_size}

        elif self.__class__.task_mode == 1:
            return {'mode': 1,'enable_color_map':self.__class__.enable_color_map,'instance_seg_flag':self.instance_seg_flag}

        elif self.__class__.task_mode == 2:
            return {'mode': 2}
        elif self.__class__.task_mode == 3:
            return {'mode': 3}

