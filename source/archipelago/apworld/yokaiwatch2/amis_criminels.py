# -*- coding: utf-8 -*-
"""Checks « Ami : <Yo-kai> » et « Yo-criminel : <Yo-kai> » (docs/systemes/archipelago_amis_criminels.md), sans Archipelago.

Données saisies à la main (règle 6 de CLAUDE.md) : noms FR / EN repris de l'ancien mod de l'humain (listes du
Médaillium de `game_data.py`, FR et EN parallèles), sauf deux saisis à la main (Benkei, Pépésbrouf / Papa Windbag) ;
identifiants numériques seulement (identifiants AP, n° du Médaillium = index de bit, n° de flag). Aucun hachage,
aucun rang ni aucune table du jeu : le chapitre de règle est NOTRE valeur de logique (dérivée du rang de l'espèce).
"""
from typing import Dict, List, Tuple

# ---------------------------------------------------------------------------
# Amis (archipelago_amis_criminels.md §2)
# ---------------------------------------------------------------------------
# Check = bit « ami » du Médaillium de la sauvegarde liée : bit n (n = n° du Médaillium de l'espèce, CHARA_PARAM_INFO
# v[49]) de P+0x44C (Comp) OU de P+0x604 (CompEx), posé par l'enregistrement d'obtention FUN_004AAA98 et jamais
# effacé [C, archipelago_rando_yokai.md §10.3, §10.6]. Lu par le client dans la lecture groupée du Médaillium qu'il
# fait déjà pour le tracker (P+0x40C..0x643) : aucun paquet GDB en plus.
# Espèces retenues (196 n° du Médaillium) [C, calcul local sur la ROM, `archipelago/outils/amis_candidats.py`] :
# - « sauvage » (162 n°, 176 espèces) : espèce recrutable en combat (taux d'amitié non nul, §3.5 du rando), non légendaire, présente
#   dans une rencontre sauvage (loupe ou errant) dont au moins un lieu est « d'avant la fin » (règle commune des
#   randomizers, `rencontres.lieu_hors_avant_fin`, archipelago_rando_yokai.md §3.7 : ni carte d'après-jeu ou du réseau
#   caché, ni condition GameClear / rang de montre S / phase d'après-jeu). Le randomizer de Yo-kai est une bijection sur
#   ses espèces : l'ensemble des espèces sauvages ne change pas (leurs lieux, si) ;
# - « evolution » (24) : évolution par niveau (CHARA_EVOLVE_INFO, niveaux 15 à 33) d'une espèce retenue ;
# - « fusion » (10) : fusion Yo-kai + Yo-kai (COMBINE_INFO) de deux espèces retenues.
# Écartées : non recrutables en combat (boss, Shogunyan, doubles de même rang…), légendaires (sceaux), Yo-kai vus
# seulement dans des combats d'histoire / de quête / de tournoi, spots (DATA_ITEM, Noko…), trains, Crank-a-kai, QR,
# évènements, transferts, fusions avec un objet, et tout ce qui n'est donné que par l'histoire [S : obtention possible
# avant l'après-jeu non prouvée].
# Logique : locations EXCLUES (remplissage seulement) : les lieux d'apparition dépendent du mélange calculé CHEZ LE JOUEUR
# (l'APWorld ne connaît pas les rencontres, règle 6) et l'amitié est aléatoire. Règle prudente (tracker) : celle de
# « Chapitre N terminé », N = `chapitre`, dérivé du rang de l'espèce (E 1, D 2, C 4, B 5, A 7, S 8) ; évolution et
# fusion : au moins un chapitre après leur(s) source(s) (au plus 8 : jamais une règle du chapitre 10 bouclé).
# `portail` (logique.PORTAILS, archipelago_portails_tardifs.md) : espèce sauvage seulement dans des salles de portail
# mystère [C, ROM européenne] : check « tardif » (déjà exclu), mention du tracker, `chapitre` au moins 3 (portails).
# Identifiants : ceux de l'ancien mod (« Amitié : X », 59420600..59420662) quand l'espèce y était ; sinon nouveaux, à la
# suite dans la plage « amitiés » de l'ancien mod (59420663..59420828, jamais utilisée ailleurs). Les identifiants des
# checks retirés (AMIS_RETIRES_AVANT_FIN) restent réservés : ceux des autres ne changent pas.
AMIS: List[dict] = []
# Origines : les trois premières sont celles des 196 checks d'origine ; « histoire », « requete » et « evenement » sont
# les amis donnés par un script ou liés à un objet d'évènement (branche `ap/checks-amis-histoire-evenement`, plus bas).
# « place » : Yo-kai d'évènement à son emplacement d'origine par une « Invitation » (branche `ap/invitations-evenement`).
# « fusion_objet » : fusion Yo-kai + objet dont l'objet a une source garantie avant la fin (FUSIONS_OBJET, plus bas).
# « armee » : les 16 Yo-kai des armées, que seul le mélange des Yo-kai par rencontre place (ARMEES, plus bas).
ORIGINES_AMIS = ("sauvage", "evolution", "fusion", "histoire", "requete", "evenement", "place", "fusion_objet", "armee")


def _a(medaille: int, id_ap: int, fr: str, en: str, chapitre: int, origine: str, **plus) -> None:
    AMIS.append({"medaille": medaille, "id_ap": id_ap, "chapitre": chapitre, "origine": origine,
                 "yokai_fr": fr, "yokai_en": en, "nom_fr": "Ami : " + fr, "nom_en": "Friend: " + en, **plus})


