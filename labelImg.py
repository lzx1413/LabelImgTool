#!/usr/bin/env python
# -*- coding: utf8 -*-
import codecs
import json
import logging
import os.path
import re
import subprocess
import sys
import time
from collections import defaultdict
from functools import partial

import qdarkstyle
import requests
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from libs.constants import *
from libs.ustr import ustr

from libs import RemoteDialog
from libs.canvas import Canvas
from libs.colorDialog import ColorDialog
from libs.labelDialog import LabelDialog
from libs.labelFile import LabelFile, LabelFileError
from libs.lib import struct, newAction, newIcon, addActions, fmtShortcut
from libs.appsettings import APPSettings
from libs.pascal_voc_io import PascalVocReader
from libs.shape import Shape, DEFAULT_LINE_COLOR, DEFAULT_FILL_COLOR
from libs.toolBar import ToolBar
from libs.zoomWidget import ZoomWidget
from libs.ImageManagement import loadImageThread, loadOnlineImgMul
from libs.SettingDialog import SettingDialog
from libs.save_mask_image import label_mask_writer
import resources

__appname__ = 'labelImgPlus'


# Utility functions and classes.
def have_qstring():
    '''p3/qt5 get rid of QString wrapper as py3 has native unicode str type'''
    return not (sys.version_info.major >= 3 or QT_VERSION_STR.startswith('5.'))


def util_qt_strlistclass():
    return QStringList if have_qstring() else list

