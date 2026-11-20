#!/usr/bin/env bash
# Récupère les icônes de jeux manquantes pour une vidéo, sans jamais les versionner en clair.
# Usage (depuis la racine du dépôt) : bash tools/social/video/icones.sh ID1,ID2,...
# Étapes : clé RSA jetable -> workflow « Icônes pour les vidéos » (icones-video.yml) -> archive chiffrée sur la branche
# tmp/icones-<run> -> déchiffrement local dans tools/social/video/icones/ (ignoré par git). Le ménage quotidien du
# workflow (4 h 17 UTC) supprime les branches temporaires.
set -euo pipefail
IDS="${1:?donner les universe_id séparés par des virgules}"
REPO="${REPO:-DRM-27/le-releve}"
DEST=tools/social/video/icones
mkdir -p "$DEST"
MANQ=$(python3 -c 'import os,sys; print(",".join(u for u in sys.argv[1].split(",") if u and not os.path.exists(f"{sys.argv[2]}/{u}.png")))' "$IDS" "$DEST")
if [ -z "$MANQ" ]; then echo "icônes : toutes déjà présentes"; exit 0; fi
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$T/priv.pem" 2>/dev/null
openssl rsa -in "$T/priv.pem" -pubout -out "$T/pub.pem" 2>/dev/null
DEPUIS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
gh api -X POST "repos/$REPO/actions/workflows/icones-video.yml/dispatches" -f ref=main -f "inputs[ids]=$MANQ" -f "inputs[cle]=$(base64 -w0 "$T/pub.pem")"
echo "icônes demandées : $MANQ"
RUN=""
FILTRE='[.workflow_runs[] | select(.created_at >= "DEPUIS")] | last | select(. != null) | "\(.id) \(.status) \(.conclusion)"'
FILTRE=${FILTRE/DEPUIS/$DEPUIS}
for i in $(seq 1 60); do
  sleep 10
  L=$(gh api "repos/$REPO/actions/workflows/icones-video.yml/runs?event=workflow_dispatch&per_page=5" --jq "$FILTRE")
  [ -z "$L" ] && continue
  set -- $L; RUN=$1
  if [ "$2" = "completed" ]; then
    [ "$3" = "success" ] || { echo "workflow des icônes en échec (run $RUN)"; exit 1; }
    break
  fi
done
[ -n "$RUN" ] || { echo "le workflow des icônes n'a pas démarré"; exit 1; }
git fetch -q --depth=1 origin "tmp/icones-$RUN"
git show FETCH_HEAD:icones.zip.enc > "$T/icones.zip.enc"
git show FETCH_HEAD:cle.enc > "$T/cle.enc"
openssl pkeyutl -decrypt -inkey "$T/priv.pem" -in "$T/cle.enc" -out "$T/k.bin"
openssl enc -d -aes-256-cbc -pbkdf2 -in "$T/icones.zip.enc" -out "$T/icones.zip" -pass "file:$T/k.bin"
python3 -c 'import zipfile,sys,os
z = zipfile.ZipFile(sys.argv[1])
for n in z.namelist():
    if n.endswith(".png"):
        open(os.path.join(sys.argv[2], os.path.basename(n)), "wb").write(z.read(n))' "$T/icones.zip" "$DEST"
echo "icônes récupérées (run $RUN) : $(ls "$DEST" | wc -l) dans $DEST"