_a(1, 59420600, 'Woko', 'Pandle', 1, "sauvage")
_a(2, 59420601, 'Pagno', 'Undy', 4, "evolution")
_a(3, 59420602, 'Alfoncéo', 'Tanbo', 5, "sauvage", portail="crank")    # salle t103i31 seulement (jeu d'origine)
_a(4, 59420603, 'Toumou', 'Cutta-nah', 1, "sauvage")
_a(5, 59420604, "Lamlam'mou", 'Cutta-nah-nah', 4, "evolution")
_a(6, 59420605, 'Samoumouraï', 'Slacka-slash', 5, "sauvage")
_a(7, 59420606, 'Samoussrai', 'Brushido', 1, "sauvage")
_a(8, 59420663, 'Ronimpec', 'Washogun', 5, "evolution")
_a(9, 59420664, 'Roupilion', 'Lie-in', 1, "sauvage")
_a(10, 59420665, 'Rugis', 'Lie-in Heart', 7, "evolution")
_a(11, 59420666, 'Trépigno', 'Hissfit', 1, "sauvage")
_a(14, 59420667, 'Sumochi', 'Mochismo', 2, "sauvage", portail="crank")           # gymnase t101i59 (portail) ou Crank-a-kai
_a(15, 59420668, 'Mochimacho', 'Minochi', 2, "sauvage")
_a(16, 59420669, 'Sale de bain', 'Tublappa', 2, "sauvage")
_a(17, 59420670, 'Agonigiri', 'Slicenrice', 2, "sauvage")
_a(18, 59420671, 'Onigirix', 'Flamurice', 7, "evolution")
_a(19, 59420672, 'Heaumer', 'Helmsman', 2, "sauvage")
_a(20, 59420673, 'Bushidos', 'Reuknight', 7, "fusion")
_a(22, 59420674, 'Bouh', 'Mudmunch', 4, "sauvage")
_a(24, 59420675, 'Feulion', 'Blazion', 4, "sauvage")
_a(25, 59420676, 'Vibrilion', 'Quaken', 5, "sauvage")
_a(26, 59420677, 'Siro', 'Siro', 7, "sauvage")
_a(27, 59420678, 'Bonneto', 'Chansin', 4, "sauvage")
_a(31, 59420679, 'Benkei', 'Benkei', 4, "sauvage")
_a(32, 59420680, 'B3-NK1', 'B3-NK1', 5, "sauvage")
_a(33, 59420681, 'Sushiyama', 'Sushiyama', 5, "sauvage")
_a(34, 59420682, 'Kapunki', 'Kapunki', 7, "sauvage")
_a(35, 59420683, 'Scatcheur', 'Beetler', 5, "sauvage")
_a(41, 59420608, 'Gastong', 'Pittapatt', 1, "sauvage")
_a(42, 59420609, 'Morvobec', 'Snotsolong', 1, "sauvage")
_a(43, 59420610, 'Matchou', 'Duchoo', 2, "sauvage")
_a(44, 59420611, 'Papa Ress', "D'wanna", 1, "sauvage")
_a(45, 59420612, 'Ralbouc', "N'more", 4, "evolution")
_a(46, 59420613, 'Bastata', "Q'wit", 4, "sauvage")
_a(47, 59420684, 'Chaipô', 'Wazzat', 1, "sauvage")
_a(48, 59420685, 'Mémogre', 'Houzzat', 5, "evolution")
_a(49, 59420686, 'Gagalurin', 'Dummkap', 1, "sauvage")
_a(51, 59420687, 'Marra', 'Lafalotta', 2, "sauvage")
_a(52, 59420688, 'Violette', 'Blips', 4, "sauvage")
_a(56, 59420689, 'Cupistol', 'Cupistol', 2, "sauvage")
_a(58, 59420691, 'Nonjuan', 'Casanono', 7, "sauvage")
_a(61, 59420692, 'Brumette', 'Smogling', 2, "sauvage")
_a(62, 59420693, 'Brumella', 'Smogmella', 7, "evolution")
_a(63, 59420694, 'Padrézo', 'Signibble', 2, "sauvage")
_a(71, 59420697, 'Nuiroir', 'Mircle', 7, "sauvage")
_a(72, 59420698, 'Hiblusion', 'Illoo', 4, "sauvage")
_a(73, 59420699, 'Hibrouille', 'Elloo', 4, "sauvage")
_a(74, 59420700, 'Hibourling', 'Alloo', 5, "sauvage")
_a(75, 59420701, 'Espi', 'Espy', 5, "sauvage")
_a(76, 59420702, 'Étassivilia', 'Infour', 5, "sauvage")
_a(77, 59420703, 'Valetino', 'Verygoodsir', 5, "sauvage")
_a(84, 59420614, 'Potache', 'Terrorpotta', 1, "sauvage")
_a(85, 59420615, 'Darabajoie', 'Dulluma', 1, "sauvage")
_a(86, 59420616, 'Darumastar', 'Darumacho', 5, "fusion", portail="crank")       # Darabajoie + Sumochi
_a(87, 59420617, 'Goruma', 'Goruma', 5, "sauvage")
_a(92, 59420706, 'Nanpart', 'Noway', 1, "sauvage")
_a(93, 59420707, 'Passpa', 'Impass', 7, "evolution")
_a(94, 59420708, 'Granpart', 'Walldin', 7, "sauvage")
_a(98, 59420709, 'Hauber', 'Armsman', 2, "sauvage")
_a(99, 59420710, 'Humainequin', 'Mimikin', 2, "sauvage")
_a(100, 59420711, 'Boulapic', 'Blowkade', 2, "sauvage")
_a(101, 59420712, 'Bouldacier', 'Ledballoon', 4, "sauvage")
_a(102, 59420713, 'Pachycoul', 'Fidgephant', 2, "sauvage")
_a(103, 59420714, 'Persévéfant', 'Touphant', 4, "sauvage")
_a(104, 59420715, 'Pachypipi', 'Enduriphant', 7, "fusion")
_a(108, 59420717, 'Lama Laya', 'Mad Mountain', 4, "sauvage")
_a(109, 59420718, 'Etna Magma', 'Lava Lord', 5, "sauvage")
_a(110, 59420719, 'Castelius III', 'Castelius III', 4, "sauvage")
_a(111, 59420720, 'Castelius II', 'Castelius II', 5, "fusion")
_a(112, 59420721, 'Castelius I', 'Castelius I', 7, "fusion")
_a(114, 59420722, 'Coléroptère', 'Rhinoggin', 5, "sauvage")
_a(123, 59420621, 'Gambeth', 'Leggly', 1, "sauvage")
_a(124, 59420622, 'Squarlett', 'Dazzabel', 1, "sauvage")
_a(125, 59420623, 'Margoth', 'Rattelle', 4, "fusion")
_a(126, 59420624, 'Squelèbelle', 'Skelebella', 5, "sauvage")
_a(127, 59420625, 'Cigalopin', 'Cadin', 1, "sauvage")
_a(128, 59420626, 'Cigaillard', 'Cadable', 4, "evolution")
_a(130, 59420723, 'Chihuaglagla', 'Pupsicle', 1, "sauvage")
_a(133, 59420724, 'Traviolette', 'Jumbelina', 2, "sauvage")
_a(139, 59420725, 'Kappacap', 'Walkappa', 2, "sauvage")
_a(140, 59420726, 'Appak', 'Appak', 7, "evolution")
_a(141, 59420727, 'Kappaloha', 'Supyo', 7, "sauvage")
_a(144, 59420728, 'Komajiro', 'Komajiro', 2, "sauvage")
_a(145, 59420729, 'Komistigri', 'Komiger', 7, "evolution")
_a(148, 59420732, 'Tapur', 'Whapir', 4, "sauvage")
_a(149, 59420733, 'Sabruine', 'Drizzelda', 4, "sauvage")
_a(150, 59420734, 'Vito', 'Nekidspeed', 4, "sauvage")
_a(151, 59420735, 'Pitou', 'Shmoopie', 4, "sauvage")
_a(155, 59420737, 'Angélik', 'Frostina', 5, "sauvage")
_a(158, 59420738, 'Faux Kappa', 'Faux Kappa', 7, "sauvage")
_a(161, 59420628, 'Amoiz', 'Wantston', 1, "sauvage")
_a(162, 59420629, 'Pikor', 'Grubsnitch', 2, "sauvage")
_a(163, 59420630, 'Noripop', 'Wiglin', 1, "sauvage")
_a(164, 59420631, 'Algacarena', 'Kelpacabana', 4, "evolution")
_a(165, 59420632, 'Wakapoeira', 'Steppa', 1, "sauvage")
_a(166, 59420633, 'Salsalga', 'Rhyth', 2, "sauvage")
_a(167, 59420634, 'Granpapéti', 'Hungramps', 1, "sauvage")
_a(172, 59420741, 'Felipaix', 'Sandmeh', 1, "sauvage")
_a(174, 59420742, 'Parasolal', 'Pallysol', 1, "sauvage")
_a(175, 59420743, 'Scarasol', 'Scarasol', 7, "fusion")
_a(176, 59420744, 'Nomoné', 'Lodo', 2, "sauvage")
_a(177, 59420745, 'Ivanupieds', 'Supoor Hero', 7, "evolution")
_a(178, 59420746, 'Noproblemo', 'Chippa', 4, "sauvage")
_a(179, 59420747, 'Lulutin', 'Gnomey', 2, "sauvage")
_a(180, 59420748, 'Grégrigry', 'High Gnomey', 7, "evolution")
_a(181, 59420749, 'Papiltation', 'Enerfly', 2, "sauvage")
_a(182, 59420750, 'Papiltension', 'Enefly', 2, "sauvage")
_a(183, 59420751, 'Hyprapillon', 'Betterfly', 7, "fusion")
_a(184, 59420752, 'Vitapillon', 'Peppillon', 8, "sauvage")
_a(185, 59420753, 'Métaureaulog', 'Predictabull', 2, "sauvage")
_a(188, 59420754, 'Sabrille', "Ray O'Light", 4, "sauvage")
_a(189, 59420755, 'Jojojoyeux', 'Happierre', 4, "sauvage")
_a(190, 59420756, 'Paradoxa', 'Reversa', 7, "fusion")
_a(191, 59420757, 'Potaumorose', 'Reversette', 7, "sauvage")
_a(192, 59420758, 'Ratatam', "Ol' Saint Trick", 5, "sauvage")
_a(193, 59420759, 'Supernoël', "Ol' Fortune", 5, "sauvage")
_a(194, 59420760, 'Dédé', 'Rollen', 5, "sauvage")
_a(195, 59420761, 'Dédestin', 'Dubbles', 7, "sauvage")
_a(196, 59420762, 'Tontonerre', 'Papa Bolt', 7, "sauvage")
_a(197, 59420763, 'Omnitonton', 'Uncle Infinite', 8, "sauvage")
_a(198, 59420764, 'Tata Aura', 'Mama Aura', 7, "sauvage")
_a(202, 59420635, 'Égaroni', 'Leadoni', 1, "sauvage")
_a(203, 59420636, 'Onisoi', 'Mynimo', 2, "sauvage")
_a(204, 59420637, 'Tortico', 'Ake', 1, "sauvage")
_a(206, 59420639, 'Contracto', 'Agon', 5, "sauvage")
_a(211, 59420766, 'Nihilistik', 'Negatibuzz', 1, "sauvage")
_a(212, 59420767, 'Émousstik', 'Moskevil', 4, "evolution")
_a(213, 59420768, 'Grattoptère', 'Scritchy', 7, "sauvage")
_a(214, 59420769, 'Marcognito', 'Dimmy', 1, "sauvage")
_a(215, 59420770, 'Ninjamévu', 'Blandon', 5, "evolution")
_a(216, 59420771, 'Nihilo', 'Nul', 7, "sauvage")
_a(217, 59420772, 'Suspicioni', 'Suspicioni', 2, "sauvage")
_a(218, 59420773, 'Ragioni', 'Tantroni', 2, "sauvage")
_a(219, 59420774, 'Contrarioni', 'Contrarioni', 5, "sauvage")
_a(220, 59420775, 'Chauvekipeut', 'Hidabat', 2, "sauvage")
_a(221, 59420776, "Chauv'coucou", 'Abodabat', 7, "fusion")
_a(222, 59420777, 'Vampiloc', 'Belfree', 7, "sauvage")
_a(223, 59420778, 'Gloups', 'Yoink', 2, "sauvage")
_a(224, 59420779, 'Chip-Chope', 'Gimme', 7, "evolution")
_a(225, 59420780, 'Hâtila', "K'mon-K'mon", 4, "sauvage")
_a(226, 59420781, 'Amédélègue', 'Yoodooit', 4, "sauvage")
_a(229, 59420782, 'Tengubre', 'Tengloom', 4, "sauvage")
_a(230, 59420783, 'Bibliotengu', 'Nird', 5, "sauvage")
_a(231, 59420784, 'Snobéa', 'Snobetty', 5, "sauvage")
_a(244, 59420642, 'Malmidal', 'Coughkoff', 1, "sauvage")
_a(245, 59420643, 'Écchinose', 'Hurchin', 2, "sauvage")
_a(246, 59420644, 'Humidon', 'Droplette', 1, "sauvage")
_a(247, 59420645, 'Délujien', 'Drizzle', 5, "evolution")
_a(248, 59420646, 'Fryzeur', 'Slush', 1, "sauvage")
_a(249, 59420647, 'Kongel', 'Alhail', 5, "evolution")
_a(250, 59420648, 'Hémorhino', 'Gush', 2, "sauvage")
_a(251, 59420788, 'Chiperpiou', 'Peckpocket', 1, "sauvage")
_a(252, 59420789, 'Rapiaf', 'Robbinyu', 5, "evolution")
_a(253, 59420790, 'Pioubidou', 'Rockabelly', 2, "sauvage")
_a(254, 59420791, 'Zikafon', 'Squeeky', 1, "sauvage")
_a(256, 59420792, 'Flamente', 'Buhu', 1, "sauvage")
_a(257, 59420793, 'Volibrius', 'Flumpy', 4, "sauvage")
_a(262, 59420794, 'Poilux', 'Furgus', 1, "sauvage")
_a(263, 59420795, 'Poil-Émile', 'Furdinand', 7, "evolution")
_a(264, 59420796, 'Non-non', 'Nosirs', 2, "sauvage")
_a(265, 59420797, 'Lulugubre', 'Dismarelda', 2, "sauvage")
_a(266, 59420798, 'Blablara', 'Chatalie', 2, "sauvage")
_a(267, 59420799, 'Umilie', 'Nagatha', 4, "sauvage")
_a(268, 59420800, 'Pépésbrouf', 'Papa Windbag', 4, "sauvage")
_a(269, 59420801, 'Adolfo Jeton', 'Ben Tover', 4, "sauvage")
_a(270, 59420802, 'Pégaz', 'Cheeksqueek', 4, "sauvage")
_a(271, 59420803, 'Méphito', 'Cuttincheez', 7, "sauvage")
_a(275, 59420804, 'Misterbide', 'Compunzer', 7, "sauvage")
_a(276, 59420805, 'Flopito', 'Lamedian', 7, "sauvage")
_a(277, 59420806, 'Cenridion', 'Grumples', 5, "sauvage")
_a(280, 59420807, 'Insomnelle', 'Insomni', 7, "sauvage")
_a(284, 59420649, 'Crampaud', 'Cricky', 1, "sauvage")
_a(288, 59420653, 'Maudieuse', 'Snaggly', 1, "sauvage")
_a(289, 59420654, 'Jérémya', 'Whinona', 7, "evolution")
_a(290, 59420655, 'Anghihihille', 'Heheheel', 2, "sauvage")
_a(291, 59420808, 'Méroubadour', 'Croonger', 4, "sauvage")
_a(292, 59420809, 'Urnaconda', 'Urnaconda', 4, "sauvage")
_a(293, 59420810, 'Murhaine', 'Fishpicable', 2, "sauvage")
_a(294, 59420811, 'Saumhonni', 'Rageon', 5, "evolution")
_a(295, 59420812, 'Vexturgeon', 'Tunatic', 7, "sauvage")
_a(296, 59420813, 'Yvantouse', 'Flushback', 2, "sauvage")
_a(300, 59420814, 'Dracounet', 'Draggie', 2, "sauvage")
_a(302, 59420815, 'Dragô', 'Azure Dragon', 8, "sauvage")
_a(303, 59420816, 'Sirénée', 'Mermaidyn', 2, "sauvage")
_a(306, 59420817, 'Mlle Coucou', 'Lady Longnek', 4, "sauvage")
_a(307, 59420818, 'Bababou', 'Daiz', 4, "sauvage")
_a(308, 59420819, 'Tourneboul', 'Confuze', 5, "sauvage")
_a(309, 59420820, 'Croquin', 'Chummer', 4, "sauvage")
_a(310, 59420821, 'Inisquale', 'Shrook', 5, "sauvage")
_a(311, 59420822, 'Claquille', 'Spenp', 4, "sauvage")
_a(312, 59420823, 'Cocpille', 'Almi', 5, "sauvage")
_a(313, 59420824, 'Jacquasseur', 'Babblong', 4, "sauvage")
_a(315, 59420825, 'Draconfus', 'Draaagin', 5, "sauvage")
_a(317, 59420826, 'Vipètesec', 'Copperled', 5, "sauvage")
_a(318, 59420827, 'Vipérâle', 'Cynake', 5, "sauvage")
_a(319, 59420828, 'Vipairflay', 'Slitheref', 7, "sauvage")

