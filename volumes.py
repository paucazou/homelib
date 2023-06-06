"""Calcule le nombre de volumes d'après les détails supplémentaires. Pas tout à fait au point"""

import mainclass

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
    txt = txt.lower()
    if not ('volumes' in txt or 'tomes' in txt):
        return 1 # why 1? Because there is at least one volume!
    l = txt.split()
    nb = 0
    for i, elt in enumerate(l):
        if elt in ("volumes","tomes") and i > 0:
            try:
                nb += to_int(l[i-1])
            except ValueError:
                print(txt)
                continue
    return nb

def volumes_nb_in_db(db: str) -> int:
    """Finds the number of volumes in a database"""
    l = mainclass.Library(db)
    books = l.listBooks()
    nb = 0
    for b in books:
        nb += volumes_nb(b[4])
    return nb
