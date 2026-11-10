"""Randomizer des boss : calcul du mélange (tables B et N de la boîte v7), commun au client, aux tests, au client de test
`tools/ap_boite_test.py rando-boss` et au tracker du lanceur. Bibliothèque standard seulement.

Analyse, règles et preuves : `docs/systemes/archipelago_rando_boss.md` (§3 boss échangeables et exclus, §4 mécanisme,
§9 implémentation) ; protocole : `docs/systemes/archipelago_boite.md` §24.

Le mélange est calculé CHEZ LE JOUEUR, de façon déterministe, depuis :
- la graine de `slot_data["rando_boss"]` (APWorld, 31 bits) et le mode (« meme_classe » ou « total ») ;
- les PLACES des boss, saisies à la main ci-dessous (hachages des rencontres, règle 6 de CLAUDE.md : identifiants
  seulement) ;
- la base locale `yokai_local.json` (format 4, générée depuis la ROM du joueur par `installation/rencontres.py`, jamais
  versionnée) : script de combat, règle et fichiers de chaque rencontre, combattants ; elle donne le DONNEUR de chaque
  boss (sa rencontre canonique de la table commune) et l'espèce du combattant de chaque boss sans script.
Même graine + même ROM (même empreinte des boss) = même mélange chez tous les joueurs de la graine.

Le jeu ne change JAMAIS le hachage d'une rencontre : la place garde son flag de victoire, ses déclencheurs et ses checks.
- B : place d'un boss à script X -> donneur de σ(X) (σ = permutation des 40 boss à script, par classe en mode
  « meme_classe », tous ensemble en mode « total ») ; les deux places de Crocho reçoivent le même donneur.
- N : place d'un boss sans script -> (espèce d'origine, espèce de σ_N(place)) (σ_N : permutation des 13 boss sans
  script entre eux, dans les deux modes : pas de mélange entre boss avec et sans script).
Anti-softlock (base au format 5, `exigees_boss`, docs `archipelago_rando_yokai.md` §3.4 et `archipelago_rando_boss.md`
§11) : un boss dont une espèce est exigée par le jeu (quête, Tablo-blabla, sceau, équipe…) et qu'on peut se faire
comme ami après le combat, ou une espèce à vaincre N fois / citée par une règle de combat, est FIGÉ : ni déplacé ni
remplacé (sur la ROM européenne : Draconfus, Faux Kappa, Misterre, Sabrille, Démophage, Anguigne, Triptyk, Carpitaine).
Périmètre (base au format 6, `archipelago_rando_boss.md` §12) : seuls les boss d'avant l'après-jeu sont mélangés ; les
boss d'après-jeu ou du réseau caché (`HORS_PERIMETRE`, toute la classe 3) sont figés, et aucun Yo-kai d'évènement n'est
place, donneur ni espèce d'un boss mélangé.
Force adaptée à la PLACE (V3, option `rando_boss_force`, clé `rando_boss_force` de slot_data ; base au format 18 ;
`archipelago_rando_boss.md` §15-§16 ; reprise de la branche `ap/boss-adaptes`) : table M = pour chaque place de B ou de
N, les 5 multiplicateurs de stats de la rencontre (v17..v21, en %) que le jeu écrit dans l'enregistrement de la place :
m(PV) = m_place(PV) × PV totaux de l'origine / PV totaux du remplaçant (membres à plus de 1 PV), m(stat) = m_place(stat)
× f, f = rapport des sommes pondérées (For, Esp, Déf, Vit) des membres principaux ; bornes [M_MIN, M_MAX] et planchers
(aucune valeur non nulle d'un membre ne tombe à 0, membre à 1 : 100 %). Mêmes σ / B / N dans les deux versions du
mélange : la force suit la PLACE (l'origine de la place), où que le mélange (calculé ici ou tiré à la génération) mette
le boss. EXCEPTION : un boss « exclu » (le boss d'un objectif « battre X », `OBJECTIF_BOSS`) n'est jamais adapté, où
qu'il soit : sa place n'a pas d'entrée dans M (le jeu y copie l'enregistrement de SON donneur : sa force d'origine).
Calculé chez le joueur (stats de SA ROM) : rien du jeu dans l'APWorld ni dans git.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import time
import zlib
from dataclasses import dataclass, field, replace
from pathlib import Path

FORMAT_BASE_BOSS = 6            # format minimal de yokai_local.json (4 : scripts de combat ; 5 : espèces exigées ;
                                # 6 : Yo-kai d'évènement)
FORMAT_EMPREINTE = 3            # version de la forme canonique de l'empreinte des boss (2 : boss figés ; 3 : + raisons,
                                # boss hors du périmètre « avant l'après-jeu »)
FORMAT_FICHIER = 1              # format de rando_boss.json (lu par le tracker du lanceur)
MODES = ("aucun", "meme_classe", "total")
NOM_FICHIER = "rando_boss.json"
CAP_B, CAP_N = 64, 16           # capacités de la boîte v7 (src/archipelago/boite.h)
CAP_M = 80                      # capacité de la table M (force adaptée, AP_CAP_BOSS_M)
FORCES = ("d_origine", "adaptee")
FORMAT_BASE_FORCE = 20          # format de yokai_local.json qui porte les stats et les multiplicateurs (§16) : 18 sur
                                # la branche, 20 après la fusion avec le lot M2a-bis (une base 19 de main n'a PAS
                                # les stats : `>= 18` la prendrait à tort)
VERSION_FORCE = 1               # version du calcul de M (entre dans la génération : un autre calcul = autre mélange)
M_MIN, M_MAX = 10, 1500         # bornes d'un multiplicateur (%) : 10 % à 15 fois (§16.2)
U16_MAX = 0xFFFF                # une stat est tronquée en u16 par le jeu (FUN_0057E628 / FUN_0057F780) : jamais au-delà
# Boss des objectifs « battre X » (V3, lot 3 / lot 10) : jamais adaptés (décision de l'humain, 2026-10-18), même si la
# graine ne les liste pas dans `rando_boss_force.exclus` (défense en profondeur : l'objectif de slot_data suffit).
OBJECTIF_BOSS = {"battre_potofeu": "potofeu", "battre_filomene": "filomene", "battre_extrabuki": "extrabuki"}
REGLE_REVANCHE = 0x230151B0     # BTL_RULE_INFO des copies de revanche (GYM_*) : jamais un donneur
TABLE_COMMUNE = "common_enc"    # table de rencontres commune (res/battle/common_enc_*.cfg.bin) : celle des donneurs
# Empreinte des boss (places, scripts, donneurs, combattants, espèces sans script) de la ROM européenne de référence
# (SHA-1 de code.bin 66143fcb…), base au format 6 (boss figés anti-softlock et boss hors du périmètre « avant l'après-jeu » ;
# format 5 : 727d0e95…, format 4 sans boss figés : 3c3bacaf…).
# Une valeur dérivée (condensat), pas une donnée du jeu.
EMPREINTE_REFERENCE = "b54d4483507fbb4081551342c8f8ec891bd35b22"

# Boss à script : (clé, nom affiché saisi à la main, classe, places). Classe = moment d'origine (§3.1) : 1 = chapitres
# 3-7, 2 = chapitres 8-10 et Lady Démona (décision de l'humain, 2026-09-28 : l'objectif est de finir le chapitre 10,
# pas de vaincre Lady Démona), 3 = après-jeu et facultatifs tardifs.
BOSS_SCRIPT: tuple[tuple[str, str, int, tuple[int, ...]], ...] = (
    ("grolos", "Grolos", 1, (0xE14B2B39,)),
    ("didgeai", "Didgeai", 1, (0xC2A8AE78,)),
    ("barbefrousse", "Barbefrousse", 1, (0xB2C75F37,)),
    ("inamygal", "Inamygal", 1, (0x68A166F3,)),
    ("volteface", "Volteface", 1, (0xF5765E4A,)),
    ("laure_et_marge", "Laure et Marge", 1, (0xFD86C9F0,)),
    ("tourboeillon", "Tourbœillon", 1, (0x978A29F6,)),
    ("crocho", "Crocho", 1, (0xB55AFD9E, 0x2C53AC24)),
    ("sabroclair", "Sabroclair", 2, (0xF6F3EFCA,)),
    ("firmain", "Firmain", 2, (0xA077F519,)),
    ("ombraptor", "Ombraptor", 2, (0x1177407A,)),
    ("lady_perpetua_3", "Lady Perpétua (3e combat)", 2, (0x79878032,)),
    ("tromploeil", "Tromplœil", 2, (0x579D69FB,)),
    ("triptyk", "Triptyk", 2, (0x8BC24D15,)),
    ("carpitaine", "Carpitaine", 2, (0x61A3E3A4,)),
    ("lady_demona", "Lady Démona", 2, (0x06B6CA2E,)),
    # Taprice : fin du Tunnel sans fin (t131d20..36), entrée = point de recherche de t131g00 (GetPhase >= 4-160, une fois
    # par jour) : facultatif faisable avant la fin, classé comme Tromplœil (donjon facultatif, PV de fin de jeu) [C / S]
    ("taprice", "Taprice", 2, (0xBDE7A020,)),
    ("thenuki", "Thénuki", 3, (0x34B6369A,)),
    ("infiniris", "Infiniris", 3, (0x0DE69AFB,)),
    ("chomino", "Chomino", 3, (0x8C0A51FF,)),
    ("extrabuki", "Extrabuki", 3, (0x26039974,)),
    ("laure_marge_ambronzio", "Laure, Marge et Ambronzio", 3, (0xAD518BF2,)),
    ("dr_jobard", "Dr Jobard", 3, (0xAADD52F6,)),
    ("mckraken", "McKraken", 3, (0xA4EA477D,)),
    ("blingos", "Blingos", 3, (0x65AB0B79,)),
    ("cycloptique", "Cycloptique", 3, (0x4E8658BA,)),
    ("maximain", "Maximain", 3, (0xC91E4475,)),
    ("bogos", "Bogos", 3, (0x7CB03A38,)),
    ("hydreux", "Hydreux", 3, (0x1400E54C,)),
    ("porcinator", "Porcinator", 3, (0x3F2DB68F,)),
    ("styx_vi", "Styx VI", 3, (0x263687CE,)),
    ("nebulor", "Nébulor", 3, (0x69771109,)),
    ("pr_letripe", "Pr Létripe", 3, (0x706C2048,)),
    ("hagacuree", "Hagacurée", 3, (0x5B41738B,)),
    ("rancornet", "Rancornet", 3, (0x425A42CA,)),
    ("barbebluff", "Barbebluff", 3, (0xF6DCFE35,)),
    ("mariotte_et_maribass", "Mariotte et Maribass", 3, (0xDDF1ADF6,)),
    ("lady_maggie", "Lady Maggie", 3, (0xC4EA9CB7,)),
    ("potofeu", "Potofeu", 3, (0xC5C25E05,)),
    ("filomene", "Filomène", 3, (0xDC33C7C1,)),
)
# Boss sans script (§3.3) : seule l'espèce de leur unique combattant change (niveau et multiplicateurs du lieu).
BOSS_SANS_SCRIPT: tuple[tuple[str, str, int], ...] = (
    ("meganyan", "Méganyan", 0x852A46F0),
    ("fumella", "Fumella", 0x925152B3),
    ("draconfus", "Draconfus", 0x80F13DB5),
    ("faux_kappa", "Faux Kappa", 0xABDC6E76),
    ("misterre", "Misterre", 0xE7C3F1A4),
    ("sabrille", "Sabrille", 0x5F48F264),
    ("demophage", "Démophage", 0x7465A1A7),
    ("injustin", "Injustin", 0x6D7E90E6),
    ("anguigne", "Anguigne", 0x1C292F01),
    ("cyrustre", "Cyrustre", 0x37047CC2),
    ("fielippine", "Fielippine", 0x2E1F4D83),
    ("maudicko", "Maudicko", 0x615EDB44),
    ("roneen", "Ronéan", 0x7845EA05),
)
# Exclus (§3.2), jamais places ni donneurs : Lady Perpétua 1-2 (flag temporaire 7:85 exigé par la suite du chapitre
# 10), revanche de Laure et Marge au chapitre 10 (règle propre, fin par 77 seul). Les autres exclus (revanches GYM,
# McKraken 2, Oni, tutoriels…) ne sont simplement pas dans les listes ci-dessus.
EXCLUS: dict[int, str] = {
    0x04F07477: "Lady Perpétua (combats 1-2)",
    0x36C616F5: "Laure et Marge (revanche du chapitre 10)",
}
CLASSES = (1, 2, 3)
# Périmètre (demande de l'humain, 2026-09-29, `archipelago_rando_boss.md` §12) : le mélange ne porte que sur les boss
# qu'on peut combattre AVANT l'après-jeu. Les boss de la classe 3 ci-dessous restent d'origine (figés, ni déplacés ni
# remplacés, leur donneur n'est donné à personne), dans les deux modes :
#   apres_jeu : requêtes de condition phase >= 11-10 (q77 Dr Jobard, q81 Infiniris, q96 Laure/Marge/Ambronzio, q120
#               Thénuki, q121 Chomino, q123 Extrabuki) [C, QUEST_CONFIG] ; McKraken (Yo-kai World t001d42) [C] ; chaîne
#               d'après-jeu `c11_trigger` (Hydreux … Filomène, dont Potofeu aux Limbes éternelles) [C] ;
#   hors_partie : salles t121d29 / t121d35 du réseau caché de San Fantastico (Blingos, Cycloptique, Maximain, Bogos),
#               atteintes seulement depuis ses cartes « c », fermé à une partie normale [C, archipelago_couverture.md §9.2].
HORS_PERIMETRE: dict[str, str] = {
    **{c: "apres_jeu" for c in ("thenuki", "infiniris", "chomino", "extrabuki", "laure_marge_ambronzio", "dr_jobard",
                                "mckraken", "hydreux", "porcinator", "styx_vi", "nebulor", "pr_letripe", "hagacuree",
                                "rancornet", "barbebluff", "mariotte_et_maribass", "lady_maggie", "potofeu", "filomene")},
    **{c: "hors_partie" for c in ("blingos", "cycloptique", "maximain", "bogos")},
}


# ---- VERSION 2 du mélange (V3, lot 10 : docs/systemes/archipelago_v3_boss_generation.md) -------------------------------
# Pour une graine à objectif d'après-jeu, la permutation est tirée À LA GÉNÉRATION (la logique doit savoir où est le
# boss de l'objectif) et portée par `slot_data.rando_boss` : {"mode": "<mode>#2", "graine", "sigma", "sigma_n"}
# (`sigma[x] = y` : le boss y prend la place de x ; clés de BOSS_SCRIPT / BOSS_SANS_SCRIPT). Le client ne tire rien :
# `appliquer_graine` CONTRÔLE la permutation sur la base locale (ROM du joueur) puis calcule les tables B / N comme la
# version 1 (donneurs et espèces lus dans la ROM). La version 1 (`calculer`) n'est pas touchée.
# Les boss d'après-jeu y sont mélangés ENTRE EUX : les 12 de la chaîne des Limbes éternelles et 6 boss de requête
# (séparément en mode « meme_classe », ensemble en mode « total »). Restent figés : les boss de l'anti-softlock de la
# ROM, le réseau caché (`hors_partie`) et McKraken.
VERSION_GRAINE = 2
LIMBES_V2: tuple[str, ...] = ("hydreux", "porcinator", "styx_vi", "nebulor", "pr_letripe", "hagacuree", "rancornet",
                              "potofeu", "barbebluff", "mariotte_et_maribass", "lady_maggie", "filomene")
REQUETES_V2: tuple[str, ...] = ("thenuki", "infiniris", "chomino", "extrabuki", "laure_marge_ambronzio", "dr_jobard")
FIGES_V2: tuple[str, ...] = ("mckraken",)
# VERSION 3 (ap/boss-voie-mystere, 2026-11-06) : graine dont la Voie du mystère est dans la partie : ses 4 boss
# (`hors_partie` en version 1 et 2) ne sont plus figés ; groupe « voie » en mode « meme_classe », avec les 18 autres
# boss d'après-jeu en mode « total » (le contrôle accepte aussi une permutation de groupes plus fins : l'APWorld garde la
# Voie à part avec l'objectif « medaillium_complet »). Mode « <mode>#3 », n° « client » 82 dans la graine.
VERSION_VOIE = 3
VERSIONS_GRAINE = (VERSION_GRAINE, VERSION_VOIE)
VOIE_V3: tuple[str, ...] = ("blingos", "cycloptique", "maximain", "bogos")


class RandoBossImpossible(Exception):
    """Mélange des boss refusé (message destiné au journal du client et au tracker)."""


@dataclass
class Boss:
    cle: str
    nom: str
    classe: int
    places: tuple[int, ...]
    script: str = ""
    donneur: int = 0
    membres: tuple[int, ...] = ()          # espèces (CHARA_PARAM) du donneur


@dataclass
class DonneesBoss:
    """Ce que le mélange des boss utilise de la base locale (validé)."""
    boss: dict[str, Boss]
    sans_script: dict[int, int]            # place -> espèce de son combattant
    noms_sans_script: dict[int, str]
    figes: dict[str, list[str]] = field(default_factory=dict)       # boss à script figé -> raisons
    figes_n: dict[int, list[str]] = field(default_factory=dict)     # place sans script figée -> raisons
    # format 18 (force adaptée, §16) : rencontre (places et donneurs) -> [(espèce, niveau)], multiplicateurs, niveaux
    # par rang ; espèce -> stats v2..v11. Vides avec une base plus ancienne (force adaptée impossible : force d'origine).
    membres: dict[int, list[tuple[int, int]]] = field(default_factory=dict)
    mult: dict[int, list[int]] = field(default_factory=dict)
    niveaux_rang: set[int] = field(default_factory=set)
    stats: dict[int, list[int]] = field(default_factory=dict)

    @classmethod
    def depuis(cls, base: dict) -> "DonneesBoss":
        if not isinstance(base, dict) or not isinstance(base.get("format"), int):
            raise RandoBossImpossible("base locale absente (réparer le mod)")
        if base["format"] < FORMAT_BASE_BOSS:
            raise RandoBossImpossible("base locale d'un format antérieur, sans les scripts de combat : à régénérer (ROM "
                                      "configurée, ou « Réparer le mod » dans le lanceur)")
        par_h = {int(e["h"]): e for e in base["rencontres"]}
        fichiers = base.get("fichiers", [])
        communs = {i for i, n in enumerate(fichiers) if TABLE_COMMUNE in n.rsplit("/", 1)[-1]}
        if len(communs) != 1:
            raise RandoBossImpossible("table de rencontres commune introuvable dans la base locale")
        commun = next(iter(communs))
        par_script: dict[str, list[dict]] = {}
        for e in base["rencontres"]:
            if e.get("s"):
                par_script.setdefault(e["s"], []).append(e)
        boss: dict[str, Boss] = {}
        for cle, nom, classe, places in BOSS_SCRIPT:
            scripts = set()
            for p in places:
                e = par_h.get(p)
                if e is None or not e.get("s"):
                    raise RandoBossImpossible(f"place 0x{p:08X} ({nom}) absente de la ROM ou sans script de combat")
                if int(e.get("r", 0)) == REGLE_REVANCHE:
                    raise RandoBossImpossible(f"place 0x{p:08X} ({nom}) : copie de revanche")
                scripts.add(e["s"])
            if len(scripts) != 1:
                raise RandoBossImpossible(f"{nom} : places de scripts différents ({sorted(scripts)})")
            script = scripts.pop()
            cands = [e for e in par_script.get(script, ())
                     if e.get("fs") == [commun] and int(e.get("r", 0)) != REGLE_REVANCHE and int(e["h"]) not in EXCLUS]
            if not cands:
                raise RandoBossImpossible(f"{nom} : aucune rencontre de la table commune avec le script {script}")
            d = min(cands, key=lambda e: int(e["h"]))
            membres = tuple(int(c[1]) for c in d["c"])
            if not 1 <= len(membres) <= 6:
                raise RandoBossImpossible(f"{nom} : donneur 0x{int(d['h']):08X} avec {len(membres)} combattants")
            boss[cle] = Boss(cle, nom, classe, tuple(places), script, int(d["h"]), membres)
        sans: dict[int, int] = {}
        noms: dict[int, str] = {}
        for _cle, nom, p in BOSS_SANS_SCRIPT:
            e = par_h.get(p)
            if e is None or e.get("s"):
                raise RandoBossImpossible(f"boss sans script 0x{p:08X} ({nom}) absent de la ROM ou avec un script")
            if len(e.get("fs", [e["f"]])) != 1 or len(e["c"]) != 1:
                raise RandoBossImpossible(f"boss sans script 0x{p:08X} ({nom}) : {len(e['c'])} combattants")
            c = e["c"][0]
            if len(c) < 5 or int(c[4]) != 1:
                raise RandoBossImpossible(f"boss sans script 0x{p:08X} ({nom}) : combattant partagé")
            sans[p] = int(c[1])
            noms[p] = nom
        places = [p for b in boss.values() for p in b.places] + list(sans)
        if len(set(places)) != len(places) or set(places) & set(EXCLUS):
            raise RandoBossImpossible("places de boss en double ou exclues")
        if len({b.donneur for b in boss.values()}) != len(boss):
            raise RandoBossImpossible("deux boss ont le même donneur")
        # anti-softlock : boss dont une espèce (donneur ou place) est une source exigée -> figé
        exig = base.get("exigees_boss")
        if not isinstance(exig, dict):
            raise RandoBossImpossible("base locale sans les espèces exigées (format 5) : à régénérer")

        def raisons(especes) -> list[str]:
            return sorted({f"0x{e:08X}:{r}" for e in especes for r in exig.get(str(e), ())})
        # périmètre (format 6) : boss d'après-jeu / hors partie, et Yo-kai d'évènement (jamais une place ni un donneur)
        evt = base.get("evenement")
        if not isinstance(evt, dict):
            raise RandoBossImpossible("base locale sans les Yo-kai d'évènement (format 6) : à régénérer")
        evt_esp = {int(p) for p in evt.get("especes", [])}
        evt_renc = {int(h) for h in evt.get("rencontres", [])}
        if set(places) & evt_renc or {b.donneur for b in boss.values()} & evt_renc:
            raise RandoBossImpossible("une place ou un donneur de boss est une rencontre d'évènement")
        figes, figes_n = {}, {}
        for cle, b in boss.items():
            especes = set(b.membres) | {int(c[1]) for p in b.places for c in par_h[p]["c"]}
            r = raisons(especes) + [f"0x{e:08X}:evenement" for e in sorted(especes & evt_esp)]
            if cle in HORS_PERIMETRE:
                r.append(HORS_PERIMETRE[cle])
            if r:
                figes[cle] = r
        for p, e in sans.items():
            r = raisons({e}) + ([f"0x{e:08X}:evenement"] if e in evt_esp else [])
            if r:
                figes_n[p] = r
        # format 18 : de quoi calculer la force adaptée (jamais dans l'empreinte : ne change pas le mélange)
        membres, mult, nr, stats = {}, {}, set(), {}
        if base["format"] >= FORMAT_BASE_FORCE:
            for h in set(places) | {b.donneur for b in boss.values()}:
                e = par_h[h]
                vus_j, ms = set(), []
                for c in e["c"]:                  # une rencontre définie dans plusieurs fichiers : 1re définition
                    j = int(c[5]) if len(c) > 5 else len(ms)
                    if j not in vus_j:
                        vus_j.add(j)
                        ms.append((int(c[1]), int(c[2])))
                membres[h] = ms
                mult[h] = [int(x) for x in e.get("m", [100] * 5)]
                if any(e.get("nr", ())):
                    nr.add(h)
            for k, v in base.get("especes", {}).items():
                st = v.get("stats") if isinstance(v, dict) else None
                if isinstance(st, list) and len(st) == 10:
                    stats[int(k)] = [int(x) for x in st]
        return cls(boss, sans, noms, figes, figes_n, membres, mult, nr, stats)

    def empreinte(self) -> str:
        canon = {"format": FORMAT_EMPREINTE,
                 "b": [[b.cle, b.classe, sorted(b.places), b.script, b.donneur, list(b.membres)]
                       for _k, b in sorted(self.boss.items())],
                 "n": [[p, e] for p, e in sorted(self.sans_script.items())],
                 "figes": sorted(self.figes), "figes_n": sorted(self.figes_n),
                 "hors": sorted((k, v) for k, v in HORS_PERIMETRE.items() if k in self.boss)}
        return hashlib.sha1(json.dumps(canon, separators=(",", ":")).encode()).hexdigest()


@dataclass
class MelangeBoss:
    mode: str
    graine: int
    empreinte: str
    generation: int                          # identifiant non nul du mélange dans la boîte (valide / table_gen)
    sigma: dict[str, str]                    # boss -> boss qui prend sa place (identités exclues)
    b: dict[int, int]                        # place -> donneur (table B)
    n: dict[int, tuple[int, int]]            # place -> (espèce d'origine, espèce cible) (table N)
    sigma_n: dict[int, int]                  # place sans script -> place dont le boss la remplace (identités exclues)
    donnees: DonneesBoss | None = field(default=None, repr=False)
    # force adaptée (§16) : option, table M (place -> 5 multiplicateurs en %), places sans données, places dont le
    # boss est exclu (objectif), boss exclus (clés), identifiant du même mélange SANS M (jeu sans la force adaptée)
    force: str = "d_origine"
    m: dict[int, tuple[int, ...]] = field(default_factory=dict)
    force_ignorees: list[int] = field(default_factory=list)
    force_exclues: list[int] = field(default_factory=list)
    exclus: tuple[str, ...] = ()
    generation_sans_force: int = 0

    @property
    def empreinte32(self) -> int:
        return int(self.empreinte[:8], 16)


class _Alea:
    """Tirages déterministes indépendants de la version de Python (comme le randomizer de Yo-kai)."""

    def __init__(self, graine: int, mode: str, empreinte: str):
        h = hashlib.sha256(f"ykw2ap-rando-boss:{graine}:{mode}:{empreinte}".encode()).digest()
        self.r = random.Random(int.from_bytes(h[:16], "little"))

    def sous(self, n: int) -> int:
        k = max(1, n.bit_length())
        while True:
            v = self.r.getrandbits(k)
            if v < n:
                return v

    def permuter(self, orig: list) -> list:
        perm = list(orig)
        for i in range(len(perm) - 1, 0, -1):             # Fisher-Yates
            j = self.sous(i + 1)
            perm[i], perm[j] = perm[j], perm[i]
        return perm


def generation(graine: int, mode: str, empreinte: str, m: dict[int, tuple[int, ...]] | None = None) -> int:
    """Identifiant du mélange (version 1) ; avec une table M non vide, elle y entre (autre force = autre mélange : le
    jeu retire l'ancien avant d'appliquer le nouveau). Sans M : valeur inchangée depuis la v7 (graines de la V2)."""
    return _avec_force(f"boss:{graine}:{mode}:{empreinte}", m)


def _avec_force(cle: str, m: dict[int, tuple[int, ...]] | None) -> int:
    if m:
        cle += f":force{VERSION_FORCE}:" + ",".join(f"{p:08x}=" + "/".join(map(str, v)) for p, v in sorted(m.items()))
    return zlib.crc32(cle.encode()) & 0xFFFFFFFF or 1


# ------------------------------------------------------------------------------------------- force adaptée (§16)
def stat_au_niveau(st: list[int], k: int, niveau: int) -> int:
    """Stat k (0 PV, 1 For, 2 Esp, 3 Déf, 4 Vit) d'une espèce au niveau donné, comme le jeu la crée pour un ennemi :
    maximale nulle (boss, parties) = minimale brute (FUN_0057E628) ; sinon formule de FUN_0040F7EC avec IV = EV = 0,
    bonus 0 : min + (max - min) * (L - 1) / 98, bornée à [1, 999] ; niveau 0 (boss à script) = instance de niveau 1."""
    mn, mx = st[k], st[5 + k]
    if mx == 0:
        return mn
    v = int(mn + (mx - mn) * (max(niveau, 1) - 1) / 98)
    return min(max(v, 1), 999)


def _puissance(membres: list[tuple[int, int]], stats: dict[int, list[int]],
               mult: list[int]) -> tuple[float, float] | None:
    """(PV totaux des membres à plus de 1 PV, somme pondérée par `mult` des 4 stats du membre principal = celui qui a
    le plus de PV), ou None si une espèce n'a pas de stats connues."""
    vals = []
    for esp, niv in membres:
        st = stats.get(esp)
        if st is None:
            return None
        vals.append([stat_au_niveau(st, k, niv) for k in range(5)])
    gros = [v for v in vals if v[0] > 1]
    if not gros:
        return None
    pv = sum(v[0] for v in gros)
    principal = max(gros, key=lambda v: v[0])                 # premier à PV égaux (ordre des combattants)
    s = sum(mult[k] * principal[k] for k in range(1, 5))
    return (pv, s) if pv > 0 and s > 0 else None


