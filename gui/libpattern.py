#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QBrush, QPen
from PyQt5.QtWidgets import QGraphicsScene, QStyle, QGraphicsView, QVBoxLayout, QWidget

alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'

def list_default(list_obj,index,default):
    """Return list_obj[index], or default if the index is out of range."""
    try:
        return list_obj[index]
    except IndexError:
        return default

class Pattern(QWidget):
    """QWidget that renders a 2D grid of library shelves.

    Each cell displays the name of the box at that grid position.
    The selected box (identified by sline and scolumn) is filled red.
    Column headers are letters (A, B, ...) and row labels are numbers.
    The library name and physical location are drawn below the grid.
    """
    def __init__(self,lines,columns,sline,scolumn,boxnames,libname,place,window):
        QWidget.__init__(self)
        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.initUI(lines,columns,sline,scolumn,boxnames,libname,place)
        if not((window.width() < 1400 or window.height() < 900) and (self.height > 3 or self.width > 3)):
            #self.view.fitInView(QRectF(0,0,self.view.width()*1.1,self.view.height()*1.1),Qt.KeepAspectRatio)
            self.setMinimumWidth(self.view.width())

    def initUI(self,lines,columns,sline,scolumn,boxnames,libname,place):
        """Build the QGraphicsView layout and draw the library grid."""
        self.drawLibrary(lines,columns,sline,scolumn,boxnames,libname,place)

        self.view.show()
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.view)
        self.setLayout(self.layout)

    def drawLibrary(self,lines,columns,sline,scolumn,boxnames,libname,place):
        """Populate the QGraphicsScene with the shelf grid.

        All positional arguments are 1-based and decremented internally to
        zero-based indices.  Each box cell is a 100×100-pixel rectangle;
        the box name is fitted inside by progressively inserting line breaks
        into the label until it fits.  The selected cell (sline, scolumn) is
        filled with a red brush.  libname and place are drawn as text below
        the last row.
        """
        lines,columns,sline,scolumn = (item - 1 for item in (lines,columns,sline,scolumn))
        pen = QPen()
        pen.setWidth(5)
        sbrush = QBrush()
        sbrush.setStyle(Qt.SolidPattern)
        sbrush.setColor(Qt.red)

        letterbrush = QBrush()
        letterbrush.setColor(Qt.red)
        letterbrush.setStyle(Qt.SolidPattern)
        side = 100
        for i in range(columns+1):
            text = self.scene.addSimpleText(alphabet[i])
            text.setPos(50+i*side,0)
            if i == scolumn:
                text.setBrush(letterbrush)
        i=0
        while i <= lines:
            j=0
            text = self.scene.addSimpleText(str(i+1))
            text.setPos(0,70+i*side)
            if i == sline:
                text.setBrush(letterbrush)
            while j <= columns:
                if i == sline and j == scolumn:
                    brush = sbrush
                else:
                    brush = QBrush()
                box = self.scene.addRect(QRectF(25+j*side,25+i*side,side,side),pen,brush)
                base_text = list_default(boxnames,i,('',)*(j+1))[j]
                boxname = self.scene.addSimpleText(base_text)
                k=-2
                while boxname.boundingRect().width() + box.boundingRect().width() *13/100 >= box.boundingRect().width():
                    text = base_text.split()
                    try:
                        text[k]+= '\n' + list_default(text,k+1,'')
                    except IndexError:
                        break
                    del(text[k+1])
                    boxname.setText(' '.join(text))
                    k-=1
                boxname.setPos(30+j*side,28+i*side)
                j+=1
            i+=1
        self.height = i
        self.width = j
        lname = self.scene.addSimpleText(libname)
        lname.setPos(25,i*side + 30)
        place = self.scene.addSimpleText(place)
        place.setPos(25,i*side+45)
