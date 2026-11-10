"""Installation du mod dans le dossier mods d'Azahar, et désinstallation (tâche I2).

    python archipelago/installation/installer.py installer --rom <ROM déchiffrée> --patch <dossier>
                                                [--mods <dossier mods>] [--version V]
    python archipelago/installation/installer.py desinstaller [--mods <dossier mods>]
    python archipelago/installation/installer.py etat [--mods <dossier mods>]

`--patch` : dossier produit par `python tools/ap_patch.py creer` (code.bps, exheader.bps, manifeste.json).
`--mods` : racine des mods (par défaut celle d'Azahar détectée par `azahar.py`, en général
%APPDATA%/Azahar/load/mods) ; le mod va dans `<mods>/00040000001B2900/`.

Étapes : extraction depuis la ROM (`rom3ds.py`), application des BPS avec vérification des SHA-1 source et
cible du manifeste (`bps.py`, même décodeur que tools/ap_patch.py), puis dépôt de `code.bin` et
`exheader.bin`. Avant d'écrire, tout fichier déjà présent du même nom, ainsi que `code.ips`/`code.bps` (qu'Azahar
appliquerait en plus), est DÉPLACÉ tel quel dans `ykw2ap_sauvegarde/` ; l'estampille `ykw2ap.json`
(écrite en dernier) note la version, les SHA-1 déposés et ce qui a été sauvegardé. La désinstallation remet
exactement l'état d'avant (fichiers d'origine restaurés, avec leurs dates ; dossiers créés supprimés).
Les dossiers `romfs/` (traduction LayeredFS…) et `ap_backup/` (ancien mod) ne sont jamais touchés.

Option `--libelle` : le bouton « Transfert de données EF/FB » de l'écran titre affiche « Archipelago »
(`libelle.py`) : un patch BPS par archive de langue est déposé dans `romfs_ext/` (généré depuis le RomFS de la
ROM, ou de `--romfs`), noté dans la même estampille et retiré par la désinstallation. Une langue dont l'archive
est déjà modifiée par un autre mod (`romfs/yw2_lg_<LG>.fa`, `romfs_ext/yw2_lg_<LG>.fa.*`) est laissée intacte.

Option `--essai-lieu-libre` (ESSAI, jamais activé par le lanceur ni par le paquet) : des Yo-kai à combattre posés
aux lieux de la table `lieux_libres.txt` (`lieux.py`, `lieu_libre.py` ; `--essai-table`, ou un lieu unique par
`--essai-lieu`), fusionnés dans le patch `romfs_ext/yw2_a.fa.bps`. La même commande SANS l'option remet
l'installation normale ; la désinstallation retire tout.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
    from . import bps, rom3ds
except ImportError:                     # lancé comme script
    import bps  # type: ignore[no-redef]
    import rom3ds  # type: ignore[no-redef]

ESTAMPILLE = "ykw2ap.json"
SAUVEGARDE = "ykw2ap_sauvegarde"
FICHIERS_MOD = ("code.bin", "exheader.bin")
FICHIERS_EN_CONFLIT = ("code.ips", "code.bps")        # Azahar les appliquerait par-dessus notre code.bin
INTOUCHABLES = ("romfs", "ap_backup")
# exception : archives sonores remplacées par la musique aléatoire sous Azahar (installation/musique.py : Azahar ne lit
# pas les patchs des sous-dossiers de romfs_ext/) ; seulement ces fichiers-là, jamais le reste de romfs/
ROMFS_PERMIS = tuple(f"romfs/snd/product/yw_sound{lg}.bcsar" for lg in ("", "_de", "_es", "_fr", "_it", "_nl", "_ru"))
MOD_ID = "ykw2ap"
TMP = ".ykw2ap-tmp"


class ErreurInstallation(Exception):
    """Refus ou échec ; le message est destiné au joueur. Rien n'a été modifié, ou tout a été remis."""


