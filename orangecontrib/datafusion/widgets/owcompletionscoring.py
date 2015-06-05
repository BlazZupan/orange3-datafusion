from collections import OrderedDict

from PyQt4 import QtCore, QtGui
from Orange.widgets import widget, gui

from skfusion import fusion
from orangecontrib.datafusion.models import Relation, RelationCompleter
from orangecontrib.datafusion.widgets.owfusiongraph import \
    relation_str

import numpy as np

def scale(X, amin, amax):
    return (X - X.min()) / (X.max() - X.min()) * (amax - amin) + amin

def RMSE(A, B):
    """ NaN-skipping RMSE of masked values between the original relation `A`
        and fuser-completed relation `B`.
    """
    n, m = B.shape
    B += np.tile(np.mean(B, 1).reshape((n, 1)), (1, m))
    B += np.tile(np.mean(B, 0).reshape((1, m)), (n, 1))
    B = scale(B, 0, 1)
    A = scale(A, 0, 1)
    if np.ma.is_masked(A):
        A, B, size = A.data[~A.mask], B[~A.mask], A.size-A.mask.sum()
    else:
        A, B, size = A.data, B.data, A.size
    return np.sqrt(np.nansum((A - B)**2) / size)


class OWCompletionScoring(widget.OWWidget):
    name = 'Completion Scoring'
    priority = 40000
    icon = 'icons/CompletionScoring.svg'
    inputs = [
        ('Fitted fusion graph', RelationCompleter, 'on_fuser_change', widget.Multiple),
        ('Relation', Relation, 'on_relation_change', widget.Multiple),
    ]

    want_main_area = True
    want_control_area = False

    def __init__(self):
        super().__init__()
        self.fusers = OrderedDict()
        self.relations = OrderedDict()
        self._create_layout()

    def _create_layout(self):
        box = gui.widgetBox(self.mainArea, 'RMSE')
        BOLD_FONT = QtGui.QFont()
        BOLD_FONT.setWeight(QtGui.QFont.DemiBold)
        widget = self

        class HereTableWidget(QtGui.QTableWidget):
            def __init__(self, parent):
                super().__init__(parent)
                parent.layout().addWidget(self)
                self.setHorizontalScrollMode(self.ScrollPerPixel)
                self.setVerticalScrollMode(self.ScrollPerPixel)

            def update_table(self, fusers, relations):
                self.clear()
                self.setRowCount(0)
                self.setColumnCount(len(fusers))
                self.setHorizontalHeaderLabels([fuser[0].name for fuser in fusers.values()])
                for id, relation in relations.items():
                    row = self.rowCount()
                    self.insertRow(row)
                    if not np.ma.is_masked(relation.data):
                        widget.warning(id, 'Relation "{}" has no missing values '
                                           '(mask)'.format(relation_str(relation)))
                    rmses = []
                    for fuser in fusers.values():
                        rep_rmse = []
                        for fuserfit in fuser:
                            if not fuserfit.can_complete(relation):
                                break
                            completion = fuserfit.complete(relation)
                            rep_rmse.append(RMSE(relation.data, completion))
                        rmses.append(np.mean(rep_rmse) if rep_rmse else None)
                    min_rmse = min(e for e in rmses if e is not None)
                    for col, rmse in enumerate(rmses):
                        if rmse is None: continue
                        item = QtGui.QTableWidgetItem('{:.05f}'.format(rmse))
                        item.setFlags(QtCore.Qt.ItemIsEnabled)
                        if rmse == min_rmse and len(rmses) > 1:
                            item.setFont(BOLD_FONT)
                        self.setItem(row, col, item)
                self.setVerticalHeaderLabels([relation_str(i) for i in relations.values()])
                self.resizeColumnsToContents()
                self.resizeRowsToContents()

        self.table = HereTableWidget(box)

    def update(self):
        self.table.update_table(self.fusers, self.relations)

    def on_fuser_change(self, fuser, id):
        if fuser:
            N_RUNS = 1
            self.fusers[id] = [fuser.retrain() for _ in range(N_RUNS)]
        else: del self.fusers[id]
        self.update()

    def on_relation_change(self, relation, id):
        if relation: self.relations[id] = relation.relation
        else: del self.relations[id]
        self.warning(id, '')
        self.update()


def main():
    from sklearn.datasets import make_blobs
    import numpy as np
    from orangecontrib.datafusion.models import FittedFusionGraph
    from orangecontrib.datafusion.widgets.owmeanfuser import MeanFuser
    X, y = make_blobs(100, 3, centers=2, center_box=(-100, 100), cluster_std=10)
    X = X.astype(int)
    X += abs(X.min())

    nrows, ncols, _ = X.max(0)
    R1 = np.zeros((nrows + 1, ncols + 1))
    R1[X[:, 0], X[:, 1]] = X[:, 2]
    R1 = np.ma.array((R1 - R1.min()) / (R1.max() - R1.min()))

    _, ncols, nrows = X.max(0)
    R2 = np.zeros((nrows + 1, ncols + 1))
    R2[X[:, 2], X[:, 1]] = X[:, 0]
    R2 = np.ma.array((R2 - R2.min()) / (R2.max() - R2.min()))

    t1 = fusion.ObjectType('Users', 10)
    t2 = fusion.ObjectType('Movies', 30)
    t3 = fusion.ObjectType('Actors', 40)
    relations = [
        fusion.Relation(R1, t1, t2, name='like'),
        fusion.Relation(R2, t3, t2, name='feature in'),
    ]
    G = fusion.FusionGraph()
    for relation in relations:
        relation.data.mask = np.random.rand(*relation.data.shape) > .8
        G.add_relation(relation)
    fuserF = fusion.Dfmf()
    fuserF.fuse(G)

    from copy import deepcopy
    G = deepcopy(G)
    fuserC = fusion.Dfmc()
    fuserC.name = 'My dfmc<3'
    fuserC.fuse(G)

    app = QtGui.QApplication([])
    w = OWCompletionScoring()
    w.on_fuser_change(FittedFusionGraph(fuserF), fuserF.__class__.__name__)
    w.on_fuser_change(FittedFusionGraph(fuserC), fuserC.__class__.__name__)
    w.on_fuser_change(MeanFuser(0), 'meanfuser')
    for i, relation in enumerate(relations, 1):
        w.on_relation_change(Relation(relation), i)
    w.show()
    app.exec()


if __name__ == "__main__":
    main()
