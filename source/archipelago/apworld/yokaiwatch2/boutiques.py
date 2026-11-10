# -*- coding: utf-8 -*-
"""Checks de boutique : premier achat de chaque article (docs/systemes/archipelago_boutiques.md), sans Archipelago.

Mécanisme (jeu v9, boîte §26) : tant que le premier achat d'un article n'est pas fait, la boutique montre à sa place
l'objet Archipelago (« <objet> (pour <joueur>) », icône Archipelago, ou l'objet de ce monde) au prix d'origine, quantité
1 ; l'achat ne donne pas l'objet d'origine, pose un bit persistant (octets de flags globaux non définis) et publie
l'évènement ACHAT ; l'article redevient aussitôt l'objet d'origine. Le client envoie le check sur l'évènement ou sur le
bit.

Données (règle 6 de CLAUDE.md) : identifiants et annotations de logique seulement, relevés localement par
`tools/romfs/boutiques.py --tsv` puis réduits à la main : n° de la boutique (N de `shop_shpN<n>_0.01n.cfg.bin`), carte
et déclencheurs (type 81), nombre d'entrées SHOP_CONFIG_INFO du fichier, RANG de l'entrée (ou des deux entrées d'une
paire) de chaque article dans le fichier (0 = première), CLASSE de prix (0 : <= 500 €, 1 : <= 1 000 €, 2 : <= 3 000 €,
3 : <= 10 000 €, 4 : plus ; jamais le prix) et classe de condition. **Aucun hachage d'article** (clé +0 de
SHOP_CONFIG_INFO, décision de l'humain du 2026-09-29 : la liste énumérait toute la table des boutiques) : le client les
lit dans la ROM DU JOUEUR (`archipelago/installation/boutiques.py`, fichier local `boutiques_local.json`, jamais
versionné ni distribué) et vérifie la lecture par `EMPREINTE_ARTICLES` (SHA-1 de la liste, pas la liste).
Aucun nom d'objet, aucun texte du jeu : les noms des locations sont saisis à la main (« Boutique : <région> (N<n>) —
article <i> ») ; le nom réel de l'objet vendu n'est jamais versionné.

Périmètre (archipelago_boutiques.md §5, vérifié [C] à l'implémentation) : boutiques normales payées en euros (type 0)
ouvertes par une carte (déclencheur type 81) ou un script (N008 : RunCheapSweetsShop de t103i23). Jamais : types 1 à 9
(points, distributeurs, billets, vélos, paiements), boutiques sans ouverture trouvée (N034, N038-N041, N043), carte
d'après-jeu t301g00 (N045), articles d'après-jeu (GameClear). Classes (`tag`) :
- '' : article toujours visible ; 'ch6' : visible à partir de 6-10 (GetPhase >= 60010) ; 'q62' : une paire d'entrées
  exclusives (quête qs0062 finie, flag 1194 posé ou non : l'une OU l'autre est visible) = une location à deux clés ;
- 'x_…' : hors du mode `principales` (seulement `toutes`, et alors EXCLUE : remplissage) : 'x_flag2172' (flag 2172
  [C] : posé seulement en parlant au Yo-kai du Tablo-blabla n° 12, présent sur t105g00 quand ce panneau est APPELÉ :
  `TABLOS_ARTICLES`), 'x_rang_s' (rang de montre S, après-jeu en pratique), 'x_beignets' (étals de beignets, présence selon l'armée
  choisie [?]), 'x_portails' (N036 : boutique de la version « portails » de t104i23, t104i23_trigger_gate [C]),
  'x_porte_quete_6' (N006 : l'entrée de t101i21 a une condition sur la quête qs0006, GATE_ENTER_INFO_COND [?]),
  'x_train' (trains N046 / N047 : rotation par jour et par trajet, octet 369).
Règles d'accès : celle de la région de la carte, au moins un chapitre terminé, et : 'ch6' -> chapitre 6 ; 'q62' ->
chapitre 5 (quête 62) ; N013 (t105i27 : porte GetWatchRank >= D [C]) -> chapitre 3 + objets du rang D ; N024 (t131i05 :
porte GetPhase >= 40120 [C]) -> chapitre 4 ; bâtiments de t104 (portes GetPhase >= 40050 [C]) : règle de la région.
"""
from typing import Dict, List, Tuple

