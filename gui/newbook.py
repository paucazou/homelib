#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

from translation import *
from PyQt5.QtCore import QCoreApplication, Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QCheckBox, QComboBox, QCompleter, QDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTextEdit, QToolButton, QVBoxLayout, QWidget

from libpattern import *
_ = QCoreApplication.translate
import util

class Selector(QComboBox,SuperTranslator):
    """Class that displays a combo box
    with a selector"""
    def __init__(self,data:dict):
        QComboBox.__init__(self)
        SuperTranslator.__init__(self)
        self.data = data
        self.initUI()
        self.setCompleter()


    def setCompleter(self):
        self.completer = QCompleter(self.data.keys())
        self.completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.completer.setFilterMode(Qt.MatchContains)
        QComboBox.setCompleter(self,self.completer)

    
    def initUI(self):
        self.setEditable(True)
        #self.editTextChanged.disconnect()
        self.fillPopup()
        self.setCurrentText("")

        #self.editTextChanged.connect(self.fillPopup)
        #self.currentTextChanged.connect(self.fillPopup)

    def fillPopup(self):
        self.clear()
        names = sorted(n for n in self.data.keys() if self.currentText().lower() in n)

        for name in names:
            self.addItem(name)

    def __invalid(self):
        return self.currentText() not in self.data.keys()

    def __current_index(self):
        return self.data[self.currentText()]

    def addElt(self,name,id):
        """Add or update an element"""
        old_text = self.currentText()
        self.data[name] = id
        self.fillPopup()
        self.setCompleter()
        self.setCurrentText(old_text)

    invalid = property(__invalid)
    index = property(__current_index)

class Dialog(QDialog,SuperTranslator):
    """Base class for every dialog box"""
    def __init__(self):
        QDialog.__init__(self)
        SuperTranslator.__init__(self)

        self.updated = False

        # OK & Cancel buttons
        self.buttons_layout = QHBoxLayout()
        self.cancel = QPushButton("Cancel")
        self.cancel.setDefault(True)
        self.ok = QPushButton("OK")
        self.buttons_layout.addStretch(1)
        self.buttons_layout.addWidget(self.cancel)
        self.buttons_layout.addWidget(self.ok)

        self.ok.setDefault(True)

        self.ok.clicked.connect(self.saveData)
        self.cancel.clicked.connect(self.close)
        Dialog.retranslateUI(self)

    def retranslateUI(self):
        self.cancel.setText(_("Dialog","Cancel"))
        self.ok.setText(_("Dialog","OK"))

    def saveData(self):
        self.updated = True
        self.close()

class NewAuthorWindow(Dialog):
    """Create a dialog window to enter or change an author"""

    def __init__(self,update,db,first_name="",last_name=""):
        Dialog.__init__(self)
        self.update = update
        self.db = db

        self.initUI()
        self.retranslateUI()
        self.exec()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.names_layout = QHBoxLayout()
        self.first = QLineEdit()
        self.last = QLineEdit()
        self.names_layout.addWidget(self.first)
        self.names_layout.addWidget(self.last)

        self.layout.addLayout(self.names_layout)
        self.layout.addLayout(self.buttons_layout)
        self.setLayout(self.layout)

    def retranslateUI(self):
        title = _("NewAuthorWindow","Update author") if self.update else _("NewAuthorWindow","New author")
        self.setWindowTitle(title)
        
        self.first.setPlaceholderText(_("NewAuthorWindow","First name"))
        self.last.setPlaceholderText(_("NewBookWindow","Last name"))

    def saveData(self):
        if self.first.text() == "" and self.last.text() == "":
            return

        if not self.update:
            self.db.addAuthor(self.first.text(),self.last.text())

        Dialog.saveData(self)

class NewPublisherWindow(Dialog):
    """Window to create a new publisher"""
    def __init__(self,update,db,name=""):
        Dialog.__init__(self)

        self.update = update
        self.db = db
        self.name = name

        self.initUI()
        self.retranslateUI()
        self.exec()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.names_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.names_layout.addWidget(self.name_edit)
        self.layout.addLayout(self.names_layout)
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def retranslateUI(self):
        title = _("NewPublisherWindow","Update author") if self.update else _("NewPublisherWindow","New publisher")
        self.setWindowTitle(title)

        self.name_edit.setPlaceholderText(_("NewPublisherWindow","Publisher's name"))

    def saveData(self):
        if self.name_edit.text().isspace() or self.name_edit.text() == "":
            return

        if not self.update:
            self.db.addPublisher(self.name_edit.text())

        Dialog.saveData(self)

