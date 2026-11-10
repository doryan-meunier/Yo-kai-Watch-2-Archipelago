"""Point d'entrée du lanceur.

    pythonw archipelago/lanceur                 # fenêtre (dépôt)
    pythonw "Lanceur YKW2 Archipelago.pyw"      # fenêtre (paquet distribué)
    python  archipelago/lanceur --diagnostic    # état détecté, sans fenêtre (aide au dépannage)
    <point d'entrée> --role <rôle> [--sortie F] ...   # un rôle de `client/execution.py` (ROLES)

Exécutable empaqueté (`archipelago/exe/entree.py`, `outils/fabriquer_exe.py`) : UN seul exécutable joue tous les
rôles ; sans argument c'est le lanceur, et il se relance lui-même avec `--role client …` pour le client invisible
(`execution.commande`). `--role` marche aussi en mode normal (mêmes chemins de code, testables sans l'outil).
`--sortie F` (juste après le rôle) écrit dans F ce que le rôle affiche : un exécutable sans console n'a pas de
sortie standard (`"Lanceur ….exe" --role diagnostic --sortie diagnostic.txt`).
"""
from __future__ import annotations

import sys


def diagnostic(argv: list[str] | None = None) -> int:
    """`--dossier D` : dossier de données à examiner (défaut : celui du joueur)."""
    from . import logique as L
    from .presentation import texte_gdb, texte_mod, texte_version_azahar
    from .textes import langue_systeme

    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    argv = list(argv or [])
    dossier = argv[argv.index("--dossier") + 1] if "--dossier" in argv[:-1] else None
    l = L.Lanceur(L.StockageConfig(dossier)) if dossier else L.Lanceur()
    lg = l.langue() or langue_systeme()
    print(f"lanceur      : {L.VERSION_LANCEUR} ({L.ARCHIPELAGO})")
    i = l.maj_identite()
    print(f"paquet       : {i.version or '-'} ; build {i.build} ; forme {i.forme}")
    print(f"exécution    : {'exécutable empaqueté' if L.gele() else 'scripts Python'} ; Python "
          f"{sys.version.split()[0]} ; {sys.executable}")
    print(f"configuration: {l.stockage.fichier}")
    print(f"patch du mod : {l.dossier_patch() or '-'}")
    r = l.verifier_rom()
    print(f"ROM          : {l.config.rom or '-'} : {'OK' if r.ok else r.msg}")
    e = l.etat_azahar(rafraichir=True)
    print(f"Azahar       : {e.executable or '-'} ; {texte_version_azahar(lg, e)} ; en cours : {e.en_cours}")
    print(f"stub GDB     : {texte_gdb(lg, e)}")
    print(f"dossier mods : {e.dossier_mods or '-'}")
    print(f"mod          : {texte_mod(lg, l.etat_mod())}")
    p = l.problemes(e)
    print("prêt à jouer : " + ("oui" if not p else "non (" + ", ".join(str(m) for m in p) + ")"))
    return 0


def role_client(argv: list[str]) -> int:
    from . import logique  # noqa: F401  (met archipelago/client sur sys.path)
    import principal       # client invisible (archipelago/client/principal.py)
    return principal.main(argv)


def role_installer(argv: list[str]) -> int:
    from . import logique  # noqa: F401  (met archipelago/ sur sys.path)
    from installation import installer
    return installer.main(argv)


def role_lanceur(argv: list[str]) -> int:
    """Fenêtre du lanceur. `--dossier D` : dossier de données (défaut : celui du joueur ; essais, installation
    portable) ; transmis par la variable `YKW2AP_DOSSIER`, que tout le mod lit. Mise à jour interrompue : reprise
    d'abord, sans fenêtre (`maj_outil.avant_lanceur`)."""
    from . import maj_outil
    code = maj_outil.avant_lanceur()
    if code is not None:
        return code
    if "--dossier" in argv[:-1]:
        import os
        os.environ["YKW2AP_DOSSIER"] = argv[argv.index("--dossier") + 1]
    from .vue import main as fenetre
    return fenetre(argv)


def role_reparer(argv: list[str]) -> int:
    """Ce que fait le bouton « Installer » / « Réparer » de la fenêtre, sans fenêtre (dépannage, essais) :
    `--rom R [--dossier D] [--mods M] [--cartes]`. Installe le mod depuis la ROM dans le dossier mods (défaut :
    celui d'Azahar), génère les fichiers locaux du dossier de données (base des Yo-kai, noms, boutiques) et, avec
    `--cartes`, les cartes du tracker. Azahar doit être fermé."""
    import argparse
    from pathlib import Path
    from . import logique as L
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    p = argparse.ArgumentParser(prog="--role reparer", description="Installe ou répare le mod, sans fenêtre")
    p.add_argument("--rom", type=Path, required=True)
    p.add_argument("--dossier", type=Path)
    p.add_argument("--mods", type=Path)
    p.add_argument("--cartes", action="store_true")
    a = p.parse_args(argv)
    l = L.Lanceur(L.StockageConfig(a.dossier) if a.dossier else None, dossier_mods=a.mods)
    try:
        r = l.choisir_rom(a.rom)
        if not r.ok:
            raise L.ErreurLanceur(r.msg)
        rapport = l.installer(a.rom)
        print(f"installé : {rapport}")
        if a.cartes:
            print(f"cartes : {l.generer_cartes()}")
    except L.ErreurLanceur as e:
        print(f"ERREUR : {e.msg}", file=sys.stderr)
        return 1
    return 0


def role_maj(argv: list[str]) -> int:
    """Remplacement du lanceur, lancé depuis la copie `.maj/outil` : `maj_outil.py`. N'importe PAS `logique`."""
    from . import maj_outil
    return maj_outil.main(argv)


ROLES = {"lanceur": role_lanceur, "client": role_client, "diagnostic": diagnostic, "installer": role_installer,
         "reparer": role_reparer, "maj": role_maj}


def executer_role(role: str, argv: list[str]) -> int:
    """Exécute un rôle ; `--sortie F` en tête de `argv` : ce qu'il affiche va dans le fichier F (UTF-8)."""
    if role not in ROLES:
        print(f"rôle inconnu : {role} (rôles : {', '.join(sorted(ROLES))})", file=sys.stderr)
        return 2
    if argv[:1] == ["--sortie"] and len(argv) >= 2:
        import contextlib
        with open(argv[1], "w", encoding="utf-8") as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            return int(ROLES[role](argv[2:]) or 0)
    return ROLES[role](argv)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--role"] and len(argv) >= 2:
        return executer_role(argv[1], argv[2:])
    if argv[:1] == ["--client"]:                 # ancienne forme de `--role client`
        return role_client(argv[1:])
    if argv[:1] == ["--diagnostic"]:
        return diagnostic(argv[1:])
    return role_lanceur(argv)