# Identifiants : nouvelle plage, jamais utilisée (59423500 + rang de l'article dans BOUTIQUES_ARTICLES) ; le bit
# persistant du jeu est le même rang (0..AP_BOUTIQUE_BITS-1, boite.h) : stable quelles que soient les options.
BOUTIQUE_ID_BASE = 59423500
# Fonction du patch (bit 28 de ApVerrous::compiles, src/archipelago/verrous.h AP_FONCTION_BOUTIQUES) exigée par une graine
# qui a des articles (slot_data `fonctions_exigees`) : le client refuse un jeu qui ne l'a pas.
FONCTION_BOUTIQUES = 28
BITS_MAX = 320                       # = AP_BOUTIQUE_BITS (40 octets de flags globaux, boite.h / boite_protocole.py)
PRIX_CLASSES = (500, 1000, 3000, 10000)   # bornes des classes 0..3 (euros) ; classe 4 : au-delà
# Empreinte des hachages d'article lus dans la ROM (installation/boutiques.py) : SHA-1 de la concaténation, dans l'ordre
# de BOUTIQUES_ARTICLES (rang), des clés +0 des entrées de chaque article (u32 petit-boutiste). Contrôle de la lecture
# chez le joueur (ROM européenne attendue) ; la liste elle-même n'est dans aucun fichier du dépôt ni du paquet.
EMPREINTE_ARTICLES = "1e4a7feafa2846644210a747350240179d963d03"
NB_CLES = 299                        # clés de la liste (297 articles, dont 2 paires `q62` à deux entrées)
# V3, lot 22 : boutique N045 (village du Château de Sawayama, t301g00), ajoutée À LA FIN (rangs 297 à 299 : identifiants
# BOUTIQUE_ID_BASE + rang, bits 297 à 299 ; rien d'autre ne bouge). Ses 3 clés ont leur PROPRE empreinte : celle des 297
# articles d'avant (`EMPREINTE_ARTICLES`, `NB_CLES`) ne change pas, et le fichier local `boutiques_local.json` déjà
# écrit chez le joueur (toutes les boutiques N de sa ROM, N045 comprise) reste valable sans être refait.
BOUTIQUES_APRES_JEU = frozenset({"N045"})
EMPREINTE_ARTICLES_APRES_JEU = "8a3e3bb7d705e7e1d3b52f899ccf8074ef0fcafe"
NB_CLES_APRES_JEU = 3
# V3, lot 22-bis : boutique N047 du wagon de l'Entrain Express (t002t04, déclencheur 81 n° 4), DÉJÀ dans la table depuis
# la V2 (17 articles, classe 'x_train' : mode `toutes` seulement, exclus ; identifiants BOUTIQUE_ID_BASE + 280..296, bits 280..296) :
# rien n'est ajouté ni déplacé (une seconde entrée pour la même clé d'article ferait deux bits pour un seul achat). Ses 13
# premières entrées (rangs 0 à 12) sont SANS condition [C, `shop_shpN047_0.01n`, `tools/romfs/boutiques.py`] : articles
# fixes, prix <= 1 000 € ; les 4 dernières (rangs 13 à 16 : stock 1 remis chaque jour, prix > 10 000 €) ne sont visibles
# que pour certaines valeurs de l'octet global 369 (`RANDOM_EVENT_ELEMENT` de `random_event` : tiré à l'arrivée sur une
# carte, 1 à 10) : stock tiré au sort, laissées au mode `toutes` comme avant. Avec `apres_jeu` = complet et la région de
# l'Entrain Express ouverte, les 13 articles fixes entrent aussi dans les modes `principales` et `une_par_boutique` (le 1er).
BOUTIQUE_ENTRAIN = "N047"
ENTREES_FIXES_ENTRAIN = frozenset(range(13))