# Nombre de checks « sauvage / évolution / fusion » ci-dessus (ceux de toute graine d'avant la branche
# `ap/checks-amis-histoire-evenement`).
NB_AMIS_SAUVAGES = len(AMIS)

# ---------------------------------------------------------------------------
# Amis donnés par l'histoire, par une requête, ou liés à un objet d'évènement
# (docs/systemes/archipelago_yokai_evenement.md §6, archipelago_amis_criminels.md §8)
# ---------------------------------------------------------------------------
# Même détection (bit « ami » du Médaillium) : un don de script passe par la fenêtre « nouvel ami » (AddPartyEx,
# 3e argument à 1 -> 0x35B8 type 1 -> AddMemberMenu -> commande 0x3CB6 = FUN_004AAA98) [C scripts ; C états d'Azahar :
# bits 135, 107, 146, 69 et 170 posés dans l'ordre de l'histoire sur 11 états sauvegardés]. Ces espèces ne sont jamais
# des rencontres sauvages d'avant la fin : le mélange des Yo-kai ne touche ni les dons de script ni les combats
# « enc_day_* » (hors du tirage, raison « evenement »).
#
# « histoire » (7) : don AUTOMATIQUE d'un déclencheur de phase (cNN_trigger, fonction RunCmd_PhaseNN sans branche :
# AddPartyEx(espèce, 0, 1, niveau, 1, 0)), joué une seule fois (condition « évènement pas encore vu ET le précédent vu »),
# sur le chemin de l'histoire : ni hasard, ni horloge, non ratable [C]. Règle : celle de l'évènement « Chapitre N
# terminé » (N = `chapitre`, le chapitre du don), dans sa région. NON exclus.
#   Jibanyan c01 n° 38 ; Suinthan c02 n° 41 (après le boss) ; Baku c03 n° 6 ; Télémir c04 n° 37 ; Papilla c04 n° 48 ;
#   Triptic-tac c05 n° 8 ; Pleurapluie c07 n° 11.
# Dérivés (origines « evolution » / « fusion », EXCLUS comme les 34 autres) : Bakuku (Baku, niveau 29), Mme Papilla
# (Papilla + Pitou) : chapitre de la source + 1.
# « requete » (4) : don du script de la requête `quete`, dans la même fonction que la fin de la requête ou juste avant
# [C] : Timours (requête 89, t107g00_quest n° 6), Cigazouille (78, t102g00_quest n° 32), Misterre (52, t102i21_quest
# n° 3, à la victoire), Maître Oden (106, ev71_0620, sur le choix « oui », suivi de la fin de la requête). Règle et région
# = celles de la location « Requête : … » (calculées même sans l'option `quetes`) ; NON exclus (aucune de ces 4 requêtes
# n'est exclue). Le check double celui de la requête (même instant).
# « evenement » (19 n°, 18 locations) : Yo-kai d'un combat du jour « enc_day_* » dont le PNJ n'apparaît qu'avec l'objet
# `objet` (famille « evenement » d'objets.json, option `objets_evenement`). Amitié AU HASARD (ligne de taux 128 : 0,8 %
# par combat, 5,3 à 9,8 % avec l'aliment préféré) : EXCLUS. Règle : l'objet ET la règle de « Chapitre N terminé »
# (N = `chapitre`), dans la région `region` de la carte du combat. Location créée seulement si l'objet est dans le pool
# (options `amis` = tous ET `objets_evenement`). Ultramax : DEUX locations, « Ami : Ultramax N » (n° 431, 59420850) et
# « Ami : Ultramax K » (n° 432, 59420851), même objet et même règle : le jeu d'origine ne montre que celui du
# personnage joué (`GetPlayerVarID`), le patch montre les deux l'un après l'autre au même endroit (fonction étendue 32,
# docs/systemes/archipelago_ultramax_deux.md), exigée par la graine (FONCTION_DEUX_ULTRAMAX). Une graine générée avant
# (une location « Ultramax N / K », 59420850, pour les deux n°) garde ses deux entrées dans `slot_data.amis` : le
# client les lit toujours (`amis_paires`). Le champ `medailles` (plusieurs n° pour une location) n'est plus utilisé
# par aucune ligne ; il reste accepté.
# Identifiants : ceux réservés de l'ancien mod ou des checks retirés quand ils existent (Pleurapluie, Télémir,
# Triptic-tac, Suinthan, Baku, Bakuku, Papilla, Mme Papilla, Cigazouille) ; sinon nouveaux, à la suite (59420829…).
# Noms FR / EN : listes du Médaillium de l'ancien mod ; Ultramax N et K (Moximous N et K) saisis à la main.
_a(135, 59420829, 'Jibanyan', 'Jibanyan', 1, "histoire")
_a(107, 59420716, 'Suinthan', 'Swelton', 2, "histoire")
_a(146, 59420730, 'Baku', 'Baku', 3, "histoire")
_a(69, 59420695, 'Télémir', 'Mirapo', 4, "histoire")
_a(170, 59420739, 'Papilla', 'Tongus', 4, "histoire")
_a(70, 59420696, 'Triptic-tac', 'Miradox', 5, "histoire")
_a(40, 59420607, 'Pleurapluie', 'Brokenbrella', 7, "histoire")
_a(147, 59420731, 'Bakuku', 'Bakulia', 4, "evolution")
_a(171, 59420740, 'Mme Papilla', 'Nurse Tongus', 5, "fusion")
_a(66, 59420830, 'Maître Oden', 'Master Oden', 4, "requete", quete=106)
_a(119, 59420831, 'Misterre', 'Dromp', 8, "requete", quete=52)
_a(129, 59420627, 'Cigazouille', 'Singcada', 7, "requete", quete=78)
_a(154, 59420832, 'Timours', 'Harry Barry', 6, "requete", quete=89)
# Yo-kai d'évènement : (n°, identifiant, FR, EN, chapitre de règle, objet, région de la carte du combat)
# - école d'Ourcival (t131i03), Canyon de la cigale (t131d04), Ourcival (t131g00) : chapitre 4 (train dès 4-70) ;
# - 6 gares (t100s02/03 et t100s14/15 : lignes de Granval et d'Ourcival ; t100s10/11 : ligne de San Fantastico) :
#   chapitre 4, par le train (t100s10/11 : région san_fantastico, 5 chapitres depuis la 2.0.1 [S : prudent]) ;
# - école de Granval (t101i53 1er étage, t101i55 2e étage, t101i58 toit, t101i59 gymnase) : chapitre 3 (l'intérieur de
#   l'école s'ouvre pendant le chapitre 3, avec les Clés de l'école).
# Chapitres prudents [S : accès non essayé en jeu ; locations exclues : la règle ne sert qu'au tracker et à la
# promesse d'accessibilité d'Archipelago].
for _n, _id, _fr, _en, _ch, _objet, _region in (
        (335, 59420833, 'Melonyan', 'Melonyan', 4, "graines_de_melon", "ourcival"),
        (336, 59420834, 'Oranyan', 'Oranyan', 4, "graines_d_orange", "ourcival"),
        (337, 59420835, 'Kiwinyan', 'Kiwinyan', 4, "graines_de_kiwi", "ourcival"),
        (338, 59420836, 'Vigninyan', 'Grapenyan', 4, "graines_de_raisin", "ourcival"),
        (339, 59420837, 'Maranyan', 'Strawbnyan', 4, "graines_de_fraise", "ourcival"),
        (340, 59420838, 'Pastènyan', 'Watermelnyan', 4, "graines_de_pasteque", "ourcival"),
        (341, 59420839, 'Robocap', 'Robokapp', 4, "rouage_de_kappacap", "ourcival"),
        (342, 59420840, 'Robokoma', 'Robokoma', 4, "rouage_de_komasan", "ourcival"),
        (343, 59420841, 'Robopapéti', 'Robogramps', 4, "rouage_de_granpapeti", "ourcival"),
        (344, 59420842, 'Robocorniot', 'Robomutt', 4, "rouage_de_corniot", "san_fantastico"),
        (345, 59420843, 'Robonoko', 'Robonoko', 4, "rouage_de_noko", "ourcival"),
        (346, 59420844, 'Robodracou', 'Robodraggie', 4, "rouage_de_dracounet", "san_fantastico"),
        (347, 59420845, 'Boucanyan', 'Wondernyan', 4, "grelot_voyageur", "ourcival"),
        (348, 59420846, 'Robonyan F', 'Robonyan F', 3, "grelot_de_serie_f", "les_hauts_de_granval"),
        (349, 59420847, 'Sailornyan', 'Sailornyan', 3, "grelot_marin", "les_hauts_de_granval"),
        (350, 59420848, 'Maskonyan', 'Machonyan', 3, "grelot_masque", "les_hauts_de_granval"),
        (354, 59420849, 'Jetnyan', 'Jetnyan', 3, "grelot_aerien", "les_hauts_de_granval"),
        (431, 59420850, 'Ultramax N', 'Moximous N', 4, "marque_d_ultramax", "ourcival"),
        (432, 59420851, 'Ultramax K', 'Moximous K', 4, "marque_d_ultramax", "ourcival")):
    _a(_n, _id, _fr, _en, _ch, "evenement", objet=_objet, region=_region)