class NewLibWindow(Dialog):
    """Window to create a new library"""
    def __init__(self,update,db,name=""):
        Dialog.__init__(self)

        self.update = update
        self.db = db
        self.name = name

        self.initUI()
        self.retranslateUI()
        self.exec()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.names_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.names_layout.addWidget(self.name_edit)
        self.layout.addLayout(self.names_layout)
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def retranslateUI(self):
        title = _("NewLibWindow","Update library") if self.update else _("NewLibWindow","New library")
        self.setWindowTitle(title)

        self.name_edit.setPlaceholderText(_("NewLibWindow","Library's name"))

    def saveData(self):
        if self.name_edit.text().isspace() or self.name_edit.text() == "":
            return

        if not self.update:
            self.db.addLibrary(self.name_edit.text())

        Dialog.saveData(self)

class NewBoxWindow(Dialog):
    def __init__(self,update,db,name=""):
        Dialog.__init__(self)
        self.update = update
        self.db = db
        self.name = name
        self.libs_data = {l[1]:l[0] for l in self.db.listLibraries()}
        self.initUI()
        self.retranslateUI()
        self.exec()

    def initUI(self):
        self.layout = QVBoxLayout()

        self.name_layout = QHBoxLayout()
        self.name_edit = QLineEdit()
        self.name_layout.addWidget(self.name_edit)

        self.lib_layout = QHBoxLayout()
        self.lib_combo = Selector(self.libs_data)
        self.new_lib_button = QPushButton("New library")
        self.new_lib_button.clicked.connect(self.new_lib)

        self.lib_layout.addWidget(self.lib_combo)
        self.lib_layout.addWidget(self.new_lib_button)

        self.layout.addLayout(self.name_layout)
        self.layout.addLayout(self.lib_layout)
        self.layout.addLayout(self.buttons_layout)

        self.setLayout(self.layout)

    def new_lib(self):
        n = NewLibWindow(False,self.db)
        if n.updated:
            lib = self.db.listLibraries()[-1]
            self.lib_combo.addElt(lib[1],lib[0])

    def retranslateUI(self):
        title = _("NewBoxWindow","Update box") if self.update else _("NewBoxWindow","New box")
        self.setWindowTitle(title)
        self.new_lib_button.setText(_("NewBoxWindow","New library"))
        self.name_edit.setPlaceholderText(_("NewBoxWindow","New box"))

    def saveData(self):
        if self.name_edit.text().isspace() or self.name_edit.text() == "":
            return

        if not self.update:
            self.db.addBox(self.name_edit.text())

        Dialog.saveData(self)


