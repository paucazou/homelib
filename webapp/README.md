# Homelib — application web

Tout ce que faisaient l'interface Qt (`gui/`) et la ligne de commande
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
| `volumes.py` compte des tomes            | onglet Statistiques, les cas douteux se règlent dans Outils |
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

## Deux points à savoir

**Le Pi fait foi.** L'application web écrit dans le `Library.db` de palantir.
Le programme de bureau continue de fonctionner, mais `dbupdater.py` remplace sa
copie par celle du Pi dès qu'elles diffèrent : saisir un livre dans l'interface
Qt pendant que le Pi tourne, c'est le perdre à la synchronisation suivante.

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
