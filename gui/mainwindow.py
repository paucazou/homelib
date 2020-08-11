#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__)) + '/'
sys.path.append(current_dir)
sys.path.append(current_dir + '../')

import dbupdater

from mainclass import Library
from newbook import NewBookWindow
from PyQt5.QtCore import pyqtSignal, QCoreApplication, QLocale, Qt, QTranslator
from PyQt5.QtWidgets import QApplication, QDockWidget, QGroupBox, QHBoxLayout, QMainWindow, QLineEdit, QPushButton, QStyle, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget
from libpattern import *
from translation import *

_ = QCoreApplication.translate

class GuiApp(QApplication):
    def __init__(self,args):
        dbupdater.updateDB()
        QApplication.__init__(self, args)
        self.translator = QTranslator()
        self.translator.load(QLocale(),'homelib','.',current_dir + 'i18n','.qm')
        
        self.installTranslator(self.translator)
        self.execute = Main(args)

class Main(QMainWindow,SuperTranslator):
    resized = pyqtSignal()
    def __init__(self,args):
        QMainWindow.__init__(self)
        SuperTranslator.__init__(self)
        self.db = Library(args[0])
        self.results = self.db.listAll()
        self.initUI()
        self.retranslateUI()
        self.defineSignals()

    def initUI(self):
        self.rightDock = QDockWidget('right_dock',self)
        self.W.searchwidget = SearchWidget()
        self.rightDock.setWidget(self.W.searchwidget)
        self.addDockWidget(Qt.RightDockWidgetArea,self.rightDock)
        self.W.results = Results(self.results)
        self.setCentralWidget(self.W.results)
        self.setGeometry(QStyle.alignedRect(Qt.LeftToRight,Qt.AlignCenter,self.size(),GuiApp.desktop().availableGeometry()))
        self.show()
        
    def retranslateUI(self):
        SuperTranslator.retranslateUI(self)
        self.setWindowTitle(_("Main","HomeLib"))
        self.rightDock.setWindowTitle(_('Main','Research'))
        
    def defineSignals(self):
        self.W.searchwidget.title.textEdited.connect(self.changeResults) # if too slow : returnPressed
        self.W.searchwidget.authors.textEdited.connect(self.changeResults)
        self.W.searchwidget.publisher.textEdited.connect(self.changeResults)
        self.W.searchwidget.boxes.textEdited.connect(self.changeResults)
        self.W.searchwidget.library.textEdited.connect(self.changeResults)
        self.W.searchwidget.all.textEdited.connect(self.changeResults)
        self.W.searchwidget.reset_button.clicked.connect(self.resetResults)
        self.W.searchwidget.new_button.clicked.connect(self.addBook)
        self.W.results.cellPressed.connect(self.libInfo)
        self.resized.connect(self.resizeThings)
        
    def resizeEvent(self,event):
        self.resized.emit()
        return super(Main, self).resizeEvent(event)
        
    def resizeThings(self):
        if self.W.searchwidget.pattern:
            self.libInfo(self.W.results.currentItem().row(),0)
            
    def resetResults(self):
        for line_edit in self.W.searchwidget.line_edits:
            line_edit.clear()
        self.changeResults()

    def addBook(self):
        """Add a new book"""
        n = NewBookWindow(False,self.db)
        if n.updated:
            self.W.results.results = self.db.listAll()
            self.W.results.createItems()
            self.changeResults()


    def changeBook(self,*args):
        """Change the content of the book"""
        NewBookWindow(True,self.db,*args)
        
    def changeResults(self,*args):
        self.W.results.fillTable(self.W.searchwidget.title.text().lower(),
                                 self.W.searchwidget.authors.text().lower(),
                                 self.W.searchwidget.publisher.text().lower(),
                                 self.W.searchwidget.boxes.text().lower(),
                                 self.W.searchwidget.library.text().lower(),
                                 self.W.searchwidget.all.text().lower()
                                 )
        
        
    
    def libInfo(self,*args):
        book = self.W.results.item(args[0],0).info
        
        box = self.results['boxes'][book[-1]-1]
        library = self.results['libraries'][box[2]-1]
        boxnames = []
        for line in range(library[3]+1):
            boxnames.append(['']*library[4])
        for temp_box in self.results['boxes']:
            if temp_box[2] == box[2]:
                boxnames[temp_box[3]-1][alphabet.index(temp_box[4])] = temp_box[1]
        pattern = Pattern(library[3],library[4],
                          box[3],alphabet.index(box[4])+1,
                          boxnames,
                          library[1],library[2],self)
       
        if self.W.searchwidget.pattern:
            self.W.searchwidget.pattern.close()
        self.W.searchwidget.layout.insertWidget(self.W.searchwidget.layout.count(),pattern)
        self.W.searchwidget.pattern = pattern
        
        
