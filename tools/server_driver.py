"""Pilote ArchipelagoServer.exe : lance le serveur et lui transmet des commandes
console via un fichier (scratchpad/srv_cmd.txt). Une ligne = une commande.
Ligne "__quit__" => arrête le serveur. Noms d'items SANS accents.
"""
import os, sys, time, subprocess, glob

AP = r"C:\ProgramData\Archipelago"
SRV = os.path.join(AP, "ArchipelagoServer.exe")
CMD = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(__file__), "..", "srv_cmd.txt")
CMD = os.path.abspath(CMD)

zips = sorted(glob.glob(os.path.join(AP, "output", "AP_*.zip")),
              key=os.path.getmtime)
seed = zips[-1]
print("SEED:", seed, flush=True)

open(CMD, "w").close()  # vide le fichier de commandes
proc = subprocess.Popen([SRV, seed], stdin=subprocess.PIPE,
                        cwd=AP, text=True, bufsize=1)

try:
    while proc.poll() is None:
        time.sleep(0.4)
        try:
            with open(CMD, "r", encoding="utf-8") as f:
                lines = [l.rstrip("\n") for l in f if l.strip()]
        except FileNotFoundError:
            lines = []
        if not lines:
            continue
        open(CMD, "w").close()
        for line in lines:
            if line.strip() == "__quit__":
                proc.stdin.write("/exit\n"); proc.stdin.flush()
                time.sleep(1); proc.terminate(); raise SystemExit
            print(">>", line, flush=True)
            proc.stdin.write(line + "\n"); proc.stdin.flush()
finally:
    if proc.poll() is None:
        proc.terminate()
