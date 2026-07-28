# Yo-kai Watch 2

## Que fait la randomisation sur ce jeu ?

Yo-kai Watch 2 : Spectres Psychiques devient un jeu multiworld : les coffres,
les objets au sol, les 83 requêtes et 10 services, les 52 planques Yo-kai,
les 26 Tablo-blabla, les aventures de Komasan, les Yo-criminels, les boss,
les rangs de montre, les chapitres d'histoire et (en option) les collections
d'insectes et de poissons, les Yo-kai recrutés, les objets de fusion et les
sceaux légendaires deviennent des checks Archipelago. Les objets clés - le
vélo, les rangs de montre, les clés et les outils - sont mélangés dans le pool
du multiworld. Les destinations en train (Ourcival, San Fantastico) et le
Vieux Granval (passé) se débloquent par la progression de l'histoire, tandis
qu'atteindre les Limbes éternelles ou le Paradis divin dépend des clés trouvées
par vous ou par les autres joueurs.

## Quel est l'objectif ?

Configurable dans votre YAML :

- **Final Boss** - vaincre Lady Démona,
- **Story 100** - terminer les 11 chapitres de l'histoire,
- **Infinite Inferno** - vaincre Potofeu au fond de l'Enfer Infini,
- **Divine Paradise** - vaincre Filomène,
- **All Legendaries** - obtenir toutes les médailles légendaires,
- **All Checks** - tout terminer.

## Quels objets peuvent se trouver dans le monde d'un autre joueur ?

Les objets de progression (vélo, rangs de montre, pass, tickets, clés,
outils, médailles légendaires, chapitres d'histoire si mélangés), les objets
utiles (Gemmes d'âme, argent, kits de soin), les objets de remplissage
(nourriture) et, en option, des pièges.

## À quoi ressemble un objet d'un autre monde dans Yo-kai Watch 2 ?

Tant que l'intégration côté jeu n'est pas finalisée, les checks sont suivis
via le client Yo-kai Watch 2 (client texte avec un pont mémoire vers
l'émulateur). Les objets reçus sont affichés dans le client et appliqués au
jeu lorsque c'est pris en charge.

## Commandes locales spécifiques

- `/citra [port]` - attache le client au stub GDB de Citra/Azahar.