REGIONS_FR = {"les_hauts_de_granval": "Hauts de Granval", "mont_sylvestre": "Mont Sylvestre",
              "coteau_fleuri": "Coteau fleuri", "centre_ville_de_granval": "Centre-ville",
              "quartier_des_boutiques": "Quartier des boutiques", "la_corniche": "La Corniche",
              "tour_excellence": "Tour Excellence", "san_fantastico": "San Fantastico", "ourcival": "Ourcival",
              "vieux_granval": "Vieux Granval", "train": "Train", "chateau_de_sawayama": "Château de Sawayama"}
REGIONS_EN = {"les_hauts_de_granval": "Uptown Springdale", "mont_sylvestre": "Mt. Wildwood",
              "coteau_fleuri": "Blossom Heights", "centre_ville_de_granval": "Downtown Springdale",
              "quartier_des_boutiques": "Shopper's Row", "la_corniche": "Breezy Hills",
              "tour_excellence": "Excellent Tower", "san_fantastico": "San Fantastico", "ourcival": "Harrisville",
              "vieux_granval": "Old Springdale", "train": "Train", "chateau_de_sawayama": "Sawayama Castle"}
# Région de logique des trains (gare du Centre-ville, comme le Tablo-blabla n° 23) ; chapitre 4 (Indications).
REGION_TRAIN = "centre_ville_de_granval"
# Règles propres à une boutique (porte de la carte) : N de « Chapitre N terminé » (3 : ses objets critiques sont ceux
# du rang D, OBJETS_RANG_D)
# N037 : étal de nuit qui n'existe qu'après les requêtes qs0005 et qs0106 (chapitre 4) -> chapitre 4 (et exclue).
CHAPITRE_BOUTIQUE = {"N013": 3, "N024": 4, "N046": 4, "N047": 4, "N037": 4}
# Boutiques du périmètre principal dont les locations sont EXCLUES (remplissage seulement) parce que leur VENDEUR
# n'est pas garanti (`NPC_APPEAR` de son PNJ, archipelago_tracker_cartes.md §12) [C] :
# - N035 et N044 (même vendeur de t101i35) : GetPhase >= 100000 (chapitre 10, ville bouclée, ou après la victoire) ;
# - N042 (2e vendeur de t101i23) : 100010 <= GetPhase <= 109990 seulement (parti après le chapitre 10 : ratable) ;
# - N037 : étal de nuit tiré au sort (25 %, partagé avec l'étal N028), après deux requêtes facultatives.
# Leur règle (région + chapitre 2) reste celle d'avant : trop permissive, sans effet sur une location exclue ; la
# règle exacte (9 chapitres terminés, à justifier dans CHAPITRE_10_JUSTIFIEES) est à décider par l'humain.
# - N028 (étal d'oden, 75 % par tirage de nuit) et N029 (étal de galettes, 30 % par arrivée de jour) : présence tirée
#   au sort, sur un seul des 15 (N029 : 3) emplacements [C, §12.2] : décision de l'humain, aucun objet nécessaire dessus.
BOUTIQUES_VENDEUR_INCERTAIN = frozenset({"N028", "N029", "N035", "N037", "N042", "N044"})
# Boutiques RETIRÉES des nouvelles graines (aucune location) : N042 (vendeur présent pendant le chapitre 10 seulement :
# check ratable). Leurs articles, identifiants (59423500 + rang) et bits restent dans BOUTIQUES_ARTICLES (jamais
# réattribués) : une graine déjà générée qui les contient continue de les lire (tracker, carte : `retirees=False`).
BOUTIQUES_RETIREES = frozenset({"N042"})
# Articles visibles seulement après un Tablo-blabla (retour d'un joueur, 2026-11-03 : le tracker les disait accessibles
# avant le panneau) : classe -> n° du Tablo-blabla dont la règle s'ajoute à celle de l'article (logique.py, pour TOUTE
# graine : locations déjà exclues, rien ne change au placement). Preuve [C, ROM européenne] :
# - 'x_flag2172' (N004, t105i25, articles 8 à 10 = entrées 7 à 9) : seule condition de vente GetGlobalBitFlag(2172) == 1
#   (`tools/romfs/boutiques.py`) ; seul écrivain du flag 2172 : `RunCmd_Map55` de t105g00 (`xq_cherche.py --hash`, seq et
#   .pck ; aucun mot dans code.bin), lancé par le déclencheur n° 55 de `t105g00_trigger` (type 11 : parler au PNJ du
#   panneau, tant que 2172 != 1) ; ce PNJ (`NPC_PRESET` -> `NPC_APPEAR` n° 82, jour et nuit, tout temps) n'apparaît
#   que si GetGlobalBitFlag(2119) == 1 = flag « appelé » du Tablo-blabla n° 12 (`TABLOS`, archipelago_tablos.md §2.2).
TABLOS_ARTICLES: Dict[str, int] = {"x_flag2172": 12}

