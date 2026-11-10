@echo off
rem Test des manettes de Zakuro (SDL) : n'ouvre aucune fenetre de jeu, ne lit ni n'ecrit aucun reglage.
title Test de la manette (Zakuro, SDL)
echo Test de la manette par SDL, comme Zakuro la lit (2 minutes).
echo  - branchez la manette ou allumez-la (Bluetooth) ; elle doit apparaitre comme "connected" ;
echo  - appuyez sur chaque bouton, bougez les sticks et les gachettes : chaque geste ecrit une ligne ;
echo  - cliquez sur une autre fenetre : les lignes doivent continuer (fenetre en arriere-plan) ;
echo  - recommencez avec Steam ouvert, puis ferme.
echo Controller test through SDL, the way Zakuro reads it (2 minutes). Ctrl+C to stop.
echo.
"%~dp0zakuro.exe" --controllers 120
echo.
pause
