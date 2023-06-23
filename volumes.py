"""Calcule le nombre de volumes d'après les détails supplémentaires. Pas tout à fait au point"""

import csv
import hashlib
import mainclass
import re

sums_file = "sums.csv"
# this global variable can be modified in the functions. Be careful
with open(sums_file, newline='') as f:
    sums = { elt[0] : int(elt[1]) for elt in csv.reader(f) }

with open("sums.csv") as f:
    # loading sums of the details to do not repeat manual entries
    details_sums = f.read()

def to_int(number: int | str) -> int:
    if isinstance(number, int):
        return number
    try:
        return int(number)
    except ValueError:
        pass
    if isinstance(number, str):
        number = number.lower().strip()
        french_numbers = {
            "zéro": 0, "un": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5,
            "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11,
            "douze": 12, "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16,
            "vingt": 20, "trente": 30, "quarante": 40, "cinquante": 50,
            "soixante": 60, "quatre-vingt": 80, "cent": 100
        }
        if number in french_numbers:
            return french_numbers[number]
        elif "et" in number:
            first, second = number.split("et")
            return to_int(first) + to_int(second)
        elif "cent" in number:
            if number == "cent":
                return 100
            else:
                first, second = number.split("cent")
                return to_int(first) * 100 + to_int(second)
        elif "-" in number:
            first, second = number.split("-")
            return to_int(first) + to_int(second)
    raise ValueError("Invalid input: {}".format(number))

def volumes_nb(txt: str) -> int:
    """Parses the txt to find the keywords 'tomes' or 'volumes'
    and return the number found before it"""
    old_txt = txt
    txt = re.sub("[\.]",
                 "",
                 txt.lower())
    txt = re.sub("[\n]"," ",txt)
    if not ('volumes' in txt or 'tomes' in txt):
        return 1 # why 1? Because there is at least one volume!
    l = txt.split()
    nb = 0
    for i, elt in enumerate(l):
        if elt in ("volumes","tomes") and i > 0:
            try:
                nb += to_int(l[i-1])
            except ValueError:
                continue
    if nb == 0:
        # try to find the value in sums.csv
        hashval = hashlib.md5(old_txt.encode())
        nb = sums.get(hashval.hexdigest(),0)
    if nb == 0:
        # no volum has been found: let's ask the user
        print(old_txt)
        while nb == 0:
            try:
                nb = int(input("Please enter the correct number: "))
            except ValueError:
                nb = 0

        print(hashval.hexdigest())
        with open(sums_file, 'a', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
            writer.writerow([hashval.hexdigest(), nb])

        sums[hashval.hexdigest()] = nb
    return nb

def volumes_nb_in_db(db: str) -> int:
    """Finds the number of volumes in a database"""
    l = mainclass.Library(db)
    books = l.listBooks()
    nb = 0
    for b in books:
        nb += volumes_nb(b[4])
    return nb

if __name__ == "__main__":
    volumes_nb_in_db("Library.db")