BOUTIQUES: List[dict] = []
BOUTIQUES_ARTICLES: List[dict] = []


def _b(code: str, carte: str, region: str, declencheurs: Tuple[str, ...], nb_entrees: int, articles) -> None:
    """Boutique `code` ; `nb_entrees` = nombre d'entrées SHOP_CONFIG_INFO de son fichier (contrôle de la ROM) ;
    `articles` = [(rangs des entrées dans le fichier, classe de prix, tag)] dans l'ordre des locations (article i = 1..)."""
    b = {"code": code, "carte": carte, "region": REGION_TRAIN if region == "train" else region,
         "region_nom": region, "declencheurs": declencheurs, "nb_entrees": nb_entrees, "articles": []}
    for i, (entrees, prix, tag) in enumerate(articles, 1):
        rang = len(BOUTIQUES_ARTICLES)
        a = {"boutique": code, "n": i, "entrees": tuple(entrees), "prix": prix, "tag": tag, "rang": rang,
             "id_ap": BOUTIQUE_ID_BASE + rang, "bit": rang,
             "nom_fr": "Boutique : %s (%s) — article %d" % (REGIONS_FR[region], code, i),
             "nom_en": "Shop: %s (%s) — item %d" % (REGIONS_EN[region], code, i)}
        b["articles"].append(a)
        BOUTIQUES_ARTICLES.append(a)
    BOUTIQUES.append(b)