class NewBookWindow(Dialog):
    """Create a dialog window to enter
    or change a book in the database"""
    def __init__(self,update,db,title="",authors="",box="",library="",details=""):
        Dialog.__init__(self)
        self.update=update
        self.db = db
        self.authors_widgets = []
        self.authors_activated = True
        self.get_authors_data()

        self.initUI()
        self.retranslateUI()
        self.fill_data()
        self.define_signals_slots()
        self.exec()

    def define_signals_slots(self):
        self.anonymous_checkbox.stateChanged.connect(self.toggle_authors)
        self.collective_checkbox.stateChanged.connect(self.toggle_authors)
        self.anonymous_checkbox.stateChanged.connect(lambda : self.collective_checkbox.setCheckState(Qt.Unchecked))
        self.collective_checkbox.stateChanged.connect(lambda : self.anonymous_checkbox.setCheckState(Qt.Unchecked))

        self.new_author_button.clicked.connect(self.new_author)
        self.new_publisher_button.clicked.connect(self.new_publisher)
        self.new_box_button.clicked.connect(self.new_box)

    def get_authors_data(self):
        raw = self.db.listAuthors()
        self.authors_data = { f"{a[2]} {a[1]}" : a[0] for a in raw }
        
        
    def new_author(self):
        n = NewAuthorWindow(False,self.db)
        if n.updated:
            # add a new author
            self.get_authors_data()
            author = self.db.listAuthors()[-1]
            nauthor = f"{author[2]} {author[1]}"
            for w in self.authors_widgets:
                w.itemAt(0).widget().addElt(nauthor,author[0])

    def new_publisher(self):
        n = NewPublisherWindow(False,self.db)
        if n.updated:
            publisher = self.db.listPublishers()[-1]
            print(publisher)
            self.publisher_combo.addElt(publisher[1],publisher[0])

    def new_box(self):
        n = NewBoxWindow(False,self.db)
        if n.updated:
            box = self.db.listBoxes()[-1]
            self.box_combo.addElt(box[1],box[0])

    def abort_save(self,text,widget_focus):
        self.message_warning.setText(text)
        self.message_warning.exec()
        widget_focus.setFocus(Qt.OtherFocusReason)

    def saveData(self):
        title = self.title_edit.text()
        if title.isspace() or title == "":
            self.message_warning.setText(self.no_title)
            self.message_warning.exec()
            self.title_edit.setFocus(Qt.OtherFocusReason)
            return
        # check wether the inpurt of publisher, authors and box is valid !

        authors = self.getAuthorsFromData()
        if not authors:
            return

        if self.publisher_combo.invalid:
            return self.abort_save(self.invalid_publisher,self.publisher_combo)
        publisher = self.publisher_combo.index

        more = self.details_edit.toPlainText()
        if self.box_combo.invalid:
            return self.abort_save(self.invalid_box,self.box_combo)
        box = self.box_combo.index

        if not self.update:
            self.db.addBook(title,authors,publisher,more,box)

        Dialog.saveData(self)

    def getAuthorsFromData(self):
        """Return a string representing the authors
        for the database"""
        if self.anonymous_checkbox.isChecked():
            return self.db.ANONYMOUS

        if self.collective_checkbox.isChecked():
            return self.db.COLLECTIVE
        # check if the input is valid !!!
        for w in self.authors_widgets:
            if w.itemAt(0).widget().invalid:
                self.message_warning.setText(self.invalid_author)
                self.message_warning.exec()
                w.itemAt(0).widget().setFocus(Qt.OtherFocusReason)
                return

        authors_ids = "|".join(str(w.itemAt(0).widget().index) for w in self.authors_widgets)
        return f"{len(self.authors_widgets)}|{authors_ids}"


    def fill_data(self):
        """Fill the combo boxes with data"""
        # authors
        self.generate_author()

        # publishers
        """
        for elt in self.db.listPublishers():
            self.publisher_combo.addItem(elt[1])
            """

        # boxes
        """for elt in self.db.listBoxes():
            self.box_combo.addItem(elt[1])
            """

    def generate_author(self):
        author_combo = Selector(self.authors_data)

        add_author = QToolButton()
        remove_author = QToolButton()
        add_author.setText('+')
        remove_author.setText('-')

        add_author.clicked.connect(self.generate_author)

        layout = QHBoxLayout()
        layout.addWidget(author_combo)
        layout.addWidget(remove_author)
        layout.addWidget(add_author)

        self.author_layout.addLayout(layout)
        i = len(self.authors_widgets)

        self.authors_widgets.append(layout)

        # logic to remove one item by clicking on remove_author button
        def __remove_author():
            if len(self.authors_widgets) == 1:
                return
            self.authors_widgets.remove(layout)
            self.author_layout.removeItem(layout)
            self.set_tab_order()

        remove_author.clicked.connect(__remove_author)

        self.set_tab_order()

    def toggle_authors(self):
        if self.authors_activated and ( self.collective_checkbox.isChecked() or self.anonymous_checkbox.isChecked()):
            # deactivation
            for w in self.authors_widgets:
                self.author_layout.removeItem(w)
            self.authors_widgets.clear()
            self.authors_activated = False

        if self.authors_activated == self.collective_checkbox.isChecked() == self.anonymous_checkbox.isChecked() == False:
            # reactivation
            self.generate_author()
            self.authors_activated = True


    def populate_authors(self,index): #DEPRECATED
        _authors = self.db.listAuthors()
        w = self.authors_widgets[index]
        for _a in _authors:
            w.itemAt(0).widget().addItem(_a[1])
            w.itemAt(1).widget().addItem(_a[2])

    def initUI(self):
        # title
        title_font = QFont()
        title_font.setPointSize(20)
        self.wtitle = QLabel('New/Change book')
        self.wtitle.setFont(title_font)
        self.wtitle.setAlignment(Qt.AlignHCenter)

        # Title
        self.title_group = QGroupBox("Name")
        self.title_edit = QLineEdit(self)
        self.title_layout = QHBoxLayout()
        self.title_layout.addWidget(self.title_edit)
        self.title_group.setLayout(self.title_layout)

        # Author choice
        self.author_group = QGroupBox("Author")
        self.author_layout = QVBoxLayout()

        self.anonymous_checkbox = QCheckBox("Anonymous")
        self.collective_checkbox = QCheckBox("Collective")
        self.new_author_button = QPushButton("New author")
        self.authors_sub_layout = QHBoxLayout()
        self.authors_sub_layout.addWidget(self.anonymous_checkbox)
        self.authors_sub_layout.addWidget(self.collective_checkbox)
        self.authors_sub_layout.addWidget(self.new_author_button)
        self.author_layout.addLayout(self.authors_sub_layout)

        self.author_group.setLayout(self.author_layout)

        # Publisher choice
        self.publisher_group = QGroupBox("Publisher")
        publisher_data = {p[1]:p[0] for p in self.db.listPublishers()}
        self.publisher_combo = Selector(publisher_data)
        self.publisher_layout = QHBoxLayout()
        self.publisher_layout.addWidget(self.publisher_combo)

        self.new_publisher_button = QPushButton("New Publisher")
        self.publisher_layout.addWidget(self.new_publisher_button)
        self.publisher_group.setLayout(self.publisher_layout)

        # Box choice
        self.box_group = QGroupBox("Box")
        box_data = {p[1]:p[0] for p in self.db.listBoxes()}
        self.box_combo = Selector(box_data)
        self.box_layout = QHBoxLayout()
        self.box_layout.addWidget(self.box_combo)

        self.preview_box_button = QPushButton("Preview")
        self.box_layout.addWidget(self.preview_box_button)
        self.preview_box_button.clicked.connect(self.preview_box)

        self.new_box_button = QPushButton("New Box")
        self.box_layout.addWidget(self.new_box_button)
        self.box_group.setLayout(self.box_layout)

        # details
        self.details_group = QGroupBox("Details")
        self.details_edit = QTextEdit()
        self.details_layout = QHBoxLayout()
        self.details_layout.addWidget(self.details_edit)
        self.details_group.setLayout(self.details_layout)


        # main layout
        self.layout = QVBoxLayout()
        self.layout.addWidget(self.wtitle)
        self.layout.addWidget(self.title_group)
        self.layout.addWidget(self.author_group)
        self.layout.addWidget(self.publisher_group)
        self.layout.addWidget(self.box_group)
        self.layout.addWidget(self.details_group)
        self.layout.addLayout(self.buttons_layout)
        self.setLayout(self.layout)

        # others
        self.message_warning = QMessageBox()
        self.message_warning.setIcon(QMessageBox.Warning)


    def preview_box(self):
        if self.box_combo.invalid:
            self.message_warning.setText(self.invalid_box)
            self.message_warning.exec()
            self.box_combo.setFocus(Qt.OtherFocusReason)
            return

        pattern = Pattern(1,1,1,1,
                ["Name"],"A lib","A place",self)
        self.layout.addWidget(pattern)

    def set_tab_order(self):
        aw = self.authors_widgets
        if len(aw) == 0:
            return

        extract = lambda x,i : x.itemAt(i).widget()
        def set_tab_in_author(f,s):
            self.setTabOrder(extract(f,0),extract(f,1))
            self.setTabOrder(extract(f,1),extract(f,2))
            self.setTabOrder(extract(f,2),s)


        self.setTabOrder(self.new_author_button,self.authors_widgets[0].itemAt(0).widget())
        set_tab_in_author(self.authors_widgets[0],self.publisher_combo)

        last = None
        for elts in [ x for x in util.pairwise(aw)]:
            f, s = elts
            set_tab_in_author(f,extract(s,0))
            last = s

        if last is None:
            return
        set_tab_in_author(last,self.publisher_combo)



    def retranslateUI(self):
        title = _("NewBookWindow","Change book") if self.update else _("NewBookWindow","New book")
        self.setWindowTitle(title)
        self.wtitle.setText(title)
        self.title_group.setTitle(_("NewBookWindow","Title"))
        self.author_group.setTitle(_("NewBookWindow","Author"))
        self.publisher_group.setTitle(_("NewBookWindow","Publisher"))
        self.box_group.setTitle(_("NewBookWindow","Box"))
        self.details_group.setTitle(_("NewBookWindow","Details"))
        self.first_name = _("NewBookWindow","First name")
        self.last_name = _("NewBookWindow","Last name")
        self.new_author_button.setText(_("NewBookWindow","New author"))
        self.new_publisher_button.setText(_("NewBookWindow","New publisher"))
        self.new_box_button.setText(_("NewBookWindow","New box"))
        self.preview_box_button.setText(_("NewBookWindow","Preview box"))
        self.collective_checkbox.setText(_("NewBookWindow","Collective"))
        self.anonymous_checkbox.setText(_("NewBookWindow","Anonymous"))

        # messages warnings
        self.no_title = _("NewBookWindow","No title entered")
        self.invalid_author = _("NewBookWindow","Invalid author")
        self.invalid_publisher = _("NewBookWindow","Invalid publisher")
        self.invalid_box = _("NewBookWindow","Invalid box")