class WindowMixin(object):

    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName(u'%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = range(3)

    def __init__(self, filename=None):
        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)
        # app mode 0=DET 1=SEG 2=CLS
        self.task_mode = 0
        self.mode_str = ['DET','SEG','CLS','BRU']

        # shape type
        self.shape_type = 'RECT'
        # info display
        self.display_timer = QTimer()
        self.display_timer.start(1000)
        QObject.connect(
            self.display_timer,
            SIGNAL("timeout()"),
            self.info_display)
        # label color map
        self.label_font_size = 10
        self.label_color_map = []
        self.label_color_map_path = None
        self.has_defined_color_map = False
        self.enable_color_map = True
        # online database
        self.database_url = None
        self.connect_remote_db = None
        self.dowload_thread_num = 4
        self.server_image_num = 0
        self.dowload_image_num = 0
        self.process_image_num = 0
        self.server_image_list = None

        #cls labels
        self.currentItemLabels = []
        self.selectedLabel = None

        # Save as Pascal voc xml
        self.defaultSaveDir = None
        self.usingPascalVocFormat = True
        if self.usingPascalVocFormat:
            LabelFile.suffix = '.xml'
        # For loading all image under a directory
        self.mImgList = []
        self.dirname = None
        self.image_size = []
        self.labelHist = []
        self.label_fre_dic = {}
        self.label_sub_dic = {}
        self.label_num_dic = {}
        self.lastOpenDir = None
        date = time.strftime('%Y_%m_%d_%H', time.localtime(time.time()))
        self.loadFilePath = 'database/pics/' + date + '/'

        # Whether we need to save or not.
        self.dirty = False

        # Enble auto saving if pressing next
        self.autoSaving = True
        self._noSelectionSlot = False
        self._beginner = True
        self.screencastViewer = "firefox"

        self.label_color_list = QListWidget()
        # Main widgets and related state.
        self.labelDialog = LabelDialog(parent=self, listItem=self.labelHist)
        self.labelList = QListWidget()
        self.itemsToShapes = {}
        self.shapesToItems = {}

        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)

        listLayout = QVBoxLayout()
        listLayout.setContentsMargins(0, 0, 0, 0)
        listLayout.addWidget(self.labelList)
        self.editButton = QToolButton()
        self.editButton.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.labelListContainer = QWidget()
        self.labelListContainer.setLayout(listLayout)
        self.info_txt = QTextEdit()

        listLayout.addWidget(self.editButton)  # , 0, Qt.AlignCenter)
        listLayout.addWidget(self.labelList)
        listLayout.addWidget(self.info_txt)

        self.dock = QDockWidget(u'Box Labels', self)
        self.dock.setObjectName(u'Labels')
        self.dock.setWidget(self.labelListContainer)
        # add file list add dock to move faster
        self.fileListWidget = QListWidget()
        self.fileListWidget.itemDoubleClicked.connect(
            self.fileitemDoubleClicked)
        filelistLayout = QVBoxLayout()
        filelistLayout.setContentsMargins(0, 0, 0, 0)
        filelistLayout.addWidget(self.fileListWidget)
        self.fileListContainer = QWidget()
        self.fileListContainer.setLayout(filelistLayout)
        self.filedock = QDockWidget(u'File List', self)
        self.filedock.setObjectName(u'Files')
        self.filedock.setWidget(self.fileListContainer)

        # brush tools
        self.brush_widget = QWidget()
        brush_layout = QVBoxLayout()
        brush_layout.setContentsMargins(0,0,0,0)
        self.brush_widget.setLayout(brush_layout)

        self.brush_size_sl = QSlider(Qt.Horizontal)
        self.brush_size_sl.setRange(1,20)
        self.brush_size_sl.setValue(10)
        self.brush_size_sp = QSpinBox()
        self.brush_size_sp.setRange(1,20)
        self.brush_size_sp.setValue(10)
        self.brush_size_sl.valueChanged.connect(self.brush_size_sp.setValue)
        self.brush_size_sl.valueChanged.connect(self.set_brush_size)
        brush_layout.addWidget(QLabel('brush size'))
        brush_layout.addWidget(self.brush_size_sl)
        brush_layout.addWidget(self.brush_size_sp)
        self.brush_eraser = QCheckBox(u'Brush Eraser')
        self.brush_eraser.stateChanged.connect(self.set_brush_eraser)
        brush_layout.addWidget(self.brush_eraser)
        self.brush_clear = QPushButton(u'Brush Clear')
        self.brush_clear.clicked.connect(self.set_brush_clear)
        brush_layout.addWidget(self.brush_clear)
        self.brush_dock = QDockWidget(u'Brush Tools',self)
        self.brush_dock.setObjectName(u'Brush')
        self.brush_dock.setWidget(self.brush_widget)

        # select a label
        self.labelListWidget = QListWidget()
        self.labelListWidget.itemDoubleClicked.connect(
            self.labelitemDoubleClicked)
        LabellistLayout = QVBoxLayout()
        LabellistLayout.setContentsMargins(0, 0, 0, 0)
        LabellistLayout.addWidget(self.labelListWidget)
        self.labelListContainer = QWidget()
        self.labelListContainer.setLayout(LabellistLayout)
        self.labelSelectDock = QDockWidget(u'Select Label', self)
        self.labelSelectDock.setObjectName(u'selectLabel')
        self.labelSelectDock.setFeatures(QDockWidget.DockWidgetFloatable |
                 QDockWidget.DockWidgetMovable)
        self.labelSelectDock.setWidget(self.labelListContainer)
        if self.task_mode != 2:
            self.labelSelectDock.setEnabled(False)
        # label color map dock
        self.label_color_list.itemDoubleClicked.connect(
            self.labelColorDoubleClicked
        )
        label_color_layout = QVBoxLayout()
        label_color_layout.setContentsMargins(0, 0, 0, 0)
        label_color_layout.addWidget(self.label_color_list)
        self.label_color_container = QWidget()
        self.label_color_container.setLayout(label_color_layout)
        self.label_color_dock = QDockWidget(u'Label Color Map', self)
        self.label_color_dock.setObjectName(u'label_color')
        self.label_color_dock.setWidget(self.label_color_container)

        #load predefined files
        if self.task_mode in [0,1]:
            self.loadPredefinedDETClasses()
        if self.task_mode in [2,3]:
            self.loadPredefinedCLSClasses()
        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = Canvas()
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scroll = QScrollArea()
        scroll.setWidget(self.canvas)
        scroll.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scroll.verticalScrollBar(),
            Qt.Horizontal: scroll.horizontalScrollBar()
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scroll)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        # add label color dock
        self.addDockWidget(Qt.RightDockWidgetArea, self.label_color_dock)
        # add file list and dock to move faster
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)
        #add brush tool
        self.addDockWidget(Qt.RightDockWidgetArea,self.brush_dock)
        # select label
        self.addDockWidget(Qt.RightDockWidgetArea, self.labelSelectDock)
        self.dockFeatures = QDockWidget.DockWidgetClosable \
            | QDockWidget.DockWidgetFloatable
        self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)
        # Actions
        action = partial(newAction, self)
        quit = action('&Quit', self.close,
                      'Ctrl+Q', 'quit', u'Quit application')
        open = action('&Open', self.openFile,
                      'Ctrl+O', 'open', u'Open image or label file')

        opendir = action('&Open Dir', self.openDir,
                         'Ctrl+u', 'open', u'Open Dir')
        remote_settings = action('&Remote DB Settings', self.setRemoteUrl,
                                 'Ctrl+m', u'set remote url')
        settings = action('Settings', self.setSettings, 'Ctrl+t', u'settings')
        loadOnlineImages = action(
            '&Get Images',
            self.loadOnlineImages,
            'Ctrl+l',
            icon='open',
            tip=u'load images')

        createPolygon = action(
            '&Create\nPolygon',
            self.createPolygon,
            'Ctrl+p',
            icon='new',
            tip=u'create polygon',
            enabled=False)

        changeSavedir = action(
            '&Change default saved Annotation dir',
            self.changeSavedir,
            'Ctrl+r',
            'open',
            u'Change default saved Annotation dir')

        openAnnotation = action('&Open Annotation', self.openAnnotation,
                                'Ctrl+q', 'openAnnotation', u'Open Annotation')

        openNextImg = action('&Next Image', self.openNextImg,
                             'Right', 'next', u'Open Next')

        openPrevImg = action('&Prev Image', self.openPrevImg,
                             'Left', 'prev', u'Open Prev')

        save = action('&Save', self.saveFile,
                      'Ctrl+S', 'save', u'Save labels to file', enabled=False)
        saveAs = action(
            '&Save As',
            self.saveFileAs,
            'Ctrl+Shift+S',
            'save-as',
            u'Save labels to a different file',
            enabled=False)
        close = action('&Close', self.closeFile,
                       'Ctrl+W', 'close', u'Close current file')
        color1 = action('Box &Line Color', self.chooseColor1,
                        'Ctrl+L', 'color_line', u'Choose Box line color')
        color2 = action('Box &Fill Color', self.chooseColor2,
                        'Ctrl+Shift+L', 'color', u'Choose Box fill color')

        createMode = action(
            'Create\nShape',
            self.setCreateMode,
            'Ctrl+N',
            'new',
            u'Start drawing Boxs',
            enabled=False)
        editMode = action(
            '&Edit\nRectBox',
            self.setEditMode,
            'Ctrl+J',
            'edit',
            u'Move and edit Boxs',
            enabled=False)

        createRect = action('Create\nRectBox', self.createRect,
                        'Ctrl+N', 'new', u'Draw a new Box', enabled=False)
        delete = action('Delete\nShape', self.deleteSelectedShape,
                        'Delete', 'delete', u'Delete', enabled=False)
        copy = action(
            '&Duplicate\nShape',
            self.copySelectedShape,
            'Ctrl+D',
            'copy',
            u'Create a duplicate of the selected Box',
            enabled=False)

        advancedMode = action(
            '&Advanced Mode',
            self.toggleAdvancedMode,
            'Ctrl+Shift+A',
            'expert',
            u'Switch to advanced mode',
            checkable=True)

        hideAll = action('&Hide\nShape', partial(self.togglePolygons, False),
                         'Ctrl+H', 'hide', u'Hide all Boxs',
                         enabled=False)
        showAll = action('&Show\nShape', partial(self.togglePolygons, True),
                         'Ctrl+A', 'hide', u'Show all Boxs',
                         enabled=False)

        help = action('&Tutorial', self.tutorial, 'Ctrl+T', 'help',
                      u'Show demos')

        zoom = QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            u"Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." % (fmtShortcut("Ctrl+[-+]"),
                                             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action(
            'Zoom &In',
            partial(
                self.addZoom,
                10),
            'Ctrl++',
            'zoom-in',
            u'Increase zoom level',
            enabled=False)
        zoomOut = action('&Zoom Out', partial(self.addZoom, -10),
                         'Ctrl+-', 'zoom-out', u'Decrease zoom level', enabled=False)
        zoomOrg = action(
            '&Original size',
            partial(
                self.setZoom,
                100),
            'Ctrl+=',
            'zoom',
            u'Zoom to original size',
            enabled=False)
        fitWindow = action('&Fit Window', self.setFitWindow,
                           'Ctrl+F', 'fit-window', u'Zoom follows window size',
                           checkable=True, enabled=False)
        fitWidth = action(
            'Fit &Width',
            self.setFitWidth,
            'Ctrl+Shift+F',
            'fit-width',
            u'Zoom follows window width',
            checkable=True,
            enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (
            self.zoomWidget,
            zoomIn,
            zoomOut,
            zoomOrg,
            fitWindow,
            fitWidth)
        # Group remote image manage
        remoteActions = (loadOnlineImages, remote_settings)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action(
            '&Edit Label',
            self.editLabel,
            'Ctrl+E',
            'edit',
            u'Modify the label of the selected Box',
            enabled=False)
        self.editButton.setDefaultAction(edit)

        shapeLineColor = action(
            'Shape &Line Color',
            self.chshapeLineColor,
            icon='color_line',
            tip=u'Change the line color for this specific shape',
            enabled=False)
        shapeFillColor = action(
            'Shape &Fill Color',
            self.chshapeFillColor,
            icon='color',
            tip=u'Change the fill color for this specific shape',
            enabled=False)

        labels = self.dock.toggleViewAction()
        labels.setText('Show/Hide Label Panel')
        labels.setShortcut('Ctrl+Shift+L')

        #Label list context menu.
        labelMenu = QMenu()
        addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Store actions for further handling.
        self.actions = struct(
            save=save,
            saveAs=saveAs,
            open=open,
            close=close,
            lineColor=color1,
            fillColor=color2,
            remote_mode=(
                loadOnlineImages,
                loadOnlineImages),
            createRect=createRect,
            delete=delete,
            edit=edit,
            copy=copy,
            createpolygon=createPolygon,
            createMode=createMode,
            editMode=editMode,
            advancedMode=advancedMode,
            shapeLineColor=shapeLineColor,
            shapeFillColor=shapeFillColor,
            zoom=zoom,
            zoomIn=zoomIn,
            zoomOut=zoomOut,
            zoomOrg=zoomOrg,
            fitWindow=fitWindow,
            fitWidth=fitWidth,
            zoomActions=zoomActions,
            fileMenuActions=(
                open,
                opendir,
                save,
                saveAs,
                close,
                quit),
            beginner=(),
            advanced=(),
            editMenu=(
                edit,
                copy,
                delete,
                None,
                color1,
                color2),
            beginnerContext=(
                #createRect,
                #createPolygon,
                edit,
                copy,
                delete),
            advancedContext=(
                createMode,
                createPolygon,
                editMode,
                edit,
                copy,
                delete,
                shapeLineColor,
                shapeFillColor),
            onLoadActive=(
                close,
            ),
            onDETActive =(
                createRect,
                createMode,
                editMode
            ),
            onSEGActive =(
                createPolygon,
                createMode,
                editMode
            ),
            onCLSActive =(

            ),
            onShapesPresent=(
                saveAs,
                hideAll,
                showAll))

        #tool menus settings
        self.menus = struct(
            file=self.menu('&File'),
            edit=self.menu('&Edit'),
            view=self.menu('&View'),
            help=self.menu('&Help'),
            recentFiles=QMenu('Open &Recent'),
            labelList=labelMenu)
        for item in self.actions.remote_mode:
            item.setEnabled(False)
        addActions(
            self.menus.file,
            (open,
             opendir,
             changeSavedir,
             openAnnotation,
             self.menus.recentFiles,
             save,
             saveAs,
             remote_settings,
             settings,
             close,
             None,
             quit))
        addActions(self.menus.help, (help,))
        addActions(self.menus.view, (
            labels, advancedMode,None,
            hideAll, showAll, None,
            zoomIn, zoomOut, zoomOrg, None,
            fitWindow, fitWidth))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.beginnerContext)
        addActions(self.canvas.menus[1], (
            action('&Copy here', self.copyShape),
            action('&Move here', self.moveShape)))

        self.tools = self.toolbar('Tools')
        self.actions.beginner = (
            loadOnlineImages,
            open,
            opendir,
            openNextImg,
            openPrevImg,
            save,
            None,
            createRect,
            createPolygon,
            copy,
            delete,
            None,
            zoomIn,
            zoom,
            zoomOut,
            fitWindow,
            fitWidth)

        self.actions.advanced = (
            open, save, None,
            createMode, editMode, None,
            hideAll, showAll)
        self.statusBar().showMessage('%s started.' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QImage()
        self.filename = filename
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.zoom_level = 100
        self.fit_window = False
        self.remoteMode = False
        self.app_settings = APPSettings()
        self.app_settings.load()
        settings = self.app_settings

        self.task_mode = int(settings.get(SETTING_TASK_MODE,0))
        self.canvas.task_mode = self.task_mode
        self.label_font_size = int(settings.get(SETTING_LABEL_FONT_SIZE,10))
        self.activeTaskMode()
        ## Fix the compatible issue for qt4 and qt5. Convert the QStringList to python list
        if settings.get(SETTING_RECENT_FILES):
            if have_qstring():
                recentFileQStringList = settings.get(SETTING_RECENT_FILES)
                self.recentFiles = [ustr(i) for i in recentFileQStringList]
            else:
                self.recentFiles = recentFileQStringList = settings.get(SETTING_RECENT_FILES)

        size = settings.get(SETTING_WIN_SIZE, QSize(600, 500))
        position = settings.get(SETTING_WIN_POSE, QPoint(0, 0))
        self.resize(size)
        self.move(position)
        saveDir = ustr(settings.get(SETTING_SAVE_DIR, None))
        self.lastOpenDir = ustr(settings.get(SETTING_LAST_OPEN_DIR, None))
        if saveDir is not None and os.path.exists(saveDir):
            self.defaultSaveDir = saveDir
            self.statusBar().showMessage('%s started. Annotation will be saved to %s' %
                                         (__appname__, self.defaultSaveDir))
            self.statusBar().show()

        # or simply:
        # self.restoreGeometry(settings[SETTING_WIN_GEOMETRY]
        self.restoreState(settings.get(SETTING_WIN_STATE, QByteArray()))
        self.lineColor = QColor(settings.get(SETTING_LINE_COLOR, Shape.line_color))
        self.fillColor = QColor(settings.get(SETTING_FILL_COLOR, Shape.fill_color))
        Shape.line_color = self.lineColor
        Shape.fill_color = self.fillColor
        # Add chris

        def xbool(x):
            if isinstance(x, QVariant):
                return x.toBool()
            return bool(x)

        if xbool(settings.get(SETTING_ADVANCE_MODE, False)):
            self.actions.advancedMode.setChecked(True)
            self.toggleAdvancedMode()

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time, make sure it runs in the
        # background.
        self.queueEvent(partial(self.loadFile, self.filename))
        self.queueEvent(partial(self.load_label_color_map))
        if self.has_defined_color_map and len(
                self.label_color_map) < len(
                self.labelHist):
            print(
                'the num of color is less than labels, please add some color into data/label_color_map.txt')
        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)
        self.populateModeActions()

    # infomation display
    def info_display(self):
        self.dowload_image_num = len(self.mImgList)
        info = 'server image num:\t' + str(self.server_image_num) + '\n' \
               + 'dowload image num:\t' + str(self.dowload_image_num) + '\n' \
               + 'precessed image num:\t' + str(self.process_image_num)
        self.info_txt.setText(info)

    ## Support Functions ##
    def set_brush_size(self,brush_size):
        self.canvas.brush_size = brush_size
    def set_brush_eraser(self,value):
        if value == Qt.Checked:
            self.canvas.brush_color = QColor(0,0,0,10)
            self.canvas.erase_mode = True
        else:
            self.canvas.erase_mode = False
            self.canvas.brush_color = QColor(255,0,0,255)
    def set_brush_clear(self):
        self.canvas.mask_pixmap.fill(QColor(0,0,0,128))

    def createPolygon(self):
        self.shape_type = 'POLYGON'
        self.canvas.set_shape_type(1)
        self.createShape()

    def loadOnlineImages(self):
        if self.image_list:
            t = loadImageThread(
                self.database_url,
                self.image_list,
                self.mImgList,
                self.loadFilePath)
            loadOnlineImgMul(
                self.database_url,
                self.image_list,
                2,
                self.mImgList,
                self.loadFilePath)
            while True:
                if self.mImgList:
                    self.dirname = self.loadFilePath
                    self.openNextImg()
                    break
    def activeTaskMode(self,setting_state = None):
        if self.task_mode in [0,1]:
            if  setting_state is not None:
                self.enable_color_map = setting_state['enable_color_map']
            self.labelSelectDock.setEnabled(False)
        elif self.task_mode in [2,3]:
            self.actions.delete.setEnabled(True)
            self.labelSelectDock.setEnabled(True)

    def setSettings(self):
        config = {'task_mode':self.task_mode,'label_font_size':self.label_font_size}
        settings_dialog = SettingDialog(parent=self,config = config)
        if settings_dialog.exec_():
            self.enable_color_map = settings_dialog.get_color_map_state()
            setting_state = settings_dialog.get_setting_state()
            if self.task_mode != setting_state['mode']:
                self.resetState()
                self.setClean()
            self.task_mode = setting_state['mode']
            self.canvas.task_mode = self.task_mode
            if self.task_mode == 0:
                self.label_font_size = setting_state['label_font_size']
                Shape.label_font_size = self.label_font_size
                if self.canvas:
                    self.canvas.update()
            self.activeTaskMode(setting_state)
            print 'change mode to',setting_state
        settings_dialog.destroy()

    def setRemoteUrl(self):
        setRemoteUrldialog = RemoteDialog.SetRemoteDialog(parent=self)
        if setRemoteUrldialog.exec_():
            self.database_url = 'http://' + setRemoteUrldialog.get_remote_url()
            self.remoteMode = setRemoteUrldialog.is_in_remote_mode()
            self.dowload_thread_num = setRemoteUrldialog.get_thread_num()
            self.server_image_list = setRemoteUrldialog.get_server_image_list()
        setRemoteUrldialog.destroy()
        print self.database_url
        if not os.path.exists(self.loadFilePath):
            os.makedirs(self.loadFilePath)
        if self.database_url:
            try:
                image_file = requests.get(
                    self.database_url + self.server_image_list)
            except requests.URLRequired as e:
                logging.error('can not get the server image list')
                return

            self.image_list = image_file.content.split('\n')[0:-1]
            self.server_image_num = len(self.image_list)
            if self.image_list:
                self.connect_remote_db = True
                self.toggleRemoteMode()

    def noShapes(self):
        return not self.itemsToShapes
    def toggleDETMode(self, value = True):
        pass


    def toggleAdvancedMode(self, value=True):
        self._beginner = not value
        self.canvas.setEditing(True)
        self.populateModeActions()
        self.editButton.setVisible(not value)
        if value:
            self.actions.createMode.setEnabled(True)
            self.actions.editMode.setEnabled(False)
            self.actions.remotemode
            self.dock.setFeatures(self.dock.features() | self.dockFeatures)
        else:
            self.dock.setFeatures(self.dock.features() ^ self.dockFeatures)

    def toggleRemoteMode(self):
        for item in self.actions.remote_mode:
            item.setEnabled(True)

    def fileitemDoubleClicked(self, item=None):
        currIndex = self.mImgList.index(str(item.text()))
        if currIndex < len(self.mImgList):
            filename = self.mImgList[currIndex]
            if filename:
                self.loadFile(filename)
    def labelColorDoubleClicked(self):
        # double clicked call back function
        pass
    def addCLSLabel(self,label):
        self.currentItemLabels.append(label)
        item = QListWidgetItem(label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.labelList.addItem(item)
        self.itemsToShapes[item] = label
        self.shapesToItems[label] = item
        self.labelList.addItem(item)
        self.setDirty()
    def labelitemDoubleClicked(self, item=None):
        if item:
            label = str(item.text())
            if label not in self.currentItemLabels:
                self.addCLSLabel(label)

    def populateModeActions(self):
        if self.beginner():
            tool, menu = self.actions.beginner, self.actions.beginnerContext
        else:
            tool, menu = self.actions.advanced, self.actions.advancedContext
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (self.actions.createRect,) if self.beginner() \
            else (self.actions.createMode, self.actions.editMode)
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setBeginner(self):
        self.tools.clear()
        addActions(self.tools, self.actions.beginner)

    def setAdvanced(self):
        self.tools.clear()
        addActions(self.tools, self.actions.advanced)

    def setDirty(self):
        self.dirty = True
        self.actions.save.setEnabled(True)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.createRect.setEnabled(False)
        self.actions.createpolygon.setEnabled(False)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)
        print 'app mode',self.task_mode
        if self.task_mode == 0:
            for action in self.actions.onDETActive:
                action.setEnabled(value)
        if self.task_mode == 1:
            for action in self.actions.onSEGActive:
                action.setEnabled(value)
        if self.task_mode == 0:
            for action in self.actions.onCLSActive:
                action.setEnabled(value)

    def queueEvent(self, function):
        QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.itemsToShapes.clear()
        self.shapesToItems.clear()
        self.currentItemLabels = []
        self.labelList.clear()
        self.filename = None
        self.imageData = None
        self.labelFile = None
        self.canvas.resetState()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filename):
        if filename in self.recentFiles:
            self.recentFiles.remove(filename)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filename)

    def beginner(self):
        return self._beginner

    def advanced(self):
        return not self.beginner()

    ## Callbacks ##
    def tutorial(self):
        subprocess.Popen([self.screencastViewer, self.screencast])

    def createRect(self):
        self.shape_type = 'RECT'
        self.canvas.set_shape_type(0)
        self.createShape()

    def createShape(self):
        assert self.beginner()
        self.canvas.setEditing(False)
        self.actions.createRect.setEnabled(False)
        self.actions.createpolygon.setEnabled(False)

    def toggleDrawingSensitive(self, drawing=True):
        """In the middle of drawing, toggling between modes should be disabled."""
        self.actions.editMode.setEnabled(not drawing)
        if not drawing and self.beginner():
            # Cancel creation.
            print 'Cancel creation.'
            self.canvas.setEditing(True)
            self.canvas.restoreCursor()
            self.actions.createMode.setEnabled(True)
            self.actions.createpolygon.setEnabled(True)

    def toggleDrawMode(self, edit=True):
        self.canvas.setEditing(edit)
        self.actions.createMode.setEnabled(edit)
        self.actions.editMode.setEnabled(not edit)

    def setCreateMode(self):
        assert self.advanced()
        self.toggleDrawMode(False)

    def setEditMode(self):
        assert self.advanced()
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        current = self.filename

        def exists(filename):
            return os.path.exists(unicode(filename))

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != current and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QAction(
                icon, '&%d %s' % (i + 1, QFileInfo(f).fileName()), self)
            action.triggered.connect(partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def editLabel(self, item=None):
        # TODO: construct this once
        if self.label_sub_dic:
            self.labelDialog = LabelDialog(
                parent=self,
                sub_label_items=self.label_sub_dic,
                label_fre_dic=self.label_fre_dic)
        elif len(self.labelHist) > 0:
            self.labelDialog = LabelDialog(
                parent=self,
                listItem=self.labelHist,
                label_fre_dic=self.label_fre_dic)
        if not self.canvas.editing():
            return
        item = item if item else self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is not None:
            item.setText(text)
            self.setDirty()

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                self.labelList.setItemSelected(self.shapesToItems[shape], True)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)
        print 'shapeSelectionChanged'

    def addLabel(self, shape):
        item = QListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.itemsToShapes[item] = shape
        self.shapesToItems[shape] = item
        self.labelList.addItem(item)
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape = None,label = None):
        if self.task_mode in [0,1]:
            item = self.shapesToItems[shape]
            temp = self.labelList.takeItem(self.labelList.row(item))
            temp = None
            del self.shapesToItems[shape]
            del self.itemsToShapes[item]
        elif self.task_mode == 2:
            items = self.labelList.selectedItems()
            for item in items:
                temp = self.labelList.takeItem(self.labelList.row(item))
                temp = None
            self.currentItemLabels.remove(label)
            del self.shapesToItems[label]
            del self.itemsToShapes[item]


    def loadLabels(self, shapes):
        s = []
        if self.task_mode in [0,1]:
            for label, points, line_color, fill_color, shape_type in shapes:
                shape = Shape(label=label, shape_type=shape_type)
                assert isinstance(shape_type, int)
                if self.task_mode == 0 and shape_type == 0 or self.task_mode == 1 and shape_type == 1:
                    for x, y in points:
                        shape.addPoint(QPointF(x, y))
                    shape.close()
                    if label not in self.labelHist:
                        self.labelHist.append(label)
                    if self.enable_color_map:
                        shape.fill_color = self.label_color_map[
                                self.label_num_dic[label]]
                    s.append(shape)
                    self.addLabel(shape)
                    if not self.enable_color_map:
                        if line_color:
                            shape.line_color = QColor(*line_color)
                        if fill_color:
                            shape.fill_color = QColor(*fill_color)
                if s:
                    self.canvas.loadShapes(s)



    def saveLabels(self, filename):
        lf = LabelFile()

        def format_shape(s):
            return dict(
                label=unicode(
                    s.label),
                line_color=s.line_color.getRgb() if s.line_color != self.lineColor else None,
                fill_color=s.fill_color.getRgb() if s.fill_color != self.fillColor else None,
                points=[
                    (p.x(),
                     p.y()) for p in s.points],
                shape_type=s.shape_type)

        shapes = [format_shape(shape) for shape in self.canvas.shapes]
        print 'shape type', self.shape_type
        imgFileName = os.path.basename(self.filename)
        if self.task_mode == 1:#seg mode
            with open(self.defaultSaveDir + 'label_num_dic.json', 'w') as label_num_file:
                for key in self.label_num_dic:
                    print type(key)
                json.dump(self.label_num_dic, label_num_file)
            # the mask image will be save as file_mask.png etc.
            result_path = self.defaultSaveDir + \
                os.path.splitext(imgFileName)[0] + '_mask.png'
            mask_writer = label_mask_writer(
                self.label_num_dic,
                result_path,
                self.image_size[0],
                self.image_size[1])
            mask_writer.save_mask_image(shapes)
        # Can add differrent annotation formats here
        if self.task_mode in [0,1]:# seg and det mode
            try:
                if self.usingPascalVocFormat is True:
                    
                    savefilename = self.defaultSaveDir + os.path.splitext(imgFileName)[0] + '.xml'  # the mask image will be save as file_mask.jpg etc.
                    print 'savePascalVocFommat save to:' + savefilename
                    lf.savePascalVocFormat(
                        savefilename, self.image_size, shapes, unicode(
                            self.filename), shape_type_=self.shape_type)
                    self.process_image_num += 1
                else:
                    lf.save(
                        filename,
                        shapes,
                        unicode(
                            self.filename),
                        self.imageData,
                        self.lineColor.getRgb(),
                        self.fillColor.getRgb())
                    self.labelFile = lf
                    self.filename = filename
                    self.process_image_num += 1
                return True
            except LabelFileError as e:
                self.errorMessage(u'Error saving label data',
                                  u'<b>%s</b>' % e)
                return False
        elif self.task_mode == 2:#cls mode
            savefilename = self.defaultSaveDir + os.path.splitext(imgFileName)[0] + '.txt' # the mask image will be save as file_mask.jpg etc.
            print savefilename
            with codecs.open(savefilename,'w','utf8') as outfile:
                for item in self.currentItemLabels:
                    outfile.write(item+'\n')
        elif self.task_mode == 3:#brush mode
            savefilename = self.defaultSaveDir + os.path.splitext(imgFileName)[0] + '.png' # the mask image will be save as file_mask.jpg etc.
            mask_img = self.canvas.get_mask_image()
            if mask_img:
                mask_img.save(savefilename)





    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def labelSelectionChanged(self):
        item = self.currentItem()
        if self.task_mode in [0,1]:
            if item and self.canvas.editing():
                self._noSelectionSlot = True
                self.canvas.selectShape(self.itemsToShapes[item])
        elif self.task_mode == 2:
            if item:
                self.selectedLabel = self.itemsToShapes[item]

    def labelItemChanged(self, item):
        shape = self.itemsToShapes[item]
        label = unicode(item.text())
        if label != shape.label:
            shape.label = unicode(item.text())
            self.setDirty()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:
    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        if self.label_sub_dic:
            self.labelDialog = LabelDialog(
                parent=self,
                sub_label_items=self.label_sub_dic,
                label_fre_dic=self.label_fre_dic)
        elif len(self.labelHist) > 0:
            self.labelDialog = LabelDialog(
                parent=self,
                listItem=self.labelHist,
                label_fre_dic=self.label_fre_dic)

        text = self.labelDialog.popUp()
        text = str(text)
        if text is not None:
            if str(text) in self.label_fre_dic:
                self.label_fre_dic[str(text)] += 1
            else:
                self.label_fre_dic[str(text)] = 1
            new_shape = self.canvas.setLastLabel(text)
            if self.enable_color_map:
                fill_color = self.label_color_map[
                    self.label_num_dic[text]]
                new_shape.fill_color = QColor(fill_color[0],fill_color[1],fill_color[2],fill_color[3])
            self.addLabel(self.canvas.setLastLabel(text))
            if self.beginner():  # Switch to edit mode.
                self.canvas.setEditing(True)
                self.actions.createMode.setEnabled(True)
                if self.task_mode == 0:
                    self.actions.createRect.setEnabled(True)
                elif self.task_mode == 1:
                    self.actions.createpolygon.setEnabled(True)
            else:
                self.actions.editMode.setEnabled(True)
            self.setDirty()

            if text not in self.labelHist:
                if not self.labelHist:
                    self.label_num_dic[str(text)] = 1
                else:
                    self.label_num_dic[text] = max(
                        self.label_num_dic.values()) + 1
                item = QListWidgetItem(text)
                self.label_color_list.addItem(item)
                self.labelHist.append(text)
        else:
            # self.canvas.undoLastLine()
            self.canvas.resetAllLines()

    def scrollRequest(self, delta, orientation):
        units = - delta / (8 * 15)
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)

    def zoomRequest(self, delta):
        units = delta / (8 * 15)
        scale = 10
        self.addZoom(scale * units)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.itemsToShapes.iteritems():
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)
    def loadCLSFile(self,filepath):
        if os.path.exists(filepath):
            with open(filepath) as infile:
                lines = infile.readlines()
                for line in lines:
                    label = line.strip()
                    self.addCLSLabel(label)
    def loadBRUFile(self,filepath):
        mask_img = QImage(filepath)
        self.canvas.loadMaskmap(mask_img)

    def loadFile(self, filename=None):
        """Load the specified file, or the last opened file if None."""
        self.resetState()
        self.canvas.setEnabled(False)
        if filename is None:
            if self.app_settings.get(SETTING_FILENAME):
                filename = self.app_settings[SETTING_FILENAME]
        filename = unicode(filename)
        if filename and self.fileListWidget.count() > 0:
            index = self.mImgList.index(filename)
            fileWidgetItem = self.fileListWidget.item(index)
            self.fileListWidget.setItemSelected(fileWidgetItem, True)
        if QFile.exists(filename):
            if LabelFile.isLabelFile(filename):
                try:
                    self.labelFile = LabelFile(filename)
                except LabelFileError as e:
                    self.errorMessage(
                        u'Error opening file', (u"<p><b>%s</b></p>"
                                                u"<p>Make sure <i>%s</i> is a valid label file.") %
                        (e, filename))
                    self.status("Error reading %s" % filename)
                    return False
                self.imageData = self.labelFile.imageData
                self.lineColor = QColor(*self.labelFile.lineColor)
                self.fillColor = QColor(*self.labelFile.fillColor)
            else:
                # Load image:
                # read data first and store for saving into label file.
                self.imageData = read(filename, None)
                self.labelFile = None
            image = QImage.fromData(self.imageData)
            if image.isNull():
                self.errorMessage(
                    u'Error opening file',
                    u"<p>Make sure <i>%s</i> is a valid image file." %
                    filename)
                self.status("Error reading %s" % filename)
                return False
            self.status("Loaded %s" % os.path.basename(unicode(filename)))
            self.setWindowTitle(
                __appname__ +
                ' ' + self.mode_str[self.task_mode] + ' ' +
                os.path.basename(
                    unicode(filename)))
            self.image = image
            self.image_size = []  # image size should be clear
            self.image_size.append(image.height())
            self.image_size.append(image.width())
            self.image_size.append( 1 if image.isGrayscale() else 3)
            self.filename = filename
            self.canvas.loadPixmap(image)
            if self.labelFile:
                self.loadLabels(self.labelFile.shapes)
            self.setClean()
            self.canvas.setEnabled(True)
            self.adjustScale(initial=True)
            self.paintCanvas()
            self.addRecentFile(self.filename)
            self.toggleActions(True)

            # Label xml file and show bound box according to its filename
            basename = os.path.basename(os.path.splitext(self.filename)[0])
            if self.task_mode in [0,1]:
                if self.usingPascalVocFormat is True and \
                        self.defaultSaveDir is not None:
                    xmlPath = os.path.join(self.defaultSaveDir, basename + '.xml')
                    self.loadPascalXMLByFilename(xmlPath)
                    if self.shape_type == 'POLYGON':
                        self.canvas.set_shape_type(1)
                    elif self.shape_type == 'RECT':
                        self.canvas.set_shape_type(0)
            elif self.task_mode == 2:
                if self.defaultSaveDir is not None:
                    txtPath = os.path.join(self.defaultSaveDir, basename + '.txt')
                    self.loadCLSFile(txtPath)
            elif self.task_mode == 3:
                if self.defaultSaveDir is not None:
                    maskPath = os.path.join(self.defaultSaveDir, basename + '.png')
                    self.loadBRUFile(maskPath)

            return True
        return False

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull() \
                and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "cannot paint null image"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap in order to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.bg_image.width() - 0.0
        h2 = self.canvas.bg_image.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.bg_image.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        settings = self.app_settings
        # If it loads images from dir, don't load it at the begining
        if self.dirname is None:
            settings[SETTING_FILENAME] = self.filePath if self.filePath else ''
        else:
            settings[SETTING_FILENAME] = ''

        settings[SETTING_WIN_SIZE] = self.size()
        settings[SETTING_TASK_MODE] = self.task_mode
        settings[SETTING_LABEL_FONT_SIZE] = self.label_font_size
        settings[SETTING_WIN_POSE] = self.pos()
        settings[SETTING_WIN_STATE] = self.saveState()
        settings[SETTING_LINE_COLOR] = self.lineColor
        settings[SETTING_FILL_COLOR] = self.fillColor
        settings[SETTING_RECENT_FILES] = self.recentFiles
        settings[SETTING_ADVANCE_MODE] = not self._beginner
        if self.defaultSaveDir is not None and len(self.defaultSaveDir) > 1:
            settings[SETTING_SAVE_DIR] = ustr(self.defaultSaveDir)
        else:
            settings[SETTING_SAVE_DIR] = ""

        if self.lastOpenDir is not None and len(self.lastOpenDir) > 1:
            settings[SETTING_LAST_OPEN_DIR] = self.lastOpenDir
        else:
            settings[SETTING_LAST_OPEN_DIR] = ""
        settings.save()

    ## User Dialogs ##

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def scanAllImages(self, folderPath):
        extensions = ['.jpeg', '.jpg', '.png', '.bmp']
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relatviePath = os.path.join(root, file)
                    images.append(os.path.abspath(relatviePath))
        images.sort(key=lambda x: x.lower())
        print images
        return images

    def changeSavedir(self, _value=False):
        if self.defaultSaveDir is not None:
            path = unicode(self.defaultSaveDir)
        else:
            path = '.'

        dirpath = unicode(
            QFileDialog.getExistingDirectory(
                self,
                '%s - Save to the directory' %
                __appname__,
                path,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.defaultSaveDir = dirpath

        self.statusBar().showMessage(
            '%s . Annotation will be saved to %s' %
            ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()

    def openAnnotation(self, _value=False):
        if self.filename is None:
            return

        path = os.path.dirname(unicode(self.filename)) \
            if self.filename else '.'
        if self.usingPascalVocFormat:
            formats = ['*.%s' % unicode(fmt).lower()
                       for fmt in QImageReader.supportedImageFormats()]
            filters = "Open Annotation XML file (%s)" % \
                      ' '.join(formats + ['*.xml'])
            filename = unicode(
                QFileDialog.getOpenFileName(
                    self, '%s - Choose a xml file' %
                    __appname__, path, filters))
            self.loadPascalXMLByFilename(filename)

    def openDir(self, _value=False):
        '''
        the default save files is orgnized as fellow:
        image_file:
                  image_file1:
                  image_file2:
                  ...
        Annotation:
                   image_file1:
                   image_file2:
                   ...
        :param _value:
        :return:
        '''
        if not self.mayContinue():
            return

        path = os.path.dirname(unicode(self.filename)) \
            if self.filename else '.'

        if self.lastOpenDir is not None and len(self.lastOpenDir) > 1:
            path = self.lastOpenDir

        dirpath = unicode(
            QFileDialog.getExistingDirectory(
                self,
                '%s - Open Directory' %
                __appname__,
                path,
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks))

        if dirpath is not None and len(dirpath) > 1:
            self.lastOpenDir = dirpath

        self.dirname = dirpath
        if '/' in dirpath:
            path_elem = dirpath.split('/')[:-2]
            last_path_elem = dirpath.split('/')[-1]
            s = '/'
            self.defaultSaveDir = s.join(
                path_elem) + '/Annotation' + '/' + last_path_elem + '/'
            if not os.path.exists(self.defaultSaveDir):
                os.makedirs(self.defaultSaveDir)
                # for windows
        elif '\\' in dirpath:
            path_elem = dirpath.split('\\')[:-1]
            last_path_elem = dirpath.split('\\')[-1]
            s = '\\'
            self.defaultSaveDir = s.join(
                path_elem) + '\\Annotation' + '\\' + last_path_elem + '\\'
            if not os.path.exists(self.defaultSaveDir):
                os.makedirs(self.defaultSaveDir)
        self.statusBar().showMessage(
            '%s . Annotation will be saved to %s' %
            ('Change saved folder', self.defaultSaveDir))
        self.statusBar().show()
        self.mImgList = self.scanAllImages(dirpath)
        self.filename = None
        self.openNextImg()
        for imgPath in self.mImgList:
            item = QListWidgetItem(imgPath)
            self.fileListWidget.addItem(item)

    def openPrevImg(self, _value=False):
        if self.autoSaving is True and self.defaultSaveDir is not None:
            if self.dirty is True and self.hasLabels():
                self.saveFile()
        #if not self.mayContinue():
        #    return

        if len(self.mImgList) <= 0:
            return

        if self.filename is None:
            return

        currIndex = self.mImgList.index(self.filename)
        if currIndex - 1 >= 0:
            filename = self.mImgList[currIndex - 1]
            if filename:
                self.loadFile(filename)

    def openNextImg(self, _value=False):
        # Proceding next image without dialog if having any label
        if self.autoSaving is True and self.defaultSaveDir is not None and not self.image.isNull():
            if self.dirty is True or self.task_mode == 3:
                self.saveFile()

       # if not self.mayContinue():
        #    return

        if len(self.mImgList) <= 0:
            return

        if self.filename is None:
            filename = self.mImgList[0]
        else:
            currIndex = self.mImgList.index(self.filename)
            if currIndex + 1 < len(self.mImgList):
                filename = self.mImgList[currIndex + 1]
            else:
                QMessageBox.about(self, "no more images !",
                                  "this is the last image")
                return

        if filename:
            self.loadFile(filename)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(unicode(self.filename)) \
            if self.filename else '.'
        formats = ['*.%s' % unicode(fmt).lower()
                   for fmt in QImageReader.supportedImageFormats()]
        if '*.jpg' not in formats:
            formats.append('*.jpg')
        if '*.jpeg' not in formats:
            formats.append('*.jpeg')
        filters = "Image & Label files (%s)" % \
                  ' '.join(formats + ['*%s' % LabelFile.suffix])
        filename = unicode(
            QFileDialog.getOpenFileName(
                self, '%s - Choose Image or Label file' %
                __appname__, path, filters))
        if filename:
            self.loadFile(filename)

    def saveFile(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.hasLabels():
            if self.defaultSaveDir is not None and len(
                    str(self.defaultSaveDir)):
                print 'handle the image:' + self.filename
                self._saveFile(self.filename)
            else:
                self._saveFile(self.filename if self.labelFile
                               else self.saveFileDialog())
        elif self.task_mode == 3:
            self._saveFile(self.filename)
        else:
            imgFileName = os.path.basename(self.filename)
            if self.task_mode in [0,1]:
                savedFileName = os.path.splitext(
                imgFileName)[0] + LabelFile.suffix
            elif self.task_mode in [2,3]:
                savedFileName = os.path.splitext(
                imgFileName)[0] + '.txt'
            savedPath = os.path.join(
            str(self.defaultSaveDir), savedFileName)
            if os.path.isfile(savedPath):
                os.remove(savedPath)

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "cannot save empty image"
        if self.hasLabels():
            self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = '%s - Choose File' % __appname__
        filters = 'File (*%s)' % LabelFile.suffix
        openDialogPath = self.currentPath()
        dlg = QFileDialog(self, caption, openDialogPath, filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QFileDialog.AcceptSave)
        dlg.setConfirmOverwrite(True)
        filenameWithoutExtension = os.path.splitext(self.filename)[0]
        dlg.selectFile(filenameWithoutExtension)
        dlg.setOption(QFileDialog.DontUseNativeDialog, False)
        if dlg.exec_():
            return dlg.selectedFiles()[0]
        return ''

    def _saveFile(self, filename):
        if filename and self.saveLabels(filename):
            self.addRecentFile(filename)
            self.setClean()
            self.statusBar().showMessage('Saved to  %s' % filename)
            self.statusBar().show()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    # Message Dialogs. #
    def hasLabels(self):
        if self.task_mode in [0,1]:
            if not self.itemsToShapes:
                # self.errorMessage(u'No objects labeled',
                # u'You must label at least one object to save the file.')
                return False
            return True
        elif self.task_mode in [2,3]:
            if not self.currentItemLabels:
                return False
            return True

    def mayContinue(self):
        return not (self.dirty and not self.discardChangesDialog())

    def discardChangesDialog(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You have unsaved changes, proceed anyway?'
        return yes == QMessageBox.warning(self, u'Attention', msg, yes | no)

    def errorMessage(self, title, message):
        return QMessageBox.critical(self, title,
                                    '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(unicode(self.filename)
                               ) if self.filename else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            # Change the color for all shape lines:
            Shape.line_color = self.lineColor
            self.canvas.update()
            self.setDirty()

    def chooseColor2(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.fillColor = color
            Shape.fill_color = self.fillColor
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        yes, no = QMessageBox.Yes, QMessageBox.No
        msg = u'You are about to permanently delete this Box, proceed anyway?'
        if yes == QMessageBox.warning(self, u'Attention', msg, yes | no):
            self.remLabel(shape=self.canvas.deleteSelected(),label=self.selectedLabel)
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(self.lineColor, u'Choose line color',
                                          default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(self.fillColor, u'Choose fill color',
                                          default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()


    def load_label_color_map(self):
        if not self.label_color_map:
            self.label_color_map = []
        if self.label_color_map_path is None:
            self.label_color_map_path = os.path.join(
                'data', 'label_color_map.txt')
        if os.path.exists(self.label_color_map_path):
            with codecs.open(self.label_color_map_path, 'r', 'utf-8') as f:
                lines = f.readlines()
                print 'color map', lines
                for line in lines:
                    line = line.strip()
                    line = line.split(',')
                    line = [int(num) for num in line]
                    # RGBA
                    if len(line) == 4:
                        self.label_color_map.append(
                            [line[0], line[1], line[2], line[3]])
                    elif len(line) == 3:
                        self.label_color_map.append(
                            [line[0], line[1], line[2], 128])
                    else:
                        print('the num of color is wrong')
                self.has_defined_color_map = True
        else:
            self.label_color_map = [color+[128] for color in COLORMAP.values()]
            print(self.label_color_map)
    def loadPredefinedCLSClasses(self):
        self.labelHist = []
        predefined_classes_path = os.path.join(
            'data','predefined_cls_classes.txt'
        )
        if os.path.exists(predefined_classes_path) is True:
            with codecs.open(predefined_classes_path,'r','utf8') as f:
                lines = f.readlines()
                for line in lines:
                    line = line.strip()
                    if self.labelHist is None:
                        self.lablHist = [line]
                    else:
                        self.labelHist.append(line)
        if self.labelHist:
            num = 0
            assert len(
                self.labelHist) <= 255, 'the num of labels should be less than 255 '
            for label in self.labelHist:
                # label - index
                self.label_num_dic[label] = num
                num += 1
        #add label to widget
        for cls_label in self.labelHist:
            item = QListWidgetItem(cls_label)
            self.labelListWidget.addItem(item)
            #self.labelListWidget.addItem(item)


    def loadPredefinedDETClasses(self):
        self.labelHist = []
        predefined_classes_path = os.path.join(
            'data', 'predefined_classes.txt')
        predefined_subclasses_path = os.path.join(
            'data', 'predefined_sub_classes.txt')
        if os.path.exists(predefined_subclasses_path) is True:
            with codecs.open(predefined_subclasses_path, 'r', 'utf8') as f:
                lines = f.readlines()
                print lines
                for line in lines:
                    line = line.strip()
                    line = line.split(':')
                    label_list = line[1].strip().split(' ')
                    self.label_sub_dic[line[0]] = label_list
                    self.labelHist = self.labelHist + label_list
            print self.label_sub_dic
        elif os.path.exists(predefined_classes_path) is True:
            with codecs.open(predefined_classes_path,'r','utf8') as f:
                for line in f:
                    line = line.strip()
                    if self.labelHist is None:
                        self.lablHist = [line]
                        self.label_fre_dic[line] = 0
                    else:
                        self.labelHist.append(line)
                        self.label_fre_dic[line] = 0
        if self.labelHist:
            num = 1
            assert len(
                self.labelHist) <= 255, 'the num of labels should be less than 255 '
            for label in self.labelHist:
                #label - color
                item = QListWidgetItem(label)
                self.label_color_list.addItem(item)
                # label - index
                self.label_num_dic[label] = num
                num += 1

    def loadPascalXMLByFilename(self, filename):
        if self.filename is None:
            return
        if os.path.exists(filename) is False:
            return

        tVocParseReader = PascalVocReader(filename)
        shapes = tVocParseReader.getShapes()
        self.loadLabels(shapes)
        self.shape_type = tVocParseReader.getShapeType()


class Settings(object):
    """Convenience dict-like wrapper around QSettings."""

    def __init__(self, types=None):
        self.data = QSettings()
        self.types = defaultdict(lambda: QVariant, types if types else {})

    def __setitem__(self, key, value):
        t = self.types[key]
        self.data.setValue(key,
                           t(value) if not isinstance(value, t) else value)

    def __getitem__(self, key):
        return self._cast(key, self.data.value(key))

    def get(self, key, default=None):
        return self._cast(key, self.data.value(key, default))

    def _cast(self, key, value):
        # XXX: Very nasty way of converting types to QVariant methods :P
        t = self.types[key]
        if t != QVariant:
            method = getattr(QVariant, re.sub('^Q', 'to', t.__name__, count=1))
            return method(value)
        return value


def inverted(color):
    return QColor(*[255 - v for v in color.getRgb()])


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except:
        return default


def main(argv):
    """Standard boilerplate Qt application code."""
    app = QApplication(argv)
    app.setStyleSheet(qdarkstyle.load_stylesheet(pyside=False))
    app.setApplicationName(__appname__)
    app.setWindowIcon(newIcon("app"))
    win = MainWindow(argv[1] if len(argv) == 2 else None)
    win.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main(sys.argv))
