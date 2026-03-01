#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende
import sqlite3

class Library():
    """SQLite abstraction layer for the HomeLib database.

    Holds a single persistent connection to the database file for the
    lifetime of the object.  Every other module imports this class and
    calls its methods instead of writing SQL directly.

    The class constants COLLECTIVE and ANONYMOUS are sentinel strings
    stored verbatim in the 'author' column of a book row when the book
    has no individually named author.  All other books store a
    pipe-delimited string 'count|id1|id2|...' of author foreign keys.
    """

    def __init__(self,library_name):
        """Open the SQLite database at library_name and keep the connection open."""
        self._db = sqlite3.connect(library_name) # open and close connection each time ? with decorator ?
        self._cursor = self._db.cursor()
        self.COLLECTIVE = "collective"
        self.ANONYMOUS = "anonymous"

    def __del__(self):
        """Close the database connection when the object is garbage-collected."""
        self._db.close()
        del(self)

    def _newID(self,base):
        """Return max(id)+1 from table base, or 1 if the table is empty.

        Used by all add* methods to assign the next available integer ID.
        base is interpolated directly into the SQL string — only pass
        trusted, hard-coded table names.
        """
        self._cursor.execute("SELECT max(id) FROM {}".format(base)) # WARNING sql injections ?
        id = self._cursor.fetchone()[0]
        if id:
            return id + 1
        return 1

    def addAuthor(self,christian_name,last_name):
        """Insert a new author row with an auto-assigned id."""
        self._cursor.execute("""INSERT INTO authors VALUES (?,?,?);""",
                (self._newID('authors'),christian_name,last_name))
        self._db.commit()

    def addBook(self,name,author,publisher,more,box,volumes=None):
        """Insert a new book row with an auto-assigned id.

        author is either a pipe-delimited string ('count|id1|id2|...') or
        one of the sentinel strings COLLECTIVE / ANONYMOUS.
        publisher, box and volumes are integers.

        The columns are named rather than positional: the books table gained a
        'volumes' column for the web application, and "VALUES (?,?,?,?,?,?)"
        would now be one value short.
        """
        self._cursor.execute("""INSERT INTO books (id,name,author,publisher,more,box,volumes) VALUES (?,?,?,?,?,?,?);""",
                (self._newID('books'),name,author,publisher,more,box,volumes))
        self._db.commit()

    def deleteBook(self,book:int):
        """Soft-delete a book by recording its id in deleted_books.

        The original row in the books table is not removed; the UI uses
        deleted_books to render struck-through titles.
        """
        self._cursor.execute("""INSERT INTO deleted_books VALUES (?,?);""",
                (self._newID('deleted_books'),book))
        self._db.commit()

    def addBox(self,name,library,line,column):
        """Insert a new box row with an auto-assigned id.

        library is an integer foreign key.  line is a 1-based row number.
        column is an uppercase letter ('A', 'B', ...) identifying the shelf column.
        """
        self._cursor.execute("""INSERT INTO boxes VALUES (?,?,?,?,?);""",
                (self._newID('boxes'),name,library,line,column))
        self._db.commit()

    def addLibrary(self,name,place,lines,columns):
        """Insert a new library row with an auto-assigned id.

        lines and columns define the dimensions of the 2D shelf grid.
        """
        self._cursor.execute("""INSERT INTO libraries VALUES (?,?,?,?,?);""",
                (self._newID('libraries'),name,place,lines,columns))
        self._db.commit()

    def addPublisher(self,name):
        """Insert a new publisher row with an auto-assigned id."""
        self._cursor.execute("""INSERT INTO publisher VALUES (?,?);""",
                (self._newID('publisher'),name))
        self._db.commit()

    def booksByAuthor(self,author_name):
        """Return all book rows whose 'author' field equals author_name.

        Note: this matches the exact stored string (the pipe-delimited id
        string or a sentinel), not resolved display names.
        """
        self._cursor.execute("""SELECT * FROM books WHERE author = ?;""",(author_name,))
        return self._cursor.fetchall()

    def booksByBox(self,box_name=None,box_id=None):
        """Return all book rows stored in the given box.

        Supply either box_name (resolved to an id via a SELECT) or box_id
        directly.  At least one must be provided.
        """
        if box_name:
            self._cursor.execute("""SELECT id FROM boxes WHERE name = ?;""",(box_name,))
            box_id = self._cursor.fetchone()[0]
        self._cursor.execute("""SELECT * FROM books WHERE box = ?;""",(box_id,))
        return self._cursor.fetchall()

    def findAuthor(self, id):
        """Return the full author row (id, christian_name, last_name), or None if not found."""
        self._cursor.execute("""SELECT * FROM authors WHERE id = ?;""",(id,))
        return self._cursor.fetchone()

    def findAuthorID(self,christian_name,last_name):
        """Return the id of the author matching christian_name and last_name.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT id FROM authors WHERE christian_name = ? AND last_name = ?;""",(christian_name,last_name))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Author '{christian_name} {last_name}' not found")
        return row[0]

    def findBoxID(self,name):
        """Return the id of the box with the given name.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT id FROM boxes WHERE name = ?;""",(name,))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Box '{name}' not found")
        return row[0]

    def findBoxName(self,ID):
        """Return the name of the box with the given id.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT name FROM boxes WHERE id = ?;""",(ID,))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Box id {ID} not found")
        return row[0]

    def findLibraryID(self,name):
        """Return the id of the library with the given name.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT id FROM libraries WHERE name = ?;""",(name,))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Library '{name}' not found")
        return row[0]

    def findLibraryName(self, id):
        """Return the name of the library with the given id.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT name FROM libraries WHERE id = ?;""",(id,))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Library id {id} not found")
        return row[0]

    def findPublisherID(self,name):
        """Return the id of the publisher with the given name.

        Raises ValueError if no match is found.
        """
        self._cursor.execute("""SELECT id FROM publisher WHERE name = ?;""",(name,))
        row = self._cursor.fetchone()
        if row is None:
            raise ValueError(f"Publisher '{name}' not found")
        return row[0]

    def listAll(self):
        """Return the entire database as a dict with keys:
        'authors', 'books', 'boxes', 'libraries', 'publishers', 'deleted_books'.

        Each value is the list returned by the corresponding list* method.
        The GUI caches this snapshot in memory for display and filtering.
        """
        result = {}
        result['authors'] = self.listAuthors()
        result['books'] = self.listBooks()
        result['boxes'] = self.listBoxes()
        result['libraries'] = self.listLibraries()
        result['publishers'] = self.listPublishers()
        result['deleted_books'] = self.listDeletedBooks()
        return result

    def listAuthors(self):
        """Return all rows from the authors table."""
        self._cursor.execute("""SELECT * FROM authors""")
        return self._cursor.fetchall()

    def listBooks(self):
        """Return all rows from the books table."""
        self._cursor.execute("""SELECT * FROM books""")
        return self._cursor.fetchall()

    def listDeletedBooks(self):
        """Return all rows from the deleted_books table."""
        self._cursor.execute("""SELECT * FROM deleted_books""")
        return self._cursor.fetchall()

    def listBoxes(self):
        """Return all rows from the boxes table."""
        self._cursor.execute("""SELECT * FROM boxes""")
        return self._cursor.fetchall()

    def listLibraries(self):
        """Return all rows from the libraries table."""
        self._cursor.execute("""SELECT * FROM libraries""")
        return self._cursor.fetchall()

    def listPublishers(self):
        """Return all rows from the publisher table."""
        self._cursor.execute("""SELECT * FROM publisher""")
        return self._cursor.fetchall()

    def backup(self, id, table_name):
        """Copy the current row for id from table_name into table_name_backup.

        Called automatically before every update* method so that the
        previous state can be recovered.  Raises ValueError if table_name
        contains a semicolon (basic SQL-injection guard).
        """
        if ";" in table_name:
            raise ValueError(f"{table_name} is not a valid identifier")
        self._cursor.execute(f"""SELECT * FROM {table_name} where id = ?;""",(id,));
        backup = self._cursor.fetchone()
        table_backup = f"{table_name}_backup"
        elts = "?,"*(len(backup)-1)
        self._cursor.execute(f"""INSERT INTO {table_backup} VALUES ({elts}?);""",
                             (id,*backup[1:]))
        self._db.commit()

    def updateAuthor(self,id,christian_name,last_name):
        """Back up the author row then update christian_name and last_name."""
        self.backup(id, "authors")
        self._cursor.execute("""UPDATE authors SET christian_name = ?, last_name = ? WHERE id = ?""",
                             (christian_name,last_name,id))
        self._db.commit()

    def updateBook(self,id,name,author,publisher,more,box):
        """Back up the book row then update all fields.

        author is a pipe-delimited id string or a sentinel.
        publisher and box are integer foreign keys.
        """
        self.backup(id, "books")
        self._cursor.execute("""UPDATE books SET name = ?, author = ?, publisher = ?, more = ?, box = ? WHERE id = ? """,
                (name,author,publisher,more,box,id))
        self._db.commit()

    def updateBoxOfBook(self,id,box):
        """Back up the book row then move it to a different box.

        id and box are both integers (book id and box foreign key).
        """
        self.backup(id, "books")
        self._cursor.execute("""UPDATE books SET box = ? WHERE id = ?""",(box,id))
        self._db.commit()

    def updateBox(self,id,name,library_id,line,column):
        """Back up the box row then update all fields."""
        self.backup(id, "boxes")
        self._cursor.execute("""UPDATE boxes SET name = ?, library = ?, line = ?, column = ? WHERE id = ?""",
                             (name,library_id,line,column,id))
        self._db.commit()

    def updateLibrary(self,id,name,place,lines,columns):
        """Back up the library row then update all fields."""
        self.backup(id, "libraries")
        self._cursor.execute("""UPDATE libraries SET name = ?, place = ?, lines = ?, columns = ? WHERE id = ?""",
                             (name,place,lines, columns,id))
        self._db.commit()

    def updatePublisher(self,id,name):
        """Back up the publisher row then update the name."""
        self.backup(id, "publisher")
        self._cursor.execute("""UPDATE publisher SET name = ? WHERE id = ? """,(name,id))
        self._db.commit()