# --- table (tools/romfs/boutiques.py --tsv, colonne `entree`, réduite à la main aux identifiants) ---
# _b(code, carte, région, déclencheurs, nombre d'entrées du fichier, [(rangs d'entrée, classe de prix, tag)])
_b('N001', 't101i23', 'les_hauts_de_granval', ('t101i23#4',), 8, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((7,), 0, ''),
])
_b('N002', 't103i25', 'coteau_fleuri', ('t103i25#1',), 7, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
])
_b('N003', 't104i33', 'centre_ville_de_granval', ('t104i33#1',), 7, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
])
_b('N004', 't105i25', 'quartier_des_boutiques', ('t105i25#1',), 10, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
    ((7,), 0, 'x_flag2172'),
    ((8,), 0, 'x_flag2172'),
    ((9,), 0, 'x_flag2172'),
])
_b('N005', 't106i21', 'la_corniche', ('t106i21#1',), 8, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
    ((7,), 0, ''),
])
_b('N006', 't101i21', 'les_hauts_de_granval', ('t101i21#1',), 4, [
    ((0,), 0, 'x_porte_quete_6'),
    ((1,), 0, 'x_porte_quete_6'),
    ((2,), 0, 'x_porte_quete_6'),
    ((3,), 1, 'x_porte_quete_6'),
])
_b('N007', 't101g00', 'les_hauts_de_granval', ('t101g00#93',), 7, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
    ((4,), 2, ''),
    ((5,), 2, ''),
    ((6,), 0, ''),
])
_b('N008', 't103i23', 'coteau_fleuri', (), 5, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
])
_b('N009', 't103i37', 'coteau_fleuri', ('t103i37#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 2, ''),
])
_b('N010', 't104i27', 'centre_ville_de_granval', ('t104i27#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
])
_b('N011', 't103i35', 'coteau_fleuri', ('t103i35#1',), 4, [
    ((0,), 2, ''),
    ((2,), 2, ''),
])
_b('N012', 't105i23', 'quartier_des_boutiques', ('t105i23#3',), 3, [
    ((0,), 0, ''),
    ((1,), 1, ''),
    ((2,), 2, ''),
])
_b('N013', 't105i27', 'quartier_des_boutiques', ('t105i27#3',), 6, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
    ((4, 5), 1, 'q62'),
])
_b('N014', 't105i20', 'quartier_des_boutiques', ('t105i20#5',), 3, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
])
_b('N015', 't105i20', 'quartier_des_boutiques', ('t105i20#6',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 1, ''),
    ((3,), 4, ''),
])
_b('N016', 't105i35', 'quartier_des_boutiques', ('t105i35#4',), 29, [
    ((0,), 1, ''),
    ((1,), 3, ''),
    ((2,), 4, 'ch6'),
    ((3,), 2, ''),
    ((4,), 2, ''),
    ((5,), 3, ''),
    ((6,), 3, ''),
    ((7,), 4, 'ch6'),
    ((8,), 4, 'ch6'),
    ((9,), 2, ''),
    ((10,), 2, ''),
    ((11,), 3, ''),
    ((12,), 3, ''),
    ((13,), 4, 'ch6'),
    ((14,), 4, 'ch6'),
    ((15,), 2, ''),
    ((16,), 2, ''),
    ((17,), 3, ''),
    ((18,), 3, ''),
    ((19,), 4, 'ch6'),
    ((20,), 4, 'ch6'),
    ((21,), 2, ''),
    ((22,), 2, ''),
    ((23,), 3, ''),
    ((24,), 3, ''),
    ((25,), 4, 'ch6'),
    ((26,), 4, 'ch6'),
    ((27,), 4, 'ch6'),
    ((28,), 4, 'x_rang_s'),
])
_b('N017', 't105i21', 'quartier_des_boutiques', ('t105i21#1',), 16, [
    ((3,), 4, ''),
    ((4,), 1, ''),
    ((6,), 1, ''),
    ((8,), 1, ''),
    ((10,), 1, ''),
    ((12,), 1, ''),
    ((14,), 1, ''),
])
_b('N018', 't102g00', 'mont_sylvestre', ('t102g00#49',), 4, [
    ((0,), 1, ''),
    ((1,), 1, ''),
    ((2,), 1, ''),
    ((3,), 1, ''),
])
_b('N019', 't101i31', 'les_hauts_de_granval', ('t101i31#9',), 1, [
    ((0,), 0, ''),
])
_b('N020', 't104i41', 'centre_ville_de_granval', ('t104i41#1',), 6, [
    ((0,), 1, ''),
    ((1,), 1, ''),
    ((2,), 2, ''),
    ((3,), 2, ''),
    ((4, 5), 1, 'q62'),
])
_b('N021', 't104i35', 'centre_ville_de_granval', ('t104i35#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 1, ''),
    ((3,), 2, ''),
])
_b('N022', 't105i37', 'quartier_des_boutiques', ('t105i37#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
])
_b('N023', 't121i03', 'san_fantastico', ('t121i03#1',), 6, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 2, ''),
    ((5,), 4, ''),
])
_b('N024', 't131i05', 'ourcival', ('t131i05#1',), 6, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 4, ''),
])
_b('N025', 't201g00', 'vieux_granval', ('t201g00#18',), 7, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
])
_b('N026', 't201i10', 'vieux_granval', ('t201i10#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 4, ''),
])
_b('N027', 't201i10', 'vieux_granval', ('t201i10#2',), 3, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 1, ''),
])
_b('N028', 't101g00', 'les_hauts_de_granval', ('t101g00#94', 't103g00#52', 't104g00#68', 't105g00#35', 't106g00#40'), 3, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
])
_b('N029', 't101g00', 'les_hauts_de_granval', ('t101g00#96', 't103g00#54', 't105g00#37', 't106g00#42'), 1, [
    ((0,), 0, ''),
])
_b('N030', 't105g00', 'quartier_des_boutiques', ('t105g00#33',), 1, [
    ((0,), 0, 'x_beignets'),
])
_b('N031', 't105g00', 'quartier_des_boutiques', ('t105g00#34',), 1, [
    ((0,), 0, 'x_beignets'),
])
_b('N032', 't104i23', 'centre_ville_de_granval', ('t104i23#1',), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
])
_b('N033', 't107i03', 'tour_excellence', ('t107i03#2',), 7, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
])
_b('N035', 't101i35', 'les_hauts_de_granval', ('t101i35#1',), 10, [
    ((0,), 4, ''),
    ((1,), 4, ''),
    ((2,), 4, ''),
    ((3,), 4, ''),
    ((4,), 4, ''),
    ((5,), 4, ''),
    ((6,), 4, ''),
    ((7,), 4, ''),
    ((8,), 4, ''),
    ((9,), 4, 'x_rang_s'),
])
_b('N036', 't104i23', 'centre_ville_de_granval', ('t104i23#3',), 6, [
    ((0,), 0, 'x_portails'),
    ((1,), 2, 'x_portails'),
    ((2,), 1, 'x_portails'),
    ((3,), 1, 'x_portails'),
    ((4,), 0, 'x_portails'),
    ((5,), 0, 'x_portails'),
])
_b('N037', 't101g00', 'les_hauts_de_granval', ('t101g00#95', 't103g00#53', 't104g00#69', 't105g00#36', 't106g00#41'), 4, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 0, ''),
])
_b('N042', 't101i23', 'les_hauts_de_granval', ('t101i23#5',), 12, [
    ((0,), 0, ''),
    ((1,), 0, ''),
    ((2,), 0, ''),
    ((3,), 1, ''),
    ((4,), 0, ''),
    ((5,), 0, ''),
    ((6,), 0, ''),
    ((7,), 0, ''),
    ((8,), 1, ''),
    ((9,), 1, ''),
    ((10,), 1, ''),
    ((11,), 1, ''),
])
_b('N044', 't101i35', 'les_hauts_de_granval', ('t101i35#2',), 29, [
    ((0,), 2, ''),
    ((1,), 3, ''),
    ((2,), 1, ''),
    ((3,), 3, ''),
    ((4,), 4, ''),
    ((5,), 2, ''),
    ((6,), 2, ''),
    ((7,), 3, ''),
    ((8,), 3, ''),
    ((9,), 4, ''),
    ((10,), 4, ''),
    ((11,), 2, ''),
    ((12,), 2, ''),
    ((13,), 3, ''),
    ((14,), 3, ''),
    ((15,), 4, ''),
    ((16,), 4, ''),
    ((17,), 2, ''),
    ((18,), 2, ''),
    ((19,), 3, ''),
    ((20,), 3, ''),
    ((21,), 4, ''),
    ((22,), 4, ''),
    ((23,), 2, ''),
    ((24,), 2, ''),
    ((25,), 3, ''),
    ((26,), 3, ''),
    ((27,), 4, ''),
    ((28,), 4, ''),
])
_b('N046', 't001t04', 'train', ('t001t04#6',), 44, [
    ((0,), 0, 'x_train'),
    ((1,), 0, 'x_train'),
    ((2,), 0, 'x_train'),
    ((3,), 0, 'x_train'),
    ((4,), 0, 'x_train'),
    ((5,), 0, 'x_train'),
    ((6,), 0, 'x_train'),
    ((7,), 0, 'x_train'),
    ((8,), 0, 'x_train'),
    ((9,), 0, 'x_train'),
    ((10,), 0, 'x_train'),
    ((11,), 1, 'x_train'),
    ((12,), 0, 'x_train'),
    ((13,), 0, 'x_train'),
    ((14,), 0, 'x_train'),
    ((15,), 0, 'x_train'),
    ((16,), 0, 'x_train'),
    ((17,), 1, 'x_train'),
    ((18,), 1, 'x_train'),
    ((19,), 1, 'x_train'),
    ((20,), 2, 'x_train'),
    ((21,), 0, 'x_train'),
    ((22,), 0, 'x_train'),
    ((23,), 0, 'x_train'),
    ((24,), 0, 'x_train'),
    ((25,), 0, 'x_train'),
    ((26,), 0, 'x_train'),
    ((27,), 0, 'x_train'),
    ((28,), 0, 'x_train'),
    ((29,), 2, 'x_train'),
    ((30,), 0, 'x_train'),
    ((31,), 0, 'x_train'),
    ((32,), 0, 'x_train'),
    ((33,), 0, 'x_train'),
    ((36,), 0, 'x_train'),
    ((37,), 0, 'x_train'),
    ((38,), 0, 'x_train'),
    ((39,), 0, 'x_train'),
    ((40,), 1, 'x_train'),
    ((41,), 4, 'x_train'),
    ((42,), 4, 'x_train'),
    ((43,), 4, 'x_train'),
])
_b('N047', 't002t04', 'train', ('t002t04#4',), 17, [
    ((0,), 0, 'x_train'),
    ((1,), 0, 'x_train'),
    ((2,), 0, 'x_train'),
    ((3,), 1, 'x_train'),
    ((4,), 0, 'x_train'),
    ((5,), 0, 'x_train'),
    ((6,), 1, 'x_train'),
    ((7,), 0, 'x_train'),
    ((8,), 0, 'x_train'),
    ((9,), 1, 'x_train'),
    ((10,), 0, 'x_train'),
    ((11,), 0, 'x_train'),
    ((12,), 0, 'x_train'),
    ((13,), 4, 'x_train'),
    ((14,), 4, 'x_train'),
    ((15,), 4, 'x_train'),
    ((16,), 4, 'x_train'),
])
# V3, lot 22 : N045, boutique du village du Château de Sawayama (t301g00, déclencheur 81 n° 2, sans condition) [C] ;
# vendeur : le PNJ de la boutique de t301g00, présent quand la requête 119 est finie (`NPC_APPEAR` : GetQuestPhase(qs0119) == 255),
# condition déjà exigée par la requête 96 qui ouvre le château ; 3 articles sans condition, prix <= 500 €. Classe « aj » :
# jamais dans une graine sans `apres_jeu` = complet (`articles_du_mode(..., apres_jeu=True)`), règle et exclusion
# données par `logique.construire_plan` (région du château, hors du chemin de l'objectif : exclus).
_b('N045', 't301g00', 'chateau_de_sawayama', ('t301g00#2',), 3, [
    ((0,), 0, 'aj'),
    ((1,), 0, 'aj'),
    ((2,), 0, 'aj'),
])