# ---------------------------------------------------------------------------
# Yo-kai d'évènement à leur EMPLACEMENT D'ORIGINE (branche `ap/invitations-evenement`,
# docs/systemes/archipelago_evenement_invitation.md §4 et §9 ; décision de l'humain, 2026-10-07)
# ---------------------------------------------------------------------------
# Quatre PNJ à combat du jour que le jeu d'origine ne montre qu'une fois le jeu fini (les deux premiers : seulement
# avec un transfert de sauvegarde d'un autre logiciel). Quand l'objet AP est reçu, le patch (fonction étendue 34,
# src/archipelago/pnj.cpp) neutralise ces clauses de la condition de LEUR apparition : le Yo-kai est à sa place du jeu
# d'origine, combat d'origine (niveau 80 ; Hovernyan 50), amitié au taux d'origine (clé 512 : 0,2 % par combat sans
# nourriture ; Hovernyan clé 256), combat répétable (fonction 25), il reste à sa place. `place` = bit k de
# ApPnj::ev_declares (AP_EV_* de boite.h), que le client pose quand l'objet `objet` est dans les objets reçus.
# - origine « place » (3) : Jibanyan S (Hauts de Granval, t101g00), Komasan S (bâtiment du Centre-ville, t104i27),
#   Komajiro S (Centre-ville, t104g00) : objet « Invitation : <nom> » (famille « invitation », aucun objet du jeu, PAS
#   d'objet d'inventaire : champ `inventaire` faux d'objets.json). Location créée avec l'option `invites`, hors de
#   l'option `amis` (comme les invités de l'Auberge), dans la liste `amis` de slot_data ;
# - Hovernyan (origine « evenement », comme les 19 autres) : objet « Capsule favorite », l'objet d'origine du jeu
#   (famille « evenement », donné par la file de dons : son dialogue de combat exige l'objet dans l'inventaire) ;
#   bâtiment du Vieil Ourcival (t231i01). Location créée avec `amis` = tous ET `objets_evenement`.
# Locations EXCLUES (amitié au hasard) ; règle = l'objet + « Chapitre N terminé » dans la région de la carte : 4 pour
# les trois S (Centre-ville ouvert pendant le chapitre 4 ; Jibanyan S sur la carte de départ : même chapitre, par
# prudence, combat de niveau 80), 6 pour Hovernyan [S : position des PNJ par rapport aux verrous de montre de leur
# carte non vue en jeu, essai T-EV1].
# PLACE LIBRE (correctif du 2026-10-09, fonction étendue 35, docs/systemes/archipelago_evenement_invitation.md §10 :
# Jibanyan S reçu au début du jeu se posait à 5 unités du Jibanyan de l'histoire, qu'on ne pouvait plus aborder) :
# - Jibanyan S n'apparaît que lorsque Jibanyan est déjà ami (demande de l'humain) ET que l'évènement ev01_2200 a été vu
#   (phase 1-130) : toujours vrai à « Chapitre 4 terminé », la règle ne change pas ;
# - Hovernyan n'apparaît qu'une fois le chapitre 6 fini (le Hovernyan de l'histoire est dans la même pièce aux
#   chapitres 5 et 6) : règle passée de « Chapitre 5 terminé » à « Chapitre 6 terminé » (location exclue : aucun
#   placement ne change, seul le tracker le montre plus tard) ;
# - Komasan S et Komajiro S : rien d'autre à leur point : dès l'objet reçu, comme avant.
# Aucune règle ne suppose leur présence avant ces moments (les quatre locations sont exclues et ne débloquent rien).
# Identifiants : 59420881..59420896 sont ceux des 16 des armées (ARMEES, plus bas : 59420881..59420891 pris, la
# suite réservée) ; objets 59429248..59429263 réservés à leur extension « invités » (INVITES_EXTENSION_ARMEES).
for _n, _id, _fr, _en, _ch, _objet, _region, _place in (
        (433, 59420897, 'Jibanyan S', 'Jibanyan S', 4, "invitation_jibanyan_s", "les_hauts_de_granval", 0),
        (434, 59420898, 'Komasan S', 'Komasan S', 4, "invitation_komasan_s", "centre_ville_de_granval", 1),
        (435, 59420899, 'Komajiro S', 'Komajiro S', 4, "invitation_komajiro_s", "centre_ville_de_granval", 2)):
    _a(_n, _id, _fr, _en, _ch, "place", objet=_objet, region=_region, place=_place)
_a(351, 59420900, 'Hovernyan', 'Hovernyan', 6, "evenement", objet="capsule_favorite", region="vieil_ourcival", place=3)
# Objet AP -> bit de ApPnj::ev_declares (slot_data `evenement_places`), pour tout objet de cette table présent dans
# le pool (même sans la location : l'objet reçu fait toujours apparaître le Yo-kai).
PLACES_PAR_OBJET: Dict[str, int] = {a["objet"]: a["place"] for a in AMIS if "place" in a}
# Fonction étendue du patch « Yo-kai d'évènement à leur place » (bit 2 de ApPnj::fonctions) et n° JAMAIS publié qui
# l'accompagne : un client d'avant, qui ne sait pas publier les objets reçus au jeu, tient tout n° >= 63 pour absent
# et refuse donc la graine, même avec le patch à jour (un client à jour retire le 63).
FONCTION_EVENEMENT_PLACE = 34
FONCTION_CLIENT_2 = 63
# V3 (lot 1) : verrous ÉTENDUS (k >= 40) et détection par phase de quête (`phase_min`) : un client d'avant ignore en
# silence un verrou de k >= 24 ; la graine porte ce n° jamais publié (et le 22) : il la refuse. 64 = FONCTION_CLIENT_3
# (slot_data.py). Numéro suivant libre pour une autre lecture / écriture nouvelle du client : 66.
FONCTION_CLIENT_4 = 65
# Version corrigée de la fonction 34 (apparition seulement place libre, bit 3 de ApPnj::fonctions) : exigée par toute
# graine générée depuis le correctif, pour qu'un patch d'avant (histoire bloquée au chapitre 1 par Jibanyan S) soit
# refusé. Les clients publiés vérifient déjà tout n° >= 32 dans ApPnj::fonctions : rien à changer chez eux.
FONCTION_EVENEMENT_LIBRE = 35
# (Le lanceur dit le moment d'apparition sur la ligne du check : `lanceur/checks.py`, APPARITION.)


AMIS_PAR_MEDAILLE: Dict[int, dict] = {n: a for a in AMIS for n in a.get("medailles", (a["medaille"],))}
AMIS_PAR_ORIGINE: Dict[str, List[dict]] = {o: [a for a in AMIS if a["origine"] == o] for o in ORIGINES_AMIS}
# Fonctions du patch (bits de ApVerrous::compiles, src/archipelago/verrous.h) exigées par slot_data `fonctions_exigees`
# quand la graine a des amis d'évènement : combats d'évènement libres (25 : sans elle, un essai par jour réel) et, pour
# les trois grelots d'eShop, bit de réception posé à la réception AP (26 : sans elle, le PNJ refuse le combat).
FONCTION_COMBATS_LIBRES = 25
FONCTION_GRELOTS_ESHOP = 26
# Fonctions ÉTENDUES du patch (n° >= 32 : bits de ApPnj::fonctions, src/archipelago/verrous.h). Une graine qui en exige
# une ajoute aussi FONCTION_ETENDUES (22) à `fonctions_exigees` : ce n° n'est JAMAIS publié par le jeu, si bien qu'un
# client d'avant les fonctions étendues (qui ignore les n° >= 31) refuse la graine (« Verrous incompatibles ») au
# lieu de laisser une location que le jeu ne rendrait jamais faisable ; un client à jour retire le 22 et vérifie
# chaque n° >= 32 dans le jeu.
FONCTION_ETENDUES = 22
FONCTION_DEUX_ULTRAMAX = 32          # Ultramax N et K dans la même partie : exigée par la location « Ami : Ultramax K »
FONCTION_INVITES_ESPECE = 33         # invités de l'Auberge à leur espèce : exigée par un invité à invitation
MEDAILLE_ULTRAMAX_K = 432
OBJETS_GRELOTS_ESHOP = ("grelot_de_serie_f", "grelot_marin", "grelot_masque")

