#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import sqlite3

class Library():

    def __init__(self,library_name):
        self._db = sqlite3.connect(library_name) # open and close connection each time ? with decorator ?
        self._cursor = self._db.cursor()
        self.COLLECTIVE = "collective"
        self.ANONYMOUS = "anonymous"

    def __del__(self):
        self._db.close()
        del(self)
        
    def _newID(self,base):
        self._cursor.execute("SELECT max(id) FROM {}".format(base)) # WARNING sql injections ?
        id = self._cursor.fetchone()[0]
        if id:
            return id + 1
        return 1

    def addAuthor(self,christian_name,last_name):
        self._cursor.execute("""INSERT INTO authors VALUES (?,?,?);""",
                (self._newID('authors'),christian_name,last_name))
        self._db.commit()

    def addBook(self,name,author,publisher,more,box):
        """publisher and box are integers"""
        self._cursor.execute("""INSERT INTO books VALUES (?,?,?,?,?,?);""",
                (self._newID('books'),name,author,publisher,more,box))
        self._db.commit()

    def deleteBook(self,book:int):
        """Tags a book as deleted"""
        self._cursor.execute("""INSERT INTO deleted_books VALUES (?,?);""",
                (self._newID('deleted_books'),book))
        self._db.commit()
    
    def addBox(self,name,library,line,column):
        """library and line are integers"""
        self._cursor.execute("""INSERT INTO boxes VALUES (?,?,?,?,?);""",
                (self._newID('boxes'),name,library,line,column))
        self._db.commit()
    
    def addLibrary(self,name,place,lines,columns):
        """lines and columns are integers"""
        self._cursor.execute("""INSERT INTO libraries VALUES (?,?,?,?,?);""",
                (self._newID('libraries'),name,place,lines,columns))
        self._db.commit()

    def addPublisher(self,name):
        self._cursor.execute("""INSERT INTO publisher VALUES (?,?);""",
                (self._newID('publisher'),name))
        self._db.commit()
        
    def booksByAuthor(self,author_name):
        self._cursor.execute("""SELECT * FROM books WHERE author = ?;""",(author_name,))
        return self._cursor.fetchall()
    
    def booksByBox(self,box_name=None,box_id=None):
        if box_name:
            self._cursor.execute("""SELECT id FROM boxes WHERE name = ?;""",(box_name,))
            box_id = self._cursor.fetchone()[0]
        self._cursor.execute("""SELECT * FROM books WHERE box = ?;""",(box_id,))
        return self._cursor.fetchall()

    def findAuthor(self, id):
        self._cursor.execute("""SELECT * FROM authors WHERE id = ?;""",(id,))
        return self._cursor.fetchone()[0]
    
    def findAuthorID(self,christian_name,last_name):
        self._cursor.execute("""SELECT id FROM authors WHERE christian_name = ? AND last_name = ?;""",(christian_name,last_name))
        return self._cursor.fetchone()[0]
    
    def findBoxID(self,name):
        self._cursor.execute("""SELECT id FROM boxes WHERE name = ?;""",(name,))
        return self._cursor.fetchone()[0]
    
    def findBoxName(self,ID):
        self._cursor.execute("""SELECT name FROM boxes WHERE id = ?;""",(ID,))
        return self._cursor.fetchone()[0]
    
    def findLibraryID(self,name):
        self._cursor.execute("""SELECT id FROM libraries WHERE name = ?;""",(name,))
        return self._cursor.fetchone()[0]
    
    def findPublisherID(self,name):
        self._cursor.execute("""SELECT id FROM publisher WHERE name = ?;""",(name,))
        return self._cursor.fetchone()[0]
    
    def listAll(self):
        """This method returns the WHOLE database"""
        result = {}
        result['authors'] = self.listAuthors()
        result['books'] = self.listBooks()
        result['boxes'] = self.listBoxes()
        result['libraries'] = self.listLibraries()
        result['publishers'] = self.listPublishers()
        result['deleted_books'] = self.listDeletedBooks()
        return result
    
    def listAuthors(self):
        self._cursor.execute("""SELECT * FROM authors""")
        return self._cursor.fetchall()
    
    def listBooks(self):
        self._cursor.execute("""SELECT * FROM books""")
        return self._cursor.fetchall()
    
    def listDeletedBooks(self):
        self._cursor.execute("""SELECT * FROM deleted_books""")
        return self._cursor.fetchall()
    
    def listBoxes(self):
        self._cursor.execute("""SELECT * FROM boxes""")
        return self._cursor.fetchall()
    
    def listLibraries(self):
        self._cursor.execute("""SELECT * FROM libraries""")
        return self._cursor.fetchall()
    
    def listPublishers(self):
        self._cursor.execute("""SELECT * FROM publisher""")
        return self._cursor.fetchall()
    
    def updateAuthor(self,id,christian_name,last_name):
        self._cursor.execute("""UPDATE authors SET christian_name = ?, last_name = ? WHERE id = ?""",
                             (christian_name,last_name,id))
        self._db.commit()
    
    def updateBook(self,id,name,author,publisher,more,box):
        """publisher and box are integers"""
        self._cursor.execute("""UPDATE books SET name = ?, author = ?, publisher = ?, more = ?, box = ? WHERE id = ? """,
                (name,author,publisher,more,box,id))
        self._db.commit()

    def updateBoxOfBook(self,id,box):
        """args are int"""
        self._cursor.execute("""UPDATE books SET box = ? WHERE id = ?""",(box,id))
        self._db.commit()
        
    def updateBox(self,id,name,library_id,line,column):
        self._cursor.execute("""UPDATE boxes SET name = ?, library = ?, line = ?, column = ? WHERE id = ?""",
                             (name,library_id,line,column,id))
        self._db.commit()
        
    def updateLibrary(self,id,name,place,lines,columns):
        self._cursor.execute("""UPDATE libraries SET name = ?, place = ?, lines = ?, columns = ? WHERE id = ?""",
                             (name,place,lines, columns,id))
        self._db.commit()
        
    def updatePublisher(self,id,name):
        self._cursor.execute("""UPDATE publisher SET name = ? WHERE id = ? """,(name,id))
        self._db.commit()