BOUTIQUES_PAR_CODE: Dict[str, dict] = {b["code"]: b for b in BOUTIQUES}
ARTICLES_PAR_ID: Dict[int, dict] = {a["id_ap"]: a for a in BOUTIQUES_ARTICLES}

# Valeurs de l'option `boutiques` (options.py). « aucune » par défaut tant que l'essai en jeu (archipelago/PLAN.md,
# « Gros test V1 », boutiques) n'est pas fait ; « principales » est le périmètre recommandé par l'analyse.
MODES_BOUTIQUES = ("aucune", "une_par_boutique", "principales", "toutes")
BOUTIQUES_PAR_DEFAUT = "aucune"
# Option `boutiques_prix_max` : classe de prix la plus chère encore en progression (au-delà : location EXCLUE, attente
# d'argent) ; 2 = 3 000 € (défaut), 4 = sans limite.
PRIX_MAX_PAR_DEFAUT = 2


def principal(a: dict) -> bool:
    """Article du périmètre `principales` (et `une_par_boutique`)."""
    return not a["tag"].startswith("x_")


def articles_avant_lot22() -> List[dict]:
    """Les 297 articles d'avant le lot 22 (empreinte `EMPREINTE_ARTICLES`), dans l'ordre des identifiants."""
    return [a for a in BOUTIQUES_ARTICLES if a["boutique"] not in BOUTIQUES_APRES_JEU]