# ---------------------------------------------------------------------------
# Invités de l'Auberge des voyageurs (branche `ap/pandanoko`, docs/systemes/archipelago_invites.md §14)
# ---------------------------------------------------------------------------
# Yo-kai qui APPARAÎT dans la Suite de l'Auberge des voyageurs (Coteau fleuri, carte t103i69) quand son déclencheur
# est rempli, annoncé par une fenêtre du jeu, combattu au niveau du plus haut Yo-kai de l'équipe, ami au hasard
# (taux d'amitié du jeu, combat en boucle : il revient tant qu'il n'est pas ami). Check « Ami : <Yo-kai> » = bit « ami » du Médaillium, comme les autres amis,
# mais location de genre « invite », HORS de la table AMIS et de l'option `amis` (décision de l'humain, 2026-10-05).
# Pandanoko (n° 287, identifiant réservé de l'ancien mod) : déclencheur « requetes » = toutes les locations de genre
# « requete » de la graine sont cochées (critère du client) ; créé seulement si l'option `quetes` n'est pas « aucune ».
# `param` = hachage CHARA_PARAM de l'espèce (identifiant numérique, règle 6), écrit par le client dans la liste des
# invités du jeu. EXCLU (amitié au hasard) : sa règle dépend de TOUTES les requêtes, dont deux ne sont pas modélisables (n° 8 : coût en
# globes du donjon des portails ; n° 80 : Yo-kai du Tablo-blabla n° 8) et dont les services se rejouent ; règle
# (tracker, accessibilité) : conjonction des règles de ces requêtes, dans la région du Coteau fleuri.
INVITES: List[dict] = [
    {"medaille": 287, "id_ap": 59420652, "yokai_fr": "Pandanoko", "yokai_en": "Pandanoko",
     "nom_fr": "Ami : Pandanoko", "nom_en": "Friend: Pandanoko", "chapitre": 3, "declencheur": "requetes",
     "param": 0xDB1CC069, "region": "coteau_fleuri"},
]
# Les 30 invités à INVITATION (branche `ap/invites-ultramax`, archipelago_invites.md §15 ; option `invites`, activée
# par défaut) : Yo-kai d'avant la fin du jeu sans voie garantie dans une partie normale (pièces de Crank-a-kai, choix
# exclusif du Quartier des boutiques, régionaux et leurs fusions à objet de mot de passe). Déclencheur « objet » : le
# client déclare l'invité au jeu quand l'objet Archipelago « Invitation : <nom> » (objets.json, famille « invitation »,
# aucun objet du jeu) est reçu ; le Yo-kai vient alors à l'Auberge des voyageurs (la Suite d'abord, puis les chambres
# 101 à 109 ; au-delà de dix présents, les suivants attendent), à SON espèce (fonction étendue 33 du patch), combattu
# au niveau du plus haut Yo-kai de l'équipe, ami au taux du jeu, autant de combats qu'il faut. Check « Ami : <nom> »
# EXCLU (amitié au hasard) ; règle (tracker, accessibilité) : l'invitation + la règle de « Chapitre 3 terminé » dans la
# région du Coteau fleuri (l'Auberge y est, ouverte à partir de 3-70 : même base que Pandanoko). L'objet cité devient
# « progression sans équilibrage » (même raison que les objets d'évènement : logique.construire_plan).
# (n° du Médaillium, identifiant AP de la location, FR, EN, CHARA_PARAM, clé de l'objet d'invitation) ; n°, hachages
# et recrutabilité (clé de taux non nulle) vérifiés sur la ROM ; noms FR / EN : listes du Médaillium de l'ancien mod.
# Identifiants : Noko reprend celui réservé de l'ancien mod (59420650, sorti de AMIS_ANCIENS_NON_CREES) ; les 29
# autres sont nouveaux, à la suite (59420852..59420880).
# L'ordre de cette table est l'ordre de la file (après Pandanoko).
for _n, _id, _fr, _en, _param, _objet in (
    (138, 59420852, 'Buchinyan', 'Buchinyan', 0x6BB26576, 'invitation_buchinyan'),
    (142, 59420853, 'Komasan', 'Komasan', 0x74A70DA9, 'invitation_komasan'),
    (285, 59420650, 'Noko', 'Noko', 0xC207F128, 'invitation_noko'),
    (59, 59420854, 'Trodésolé', 'So-Sorree', 0x8585E90F, 'invitation_trodesole'),
    (68, 59420855, 'Apélicain', 'Apelican', 0xC1BBADFD, 'invitation_apelicain'),
    (233, 59420856, 'Dracunyan', 'Dracunyan', 0x8C876C58, 'invitation_dracunyan'),
    (228, 59420857, 'Raltesse', 'Tyrat', 0x7907CA98, 'invitation_raltesse'),
    (259, 59420858, 'Corniot', 'Manjimutt', 0x33077779, 'invitation_corniot'),
    (95, 59420859, 'Loubarbare', 'Roughraff', 0x8C37C918, 'invitation_loubarbare'),
    (53, 59420860, 'Toutouïe', 'Tattletell', 0x8C516E01, 'invitation_toutouie'),
    (136, 59420861, 'Épinyan', 'Thornyan', 0x1B1AEDCD, 'invitation_epinyan'),
    (137, 59420862, 'Bandinyan', 'Baddinyan', 0x86CDD574, 'invitation_bandinyan'),
    (370, 59420863, 'Mélobê', 'Grumpus Khan', 0xAFAA492B, 'invitation_melobe'),
    (372, 59420864, 'Bon-huiii', 'Slumberhog', 0x05A381A0, 'invitation_bon_huiii'),
    (374, 59420865, 'Petit panja', 'Panja Pupil', 0x20C8DE7C, 'invitation_petit_panja'),
    (376, 59420866, 'Samuren', 'Samureel', 0x8AC116F7, 'invitation_samuren'),
    (378, 59420867, 'Poulpatouch', 'Takoyakid', 0x6A1E61C4, 'invitation_poulpatouch'),
    (380, 59420868, 'Avallée', 'Danke Sand', 0x92CA609B, 'invitation_avallee'),
    (382, 59420869, 'Sumodon', 'Sumodon', 0x38C3A810, 'invitation_sumodon'),
    (384, 59420870, 'Pfffuji', 'Whateverest', 0x1DA8F7CC, 'invitation_pfffuji'),
    (386, 59420871, 'Lacanne', 'Happycane', 0xB7A13F47, 'invitation_lacanne'),
    (371, 59420872, 'Geigneau', 'Groupus Khan', 0xBD1FE6C5, 'invitation_geigneau'),
    (373, 59420873, 'Verrascible', 'Snortlehog', 0x9874B919, 'invitation_verrascible'),
    (375, 59420874, 'Panja-san', 'Panja Pro', 0x327D7192, 'invitation_panja_san'),
    (377, 59420875, 'Barrakéda', 'Time Keeler', 0xD2A206A1, 'invitation_barrakeda'),
    (379, 59420876, 'Poulpater', 'Takoyaking', 0x2A7607FE, 'invitation_poulpater'),
    (381, 59420877, 'Mont merci', 'No Sandkyu', 0x807FCF75, 'invitation_mont_merci'),
    (383, 59420878, 'Soupotori', 'Yokozudon', 0xA51490A9, 'invitation_soupotori'),
    (385, 59420879, 'Krakatouaaah', 'Whatuption', 0x0F1D5822, 'invitation_krakatouaaah'),
    (387, 59420880, 'Canastelle', 'Starrycane', 0xEFC22F11, 'invitation_canastelle'),
):
    INVITES.append({"medaille": _n, "id_ap": _id, "yokai_fr": _fr, "yokai_en": _en, "nom_fr": "Ami : " + _fr,
                    "nom_en": "Friend: " + _en, "chapitre": 3, "declencheur": "objet", "param": _param,
                    "region": "coteau_fleuri", "objet": _objet})
INVITES_PAR_MEDAILLE: Dict[int, dict] = {a["medaille"]: a for a in INVITES}
# ---------------------------------------------------------------------------
# Évolutions par niveau des invités de l'Auberge (branche `ap/invitations-evenement`, lot 3 ;
# docs/systemes/archipelago_amis_criminels.md §9 ; décision de l'humain, 2026-10-07 : un check « Ami » pour TOUTES les
# évolutions obtenables avant la fin)
# ---------------------------------------------------------------------------
# Recensement sur la ROM [C] : CHARA_EVOLVE_INFO a 39 lignes = 33 évolutions par niveau distinctes (6 lignes en double
# pour des variantes de la même espèce). 25 avaient déjà leur check (24 d'une espèce sauvage, Bakuku de Baku) ; 2 ont
# leur source ET leur cible parmi les 16 des armées (Parantonn, Scolérique : sans check, comme leur source, voir
# INVITES_EXTENSION_ARMEES) ; les 6 autres sont l'évolution d'un invité de l'Auberge : ci-dessous. Aucun ami d'histoire
# (hors Baku), de requête, d'évènement, ni Ultramax, ni Yo-kai à emplacement d'origine n'a d'évolution par niveau.
# Check = bit « ami » du Médaillium de l'espèce évoluée, comme les 25 autres. EXCLUS (il faut d'abord l'amitié de la
# base, au hasard, puis le niveau : aucune contrainte de niveau dans la logique). Règle = celle de la base (son
# invitation, région de l'Auberge) un chapitre plus tard (convention des dérivés : chapitre de la source + 1). Créés
# avec `amis` = tous ET `invites` (la base est un invité à invitation). `base_invite` = n° du Médaillium de la base.
# (n° du Médaillium, identifiant AP, FR, EN, n° de la base, niveau d'évolution dans le jeu : information seulement)
# Identifiants : Nénunoko reprend celui réservé de l'ancien mod (59420651, sorti de AMIS_ANCIENS_NON_CREES) ; les 5
# autres sont nouveaux, à la suite (59420901..59420905). Noms FR / EN : listes du Médaillium de l'ancien mod.
EVOLUTIONS_INVITES = (
    (54, 59420901, 'Babalance', 'Tattlecast', 53, 22),         # Toutouïe
    (60, 59420902, 'Pardomino', 'Bowminos', 59, 30),           # Trodésolé
    (96, 59420903, 'Racaïd', 'Badude', 95, 25),                # Loubarbare
    (143, 59420904, 'Komaous', 'Komane', 142, 25),             # Komasan
    (260, 59420905, 'Bicorniot', 'Multimutt', 259, 22),        # Corniot
    (286, 59420651, 'Nénunoko', 'Bloominoko', 285, 25),        # Noko
)
for _n, _id, _fr, _en, _base, _niveau in EVOLUTIONS_INVITES:
    _a(_n, _id, _fr, _en, INVITES_PAR_MEDAILLE[_base]["chapitre"] + 1, "evolution", base_invite=_base,
       region=INVITES_PAR_MEDAILLE[_base]["region"])