def sha1(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()


def sha1_fichier(p: Path) -> str:
    return sha1(p.read_bytes())


@dataclass
class Patch:
    manifeste: dict
    code_bps: bytes
    exheader_bps: bytes
    version: str


def charger_patch(dossier: str | Path, version: str | None = None) -> Patch:
    d = Path(dossier)
    try:
        man = json.loads((d / "manifeste.json").read_text(encoding="utf-8"))
        code_bps = (d / "code.bps").read_bytes()
        exh_bps = (d / "exheader.bps").read_bytes()
    except (OSError, ValueError) as e:
        raise ErreurInstallation(f"Patch du mod introuvable ou illisible dans {d} : {e}") from e
    for k in ("code", "exheader"):
        if not isinstance(man.get(k), dict) or not {"source_sha1", "cible_sha1"} <= man[k].keys():
            raise ErreurInstallation(f"manifeste.json incomplet (section {k})")
    fichiers = man.get("fichiers", {})
    for n, b in (("code.bps", code_bps), ("exheader.bps", exh_bps)):
        if n in fichiers and fichiers[n] != sha1(b):
            raise ErreurInstallation(f"{n} ne correspond pas au manifeste (fichier abîmé ?)")
    v = version or man.get("version") or f"dev-{man['code']['cible_sha1'][:12]}"
    return Patch(man, code_bps, exh_bps, v)


def appliquer_patchs(code: bytes, exheader: bytes, patch: Patch) -> tuple[bytes, bytes]:
    """Applique code.bps et exheader.bps ; vérifie les SHA-1 source et cible du manifeste."""
    res = []
    for nom, src, p in (("code", code, patch.code_bps), ("exheader", exheader, patch.exheader_bps)):
        attendu = patch.manifeste[nom]
        if sha1(src) != attendu["source_sha1"]:
            raise ErreurInstallation(f"Le {nom} de la ROM n'est pas celui attendu par le patch (SHA-1 "
                                     f"{sha1(src)}, attendu {attendu['source_sha1']}).")
        try:
            dst = bps.bps_appliquer(src, p)
        except bps.ErreurBps as e:
            raise ErreurInstallation(f"Application de {nom}.bps impossible : {e}") from e
        if sha1(dst) != attendu["cible_sha1"]:
            raise ErreurInstallation(f"{nom} patché : SHA-1 inattendu ({sha1(dst)})")
        res.append(dst)
    return res[0], res[1]


# ------------------------------------------------------------------------------------------------
# Dossier mods
# ------------------------------------------------------------------------------------------------
def dossier_mods_defaut() -> Path:
    try:
        from . import azahar
    except ImportError:
        import azahar  # type: ignore[no-redef]
    u = azahar.dossier_utilisateur()
    if u is None:
        raise ErreurInstallation("Dossier utilisateur d'Azahar introuvable : lancez Azahar une fois, ou "
                                 "indiquez le dossier mods.")
    return u / "load" / "mods"


def dossier_titre(dossier_mods: str | Path, title_id: str = rom3ds.TITLE_ID_STR) -> Path:
    return Path(dossier_mods) / title_id


def lire_estampille(dossier_mods: str | Path) -> dict | None:
    p = dossier_titre(dossier_mods) / ESTAMPILLE
    if not p.is_file():
        return None
    try:
        e = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as ex:
        raise ErreurInstallation(f"Estampille {p} illisible : {ex}") from ex
    if e.get("mod") != MOD_ID:
        raise ErreurInstallation(f"{p} n'est pas une estampille du mod")
    return e


def _ecrire_atomique(p: Path, data: bytes) -> None:
    t = p.with_name(p.name + TMP)
    t.write_bytes(data)
    os.replace(t, p)


def _creer_dossiers(d: Path) -> list[str]:
    """Crée d et ses parents manquants ; renvoie les dossiers créés, du plus haut au plus profond."""
    manquants = []
    x = d
    while not x.exists():
        manquants.append(x)
        if x.parent == x:
            break
        x = x.parent
    cree = []
    for m in reversed(manquants):
        m.mkdir()
        cree.append(str(m))
    return cree


@dataclass
class Rapport:
    action: str                           # "installe", "mis_a_jour", "deja_installe", "desinstalle"
    dossier: Path
    version: str | None = None
    sauvegardes: list[str] = field(default_factory=list)
    avertissements: list[str] = field(default_factory=list)


def installer_fichiers(code_mod: bytes, exheader_mod: bytes, dossier_mods: str | Path, version: str,
                       infos: dict | None = None, supplementaires: dict[str, bytes] | None = None,
                       avertissements: list[str] | None = None) -> Rapport:
    """Dépose code.bin et exheader.bin (déjà patchés) avec sauvegarde et estampille.

    `supplementaires` : autres fichiers du mod, chemins relatifs au dossier du titre avec « / » (ex.
    `romfs_ext/yw2_lg_fr.fa.bps`, libellé du bouton) ; ils ne doivent pas exister (sauf s'ils sont à nous),
    leurs dossiers créés sont notés pour la désinstallation. Un fichier supplémentaire d'une installation
    précédente absent de la nouvelle liste est retiré."""
    cible = dossier_titre(dossier_mods)
    nouveaux = {"code.bin": code_mod, "exheader.bin": exheader_mod}
    for n, d in (supplementaires or {}).items():
        if n in nouveaux or n.startswith("/") or ".." in n.split("/") or \
                (n.split("/")[0] in INTOUCHABLES + (SAUVEGARDE,) and n not in ROMFS_PERMIS):
            raise ErreurInstallation(f"chemin de fichier du mod refusé : {n}")
        nouveaux[n] = d
    sha_nouveaux = {n: sha1(d) for n, d in nouveaux.items()}
    avert = list(avertissements or [])
    if (cible / "exefs").is_dir():
        avert.append(f"{cible / 'exefs'} existe (autre mod) : Azahar pourrait l'utiliser à la place de code.bin ; "
                     "il n'est pas modifié.")
    est = lire_estampille(dossier_mods)
    if est is not None:
        # déjà installé : rien à faire si identique ; sinon mise à jour de NOS fichiers seulement
        for n, s in est["fichiers"].items():
            p = cible / n
            if p.exists() and sha1_fichier(p) != s:
                raise ErreurInstallation(f"{p} a été modifié depuis l'installation du mod : désinstallez le mod "
                                         "ou retirez ce fichier avant de réinstaller.")
        if est.get("version") == version and est["fichiers"] == sha_nouveaux and \
                all((cible / n).is_file() for n in nouveaux):
            return Rapport("deja_installe", cible, version, avertissements=avert)
    for n in nouveaux:
        if n not in FICHIERS_MOD and (cible / n).exists() and (est is None or n not in est["fichiers"]):
            raise ErreurInstallation(f"{cible / n} existe déjà (autre mod ?) : installation impossible.")
    a_retirer = [n for n in (est["fichiers"] if est is not None else {}) if n not in nouveaux]
    a_sauver = []
    for n in FICHIERS_MOD + FICHIERS_EN_CONFLIT:
        p = cible / n
        if not p.exists():
            continue
        if est is not None and n in est["fichiers"]:
            continue                       # c'est notre fichier (SHA-1 vérifié plus haut)
        if not p.is_file():
            raise ErreurInstallation(f"{p} n'est pas un fichier : installation impossible.")
        a_sauver.append(n)
    sauv = cible / SAUVEGARDE
    deja_sauves = dict(est["sauvegarde"]) if est is not None else {}
    for n in a_sauver:
        if n in deja_sauves or (sauv / n).exists():
            raise ErreurInstallation(f"{cible / n} : une sauvegarde de ce fichier existe déjà dans {sauv} ; "
                                     "désinstallez d'abord le mod.")
    if est is None and sauv.exists():
        raise ErreurInstallation(f"{sauv} existe déjà sans installation du mod : retirez-le d'abord.")

    # --- modifications, annulées en cas d'erreur ---
    crees: list[str] = []
    deplaces: list[str] = []
    ecrits: list[str] = []
    anciens: dict[str, bytes] = {}
    sauv_cree = False
    retires: dict[str, bytes] = {}
    try:
        crees = _creer_dossiers(cible)
        for n in nouveaux:
            if "/" in n:
                crees += _creer_dossiers((cible / n).parent)
        if a_sauver and not sauv.exists():
            sauv.mkdir()
            sauv_cree = True
        for n in a_sauver:
            deja_sauves[n] = sha1_fichier(cible / n)
            os.replace(cible / n, sauv / n)
            deplaces.append(n)
        for n, d in nouveaux.items():
            if (cible / n).exists():
                anciens[n] = (cible / n).read_bytes()     # notre version précédente (mise à jour)
            _ecrire_atomique(cible / n, d)
            ecrits.append(n)
        for n in a_retirer:
            if (cible / n).exists():
                retires[n] = (cible / n).read_bytes()
                (cible / n).unlink()
        e = {
            "mod": MOD_ID,
            "version": version,
            "installe_le": _dt.datetime.now().isoformat(timespec="seconds"),
            "title_id": rom3ds.TITLE_ID_STR,
            "fichiers": sha_nouveaux,
            "sauvegarde": deja_sauves,
            "dossiers_crees": (est or {}).get("dossiers_crees", []) + crees,
            "dossier_sauvegarde_cree": bool((est or {}).get("dossier_sauvegarde_cree")) or sauv_cree,
            "infos": infos or {},
        }
        _ecrire_atomique(cible / ESTAMPILLE, json.dumps(e, indent=1, ensure_ascii=False).encode("utf-8"))
    except BaseException:
        for n, d in retires.items():
            _ecrire_atomique(cible / n, d)
        for n in ecrits:
            if n in anciens:
                _ecrire_atomique(cible / n, anciens[n])
            else:
                (cible / n).unlink(missing_ok=True)
        for n in deplaces:
            os.replace(sauv / n, cible / n)
        if sauv_cree:
            sauv.rmdir()
        for d in reversed(crees):
            try:
                Path(d).rmdir()
            except OSError:
                pass
        raise
    return Rapport("mis_a_jour" if est is not None else "installe", cible, version, a_sauver, avert)


def installer(rom: str | Path, dossier_patch: str | Path, dossier_mods: str | Path | None = None,
              version: str | None = None, libelle: bool = False, romfs: str | Path | None = None,
              langues: list[str] | None = None, icone: bool = False, lieu_libre=None,
              invitations: bool = False) -> Rapport:
    """Parcours complet depuis la ROM déchiffrée du joueur (`libelle` : bouton « Archipelago » ; `icone` : icône
    de l'objet vitrine ; `lieu_libre` : un `lieu_libre.Lieu` ou une liste (table), ESSAI d'invités à des lieux
    libres ; patchs générés depuis le RomFS de la ROM, ou du dossier `romfs` s'il est donné)."""
    patch = charger_patch(dossier_patch, version)
    try:
        contenu = rom3ds.extraire(rom)
    except rom3ds.ErreurRom as e:
        raise ErreurInstallation(str(e)) from e
    return installer_depuis_contenu(contenu, patch, dossier_mods,
                                    libelle_source=(romfs or rom) if (libelle or icone or lieu_libre or invitations)
                                    else None,
                                    langues=langues, libelle=libelle, icone=icone, lieu_libre=lieu_libre,
                                    invitations=invitations)


def preparer_libelle(source: str | Path, dossier_mods: str | Path,
                     langues: list[str] | None = None) -> tuple[dict[str, bytes], list[str]]:
    """Patchs `romfs_ext/yw2_lg_<LG>.fa.bps` du libellé seul (voir libelle.py), sans les langues en conflit."""
    supp, avert, _infos = preparer_romfs(source, dossier_mods, langues, libelle=True, icone=False)
    return supp, avert


def conflits_romfs(titre: Path, fichiers: list[str], nos_fichiers=()) -> tuple[list[str], list[str]]:
    """Écarte les archives déjà modifiées par un autre mod (`romfs/<archive>`, ou `romfs_ext/<archive>.{ips,bps,
    stub}` qui n'est pas à nous) : on ne les touche pas. Renvoie (archives gardées, avertissements)."""
    garde, avert = [], []
    for fa in fichiers:
        autres = [titre / "romfs" / fa] + [titre / "romfs_ext" / (fa + e) for e in (".ips", ".bps", ".stub")]
        pris = [a for a in autres if a.exists() and a.relative_to(titre).as_posix() not in nos_fichiers]
        if pris:
            avert.append(f"{fa} : {', '.join(str(a) for a in pris)} existe (autre mod) : ni libellé ni icône "
                         "installés pour cette archive")
            continue
        garde.append(fa)
    return garde, avert


def preparer_romfs(source: str | Path, dossier_mods: str | Path, langues: list[str] | None = None,
                   libelle: bool = True, icone: bool = True,
                   lieu_libre=None, invitations: bool = False,
                   apparence=None) -> tuple[dict[str, bytes], list[str], dict]:
    """Patchs `romfs_ext/<archive>.bps` générés depuis le RomFS du joueur : libellé « Archipelago » du bouton
    (libelle.py, archives de langue) et icône de l'objet vitrine (icone.py : `yw2_a.fa` et archives de langue
    de/nl/ru). UN patch par archive : les remplacements d'une même archive sont fusionnés. Si les deux sont
    demandés, l'échec de l'un n'empêche pas l'autre (avertissement). Renvoie ({chemin: octets},
    avertissements, {"libelle": [chemins], "icone": [chemins]}) pour l'estampille (+ "lieu_libre" avec l'essai).

    `lieu_libre` (ESSAI ; `lieu_libre.Lieu`, liste de lieux ou None) : PNJ ajoutés à des cartes (lieu_libre.py,
    table `lieux_libres.txt`), dans `yw2_a.fa`, dont
    l'archive GRANDIT (octets ajoutés à la fin). Ce module et la grande image de l'icône réécrivent tous deux les
    tables de tête : la grande image est alors ajoutée à la tête déjà modifiée par l'essai (un seul calcul, par
    `lieu_libre.modifications(grande_icone=True)`). Si l'essai échoue, l'icône est installée comme d'habitude.

    `invitations` : les 33 objets du jeu « Invitation : <nom> » (invitations.py) : configuration des objets et grande
    image dans `yw2_a.fa` (tête réécrite : même chaînage que l'essai, la grande image de la vitrine est ajoutée à la
    tête des invitations), textes dans TOUTES les archives de langue présentes (qui grandissent), enveloppe dans les
    atlas d'icônes. TOUT OU RIEN : si une seule de ces archives ne peut pas être modifiée (autre mod, fichier
    inattendu, patch impossible), rien des invitations n'est installé (avertissement) et le reste est préparé comme
    sans elles. Sans `invitations`, le résultat est celui d'avant, octet pour octet.

    (V3, lot 20 : l'option `invitations_sac` du lot 14, 16 objets ORDINAIRES du sac pour les invitations des Yo-kai
    de Pièce 5 étoiles, est retirée avec ces invitations.)

    `apparence` : réglage de l'onglet « Apparence » du lanceur (champ `apparence` de `config.json`, apparence.py) :
    textures du personnage principal remplacées dans `yw2_a.fa`. Le module est CHAÎNÉ après les autres modules de
    cette archive (il part de leur tête et garde leurs ajouts de fin) et avant la grande image de la vitrine (ajout
    par `arc0_ajouter_fichier`, qui doit venir en dernier : elle abaisse le début des données) ; ses fichiers sont
    notés dans `infos["apparence"]`. Le réglage peut porter un mod d'apparence importé (clé `import`,
    apparence_import.py) : ses fichiers passent par le même chaînage et l'emportent sur ceux de la tenue. S'il
    échoue, tout est préparé comme sans lui (avertissement). Sans réglage (None
    ou réglage d'origine), rien ne change : le résultat est celui d'avant, octet pour octet."""
    return _preparer_romfs(source, dossier_mods, langues, libelle, icone, lieu_libre, invitations, apparence)


def _preparer_romfs(source, dossier_mods, langues, libelle, icone, lieu_libre, invitations, apparence=None):
    """Corps de `preparer_romfs`."""
    try:
        from . import (apparence as app, bps, icone as ico, level5, libelle as lib, lieu_libre as ll,
                       invitations as inv)
    except ImportError:
        import apparence as app  # type: ignore[no-redef]
        import bps  # type: ignore[no-redef]
        import icone as ico  # type: ignore[no-redef]
        import level5  # type: ignore[no-redef]
        import libelle as lib  # type: ignore[no-redef]
        import lieu_libre as ll  # type: ignore[no-redef]
        import invitations as inv  # type: ignore[no-redef]
    try:
        src = level5.SourceRomfs(source)
    except (level5.ErreurFormat, OSError) as e:
        raise ErreurInstallation(f"RomFS : {e}") from e
    avec_apparence = bool(app.normaliser(apparence))
    # avec l'apparence, la grande image de la vitrine est posée APRÈS elle (`app.chainer`) : les autres modules de
    # yw2_a.fa sont alors calculés sans elle
    grande_apres = avec_apparence and icone

    def sans_apparence(pourquoi: str):
        supp, avert, infos = _preparer_romfs(source, dossier_mods, langues, libelle, icone, lieu_libre, invitations,
                                             None)
        infos["apparence"] = []
        return supp, [f"Apparence du personnage non installée ({pourquoi})"] + avert, infos

    def sans_invitations(pourquoi: str):
        supp, avert, infos = _preparer_romfs(source, dossier_mods, langues, libelle, icone, lieu_libre, False,
                                             apparence)
        infos["invitations"] = []
        return supp, [f"Objets « Invitation » non installés ({pourquoi}) : les invitations (et l'Abonnement de "
                      "train, le Voyage dans le temps, les Miroirs, le Mirapo de poche, le Trousseau du "
                      "donjon) restent des objets Archipelago sans objet dans l'inventaire"] + avert, infos

    est = lire_estampille(dossier_mods)
    fichiers_inv, necessaires = None, []
    invs = None                                  # None : ceux du module (`invitations.objets_installes()` : invitations
                                                 # puis objets de voyage de la V3)
    if invitations:
        # tout ou rien : chaque archive du module doit être libre (aucun autre mod), et ses fichiers lisibles
        try:
            necessaires = inv.archives(src)
            garde, refus = conflits_romfs(dossier_titre(dossier_mods), necessaires, (est or {}).get("fichiers", {}))
            if len(garde) != len(necessaires):
                return sans_invitations("; ".join(refus))
            fichiers_inv = inv.fichiers_a(src, invs)
        except (level5.ErreurFormat, OSError, ValueError, KeyError) as e:
            return sans_invitations(str(e))
    icone_dans_essai = []
    cases = inv.cases_atlas() if invitations else ()   # enveloppe + objets de voyage (cases réaffectées)
    # la tête de `yw2_a.fa` n'est calculée qu'une fois : par l'essai « lieu libre » s'il est demandé (les fichiers
    # des invitations lui sont passés), sinon par les invitations, sinon par l'icône seule
    icone_ailleurs = lieu_libre is not None or invitations

    def essai_lieu():
        m, a, resume = ll.modifications(src, lieu_libre, grande_icone=icone and not grande_apres,
                                        supplement=fichiers_inv[:2] if fichiers_inv else None)
        if grande_apres:
            pass                                 # grande image posée après l'apparence
        elif icone and not resume.icone:         # la grande image n'a pas pu être ajoutée à la tête de l'essai
            a = a + ["grande image de la vitrine non installée avec l'essai « lieu libre »"]
        elif icone:
            icone_dans_essai.append(ll.ARCHIVE)
        return m, a

    def objets_invitation():
        seules = lieu_libre is None
        m, a, _res = inv.modifications(src, invs, grande_vitrine=icone and seules and not grande_apres,
                                       fichiers=None if seules else fichiers_inv)
        if icone and seules and not grande_apres:
            if a:
                a = a + ["grande image de la vitrine non installée avec les objets « Invitation »"]
            else:
                icone_dans_essai.append(inv.ARCHIVE)
        return m, a
    etapes = [(cle, nom, f) for cle, nom, f, actif in (
        ("libelle", "Libellé du bouton", lambda: lib.modifications(src, langues), libelle),
        ("icone", "Icône de la vitrine",
         (lambda: ico.modifications(src)) if not icone_ailleurs and not grande_apres
         else (lambda: ico.modifications(src, grande=False)) if not icone_ailleurs
         else (lambda: ico.modifications(src, grande=False)) if not invitations
         else (lambda: ico.modifications(src, grande=False, cases_en_plus=cases)),
         icone),
        ("lieu_libre", "Essai « lieu libre »", essai_lieu, lieu_libre is not None),
        ("invitations", "Objets « Invitation »", objets_invitation, invitations)) if actif]
    mods, avert = [], []
    for cle, nom, fonction in etapes:
        if invitations and cle in ("lieu_libre", "invitations"):
            try:
                m, a = fonction()
            except (level5.ErreurFormat, OSError) as e:
                # l'essai porte les fichiers des invitations dans la même tête : son échec les emporte
                return sans_invitations(f"{nom} : {e}")
            mods += [(cle, x) for x in m]
            avert += a
            continue
        try:
            m, a = fonction()
        except (level5.ErreurFormat, OSError) as e:
            if len(etapes) == 1:
                raise ErreurInstallation(f"{nom} : {e}") from e
            avert.append(f"{nom} : {e}")
            if cle == "lieu_libre" and icone and not grande_apres:   # repli : la grande image seule, comme sans l'essai
                m, a = ico.modifications_grande(src, sha1_tete=ico.SHA1_TETE_A)
                mods += [("icone", x) for x in m]
                avert += a
            continue
        mods += [(cle, x) for x in m]
        avert += a
    portes: dict[str, list[str]] = {}            # archive -> modules dont le travail est dans les modifications chaînées
    if avec_apparence:
        # chaîne : tête des modules précédents de yw2_a.fa -> apparence -> grande image de la vitrine
        try:
            rempl, res_app = app.fichiers_a(src, apparence)
            prec = [m for c, m in mods if m.fichier == app.ARCHIVE]
            cles_prec = sorted({c for c, m in mods if m.fichier == app.ARCHIVE})
            m2, a2, pose, grande = app.chainer(src, prec, rempl, grande_apres)
        except Exception as e:                   # noqa: BLE001 - l'apparence est cosmétique : jamais bloquante
            return sans_apparence(str(e) or type(e).__name__)
        if not pose:
            return sans_apparence("; ".join(a2))
        mods = [(c, m) for c, m in mods if m.fichier != app.ARCHIVE] + [("apparence", m) for m in m2]
        portes[app.ARCHIVE] = cles_prec + (["icone"] if grande else [])
        avert += app.messages(res_app) + a2
    par_fichier: dict[str, list] = {}
    for cle, m in mods:
        par_fichier.setdefault(m.fichier, []).append((cle, m))
    garde, avert2 = conflits_romfs(dossier_titre(dossier_mods), sorted(par_fichier),
                                   (est or {}).get("fichiers", {}))
    supp: dict[str, bytes] = {}
    infos: dict[str, list] = {"libelle": [], "icone": []}
    if lieu_libre is not None:
        infos["lieu_libre"] = []
    if invitations:
        infos["invitations"] = []
    if avec_apparence:
        infos["apparence"] = []
    for fa in garde:
        try:
            f, base, taille = src.ouvrir(fa)
            with f:
                sur_place, ajout = ll.separer_ajout([m for _c, m in par_fichier[fa]], taille)
                p = bps.bps_sur_place(f, base, taille, sur_place, ajout)
        except (level5.ErreurFormat, bps.ErreurBps, OSError) as e:
            if invitations and fa in necessaires:
                return sans_invitations(f"{fa} : {e}")
            avert.append(f"{fa} : {e} ; archive non modifiée")
            continue
        chemin = f"romfs_ext/{fa}.bps"
        supp[chemin] = p
        for cle in [c for c, _m in par_fichier[fa]] + portes.get(fa, []):
            if chemin not in infos[cle]:
                infos[cle].append(chemin)
        if fa in icone_dans_essai and chemin not in infos["icone"]:
            infos["icone"].append(chemin)        # la grande image est dans les modifications de l'essai
        if invitations and fa == inv.ARCHIVE and lieu_libre is not None and chemin not in infos["invitations"]:
            infos["invitations"].append(chemin)  # la configuration est dans les modifications de l'essai
    if invitations and sorted(infos["invitations"]) != sorted(f"romfs_ext/{fa}.bps" for fa in necessaires):
        return sans_invitations("une archive nécessaire n'a pas pu être préparée")
    return supp, avert + avert2, infos


def installer_depuis_contenu(contenu: rom3ds.ContenuRom, patch: Patch,
                             dossier_mods: str | Path | None = None, libelle_source: str | Path | None = None,
                             langues: list[str] | None = None, libelle: bool = True,
                             icone: bool = False, lieu_libre=None, invitations: bool = False) -> Rapport:
    code_mod, exh_mod = appliquer_patchs(contenu.code, contenu.exheader, patch)
    infos = {"source_code_sha1": contenu.sha1_code, "source_exheader_sha1": contenu.sha1_exheader,
             "code_produit": contenu.code_produit}
    dossier_mods = dossier_mods or dossier_mods_defaut()
    supp, avert = {}, []
    if libelle_source is not None and (libelle or icone or lieu_libre is not None or invitations):
        supp, avert, inf = preparer_romfs(libelle_source, dossier_mods, langues, libelle=libelle, icone=icone,
                                          lieu_libre=lieu_libre, invitations=invitations)
        for cle, actif in (("libelle", libelle), ("icone", icone), ("lieu_libre", lieu_libre is not None),
                           ("invitations", invitations)):
            if actif:
                infos[cle] = sorted(inf.get(cle, []))
        if lieu_libre is not None and inf["lieu_libre"]:
            lieux = lieu_libre if isinstance(lieu_libre, (list, tuple)) else [lieu_libre]
            infos["lieu_libre_essai"] = " | ".join(x.decrire() for x in lieux)
    return installer_fichiers(code_mod, exh_mod, dossier_mods, patch.version, infos, supp, avert)


def desinstaller(dossier_mods: str | Path | None = None) -> Rapport:
    """Remet le dossier du jeu exactement comme avant l'installation."""
    dossier_mods = dossier_mods or dossier_mods_defaut()
    cible = dossier_titre(dossier_mods)
    est = lire_estampille(dossier_mods)
    if est is None:
        raise ErreurInstallation(f"Le mod n'est pas installé dans {cible} (pas d'estampille {ESTAMPILLE}).")
    sauv = cible / SAUVEGARDE
    # contrôles avant toute modification
    for n, s in est["fichiers"].items():
        p = cible / n
        if p.exists() and sha1_fichier(p) != s:
            raise ErreurInstallation(f"{p} a été modifié depuis l'installation : il n'est pas supprimé. "
                                     "Retirez-le vous-même puis relancez la désinstallation.")
    for n, s in est["sauvegarde"].items():
        if not (sauv / n).is_file() or sha1_fichier(sauv / n) != s:
            raise ErreurInstallation(f"Sauvegarde {sauv / n} absente ou modifiée : restauration impossible.")
        if n not in est["fichiers"] and (cible / n).exists():
            raise ErreurInstallation(f"{cible / n} existe à nouveau : il écraserait la sauvegarde ; retirez-le.")
    # suppression de nos fichiers, puis restauration
    for n in est["fichiers"]:
        (cible / n).unlink(missing_ok=True)
    restaures = []
    for n in est["sauvegarde"]:
        os.replace(sauv / n, cible / n)
        restaures.append(n)
    (cible / ESTAMPILLE).unlink()
    avert = []
    if est.get("dossier_sauvegarde_cree") and sauv.is_dir():
        try:
            sauv.rmdir()
        except OSError:
            avert.append(f"{sauv} n'est pas vide : laissé en place.")
    for d in reversed(est.get("dossiers_crees", [])):
        try:
            Path(d).rmdir()
        except OSError:
            break                           # non vide (autre contenu ajouté depuis) : on le garde
    return Rapport("desinstalle", cible, est.get("version"), restaures, avert)


def main(argv: list[str] | None = None) -> int:
    for flux in (sys.stdout, sys.stderr):
        try:
            flux.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    i = sp.add_parser("installer")
    i.add_argument("--rom", type=Path, required=True)
    i.add_argument("--patch", type=Path, required=True)
    i.add_argument("--version")
    i.add_argument("--libelle", action="store_true",
                   help="bouton « Transfert de données EF/FB » renommé « Archipelago » (patchs romfs_ext/)")
    i.add_argument("--icone", action="store_true",
                   help="icône Archipelago de l'objet vitrine en jeu (patchs romfs_ext/, dont yw2_a.fa)")
    i.add_argument("--invitations", action="store_true",
                   help="objets du jeu « Invitation : <nom> » dans l'inventaire (patchs romfs_ext/ de yw2_a.fa et "
                        "de toutes les archives de langue ; tout ou rien)")
    i.add_argument("--romfs", type=Path,
                   help="avec --libelle/--icone : RomFS déjà extrait (défaut : celui de la ROM)")
    i.add_argument("--langues", help="avec --libelle : ex. fr,engb (défaut : toutes)")
    i.add_argument("--essai-lieu-libre", nargs="?", const="toujours", metavar="CONDITION",
                   help="ESSAI : invités à combattre posés aux lieux de la table (lieu_libre.py, patch de yw2_a.fa) ; "
                        "condition d'apparition des lieux qui n'en ont pas : toujours (défaut) ou "
                        "bit:0x<hachage d'un flag global>")
    i.add_argument("--essai-table", type=Path, metavar="FICHIER",
                   help="avec --essai-lieu-libre : table des lieux (défaut : installation/lieux_libres.txt)")
    i.add_argument("--essai-lieu", metavar="CARTE:X,Z | CARTE:X,Y,Z[,ANGLE]",
                   help="avec --essai-lieu-libre : UN lieu au lieu de la table (carte:x,z = ce que copie le lanceur ; "
                        "hauteur déduite)")
    i.add_argument("--essai-espece", metavar="0x<CHARA_PARAM>", help="avec --essai-lieu : autre espèce")
    i.add_argument("--essai-reste", action="store_true",
                   help="avec --essai-lieu : le Yo-kai reste à sa place après le combat")
    for p in (i, sp.add_parser("desinstaller"), sp.add_parser("etat")):
        p.add_argument("--mods", type=Path, help="racine des mods (défaut : celle d'Azahar)")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "etat":
            mods = a.mods or dossier_mods_defaut()
            e = lire_estampille(mods)
            print(f"{dossier_titre(mods)} : " + ("mod non installé" if e is None else
                  f"mod installé, version {e['version']} (le {e['installe_le']}), sauvegardés : "
                  f"{', '.join(e['sauvegarde']) or 'rien'}"))
            return 0
        lieu = None
        if a.cmd == "installer" and a.essai_lieu_libre:
            try:
                from . import level5, lieu_libre as ll
            except ImportError:
                import level5  # type: ignore[no-redef]
                import lieu_libre as ll  # type: ignore[no-redef]
            try:
                lieu = ll.lieux_demandes(a.essai_table, a.essai_lieu, a.essai_espece, a.essai_lieu_libre,
                                         a.essai_reste)
            except (level5.ErreurFormat, ValueError) as e:
                raise ErreurInstallation(f"essai « lieu libre » : {e}") from e
        r = installer(a.rom, a.patch, a.mods, a.version, a.libelle, a.romfs,
                      a.langues.split(",") if a.langues else None, a.icone, lieu, a.invitations) \
            if a.cmd == "installer" \
            else desinstaller(a.mods)
    except ErreurInstallation as e:
        print(f"ERREUR : {e}", file=sys.stderr)
        return 1
    print(f"{r.action} : {r.dossier} (version {r.version})" +
          (f" ; fichiers sauvegardés/restaurés : {', '.join(r.sauvegardes)}" if r.sauvegardes else ""))
    for w in r.avertissements:
        print(f"attention : {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