def multiplicateurs(origine: list[tuple[int, int]], remplacant: list[tuple[int, int]], m_place: list[int],
                    stats: dict[int, list[int]]) -> tuple[int, ...] | None:
    """Les 5 multiplicateurs (%) à écrire dans la place pour que le remplaçant ait la force de l'origine (voir le
    docstring du module), ou None si les données manquent. `origine` / `remplacant` : [(espèce, niveau)] ; `m_place` :
    multiplicateurs d'origine de la place (100 pour la plupart des boss à script, 120-460 pour un boss sans script)."""
    po = _puissance(origine, stats, m_place)
    pr = _puissance(remplacant, stats, m_place)
    if po is None or pr is None:
        return None
    f_pv, f_s = po[0] / pr[0], po[1] / pr[1]
    vals_r = [[stat_au_niveau(stats[e], k, n) for k in range(5)] for e, n in remplacant]
    out = []
    for k in range(5):
        m = int(m_place[k] * (f_pv if k == 0 else f_s) + 0.5)
        m = min(max(m, M_MIN), M_MAX)
        nonnuls = [v[k] for v in vals_r if v[k] > 0]
        if nonnuls:
            # plancher : aucune valeur non nulle d'un membre ne tombe à 0 (troncature du jeu, sans plancher) ; un
            # membre à 1 (nuages de Tourbœillon / Tromplœil, aide de Grolos) exige 100 % ; ailleurs >= 1,01 avant
            # troncature (marge sur l'arrondi des flottants)
            v = min(nonnuls)
            m = max(m, 100 if v == 1 else -(-101 // v))
            # plafond : la plus grande valeur reste dans un u16 (le jeu la tronque sinon)
            m = min(m, U16_MAX * 100 // max(nonnuls))
        out.append(m)
    return tuple(out)


def exclus_force(objectif: str | None = None, liste=()) -> tuple[str, ...]:
    """Boss jamais adaptés : ceux de `liste` (slot_data `rando_boss_force.exclus`) et le boss de l'objectif."""
    out = {str(x) for x in (liste or ()) if isinstance(x, str)}
    if objectif in OBJECTIF_BOSS:
        out.add(OBJECTIF_BOSS[objectif])
    return tuple(sorted(out))


def table_m(don: DonneesBoss, b: dict[int, int], n: dict[int, tuple[int, int]], sigma_n: dict[int, int] | None = None,
            exclus=()) -> tuple[dict[int, tuple[int, ...]], list[int], list[int]]:
    """Table M d'un mélange : place de B -> force de l'origine de la place portée par les membres du donneur ; place
    de N -> force de l'espèce d'origine portée par l'espèce cible, au niveau du combattant de la place. `exclus` : clés
    de boss jamais adaptés (objectif) : une place dont le DONNEUR (B) ou le boss remplaçant (N, par `sigma_n`) est exclu
    n'a pas d'entrée. Renvoie (M, places ignorées faute de données : base trop ancienne, stats inconnues, niveaux
    imposés par rang ; places exclues)."""
    ex = set(exclus or ())
    donneurs_exclus = {bo.donneur for k, bo in don.boss.items() if k in ex}
    places_n_exclues = {p for k, _nom, p in BOSS_SANS_SCRIPT if k in ex}
    m, ignorees, exclues = {}, [], []
    for p, d in sorted(b.items()):
        if d in donneurs_exclus:
            exclues.append(p)
            continue
        if p in don.niveaux_rang or d in don.niveaux_rang or p not in don.membres or d not in don.membres:
            ignorees.append(p)
            continue
        v = multiplicateurs(don.membres[p], don.membres[d], don.mult[p], don.stats)
        if v is None:
            ignorees.append(p)
        else:
            m[p] = v
    for p, (_o, c) in sorted(n.items()):
        if (sigma_n or {}).get(p, p) in places_n_exclues:
            exclues.append(p)
            continue
        if p in don.niveaux_rang or p not in don.membres or len(don.membres[p]) != 1:
            ignorees.append(p)
            continue
        esp, niv = don.membres[p][0]
        v = multiplicateurs([(esp, niv)], [(c, niv)], don.mult[p], don.stats)
        if v is None:
            ignorees.append(p)
        else:
            m[p] = v
    if len(m) > CAP_M:
        raise RandoBossImpossible("table de force adaptée trop grande pour la boîte")
    return m, ignorees, exclues


def avec_force(m: MelangeBoss, force: str, exclus=()) -> MelangeBoss:
    """Le mélange `m` (calculé sans force) avec l'option de force de la graine : mêmes σ / B / N ; avec « adaptee »,
    table M et génération qui l'inclut (`generation_sans_force` garde l'identifiant sans M)."""
    if force not in FORCES:
        raise RandoBossImpossible(f"force des boss inconnue : {force!r}")
    m.generation_sans_force = m.generation
    m.force, m.exclus = force, tuple(sorted(set(exclus or ())))
    if force == "adaptee" and m.donnees is not None:
        m.m, m.force_ignorees, m.force_exclues = table_m(m.donnees, m.b, m.n, m.sigma_n, m.exclus)
        if m.m:
            m.generation = _avec_force(f"gen:{m.generation:08x}", m.m)
    return m


def sans_force(m: MelangeBoss) -> MelangeBoss:
    """Le même mélange SANS la table M (jeu qui n'applique pas la force adaptée) : génération d'avant."""
    if not m.m:
        return m
    return replace(m, m={}, generation=m.generation_sans_force or m.generation)


_REFERENCE = object()


def tables(don: DonneesBoss, sigma: dict[str, str], sigma_n: dict[int, int]) -> tuple[dict[int, int],
                                                                                   dict[int, tuple[int, int]]]:
    """Tables B et N d'un mélange (σ sur les boss à script, σ_N sur les places sans script)."""
    b = {p: don.boss[y].donneur for x, y in sigma.items() if x != y for p in don.boss[x].places}
    n = {p: (don.sans_script[p], don.sans_script[q]) for p, q in sigma_n.items()
         if p != q and don.sans_script[p] != don.sans_script[q]}
    if len(b) > CAP_B or len(n) > CAP_N:
        raise RandoBossImpossible("mélange des boss trop grand pour la boîte")
    return b, n


def calculer(base: dict, graine: int, mode: str, reference=_REFERENCE, force: str = "d_origine",
             exclus=()) -> MelangeBoss:
    """Mélange des boss de la graine (voir le docstring du module). `reference` : empreinte exigée (défaut :
    EMPREINTE_REFERENCE, lue à l'appel ; None ou vide : pas de contrôle, bases synthétiques des tests). `force` :
    « d_origine » (aucune table M : résultat identique à la V2) ou « adaptee » (table M, mêmes σ / B / N) ; `exclus` :
    boss jamais adaptés."""
    if reference is _REFERENCE:
        reference = EMPREINTE_REFERENCE
    if mode not in MODES or mode == "aucun":
        raise RandoBossImpossible(f"mode de mélange des boss inconnu : {mode!r}")
    don = DonneesBoss.depuis(base)
    emp = don.empreinte()
    if reference and emp != reference:
        raise RandoBossImpossible(f"boss de la ROM différents de la référence (empreinte {emp[:12]}… au lieu de "
                                  f"{reference[:12]}…) : ROM d'une autre version ou RomFS modifié ; mélange refusé")
    alea = _Alea(graine, mode, emp)
    classes: dict[str, list[str]] = {}
    for cle, b in sorted(don.boss.items()):
        if cle not in don.figes:                           # boss figé : ni déplacé ni remplacé
            classes.setdefault(f"classe{b.classe}" if mode == "meme_classe" else "tout", []).append(cle)
    sigma: dict[str, str] = {}
    for c in sorted(classes):
        orig = classes[c]
        sigma.update({x: y for x, y in zip(orig, alea.permuter(orig)) if x != y})
    orig_n = sorted(p for p in don.sans_script if p not in don.figes_n)
    sigma_n = {p: q for p, q in zip(orig_n, alea.permuter(orig_n)) if p != q}
    b, n = tables(don, sigma, sigma_n)
    m = MelangeBoss(mode, graine, emp, generation(graine, mode, emp), sigma, b, n, sigma_n, don)
    return avec_force(m, force, exclus) if force != "d_origine" else m


def mode_et_version(mode) -> tuple[str, int] | None:
    """(mode, version) d'un mode de `slot_data.rando_boss` : « meme_classe » = version 1, « meme_classe#2 » = version
    2 ; None si le mode ou la version est inconnu de ce client (jamais un autre calcul à la place)."""
    if not isinstance(mode, str):
        return None
    nom, _, v = mode.partition("#")
    if nom not in MODES:
        return None
    if not v:
        return nom, 1
    return (nom, int(v)) if v in tuple(str(x) for x in VERSIONS_GRAINE) and nom != "aucun" else None


def version_du_mode(mode: str) -> int:
    """Version d'un mode écrit par ce module (`MelangeBoss.mode`) : « total#3 » -> 3, « total » -> 1."""
    _nom, _, v = str(mode).partition("#")
    return int(v) if v.isdigit() else 1


def groupes_v2(don: DonneesBoss, mode: str, version: int = VERSION_GRAINE) -> dict[str, list[str]]:
    """Groupes de boss à script permutés entre eux en version 2 (boss figés de CETTE ROM retirés) : classes 1 et 2
    d'avant la fin (ensemble en mode « total »), Limbes et requêtes d'après-jeu (ensemble en mode « total ») ; version
    3 : et la Voie du mystère (groupe « voie », ou avec les autres boss d'après-jeu en mode « total »)."""
    figes = figes_v2(don, version)
    voie = VOIE_V3 if version == VERSION_VOIE else ()
    g: dict[str, list[str]] = {}
    for cle, b in sorted(don.boss.items()):
        if cle in figes:
            continue
        if b.classe in (1, 2):
            g.setdefault(f"classe{b.classe}" if mode == "meme_classe" else "avant", []).append(cle)
        elif cle in LIMBES_V2:
            g.setdefault("limbes" if mode == "meme_classe" else "apres", []).append(cle)
        elif cle in REQUETES_V2:
            g.setdefault("requetes" if mode == "meme_classe" else "apres", []).append(cle)
        elif cle in voie:
            g.setdefault("voie" if mode == "meme_classe" else "apres", []).append(cle)
    return g


def figes_v2(don: DonneesBoss, version: int = VERSION_GRAINE) -> dict[str, list[str]]:
    """Boss à script figés en version 2 sur CETTE ROM : toute raison autre que « apres_jeu » (anti-softlock, Yo-kai
    d'évènement, réseau caché), McKraken, et tout boss d'après-jeu hors des deux groupes mélangés. Version 3 : la
    raison « hors_partie » des 4 boss de la Voie du mystère ne compte plus (toute autre raison les fige encore)."""
    voie = VOIE_V3 if version == VERSION_VOIE else ()
    out = {}
    for cle, b in don.boss.items():
        r = [x for x in don.figes.get(cle, ()) if x != "apres_jeu" and not (cle in voie and x == "hors_partie")]
        if cle in FIGES_V2 or (b.classe == 3 and cle not in LIMBES_V2 + REQUETES_V2 + voie):
            r.append("fige_v2")
        if r:
            out[cle] = r
    return out


def appliquer_graine(base: dict, mode: str, graine: int, sigma: dict, sigma_n: dict,
                     reference=_REFERENCE, force: str = "d_origine", exclus=(),
                     version: int = VERSION_GRAINE) -> MelangeBoss:
    """Mélange de VERSION 2 (ou 3 : Voie du mystère) : la permutation vient de la graine (tirée par l'APWorld).
    CONTRÔLE sur la base locale puis tables B / N. Refus (RandoBossImpossible) si la ROM n'a pas l'empreinte de
    référence, si une clé est inconnue, si un boss figé sur cette ROM est déplacé ou si un groupe n'est pas permuté dans
    lui-même : jamais un autre mélange à la place (la logique de la graine suppose CELUI-CI)."""
    if reference is _REFERENCE:
        reference = EMPREINTE_REFERENCE
    if mode not in MODES or mode == "aucun":
        raise RandoBossImpossible(f"mode de mélange des boss inconnu : {mode!r}")
    if version not in VERSIONS_GRAINE:
        raise RandoBossImpossible(f"version du mélange des boss inconnue : {version!r}")
    if not isinstance(sigma, dict) or not isinstance(sigma_n, dict) \
            or not all(isinstance(k, str) and isinstance(v, str) for d in (sigma, sigma_n) for k, v in d.items()):
        raise RandoBossImpossible("permutation des boss de la graine illisible")
    don = DonneesBoss.depuis(base)
    emp = don.empreinte()
    if reference and emp != reference:
        raise RandoBossImpossible(f"boss de la ROM différents de la référence (empreinte {emp[:12]}… au lieu de "
                                  f"{reference[:12]}…) : ROM d'une autre version ou RomFS modifié ; mélange refusé")
    reste = dict(sigma)
    for nom, membres in sorted(groupes_v2(don, mode, version).items()):
        part = {x: reste.pop(x) for x in list(reste) if x in membres}
        if sorted(part) != sorted(part.values()) or any(x == y for x, y in part.items()):
            raise RandoBossImpossible(f"permutation des boss de la graine : le groupe « {nom} » n'est pas permuté "
                                      "dans lui-même")
    if reste:
        raise RandoBossImpossible("permutation des boss de la graine : boss inconnus ou figés sur cette ROM déplacés ("
                                  + ", ".join(sorted(reste)) + ")")
    cles_n = {cle: p for cle, _nom, p in BOSS_SANS_SCRIPT}
    libres_n = {cle for cle, p in cles_n.items() if p not in don.figes_n}
    if set(sigma_n) - libres_n or sorted(sigma_n) != sorted(sigma_n.values()) \
            or any(x == y for x, y in sigma_n.items()):
        raise RandoBossImpossible("permutation des boss sans script de la graine : boss inconnus ou figés sur cette "
                                  "ROM déplacés, ou pas une permutation")
    sig = {x: y for x, y in sorted(sigma.items())}
    sig_n = {cles_n[x]: cles_n[y] for x, y in sorted(sigma_n.items())}
    b, n = tables(don, sig, sig_n)
    canon = json.dumps([version, mode, sorted(sig.items()), sorted(sigma_n.items()), emp],
                       separators=(",", ":"))
    gen = zlib.crc32(("boss2:" + canon).encode()) & 0xFFFFFFFF or 1
    m = MelangeBoss(f"{mode}#{version}", int(graine), emp, gen, sig, b, n, sig_n, don)
    # force adaptée (§15) : la force suit la PLACE ; le boss d'un objectif n'est jamais adapté (`exclus`)
    return avec_force(m, force, exclus) if force != "d_origine" else m


def echange_manuel(base: dict, paires: list[tuple[str, str]], force: str = "d_origine", exclus=()) -> MelangeBoss:
    """Mélange écrit à la main (client de test) : chaque paire (X, Y) met Y à la place de X ET X à la place de Y (clés
    de boss à script ou de boss sans script) ; aucune empreinte exigée. `force`, `exclus` : comme `calculer`."""
    don = DonneesBoss.depuis(base)
    cles_n = {cle: p for cle, _nom, p in BOSS_SANS_SCRIPT}
    sigma: dict[str, str] = {}
    sigma_n: dict[int, int] = {}
    for x, y in paires:
        if x in don.boss and y in don.boss:
            sigma[x], sigma[y] = y, x
        elif x in cles_n and y in cles_n:
            sigma_n[cles_n[x]], sigma_n[cles_n[y]] = cles_n[y], cles_n[x]
        else:
            raise RandoBossImpossible(f"échange {x}:{y} : clés inconnues ou de genres différents (avec / sans script)")
    b, n = tables(don, sigma, sigma_n)
    emp = don.empreinte()
    m = MelangeBoss("manuel", 0, emp, zlib.crc32(repr((sorted(b.items()), sorted(n.items()))).encode()) or 1,
                    {x: y for x, y in sigma.items() if x != y}, b, n, sigma_n, don)
    return avec_force(m, force, exclus) if force != "d_origine" else m


def appliquer(base: dict, m: MelangeBoss) -> dict[int, dict]:
    """Ce que fait le jeu (rando_boss.cpp), pour les tests et le tracker : pour chaque place, {hachage (inchangé),
    script, combattants} en jeu."""
    don = m.donnees or DonneesBoss.depuis(base)
    par_h = {int(e["h"]): e for e in base["rencontres"]}
    out = {}
    for b in don.boss.values():
        for p in b.places:
            d = m.b.get(p)
            src = par_h[d] if d else par_h[p]
            out[p] = {"hachage": p, "script": src["s"], "combattants": [int(c[1]) for c in src["c"]]}
    for p, esp in don.sans_script.items():
        out[p] = {"hachage": p, "script": None, "combattants": [m.n.get(p, (esp, esp))[1]]}
    return out


def _ecrire_json(p: Path, d: dict) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def ecrire_fichier_local(dossier: str | Path, m: MelangeBoss | None, ident_partie: int | None, etat: str,
                         jeu: dict | None = None) -> Path:
    """`rando_boss.json` pour le tracker du lanceur : pour chaque boss, sa place et le boss qui la prend (clés et noms
    saisis à la main, espèces du remplaçant pour le dévoilement par le Médaillium). `etat` : « actif », « aucun »,
    « refuse », « attente »."""
    d: dict = {"format": FORMAT_FICHIER, "horodatage": time.time(), "ident_partie": ident_partie, "etat": etat,
               "jeu": jeu or {}}
    if m is not None and m.donnees is not None:
        don = m.donnees
        boss = []
        # version 2 (mélange porté par la graine) : les boss d'après-jeu des deux groupes mélangés ne sont plus figés
        version = version_du_mode(m.mode)               # (3 : Voie du mystère aussi, ap/boss-voie-mystere)
        v2 = version in VERSIONS_GRAINE
        figes_script = figes_v2(don, version) if v2 else don.figes
        for cle, b in sorted(don.boss.items(), key=lambda kv: (kv[1].classe, kv[0])):
            y = don.boss[m.sigma.get(cle, cle)]
            boss.append({"cle": cle, "nom": b.nom, "classe": b.classe, "places": [f"{p:#010x}" for p in b.places],
                         "remplace_par": y.cle if y.cle != cle else None, "remplace_par_nom": y.nom,
                         "especes": [f"{e:#010x}" for e in y.membres],
                         "especes_origine": [f"{e:#010x}" for e in b.membres], "fige": figes_script.get(cle, [])})
        noms_n = don.noms_sans_script
        for p in sorted(don.sans_script):
            q = m.sigma_n.get(p, p)
            boss.append({"cle": next(c for c, _n, x in BOSS_SANS_SCRIPT if x == p), "nom": noms_n[p], "classe": 0,
                         "places": [f"{p:#010x}"], "remplace_par": None if q == p else
                         next(c for c, _n, x in BOSS_SANS_SCRIPT if x == q),
                         "remplace_par_nom": noms_n[q], "especes": [f"{don.sans_script[q]:#010x}"],
                         "especes_origine": [f"{don.sans_script[p]:#010x}"], "fige": don.figes_n.get(p, [])})
        # force adaptée (§16) : multiplicateurs (%) de la 1re place de chaque boss remplacé, si la table M en a ;
        # « force_exclue » : le remplaçant de cette place est un boss jamais adapté (objectif), force d'origine
        exclues = set(m.force_exclues)
        for x in boss:
            p0 = int(x["places"][0], 16)
            v = m.m.get(p0)
            if v is not None:
                x["force"] = list(v)
            elif p0 in exclues:
                x["force_exclue"] = True
        d.update({"mode": m.mode, "version": version if v2 else 1,
                  "graine": m.graine, "empreinte": m.empreinte, "generation": m.generation,
                  "boss": boss, "nb_b": len(m.b), "nb_n": len(m.n)})
        if m.force != "d_origine":
            d.update({"force": m.force, "nb_m": len(m.m), "force_exclus": list(m.exclus),
                      "force_ignorees": len(m.force_ignorees)})
    p = Path(dossier) / NOM_FICHIER
    _ecrire_json(p, d)
    return p


def lire_fichier_local(dossier: str | Path) -> dict | None:
    try:
        d = json.loads((Path(dossier) / NOM_FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and d.get("format") == FORMAT_FICHIER else None