AMIS_PAR_MEDAILLE.update({a["medaille"]: a for a in AMIS if "base_invite" in a})
AMIS_PAR_ORIGINE["evolution"] = [a for a in AMIS if a["origine"] == "evolution"]
# ---------------------------------------------------------------------------
# Fusions Yo-kai + OBJET (branche `ap/checks-fusions-armees`, lot A ; docs/systemes/archipelago_amis_criminels.md §10 ;
# décision de l'humain, 2026-10-07)
# ---------------------------------------------------------------------------
# Recensement sur la ROM [C, `outils/amis_candidats.py --fusions`] : COMBINE_INFO a 33 résultats de fusion Yo-kai +
# objet sans check (les 9 fusions régionales sont des invités de l'Auberge). Un check n'est créé que si la BASE a déjà
# son check (obtenable avant la fin) ET si l'OBJET a une source GARANTIE avant la fin : ni tirage (Crank-a-kai,
# loterie, tickets à gratter, butin, récompense du jeu musical), ni choix exclusif, ni attente en jours réels, et que
# le mélange du mod ne retire pas (une récompense de requête est remplacée par l'objet Archipelago, un coffre aussi ;
# un don de script, la boutique d'échange à points et le 2e achat d'un article de boutique ne le sont pas). 5 sur 33 :
# - Choubidou, Babarouf, Ed Mémoire : objet vendu sans condition par la boutique d'échange à points des Hauts de
#   Granval (fichier de type T, carte de la boutique N019 : hors du mélange des boutiques, stock illimité) ;
# - Zerberker : objet vendu par la boutique N016 du Quartier des boutiques à partir de la phase 6-10 (article de tag
#   « ch6 » ; avec l'option `boutiques` le 1er achat est le check, l'article redevient l'objet d'origine ensuite) ;
#   ses deux coffres sont des locations du mod (contenu remplacé) : ils ne comptent pas ;
# - Tendino : objet donné par le script de la requête 4 juste avant sa fin (don de script : gardé quelle que soit
#   l'option `quetes`) ; `quete` = 4 : la règle de la requête s'ajoute.
# Les 28 autres sont écartés (raison par Yo-kai : §10.3 du document).
# Check = bit « ami » du Médaillium du résultat (la fusion passe par l'enregistrement d'obtention, comme les fusions
# Yo-kai + Yo-kai [S fort]). EXCLUS (amitié de la base au hasard). Règle = celle de « Chapitre N terminé », N =
# max(chapitre de la base + 1, chapitre de la source de l'objet), dans la région de la source (son accès s'ajoute par
# la connexion), avec la règle de la requête pour Tendino. Créés avec l'option `amis` = tous. `base` = n° de la base.
# (n° du Médaillium, identifiant AP, FR, EN, n° de la base, chapitre de la source de l'objet, région de la source,
#  requête de la source ou None)
# Identifiants : Tendino reprend celui réservé de l'ancien mod (59420638, sorti de AMIS_ANCIENS_NON_CREES) ; les 4
# autres sont nouveaux, à la suite (59420906..59420909). Noms FR / EN : listes du Médaillium de l'ancien mod.
FUSIONS_OBJET = (
    (12, 59420906, 'Zerberker', 'Zerberker', 11, 6, "quartier_des_boutiques", None),      # Trépigno
    (152, 59420907, 'Choubidou', 'Pinkipoo', 151, 2, "les_hauts_de_granval", None),       # Pitou
    (205, 59420638, 'Tendino', 'Payn', 204, 3, "coteau_fleuri", 4),                       # Tortico
    (255, 59420908, 'Babarouf', 'Rawry', 254, 2, "les_hauts_de_granval", None),           # Zikafon
    (297, 59420909, 'Ed Mémoire', 'Vacuumory', 296, 2, "les_hauts_de_granval", None),     # Yvantouse
)
CHAPITRE_AMI_MAX = 8                         # jamais une règle du chapitre 10 bouclé (I8 de l'audit)
for _n, _id, _fr, _en, _base, _ch, _region, _quete in FUSIONS_OBJET:
    _plus = {"quete": _quete} if _quete is not None else {}
    _a(_n, _id, _fr, _en, min(CHAPITRE_AMI_MAX, max(AMIS_PAR_MEDAILLE[_base]["chapitre"] + 1, _ch)), "fusion_objet",
       base=_base, region=_region, **_plus)
AMIS_PAR_MEDAILLE.update({a["medaille"]: a for a in AMIS if a["origine"] == "fusion_objet"})
AMIS_PAR_ORIGINE["fusion_objet"] = [a for a in AMIS if a["origine"] == "fusion_objet"]
INVITES_PAR_DEFAUT = True                   # option `invites` (les 30 invitations ; Pandanoko n'en dépend pas)
NB_INVITATIONS = sum(1 for a in INVITES if a["declencheur"] == "objet")
# Le jeu loge au plus AP_CAP_INVITES (32) invités déclarables (src/archipelago/boite.h) : Pandanoko + 30.
CAP_INVITES_JEU = 32
# EXTENSION PRÉVUE, NON ACTIVÉE (décision à prendre : « 16 des armées quand le mélange des Yo-kai est désactivé ») :
# les 16 Yo-kai des armées du chapitre 8 et leurs proches, tous recrutables [C], que le mélange des Yo-kai (version 4)
# met dans la nature ; sans mélange, aucune voie. Même code du jeu et du client (16 entrées de plus dans cette
# table, déclencheur « objet »). Ce qu'il faudra pour l'activer : (1) porter AP_CAP_INVITES à 64 (masques `forcer` et
# `annoncees` de ApInvites sur 64 bits, liste prolongée : la zone a la place jusqu'à 0x23E00) ; (2) identifiants à la
# suite (locations à partir de 59420881, sauf les identifiants réservés de l'ancien mod à reprendre : 59420618
# Jalouseriz, 59420619 Fanfanfaron, 59420620 Égare-dare, 59420640 Couchtar, 59420641 Noctambill ; objets
# 59429248..59429263) ; (3) condition de création : option `invites` ET
# `rando_yokai` = aucun (sinon ces espèces ont déjà des lieux). Rien de cette table n'est dans le paquet de données.
# Les LOCATIONS « Ami : <nom> » de ces 16 existent depuis la branche `ap/checks-fusions-armees` (table ARMEES, plus
# bas, graines à mélange par rencontre) : l'extension devra reprendre les mêmes identifiants de location.
# (n° du Médaillium, FR, EN, CHARA_PARAM ; Mythovni et Comte Zapzap ont un second CHARA_PARAM à clé nulle : pas celui-là)
INVITES_EXTENSION_ARMEES = (
    (50, 'Ovide', 'Faysoff', 0x554C72E4),
    (67, 'Mythovni', 'Failian', 0x2F8C2184),
    (88, 'Jalouseriz', 'Wotchagot', 0xB8E5C0BF),
    (89, 'Fanfanfaron', 'Pride Shrimp', 0xC89B4A5D),
    (90, 'Égare-dare', 'No-Go Kart', 0x4A8F1862),
    (91, 'Charivari', 'Mistank', 0x70272D38),
    (105, 'Antonnerre', 'Zappary', 0x12EC0834),
    (106, 'Parantonn', 'Frazzel', 0x47F9DD0A),
    (134, 'Yokœil', 'Boyclops', 0x0D2F62B2),
    (207, 'Couchtar', 'Wydeawake', 0xE0C21507),
    (208, 'Noctambill', 'Allnyta', 0x343B0B3D),
    (209, 'Herbert', 'Herbiboy', 0xC5A94ADB),
    (210, 'Carnanova', 'Carniboy', 0xDA2EE5B3),
    (227, 'Comte Zapzap', 'Count Zapaway', 0xD71CE535),
    (298, 'Scoltine', 'Irewig', 0xF6473F38),
    (299, 'Scolérique', 'Firewig', 0x7925A86F),
)
# ---------------------------------------------------------------------------
# Les 16 Yo-kai « des armées » (branche `ap/checks-fusions-armees`, lot B ; docs/systemes/archipelago_amis_criminels.md
# §11 ; décision de l'humain, 2026-10-07)
# ---------------------------------------------------------------------------
# Aucune voie dans une partie normale (combats scénarisés sous la règle « pas d'amitié ») : seul le mélange des Yo-kai
# (version 4, archipelago_rando_yokai.md §22) les met dans la nature. Le check n'EXISTE que dans les graines où
# l'APWorld peut le garantir (`armees_garanties`) : mélange PAR RENCONTRE (`par_rencontre_rang`, `par_rencontre_total`)
# de version >= 4, où chacune des 16 reçoit au moins un lieu NORMAL (hors portail mystère, qui sort, d'avant la fin)
# quelle que soit la graine [C : le client couvre les espèces par un couplage MAXIMUM entre espèces à couvrir et unités
# normales qui les acceptent ; ce graphe ne dépend que de la ROM et du mode, pas de la graine ; sur la ROM européenne
# il sature les 42 espèces à couvrir, donc tout couplage maximum les couvre toutes : test_amis_armees.py]. Modes par
# espèce (`par_rang`, `total` : 6 à 7 sur 16 seulement, et l'APWorld ne sait pas lesquelles) et sans mélange : PAS de
# check. Parantonn et Scolérique sont aussi les évolutions d'Antonnerre et de Scoltine ; Fanfanfaron, Charivari,
# Noctambill et Carnanova aussi des fusions Yo-kai + Yo-kai : un seul check chacun (le bit « ami » de l'espèce), par
# l'une ou l'autre voie. EXCLUS (amitié au hasard, lieu inconnu de l'APWorld : parfois un seul). Règle prudente : celle
# de « Chapitre 9 terminé » (8 chapitres terminés : tout lieu d'avant la fin est ouvert pendant le chapitre 9 [S] ;
# jamais le chapitre 10 bouclé), sans région. Créés avec l'option `amis` = tous.
# Identifiants : ceux réservés de l'ancien mod quand ils existent (Jalouseriz, Fanfanfaron, Égare-dare, Couchtar,
# Noctambill, sortis de AMIS_ANCIENS_NON_CREES), sinon la plage réservée à ces 16 (59420881..59420891 ; 59420892 à
# 59420896 restent réservés). Noms FR / EN : ceux de INVITES_EXTENSION_ARMEES (listes du Médaillium de l'ancien mod).
MODES_RANDO_ARMEES = ("par_rencontre_rang", "par_rencontre_total")
VERSION_MELANGE_ARMEES = 4
CHAPITRE_ARMEES = 9
ID_ARMEES = {50: 59420881, 67: 59420882, 88: 59420618, 89: 59420619, 90: 59420620, 91: 59420883, 105: 59420884,
             106: 59420885, 134: 59420886, 207: 59420640, 208: 59420641, 209: 59420887, 210: 59420888, 227: 59420889,
             298: 59420890, 299: 59420891}