def articles_apres_jeu() -> List[dict]:
    """Les articles des boutiques d'après-jeu (lot 22 : N045 ; empreinte `EMPREINTE_ARTICLES_APRES_JEU`)."""
    return [a for a in BOUTIQUES_ARTICLES if a["boutique"] in BOUTIQUES_APRES_JEU]


def ids_retires() -> frozenset:
    """Identifiants AP des articles des boutiques retirées des nouvelles graines (`BOUTIQUES_RETIREES`)."""
    return frozenset(a["id_ap"] for a in BOUTIQUES_ARTICLES if a["boutique"] in BOUTIQUES_RETIREES)


def article_fixe_entrain(a: dict) -> bool:
    """Article fixe (sans condition) de la boutique de l'Entrain Express (V3, lot 22-bis)."""
    return a["boutique"] == BOUTIQUE_ENTRAIN and len(a["entrees"]) == 1 and a["entrees"][0] in ENTREES_FIXES_ENTRAIN


def articles_entrain_fixes() -> List[dict]:
    """Les 13 articles fixes de N047 (V3, lot 22-bis), dans l'ordre des identifiants."""
    return [a for a in BOUTIQUES_ARTICLES if article_fixe_entrain(a)]


def articles_du_mode(mode: str, retirees: bool = True, apres_jeu: bool = False, entrain: bool = False) -> List[dict]:
    """Articles devenus locations dans ce mode (ordre de BOUTIQUES_ARTICLES). `retirees` : sans les boutiques de
    `BOUTIQUES_RETIREES` (toute nouvelle graine) ; False : graine générée avant leur retrait (tracker, carte).
    `apres_jeu` (V3, lot 22) : avec les boutiques d'après-jeu (`BOUTIQUES_APRES_JEU` : N045) ; False (défaut) : la liste
    d'avant le lot 22, exactement. `entrain` (V3, lot 22-bis) : les articles fixes de N047 comptent aussi dans les modes
    `principales` et `une_par_boutique` (le mode `toutes` les a toujours) ; False (défaut) : la liste d'avant."""
    if mode == "aucune":
        return []
    ecarte = BOUTIQUES_RETIREES if retirees else frozenset()
    if not apres_jeu:
        ecarte = ecarte | BOUTIQUES_APRES_JEU

    def retenu(a: dict) -> bool:
        return principal(a) or (entrain and article_fixe_entrain(a))

    if mode == "toutes":
        return [a for a in BOUTIQUES_ARTICLES if a["boutique"] not in ecarte]
    if mode == "principales":
        return [a for a in BOUTIQUES_ARTICLES if retenu(a) and a["boutique"] not in ecarte]
    if mode == "une_par_boutique":
        out = []
        for b in BOUTIQUES:
            if b["code"] in ecarte:
                continue
            p = [a for a in b["articles"] if retenu(a)]
            if p:
                out.append(p[0])
        return out
    raise ValueError(f"mode de boutiques inconnu : {mode!r}")


def chapitre_article(a: dict) -> int:
    """N de la règle « Chapitre N terminé » (au moins 2 : un chapitre terminé) de l'article."""
    n = max(2, CHAPITRE_BOUTIQUE.get(a["boutique"], 2))
    if a["tag"] == "ch6":
        n = max(n, 6)
    elif a["tag"] in ("q62", "x_portails"):     # N036 : salle de portail t104i23 (GetPhase >= 4-50, portails fermés
        n = max(n, 5)                           # de 4-35 à la fin du chapitre 4 : archipelago_portails_tardifs.md)
    return n


def exclu(a: dict, prix_max: int) -> bool:
    """Location exclue (remplissage seulement) : hors du périmètre principal, plus chère que la classe `prix_max`, ou
    d'une boutique dont le vendeur n'est pas garanti (`BOUTIQUES_VENDEUR_INCERTAIN`)."""
    return not principal(a) or a["prix"] > prix_max or a["boutique"] in BOUTIQUES_VENDEUR_INCERTAIN
