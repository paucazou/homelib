#!/usr/bin/python3
# -*-coding:Utf-8 -*
#Deus, in adjutorium meum intende

import mainclass
import os
import sys
if sys.platform == 'linux':
    import readline
    
current_dir = os.path.dirname(os.path.abspath(__file__)) + '/'
library = mainclass.Library(current_dir + 'Library.db')

alphabet = ('A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O', 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W', 'X', 'Y', 'Z')

def alphaSort(string_list,new_name,research='',new_item=True):
    for elt in sorted(string_list,key=lambda x: x.split(' - ')[1]):
        if research.lower() in elt.lower():
            print(elt)
    if new_item:
        print("{} - New {}".format(len(string_list)+1,new_name))
    
def setFinput(function):
    if sys.platform == 'linux':
        return function
    else:
        def function(prompt='>>> ', text=''):
            print(text)
            return input(prompt).replace('\\n','\n')
        return function


def list_books():
    books = []
    list_books = library.listBooks()
    list_authors = library.listAuthors()
    list_publishers = library.listPublishers()
    for i, book in enumerate(list_books):
        authors_names = ''
        for nb in book[2].split('|')[1:]:
            nb = int(nb) - 1
            infos = list_authors[nb]
            authors_names += " {} {}.".format(infos[1],infos[2])
        publisher_name = list_publishers[book[3]-1][1]
        books.append("{} - {}. Author(s): {} Publisher: {}.".format(i,book[1],authors_names,publisher_name))
    return books



def delete_book():
    """Tags a book as deleted"""
    books = list_books()
    answer = ""
    while True:
        alphaSort(books,"",answer,new_item=False)
        answer = input("Choose the book you want to delete: ")
        if answer.isnumeric() and int(answer) <= len(books):
            check = input("Are you sure you want to delete: {}[y/NO]".format(books[int(answer)]))
            if check == "y":
                library.deleteBook(int(answer)+1)
                print("Book deleted")
            else:
                print("Canceled")
            break

def mass_change():
    """Change box of many books"""
    # select box
    answer = 'no'
    while answer != "yes":
        list_boxes = library.listBoxes()
        choices = [ "{} - {}".format(i+1,elt[1]) for i, elt in enumerate(list_boxes)]
        box = limit_or_choose(choices,' box',)
        list_boxes = library.listBoxes()
        box_name = list_boxes[box-1][1] 
        answer = finput("Box chosen: {}. Continue?([no]/yes)".format(box_name))
    # select books
    ## building list
    choices = []
    list_books = library.listBooks()
    list_authors = library.listAuthors()
    list_publishers = library.listPublishers()
    for i, book in enumerate(list_books):
        authors_names = ''
        for nb in book[2].split('|')[1:]:
            nb = int(nb) - 1
            infos = list_authors[nb]
            authors_names += " {} {}.".format(infos[1],infos[2])
        publisher_name = list_publishers[book[3]-1][1]
        choices.append("{} - {}. Author(s): {} Publisher: {}.".format(i,book[1],authors_names,publisher_name))
    ## selecting books
    answer = 'yes'
    books_selected = []
    while answer != 'no':
        books_selected.append(limit_or_choose(choices,' book'))
        answer = finput('Do you want to continue ([yes]/no)')

    # applying changes
    for j in books_selected:
        library.updateBoxOfBook(j+1,box)     

def _select_box(string_to_print=' box'):
    answer = 'no'
    while answer != "yes":
        list_boxes = library.listBoxes()
        choices = [ "{} - {}".format(i+1,elt[1]) for i, elt in enumerate(list_boxes)]
        box = limit_or_choose(choices,string_to_print)
        list_boxes = library.listBoxes()
        box_name = list_boxes[box-1][1] 
        answer = finput("Box chosen: {}. Continue?([no]/yes)".format(box_name))
    return box, box_name

def switch_boxes():
    """Change the box of books of a specified box"""
    fbox, first_box = _select_box(' box from')
    sbox, second_box = _select_box(' box to')
    if first_box == second_box:
        input(f"You selected the same box: {first_box}. Press any key to continue...")
        return switch_boxes()
    else:
        answer = input(f"Books from {first_box} will go to {second_box}. Are you sure?[NO/yes]")
        if answer.lower() != "yes":
            input("Abandon. Press any key")
            return switch_boxes()

    # select books and update
    books_selected = library.booksByBox(box_name=first_box)
    for b in books_selected:
        library.updateBoxOfBook(b[0], sbox)
    print("Library updated")





def correct():
    for i, elt in enumerate(('Books','Authors','Publishers','Boxes','Libraries','Boxes: mass', 'Switch boxes')):
        print('{} - {}'.format(i,elt))
    answer=input("Choose which kind of items you want to correct : ")
    
    if answer == '0':
        list_books = library.listBooks()
        list_authors = library.listAuthors()
        list_books_ = []
        for i,book in enumerate(list_books):
            authors_names = ''
            for nb in book[2].split('|')[1:]:
                nb = int(nb) - 1
                infos = list_authors[nb]
                authors_names += "{} {}. ".format(infos[1],infos[2])
            list_books_.append("{} - {}. Auteur(s) : {}".format(i,book[1],authors_names))
        while True:
            alphaSort(list_books_,'book',answer)
            answer = input("Choose which item you want to correct : ")
            if answer.isnumeric() and int(answer) <= i:
                newBook(update=True,book=list_books[int(answer)])
                break
    elif answer == '1':
        list_authors = library.listAuthors()
        for i, author in enumerate(list_authors):
            print("{} - {} {}".format(i,author[1],author[2]))
        answer = int(input("Choose which item you want to correct : "))
        if answer <= i:
            newAuthor(update=True,author=list_authors[answer])
    elif answer == '2':
        list_publishers = library.listPublishers()
        for i, publisher in enumerate(list_publishers):
            print("{} - {}".format(i,publisher[1]))
        answer = int(input("Choose which item you want to correct : "))
        if answer <= i:
            newPublisher(update=True,pre_publisher=list_publishers[answer])
    elif answer == '3':
        list_boxes = library.listBoxes()
        for i, box in enumerate(list_boxes):
            print("{} - {}".format(i,box[1]))
        answer = int(input("Choose which item you want to correct : "))
        if answer <= i:
            newBox(update=True,box=list_boxes[answer])
    elif answer == "4":
        list_libraries = library.listLibraries()
        for i, lib in enumerate(list_libraries):
            print("{} - {}".format(i,lib))
        answer = int(input("Choose which item you want to correct : "))
        if answer <= i:
            newLibrary(update=True,lib=list_libraries[answer])

    elif answer == '5':
        mass_change()
    elif answer == '6':
        switch_boxes()
    
def drawLib(lines, columns, sline=-1, scolumn=-1):
    """All args are integers. sline & scolumn represents the
    box selected"""
    pic = ""
    endline = ['\n']*10
    for i, letter in enumerate(alphabet):
        pic += " " * 5 + letter + " " * 5
        if i+1 == columns:
            pic += "\n"
            break
    i=1
    while i <= lines:
        pic += "*" *11*columns + '\n'
        j=1
        while j <= 9:
            if j == 5:
                endline[j] = " {}\n".format(i)
            if i != sline:
                pic += ("*"+" "*9 +"*")*columns + endline[j]
            else:
                pic += ("*"+" "*9 + "*")*(scolumn-1) + "*"+"+"*9+"*" + ("*"+" "*9+"*")*(columns - scolumn) + endline[j]

            j+=1
        pic += "*" *11*columns + '\n'
        i+=1
    return pic

@setFinput
def finput(prompt='>>> ', text=''):
    text = str(text)
    def hook():
        readline.insert_text(text)
        readline.redisplay()
    readline.set_pre_input_hook(hook)
    result = input(prompt + '\n')
    readline.set_pre_input_hook()
    return result.replace('\\n','\n')

def limit_or_choose(choices,choice_type,pre_choice=''):
    """Let the user limit the choice or choose an item from choices.
    pre_choice is a string default choice
    choice_type is a string for the sentence Please choose..."""
    str_choice = ''
    choices_length = len(choices) + 1
    news_item_hash = {' box':newBox,' book':newBook} # TODO develop
    while True:
        alphaSort(choices,choice_type,str_choice)
        str_choice = finput('Please choose a{}'.format(choice_type),pre_choice)
        if str_choice.isnumeric():
            int_choice = int(str_choice)
            if int_choice == choices_length:
                int_choice = news_item_hash[choice_type]()
            if int_choice <= choices_length:
                return int_choice 
        

def goon(function):
    print("""If you want to enter a new line, press \\n""")
    while True:
        function()
        answer = input("Do you want to continue ? (no/yes (default))")
        if answer.lower() == 'no':
            break

def newAuthor(update=False,author=('',)*3):
    christian_name = ''
    last_name = ''
    while christian_name == "":
        christian_name = finput("Enter author's christian name : ",author[1])
    while last_name == "":
        last_name = finput("Enter author's last name : ",author[2])
    while True:
        answer = input("{} {}: are you satisfied ? (y/n) : ".format(christian_name,last_name))
        if 'y' in answer.lower():
            if update:
                library.updateAuthor(author[0],christian_name,last_name)
            else:
                library.addAuthor(christian_name,last_name)
            return library.findAuthorID(christian_name,last_name)
        elif 'n' in answer.lower():
            return newAuthor(update,author)

def newBox(update=False,box=('',)*5):
    name=''
    library_id =-1
    line=-1
    column = ''
    while name == '':
        name = finput("Enter box's name : ",box[1])
    while library_id == -1:
        list_libraries = library.listLibraries()
        list_libraries.append(("","New library"))
        for i, elt in enumerate(list_libraries):
            print("{} - {}".format(i+1,elt[1]))
        library_id = int(finput("Please enter Library ID : ",box[2]))
        if library_id == i+1:
            library_id = newLibrary()
        elif library_id > i+1:
            library_id = -1
    list_libraries = library.listLibraries()
    print(list_libraries)
    while line <= 0 or line > list_libraries[library_id-1][3]:
        line = int(finput("Enter line number : ",box[3]))
    while column == '':
        column = finput("Enter column letter : ",box[4])
        try:
            if alphabet.index(column) > list_libraries[library_id-1][4] -1:
                column = ''
        except ValueError:
            column = ''
    while True:
        print(drawLib(list_libraries[library_id-1][3],list_libraries[library_id-1][4],line,alphabet.index(column)+1))
        answer = input("""Name : {}
                       Library_id : {}
                       Line : {}
                       Column : {}
                       Are you satisfied ? (y/n) : """.format(name,library_id,line,column))
        if 'y' in answer.lower():
            if update:
                library.updateBox(box[0],name,library_id,line,column)
            else:
                library.addBox(name,library_id,line,column)
            return library.findBoxID(name)
        elif 'n' in answer.lower():
            return newBox(update,box)
        
def newBook(update=False,book=('',)*6):
    authors_nb = -1
    authors = ''
    authors_names = ''
    author = ''
    name = ""
    publisher = -1
    box = -1
    while name == "":
        name = finput("Please enter the name of the book : ",book[1])
    if update:
        pre_authors_nb = book[2].split('|')[0]
        pre_authors = book[2].split('|')[1:]
    else:
        pre_authors_nb = ''
        pre_authors = ''
    if pre_authors == '' or pre_authors == []:
        pre_authors = ['']*15 # more than 15 authors for one book, really ?
    while authors_nb < 0:
        authors_nb = finput("Enter number of authors. 0 = anonymous, inf = collective : ",pre_authors_nb)
        if authors_nb == "collective":
            authors_nb = float('inf')
        try:
            authors_nb = float(authors_nb)
        except ValueError:
            authors_nb = -1
        
    if authors_nb == 0:
        authors = "anonymous"
    elif authors_nb == float('inf'):
        authors = "collective"
    else:
        authors_nb = int(authors_nb)
        authors = str(authors_nb)
        while authors_nb > 0:
            while not author.isnumeric():
                list_authors = library.listAuthors()
                temp_list_authors = []
                for i, elt in enumerate(list_authors):
                    temp_list_authors.append("{} - {} {}".format(i+1,elt[1],elt[2]))
                alphaSort(temp_list_authors,'author',author)
                if not author.isnumeric():
                    pre_auth_index = -1
                else:
                    pre_auth_index = int(author)
                author = finput("Please choose an author : ",pre_authors[pre_auth_index])
                if not author.isnumeric():
                    continue
                elif int(author) == i+2:
                    author = str(newAuthor())
                elif int(author) > i+2:
                    author = ''
                    continue
            authors += '|' + author
            authors_nb-=1
            author = ''
            del(pre_authors[-1])
            
    list_authors = library.listAuthors()
    for nb in authors.split('|')[1:]:
        nb = int(nb) - 1
        infos = list_authors[nb]
        authors_names += "{} {}. ".format(infos[1],infos[2])
    pub_kw = ''
    while publisher == -1:
        list_publishers = library.listPublishers()
        temp_list_publishers = []
        for i, elt in enumerate(list_publishers):
            temp_list_publishers.append("{} - {}".format(i+1,elt[1]))
        alphaSort(temp_list_publishers,'publisher',pub_kw)
        publisher = finput("Please choose a publisher : ",book[3])
        if publisher.isnumeric():
            publisher = int(publisher)
        else:
            pub_kw = publisher
            publisher = -1
            continue
        if publisher == 2+i:
            publisher = newPublisher()
        elif publisher > i+2:
            publisher = -1
    publisher_name = library.listPublishers()[publisher - 1][1]
    more = finput("If you need to enter more information about the book, please enter it : ",book[4])
    """while box == -1:
        list_boxes = library.listBoxes()
        list_boxes.append(('','New box'))
        for i, elt in enumerate(list_boxes):
            print("{} - {}".format(i+1,elt[1]))
        box = finput("Please choose a box : ",book[5])
        try:
            box = int(box)
            if box == 1+i:
                box = newBox()
            elif box > i+1:
                box = -1
        except ValueError:
            box = -1
            continue"""
    list_boxes = library.listBoxes()
    choices = [ "{} - {}".format(i+1,elt[1]) for i, elt in enumerate(list_boxes)]
    box = limit_or_choose(choices,' box',book[5])
    list_boxes = library.listBoxes()
    box_name = list_boxes[box-1][1]  
    print("""New book :
        Name : {}
        Authors : {} - {}
        Publisher : {} - {}
        Other informations : {}
        Box : {} - {}""".format(name,
                                authors, authors_names,
                                publisher,publisher_name,
                                more,
                                box,box_name))
    while True:
        answer = input("Are you satisfied ? (y/n) : ")
        if 'y' in answer.lower():
            if update:
                library.updateBook(book[0],name,authors,publisher,more,box)
            else:
                library.addBook(name,authors,publisher,more,box)
            print("Book saved")
            break
        elif 'n' in answer.lower():
            print("Discarded")
            break
           
def newLibrary(update=False,lib=('',)*5):
    name = ''
    place = ''
    lines = -1
    columns = -1
    while name == '':
        name = finput("Enter library's name : ",lib[1])
    while place == "":
        place = finput("Enter library's whereabouts : ",lib[2])
    while lines < 0:
        lines = int(finput('Enter number of lines : ',lib[3]))
    while columns < 0:
        columns = int(finput('Enter number of columns : ',lib[4]))
    print(drawLib(lines,columns))
    while True:
        answer = input("""Name : {}
                       Whereabouts : {}
                       Lines : {}
                       Columns : {}
                       Are you satisfied ? (y/n)""".format(name,place,lines,columns))
        if 'y' in answer.lower():
            if update:
                library.updateLibrary(lib[0],name,place,lines,columns)
            else:
                library.addLibrary(name,place,lines,columns)
            return library.findLibraryID(name)
        elif 'n' in answer.lower():
            return newLibrary(update,lib)

def newPublisher(update=False,pre_publisher=('',)*2):
    name = ''
    while name == "":
        name = finput("Enter publisher's name : ",pre_publisher[1])
    while True:
        answer = input("{} : are you satisfied ? (y/n) : ".format(name))
        if 'y' in answer.lower():
            if update:
                library.updatePublisher(pre_publisher[0],name)
            else:
                library.addPublisher(name)
            return library.findPublisherID(name)
        elif 'n' in answer.lower():
            return newPublisher(update,pre_publisher)
        
        
        
    