for _n, _fr, _en, _param in INVITES_EXTENSION_ARMEES:
    _a(_n, ID_ARMEES[_n], _fr, _en, CHAPITRE_ARMEES, "armee")
AMIS_PAR_MEDAILLE.update({a["medaille"]: a for a in AMIS if a["origine"] == "armee"})
AMIS_PAR_ORIGINE["armee"] = [a for a in AMIS if a["origine"] == "armee"]


def armees_garanties(mode_rando_yokai, version_melange: int) -> bool:
    """Vrai si une graine de ce mode de mélange des Yo-kai (nom sans suffixe de version : « aucun », « par_rang »…) et
    de cette version garantit un lieu normal aux 16 des armées : seule condition d'existence de leurs checks."""
    return mode_rando_yokai in MODES_RANDO_ARMEES and int(version_melange) >= VERSION_MELANGE_ARMEES


# N° de `fonctions_exigees` (slot_data) qui désigne les invités : JAMAIS publié dans ApVerrous::compiles (bit 23
# réservé, src/archipelago/verrous.h AP_FONCTION_INVITES) : un client d'avant les invités refuse la graine (« Verrous
# incompatibles »), un client à jour le vérifie dans la zone des invités du jeu (ApInvites::compile).
FONCTION_INVITES = 23
# ---------------------------------------------------------------------------
# V3, lots 14 et 20 : les 16 Yo-kai de Pièce 5 étoiles, ordre de réception des invitations, armées à l'Auberge
# (docs/systemes/archipelago_v3_invites_5_etoiles.md, archipelago_v3_pieces_speciales.md §13)
# ---------------------------------------------------------------------------
# Les 16 Yo-kai de Pièce 5 étoiles (8 du présent, 8 du passé : tirage à 4 % au Crank-a-kai, 13 aussi au Tunnel sans
# fin). Lot 14 : ils étaient des invités de l'Auberge (option `invites_5_etoiles`). Lot 20 (décision de l'humain du
# 2026-10-13, aucune graine de la V3 n'étant publiée) : cette option est RETIRÉE, ils ne sont JAMAIS des invités ;
# avec l'option `pieces_speciales` (pieces.py), 16 Pièces 5 étoiles sont au pool et leurs locations « Ami » (mêmes
# identifiants) ont la règle « k pièces » ; sans elle, ces 16 locations n'existent pas. Le taux d'amitié relevé de
# l'Auberge (ligne 5, clé `taux` de slot_data) est abandonné : tout invité est au taux du jeu.
# Cette table reste une table de DONNÉES : (n° du Médaillium, identifiant AP de la location, FR, EN, CHARA_PARAM) ;
# n°, hachages et noms anglais relus sur la ROM européenne (archive `engb`) ; aucun n'a d'évolution par niveau.
# Identifiants : locations 59420925..59420940. Les 16 objets « Invitation : <nom> » du lot 14 (59429268..59429283)
# n'existent plus : identifiants RÉSERVÉS, jamais réutilisés (`OBJETS_RETIRES`, `identifiants_reserves` d'objets.json).
AMIS_5_ETOILES: List[dict] = []
for _n, _id, _fr, _en, _param in (
    (37, 59420925, 'Scarnage', 'Cruncha', 0xD2EA2590),
    (81, 59420926, 'Barakabo', 'Frostail', 0x10961195),
    (118, 59420927, 'Oronyan', 'Goldenyan', 0x276A8350),
    (157, 59420928, 'Damona', 'Damona', 0x8D41292C),
    (199, 59420929, 'Tata Câlin', 'Auntie Heart', 0xE824B7D3),
    (238, 59420930, 'Dente', 'Count Cavity', 0x23C8C136),
    (279, 59420931, 'Éterna', 'Eterna', 0xC7F1318D),
    (321, 59420932, 'Octorgombre', 'Shad. Venoct', 0x9CBCBAB9),
    (39, 59420933, 'Vampéric', 'Devourer', 0x0149E0F7),
    (83, 59420934, 'Chyper', 'Kingmera', 0x8495AE22),
    (122, 59420935, 'Geeko', 'Uber Geeko', 0xF4EB24C0),
    (159, 59420936, 'Kappadissi', 'Tigappa', 0x6382C5FB),
    (201, 59420937, 'Kyrycorne', 'Unikirin', 0x53D0ECCD),
    (240, 59420938, 'Précyeux', 'Eyellure', 0x7B89B397),
    (283, 59420939, 'Arachnia', 'Arachnia', 0xBA49DB47),
    (305, 59420940, 'Sireine-mère', 'Mermother', 0x728B36C0),
):
    AMIS_5_ETOILES.append({"medaille": _n, "id_ap": _id, "yokai_fr": _fr, "yokai_en": _en,
                           "nom_fr": "Ami : " + _fr, "nom_en": "Friend: " + _en, "param": _param,
                           "region": "mont_sylvestre"})
AMIS_5_ETOILES_PAR_MEDAILLE: Dict[int, dict] = {a["medaille"]: a for a in AMIS_5_ETOILES}
# V3, lot 21 : Bananar (n° 314), Yo-kai de la Pièce bleu ciel du Crank-a-kai du passé (3 % dans le jeu d'origine) :
# location « Ami » avec l'option `pieces_speciales` (une Pièce bleu ciel au pool, tirage dirigé : pieces.py). Jamais
# un invité. Noms relus sur la ROM européenne (archives `fr` et `engb`) ; identifiant à la suite des amis de la Voie.
AMI_BANANAR: dict = {"medaille": 314, "id_ap": 59420948, "yokai_fr": "Bananar", "yokai_en": "Bananose",
                     "nom_fr": "Ami : Bananar", "nom_en": "Friend: Bananose", "param": 0x1EA8E886,
                     "region": "mont_sylvestre"}
# Identifiants AP d'objets retirés (jamais réutilisés) : les 16 « Invitation : <Yo-kai de Pièce 5 étoiles> » du lot 14
OBJETS_RETIRES = range(59429268, 59429284)
# Les 16 des armées à l'Auberge (décision (c) : TOUJOURS avec l'objectif « medaillium_complet », lot 18), derrière le
# paramètre interne `invites_armees` de `logique.construire_plan` (aucune option ne le pose).
# Mêmes locations que les checks des armées (ID_ARMEES : une seule location par Yo-kai, de genre « invite » au lieu
# d'« ami » quand le paramètre est posé), objets 59429248..59429263 (réservés depuis `ap/invites-ultramax`), taux du
# jeu (clé 16 à 256). Sans objet d'inventaire (`inventaire` faux d'objets.json : le sac ordinaire n'a pas la place
# pour 32 invitations).
INVITES_ARMEES: List[dict] = []
for (_n, _fr, _en, _param), _cle in zip(INVITES_EXTENSION_ARMEES, (
        'ovide', 'mythovni', 'jalouseriz', 'fanfanfaron', 'egare_dare', 'charivari', 'antonnerre', 'parantonn',
        'yokoeil', 'couchtar', 'noctambill', 'herbert', 'carnanova', 'comte_zapzap', 'scoltine', 'scolerique')):
    INVITES_ARMEES.append({"medaille": _n, "id_ap": ID_ARMEES[_n], "yokai_fr": _fr, "yokai_en": _en,
                           "nom_fr": "Ami : " + _fr, "nom_en": "Friend: " + _en, "chapitre": 3,
                           "declencheur": "objet", "param": _param, "region": "coteau_fleuri",
                           "objet": "invitation_" + _cle, "groupe": "armees"})
