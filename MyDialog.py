from PyQt4 import QtGui, QtCore
import re
class SetRemoteDialog(QtGui.QDialog):
    def __init__(self, parent=None):
        QtGui.QDialog.__init__(self, parent)
        self.resize(240, 200)
        grid = QtGui.QGridLayout()
        grid.addWidget(QtGui.QLabel(u'name', parent=self), 0, 0, 1, 1)
        self.remote_url = QtGui.QLineEdit(parent=self)
        grid.addWidget(self.remote_url, 0, 1, 1, 1)
        buttonBox = QtGui.QDialogButtonBox(parent=self)
        buttonBox.setOrientation(QtCore.Qt.Horizontal)
        buttonBox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
        buttonBox.accepted.connect(self.accept)
        buttonBox.rejected.connect(self.reject)
        layout = QtGui.QVBoxLayout()
        layout.addLayout(grid)
        spacerItem = QtGui.QSpacerItem(20, 48, QtGui.QSizePolicy.Minimum, QtGui.QSizePolicy.Expanding)
        layout.addItem(spacerItem)

        layout.addWidget(buttonBox)

        self.setLayout(layout)
    def get_remote_url(self):
        origin_url = self.remote_url.text()
        if re.match(r'^https?:/{2}\w.+$',origin_url):
            return origin_url