class Results(QTableWidget,SuperTranslator):
    def __init__(self,results,title='',authors='',publisher='',box='',library=''):
        QWidget.__init__(self)
        SuperTranslator.__init__(self)
        self.results = results
        self.createItems()
        self.initUI(title,authors,publisher,box,library)
        self.retranslateUI()
        #self.clearContents()
    
    def initUI(self,title_,authors_,publisher_,box_,library_):
        self.setColumnCount(6)
        self.setRowCount(len(self.results['books']))
        self.fillTable(title_,authors_,publisher_,box_,library_)
        self.horizontalHeader().sectionClicked.connect(self.resizeRows)
        
    def resizeRows(self,index):
        for rownb in range(self.rowCount()):
            if '\n' in self.item(rownb,5).text() or '\n' in self.item(rownb,1).text():
                if self.item(rownb,5).text().count('\n') > self.item(rownb,1).text().count('\n'):
                    column = 5
                else:
                    column = 1
                self.setRowHeight(rownb,(self.item(rownb,column).text().count('\n')+1)*19)
            else:
                self.setRowHeight(rownb,30)
        
    def createItems(self):
        self.items = []
        for i,book in enumerate(self.results['books']):
            book_name = book[1]
            if book[2] == 'anonymous':
                book_authors = 'Anonyme'
            elif book[2] == 'collective':
                book_authors = 'Collectif'
            else:
                authors_list = book[2].split('|')[1:]
                book_authors = ''
                for j in authors_list:
                    j = int(j) - 1
                    book_authors += """{} {}\n""".format(self.results['authors'][j][1],self.results['authors'][j][2])
                book_authors = book_authors[:-1]
            box = self.results['boxes'][book[-1]-1]
            book_box_name = "{} - {}{}".format(box[1],box[4],box[3])
            book_publisher = self.results['publishers'][book[3]-1][1]
            book_library = self.results['libraries'][box[2]-1][1]
            firstitem = QTableWidgetItem(book_name)
            firstitem.info = book
            self.items.append((firstitem,) + tuple((QTableWidgetItem(raw_item) for raw_item in (book_authors,book_publisher,book_box_name,book_library,book[4]))))
          
    def fillTable(self,title_,authors_,publisher_,box_,library_,all_info_=""):
        title_, authors_, publisher_, box_, library_, all_info_ = (x.lower() for x in (title_, authors_, publisher_, box_, library_, all_info_))
        self.setSortingEnabled(False)
        self.clearSpans()
        self.verticalHeader().setDefaultSectionSize(30)
        self.setRowCount(len(self.items))
        line_number = 0
        for book in self.items:
            info = book[0].info
            book_info = [ x.text().lower() for x in book ]
            #if (title_.lower() in book[0].text().lower() and authors_.lower() in book[1].text().lower() and publisher_.lower() in book[2].text().lower() and box_.lower() in book[3].text().lower() and library_.lower() in book[4].text().lower()):
            if (title_ in book_info[0] and authors_ in book_info[1] and publisher_ in book_info[2] and box_ in book_info[3] and library_ in book_info[4] and all_info_ in "".join(book_info)):
                items_list = []
                for i, item in enumerate(book):
                    items_list.append(item.clone())
                    self.setItem(line_number,i,items_list[-1])
                items_list[0].info = info
                line_number+=1
        self.setRowCount(line_number)
        for i in range(5):
            self.resizeColumnToContents(i)
        self.horizontalHeader().setStretchLastSection(True)
        self.setSortingEnabled(True)
        self.resizeRows('index')
        
    def retranslateUI(self):
        SuperTranslator.retranslateUI(self)
        self.setHorizontalHeaderLabels([_("Results","Title"),_("Results","Authors"),_("Results","Publisher"),
                                        _("Results","Box"),_("Results","Library"),_("Results","Other information")])

