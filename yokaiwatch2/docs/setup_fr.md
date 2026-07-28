# Guide d'installation - Yo-kai Watch 2

## Logiciels requis

- [Archipelago](https://github.com/ArchipelagoMW/Archipelago/releases) 0.5.0
  ou plus récent,
- le fichier `yokaiwatch2.apworld`,
- une copie légalement dumpée de *Yo-kai Watch 2 : Spectres Psychiques* (3DS),
- **Via émulateur :** Citra ou son successeur Azahar,
- **Via console :** une 3DS avec le custom firmware Luma3DS.

## Installer l'APWorld

1. Ouvrez le Launcher Archipelago.
2. Cliquez sur **Install APWorld** et sélectionnez `yokaiwatch2.apworld`
   (ou double-cliquez sur le fichier, ou copiez-le dans
   `Archipelago/custom_worlds/`).
3. Redémarrez le Launcher : « Yo-kai Watch 2 » apparaît dans la liste.

## Créer votre YAML

1. Dans le Launcher, lancez **Generate Template Options** ; un modèle
   `Yo-kai Watch 2.yaml` est créé dans `Archipelago/Players/Templates/`.
2. Copiez-le dans `Archipelago/Players/`, renseignez votre `name` et ajustez
   les options (objectif, shuffles, difficulté logique...). Un exemple
   commenté est fourni avec le projet (`Yo-kai Watch 2 - Example.yaml`).

## Générer et héberger

1. Placez les YAML de tous les joueurs dans `Archipelago/Players/`.
2. Lancez **Generate** depuis le Launcher (ou `ArchipelagoGenerate`).
3. Hébergez le zip généré sur [archipelago.gg](https://archipelago.gg/uploads)
   ou localement avec **Host** (`ArchipelagoServer`).

## Se connecter

1. Depuis le Launcher, ouvrez le **Yo-kai Watch 2 Client**.
2. Entrez l'adresse du serveur (ex. `archipelago.gg:38281`) et votre nom de
   slot.

### Avec Citra / Azahar

1. Lancez le jeu dans l'émulateur.
2. Activez le stub GDB : *Émulation > Configurer > Debug > Enable GDB stub*
   (port 24689 par défaut), puis relancez l'émulation.
3. Dans le client, tapez `/citra` (ou `/citra <port>`).

### Sur 3DS moddée (Luma3DS)

1. Activez le débogueur de Rosalina (L+Bas+Select > Debugger options).
2. Faites pointer le client vers l'IP de la console et le port du débogueur
   avec `/citra <port>` après avoir réglé l'hôte dans les paramètres client.

> **Note :** le pont mémoire est un chantier communautaire. Tant que la
> table d'adresses n'est pas remplie (voir `client.py`), les checks peuvent
> être envoyés manuellement depuis le client texte pendant que l'intégration
> côté jeu progresse.
