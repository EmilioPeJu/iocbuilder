from PyQt5.QtCore import Qt, QVariant
from PyQt5.QtWidgets import QUndoCommand

class ChangeValueCommand(QUndoCommand):
    def __init__(self, row, column, value, model):
        QUndoCommand.__init__(self)
        self.old = model.rows[row][column]
        # to ensure we are working with a QVariant
        qvar = QVariant(value)
        self.new = qvar
        self.row = row
        self.column = column
        self.model = model
        label = str(qvar.value())
        if "\n" in label or len(label) > 20:
            label = str(label).splitlines()[0].rstrip()[:18] + "..."
        self.setText('Row %s: Set %s = "%s"' %
            (row + 1, str(model._header[column].value()), label))

    def _do(self, new, old):
        if str(new.value()) == '':
            new = QVariant()
        elif str(new.value()) == '""':
            new = QVariant('')

        self.model.rows[self.row][self.column] = new

        if self.column == 0:
            # commented or uncommented
            index1 = self.model.index(self.row, 0)
            index2 = self.model.index(self.row, self.model.columnCount()-1)
        elif self.column==1:
            # we have just changed the object name, other objects might
            # reference it
            index1 = self.model.index(0, 0)
            index2 = self.model.index(
                self.model.rowCount()-1, self.model.columnCount()-1)
        else:
            # just changed this cell
            index1 = self.model.index(self.row, self.column)
            index2 = index1
        self.model.dataChanged.emit(index1, index2)

    def redo(self):
        self._do(self.new, self.old)

    def undo(self):
        self._do(self.old, self.new)


class RowCommand(QUndoCommand):
    def __init__(self, row, model, parent, add = True):
        QUndoCommand.__init__(self)
        self.row = row
        self.add = add
        self.model = model
        self._parent = parent
        if add:
            self.rowdata = [ QVariant() for x in model._header ]
            self.setText('Inserted Row %s' % (row + 1))
        else:
            self.rowdata = [ QVariant(x) for x in model.rows[row] ]
            self.setText('Removed Row %s' % (row + 1))

    def addRow(self):
        self.model.beginInsertRows(self._parent, self.row, self.row)
        self.model.rows = \
            self.model.rows[:self.row] + [self.rowdata] + \
            self.model.rows[self.row:]
        self.model.endInsertRows()
        self.emitDataChanged()

    def removeRow(self):
        self.model.beginRemoveRows(self._parent, self.row, self.row)
        self.model.rows = \
            self.model.rows[:self.row] + self.model.rows[self.row + 1:]
        self.model.endRemoveRows()
        self.emitDataChanged()

    def emitDataChanged(self):
        # say which rows we've changed
        index1 = self.model.index(self.row, 0)
        index2 = self.model.index(
            self.model.rowCount()-1, self.model.columnCount()-1)
        self.model.dataChanged.emit(index1, index2)

    def redo(self):
        if self.add == True:
            self.addRow()
        else:
            self.removeRow()

    def undo(self):
        if self.add == True:
            self.removeRow()
        else:
            self.addRow()