class SearchWidget(QWidget,SuperTranslator):
    def __init__(self):
        QWidget.__init__(self)
        SuperTranslator.__init__(self)
        self.initUI()
        self.layoutSettings()
    
    def initUI(self):
        self.title_group = QGroupBox("Title")
        self.title_layout = QHBoxLayout()
        self.title = QLineEdit(self)
        #self.title.setClearButtonEnabled(True)
        self.title_layout.addWidget(self.title)
        self.title_group.setLayout(self.title_layout)
        
        self.authors_group = QGroupBox("Authors")
        self.authors_layout = QHBoxLayout()
        self.authors = QLineEdit(self)
        self.authors_layout.addWidget(self.authors)
        self.authors_group.setLayout(self.authors_layout)
        
        self.publisher_group = QGroupBox("Publisher")
        self.publisher_layout = QHBoxLayout()
        self.publisher = QLineEdit(self)
        self.publisher_layout.addWidget(self.publisher)
        self.publisher_group.setLayout(self.publisher_layout)
        
        self.boxes_group = QGroupBox("Box")
        self.boxes_layout = QHBoxLayout()
        self.boxes = QLineEdit(self)
        self.boxes_layout.addWidget(self.boxes)
        self.boxes_group.setLayout(self.boxes_layout)
        
        self.library_group = QGroupBox("Library")
        self.library_layout = QHBoxLayout()
        self.library = QLineEdit(self)
        self.library_layout.addWidget(self.library)
        self.library_group.setLayout(self.library_layout)

        self.boxnlib_layout = QHBoxLayout()
        self.boxnlib_layout.addWidget(self.boxes_group)
        self.boxnlib_layout.addWidget(self.library_group)

        self.all_group = QGroupBox("All")
        self.all_layout = QHBoxLayout()
        self.all = QLineEdit(self)
        self.all_layout.addWidget(self.all)
        self.all_group.setLayout(self.all_layout)
        
        self.reset_button = QPushButton('Reset')
        self.new_button = QPushButton('New')
        self.resetnnew_layout = QHBoxLayout()

        self.resetnnew_layout.addWidget(self.reset_button)
        self.resetnnew_layout.addWidget(self.new_button)
        
        self.line_edits = (self.title,self.authors,self.publisher,self.boxes,self.library,self.all)
        for line_edit in self.line_edits:
            line_edit.setClearButtonEnabled(True)
        
    def layoutSettings(self):
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.title_group)
        self.layout.addWidget(self.authors_group)
        self.layout.addWidget(self.publisher_group)
        self.layout.addLayout(self.boxnlib_layout)
        self.layout.addWidget(self.all_group)
        self.layout.addLayout(self.resetnnew_layout)
        self.layout.addStretch(1)
        self.pattern = None
        self.setLayout(self.layout)
        
    def retranslateUI(self):
        SuperTranslator.retranslateUI(self)
        self.title_group.setTitle(_("SearchWidget","Book's title"))
        self.authors_group.setTitle(_("SearchWidget","Author's name"))
        self.publisher_group.setTitle(_("SearchWidget","Publisher's name"))
        self.boxes_group.setTitle(_("SearchWidget","Box's name"))
        self.library_group.setTitle(_("SearchWidget","Library's name"))
        self.all_group.setTitle(_("SearchWidget","In all fields"))
        self.reset_button.setText(_("SearchWidget","Reset results"))
        self.new_button.setText(_("SearchWidget","New book"))
        
