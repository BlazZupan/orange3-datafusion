import sys
import copy
import Orange.data.table
from PyQt4 import QtGui
from PyQt4.QtCore import Qt
from Orange.widgets.widget import OWWidget
from Orange.widgets import widget, gui, settings
from orangecontrib.datafusion.movielens import hide_data, SampleBy
from orangecontrib.datafusion.models import Relation

import numpy as np


class Output:
    IN_SAMPLE_DATA = "In-sample Data"
    OUT_OF_SAMPLE_DATA = "Out-of-sample Data"


class OWSampleMatrix(OWWidget):
    name = "Matrix Sampler"
    priority = 60000
    icon = "icons/MatrixSampler.svg"
    want_main_area = False
    description = "Sample a data matrix"
    inputs = [("Data", Orange.data.table.Table, "set_data", widget.Default)]
    outputs = [(Output.IN_SAMPLE_DATA, Relation),
               (Output.OUT_OF_SAMPLE_DATA, Relation)]

    percent = settings.Setting(90)
    method = settings.Setting(0)
    bools = settings.Setting([])

    def __init__(self):
        super().__init__()
        self.relation = None

        form = QtGui.QGridLayout()
        methodbox = gui.radioButtonsInBox(
            self.controlArea, self, "method", [],
            box=self.tr("Sampling method"), orientation=form)

        rows = gui.appendRadioButton(methodbox, "Rows", addToLayout=False)
        form.addWidget(rows, 0, 0, Qt.AlignLeft)

        cols = gui.appendRadioButton(methodbox, "Columns", addToLayout=False)
        form.addWidget(cols, 0, 1, Qt.AlignLeft)

        rows_and_cols = gui.appendRadioButton(methodbox, "Rows and columns", addToLayout=False)
        form.addWidget(rows_and_cols, 1, 0, Qt.AlignLeft)

        entries = gui.appendRadioButton(methodbox, "Entries", addToLayout=False)
        form.addWidget(entries, 1, 1, Qt.AlignLeft)

        sample_size = gui.widgetBox(self.controlArea, "Proportion of data in the sample")
        percent = gui.hSlider(
            sample_size, self, 'percent', minValue=1, maxValue=100, step=5,
            ticks=10, labelFormat=" %d%%")

        gui.button(self.controlArea, self, "&Apply",
                   callback=self.send_output, default=True)

        self.setSizePolicy(
            QtGui.QSizePolicy(QtGui.QSizePolicy.Fixed,
                              QtGui.QSizePolicy.Fixed))

        self.setMinimumWidth(250)
        self.send_output()

    def set_data(self, data):
        self.relation = data
        self.send_output()

    def send_output(self):
        if self.relation is not None:
            sample_mask, oos_mask = hide_data(self.relation,
                                              self.percent / 100,
                                              SampleBy.all[self.method])
            def _mask_relation(relation, mask):
                if np.ma.is_masked(relation.data):
                    mask = np.logical_or(mask, relation.data.mask)
                data = copy.copy(relation)
                data.data = np.ma.array(data.data, mask=mask)
                return data

            sample_data = _mask_relation(self.relation.relation, sample_mask)
            oos_data = _mask_relation(self.relation.relation, oos_mask)

            self.send(Output.IN_SAMPLE_DATA, Relation(sample_data))
            self.send(Output.OUT_OF_SAMPLE_DATA, Relation(oos_data))


if __name__ == "__main__":
    app = QtGui.QApplication(sys.argv)
    ow = OWSampleMatrix()
    # ow.set_data(Orange.data.Table("housing.tab"))
    ow.send_output()
    ow.show()
    app.exec_()
