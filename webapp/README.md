# Homelib — application web

Tout ce que faisaient l'ancienne interface Qt (retirée) et la ligne de commande
(`homelib.pyw`, `clfun.py`) se retrouve ici, dans un navigateur, sur ordinateur
comme sur téléphone.

## Lancer

    python3 -m venv .venv
    .venv/bin/pip install -r requirements-web.txt
    .venv/bin/gunicorn --config deploy/gunicorn.conf.py webapp.wsgi:app

Sur le Raspberry Pi, `./deploy/install.sh` fait tout : environnement Python,
clé de déploiement, service systemd, minuterie quotidienne et nginx.
L'application répond alors sur **http://palantir:8888/**.

## Ce qui a été repris

| Ancien                                   | Nouveau |
|------------------------------------------|---------|
| Recherche par titre / auteur / éditeur / étagère / bibliothèque, et « tout » | idem, instantanée, sans accents obligatoires |
| Tableau triable, livres supprimés barrés | idem |
| Plan de la bibliothèque (`libpattern.py`) | dessin SVG, et les cases sont cliquables |
| Nouveau livre, auteur, éditeur, étagère, bibliothèque | idem, sans changer de fenêtre |
| `-d` supprimer un livre                  | idem, **avec annulation et corbeille** |
| `Boxes: mass` déplacer des livres        | onglet Outils |
| `Switch boxes` vider une étagère         | onglet Outils |
| `export.py` liste « auteur :: titre »    | onglet Export, plus CSV et JSON |
| `volumes.py` compte des tomes            | colonne `volumes` en base, les cas douteux se règlent dans Outils |
| Traduction FR/EN (`gui/i18n`)            | idem, bouton dans la barre du haut |

## Ce qui est nouveau

- **Corbeille** : les livres supprimés se retrouvent et se restaurent.
- **Historique** : les tables `*_backup` accumulaient des versions depuis des
  années sans que rien ne les affiche ; chaque livre montre les siennes.
- **Fusion d'auteurs et d'éditeurs**, impossible auparavant.
- **Doublons** repérés automatiquement.
- **Statistiques** : nombre de volumes, remplissage des étagères, etc.
- **ISBN** : saisir un ISBN pré-remplit titre, auteurs et éditeur.
- **Hors ligne** : le catalogue reste consultable sans réseau.
- **Git** : chaque ajout ou suppression devient un commit, poussé chaque nuit.
- **Fiches à imprimer** : une fiche par livre (à glisser dedans), par étagère
  (à coller sur le rayon, avec au besoin la liste de ses livres) ou par
  bibliothèque (avec le plan de ses étagères).  Chaque livre, étagère et
  bibliothèque a son bouton « Fiche » ; la page Fiches imprime en masse, filtrée
  par bibliothèque, étagère ou recherche, en quatre formats qui pavent une page
  A4 (dont les planches de 21 étiquettes 63,5 × 38,1 mm).  Tout se fait dans le
  navigateur, avec sa boîte d'impression.

## La colonne `volumes`

La table `books` a gagné une colonne `volumes` : le nombre de tomes physiques,
lu une fois pour toutes depuis les détails plutôt que recalculé à chaque
affichage. Elle vaut `NULL` tant que personne n'a tranché ; l'onglet Outils
liste ces cas. Le formulaire laisse la saisir à la main, et un champ vide veut
dire « déduis-le de la description ».

`books_backup` a reçu la même colonne, sans quoi `mainclass.backup()`, qui
recopie une ligne entière avec des marqueurs positionnels, aurait cessé de
fonctionner. Pour la même raison `addBook` nomme désormais ses colonnes, et les
trois `book[-1]` de `gui/mainwindow.py` — qui désignaient l'étagère — sont
devenus `book[5]`.

## Deux points à savoir

**Le Pi fait foi.** L'application web écrit dans le `Library.db` de palantir.
L'interface Qt et son `dbupdater.py` ont été retirés ; la ligne de commande
(`clfun.py`) travaille sur une copie locale, qui ne remonte pas toute seule.

**Rien n'est jamais effacé de la base.** Supprimer un livre le marque dans
`deleted_books` ; fusionner deux auteurs laisse le perdant en place, sans livre.
C'est délibéré : le programme de bureau retrouve auteurs et éditeurs par leur
*position* dans la liste (`list_authors[nb]`), donc retirer une ligne
réattribuerait silencieusement tous les livres suivants au mauvais auteur.
L'application web, elle, ne travaille que par identifiant.

## Structure

    webapp/db.py        accès à la base, jointures par identifiant
    webapp/volumes.py   comptage des tomes (nombres français compris)
    webapp/gitsync.py   commits groupés, envoi quotidien
    webapp/app.py       routes HTTP
    webapp/static/      interface (sans outil de compilation : c'est du JS)
    deploy/             systemd, nginx, installation