# Tous les invités que l'APWorld connaît, dans l'ordre de `slot_data.invites` : la table de la V2 (rangs inchangés),
# puis les 16 des armées. 47 <= CAP_INVITES_V3 (plus de 32 : liste à 64 du jeu, fonction 38, n° « client » 70).
INVITES_TOUS: List[dict] = INVITES + INVITES_ARMEES
INVITES_TOUS_PAR_MEDAILLE: Dict[int, dict] = {a["medaille"]: a for a in INVITES_TOUS}
CAP_INVITES_V3 = 64
FONCTION_INVITES_V3 = 38             # fonction étendue du patch : liste à 64 (le taux relevé par invité n'est plus utilisé)
FONCTION_CLIENT_9 = 70               # n° « client » jamais publié : le client sait écrire ApInvites2
# ORDRE D'ARRIVÉE à l'Auberge (décision (b) de l'humain) : `slot_data.invites_ordre` = "reception" : les invités à
# invitation entrent dans la liste du jeu dans l'ordre de RÉCEPTION de leurs invitations (la première reçue = le
# premier logé) et non dans l'ordre de `slot_data.invites`. Clé absente (toute graine de la V2) : ordre de la liste.
ORDRE_INVITES_LISTE, ORDRE_INVITES_RECEPTION = "liste", "reception"
# « Amitié : X » de l'ancien mod dont l'espèce n'est pas retenue (identifiants réservés, jamais des locations) : vues
# seulement hors des rencontres sauvages (spots, tournois, histoire), non recrutables ou Kaima d'histoire.
AMIS_ANCIENS_NON_CREES: Dict[int, str] = {
    59420656: "Injustin", 59420657: "Fielippine", 59420658: "Cyrustre", 59420659: "Maudicko",
    59420660: "Ronéan", 59420661: "Gale de bain", 59420662: "Mabouhl"}

# Retirés (branche `ap/amis-avant-fin`, demande de l'humain 2026-09-29 : tous les checks faisables AVANT l'après-jeu) :
# espèces qu'on ne trouve en sauvage qu'après la fin ou dans le réseau caché (règle commune des randomizers,
# `rencontres.lieu_hors_avant_fin`, archipelago_rando_yokai.md §3.7), et leurs évolutions / fusions sans autre source.
# Identifiants réservés, jamais des locations ni réutilisés : {identifiant AP: nom FR}.
# (Pandanoko, 59420652, et Noko, 59420650, sont sortis de AMIS_ANCIENS_NON_CREES : invités de l'Auberge des voyageurs,
# table INVITES ; Nénunoko, 59420651, aussi : évolution de Noko, table EVOLUTIONS_INVITES.)
# (Pleurapluie, Télémir, Triptic-tac, Suinthan, Baku, Bakuku, Papilla et Mme Papilla en sont sortis : recréés comme amis
# d'histoire et dérivés, avec le même identifiant ; Cigazouille est sorti de AMIS_ANCIENS_NON_CREES : ami de requête.)
# (Tendino, 59420638, est sorti de AMIS_ANCIENS_NON_CREES : fusion avec objet, table FUSIONS_OBJET ; Jalouseriz,
# Fanfanfaron, Égare-dare, Couchtar et Noctambill aussi : les 16 des armées, table ARMEES.)
AMIS_RETIRES_AVANT_FIN: Dict[int, str] = {
    59420690: 'Donjouant', 59420704: 'Tengu', 59420705: 'Chymère', 59420736: 'Satandre', 59420765: 'Kyryn',
    59420785: 'Nimpégase', 59420786: 'Timidémon', 59420787: 'Vénaldo'}

# Valeurs de l'option `amis` (options.py) ; « aucun » par défaut. « tous » : 198 locations de remplissage (196 + 2
# dérivés), 7 amis d'histoire et 4 de requête NON exclus, et jusqu'à 18 amis d'évènement exclus (`objets_evenement`).
MODES_AMIS = ("aucun", "tous")
AMIS_PAR_DEFAUT = "aucun"


# ---------------------------------------------------------------------------
# Yo-criminels (archipelago_amis_criminels.md §3)
# ---------------------------------------------------------------------------
# Check = criminel n° N ARRÊTÉ : octet `wantedNN` (flag de catégorie 6 n° 396 + N de flag_config, octet P + 0x2D0 + N,
# sauvegardé) = nombre d'étapes gagnées ; posé seulement après une VICTOIRE (common_trigger n° 44 -> ev76_0400 :
# commande 0x36BB, +1 par étape ; à la dernière, objet de récompense et bit 2072), jamais après une défaite ou une fuite
# (n° 45, ev76_0300), jamais remis à zéro [C]. Arrêté ⇔ octet >= `etapes` (1, 2 ou 3 combats ; 72 étapes en tout).
# Les bits « v4..v6 » de WANTED_INFO ne sont que des marqueurs « vu dans le menu » (remis à 0 à chaque victoire) :
# inutilisables. Lu par le client dans la lecture groupée des flags de la partie (même paquet : P+0x2D1..0x304).
# Disponibilité d'origine [C] : fonction débloquée au chapitre 3 (bit 69, c03_trigger n° 13 / phase_set_c03
# PhCmd_3_75) ; UN SEUL criminel par semaine RÉELLE de l'horloge de la console (n° = semaine de l'année, ou le suivant
# non arrêté ; un par semaine : bit 2072), jamais pendant 7-40..7-70 ni de 10-20 à la fin du chapitre 10 ; emplacement
# tiré parmi 30 points de 5 cartes (Hauts de Granval, Coteau fleuri, Centre-ville, Quartier des boutiques, La Corniche),
# retiré chaque jour ; aucun d'après-jeu.
# Yo-criminels LIBRES (patch du mod, fonction 24 de la boîte, archipelago_amis_criminels.md §6) : le jeu propose
# toujours le premier criminel NON arrêté dans l'ordre ORDRE_CRIMINELS (par `chapitre`, puis par numéro), sans attendre
# la semaine suivante. Logique : locations NON exclues ; criminel n : règle « Chapitre max(chapitre, 4) terminé »
# (`chapitre` dérivé du niveau le plus élevé de ses combats : <= 25 : 3 ; <= 40 : 5 ; <= 60 : 7 ; au-delà : 8 ; au moins
# 4 : les 5 cartes du tirage, dont le Centre-ville après les Indications de Maman, 4-50) ; tous ceux qui le précèdent
# dans l'ordre ont un chapitre inférieur ou égal. Noms par numéro (le n° est aussi la semaine de l'année où il
# apparaît dans le jeu d'origine), aucun nom du jeu. Identifiants nouveaux 59423100 + N - 1 (hors des plages de
# l'ancien mod ; ses 5 paliers « Yo-criminels : N captures », 59422450..59422454, restent réservés, jamais créés).
# (n, étapes, chapitre)
_CRIMINELS = (
    (1, 1, 8),
    (2, 1, 8),
    (3, 2, 7),
    (4, 1, 3),
    (5, 1, 8),
    (6, 2, 7),
    (7, 1, 5),
    (8, 1, 5),
    (9, 1, 7),
    (10, 3, 8),
    (11, 1, 3),
    (12, 1, 5),
    (13, 1, 8),
    (14, 2, 8),
    (15, 1, 3),
    (16, 1, 3),
    (17, 1, 3),
    (18, 1, 3),
    (19, 1, 5),
    (20, 1, 5),
    (21, 2, 5),
    (22, 1, 5),
    (23, 1, 5),
    (24, 1, 7),
    (25, 3, 3),
    (26, 1, 3),
    (27, 1, 3),
    (28, 3, 7),
    (29, 1, 5),
    (30, 1, 7),
    (31, 1, 7),
    (32, 3, 3),
    (33, 1, 7),
    (34, 1, 7),
    (35, 1, 8),
    (36, 2, 5),
    (37, 1, 5),
    (38, 1, 7),
    (39, 3, 8),
    (40, 1, 3),
    (41, 1, 5),
    (42, 1, 7),
    (43, 3, 8),
    (44, 1, 7),
    (45, 1, 5),
    (46, 1, 5),
    (47, 3, 5),
    (48, 1, 8),
    (49, 1, 7),
    (50, 1, 8),
    (51, 2, 8),
    (52, 1, 5),
)
CRIMINEL_ID_BASE = 59423100
CRIMINEL_REGION = "les_hauts_de_granval"
CRIMINELS: List[dict] = [
    {"n": n, "id_ap": CRIMINEL_ID_BASE + n - 1, "etapes": e, "chapitre": c, "region": CRIMINEL_REGION,
     "nom_fr": "Yo-criminel n°%02d" % n, "nom_en": "Yo-criminal #%02d" % n}
    for n, e, c in _CRIMINELS]
CRIMINELS_PAR_NUMERO: Dict[int, dict] = {c["n"]: c for c in CRIMINELS}
CRIMINELS_ANCIENS_NON_CREES = tuple(range(59422450, 59422455))   # paliers de captures de l'ancien mod

# Ordre dans lequel le patch propose les criminels (MÊME ORDRE que `k_ordre` de src/archipelago/limites.cpp, vérifié
# par archipelago/tests/test_criminels_libres.py) : par chapitre de règle, puis par numéro.
ORDRE_CRIMINELS: Tuple[int, ...] = tuple(c["n"] for c in sorted(CRIMINELS, key=lambda c: (c["chapitre"], c["n"])))
# Chapitres terminés minimaux de toute location de Yo-criminel : les 5 cartes du tirage de l'emplacement accessibles
# (Centre-ville : Indications de Maman et phase 4-50 ; La Corniche : Pile ou passe, chapitre 1).
CRIMINELS_CHAPITRE_MIN = 4
# Bit de ApVerrous::compiles publié par un patch qui rend les Yo-criminels libres (src/archipelago/verrous.h,
# AP_FONCTION_CRIMINELS_LIBRES) ; exigé par slot_data `fonctions_exigees` quand l'option vaut « tous ».
FONCTION_CRIMINELS_LIBRES = 24

# Valeurs de l'option `yo_criminels` (options.py) ; « tous » par défaut (décision de l'humain, 2026-09-29 : jouables,
# avec le patch des criminels libres).
MODES_CRIMINELS = ("aucun", "tous")
CRIMINELS_PAR_DEFAUT = "tous"
