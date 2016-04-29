from PyQt4 import QtGui, QtCore
import socket
import re


class SetRemoteDialog(QtGui.QDialog):
    remote_mode = True
    remote_url = ""
    dowload_thead_num = 4

    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.resize(320, 100)
        self.remote_cb = QtGui.QCheckBox("use remote database")
        if self.__class__.remote_mode:
            self.remote_cb.toggle()
        self.remote_cb.stateChanged.connect(self.set_remote_mode)
        grid = QtGui.QGridLayout()
        grid.addWidget(self.remote_cb, 0, 0, 1, 1)
        grid.addWidget(QtGui.QLabel(u'dowload image thread num', parent=self), 1, 0, 1, 1)
        self.thread_num = QtGui.QSpinBox()
        self.thread_num.setRange(1, 10)
        self.thread_num.setValue(self.__class__.dowload_thead_num)
        self.thread_num.valueChanged.connect(self.set_thread_num)
        grid.addWidget(self.thread_num, 1, 1, 1, 1)
        grid.addWidget(QtGui.QLabel(u'remote db url[123.57.438.245/]', parent=self), 2, 0, 1, 1)
        self.remote_url_line = QtGui.QLineEdit(parent=self)
        if self.__class__.remote_url:
            self.remote_url_line.setText(self.__class__.remote_url)
        grid.addWidget(self.remote_url_line, 2, 1, 1, 1)
        buttonBox = QtGui.QDialogButtonBox(parent=self)
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel | QtGui.QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout = QtGui.QVBoxLayout()
        layout.addLayout(grid)
        spacerItem = QtGui.QSpacerItem(20, 48, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        layout.addItem(spacerItem)
        layout.addWidget(buttonBox)
        self.setLayout(layout)

    def test_remote_url(self, url, port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((url, port))
            return True
        except socket.error, e:
            return False
        finally:
            sock.close()

    def set_remote_mode(self, state):
        if state == QtCore.Qt.Checked:
            self.__class__.remote_mode = True
        else:
            self.__class__.remote_mode = False

    def set_thread_num(self, num):
        self.__class__.dowload_thead_num = num

    def get_thread_num(self):
        return self.__class__.dowload_thead_num

    def is_in_remote_mode(self):
        return self.__class__.remote_mode

    def get_remote_url(self):
        origin_url = self.remote_url_line.text()
        if re.match(r'\w.+$', origin_url):
            if self.test_remote_url(origin_url.split('/')[0], 80):
                self.__class__.remote_url = origin_url
                return self.__class__.remote_url
            else:
                QtGui.QMessageBox.about(self, "server connect error!", "can not connect the server")

        else:
            QtGui.QMessageBox.about(self, "url format error!",
                                    "the url is not in the correct format \n such as 1.1.1.1/sf/")
