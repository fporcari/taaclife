#!/usr/bin/env bash
#
# NutriCoach - script di build interattivo (Fase 0, PROJECT.md §15).
#
# Gira sulla macchina di sviluppo. Fa cinque domande con default sensati,
# poi produce un'immagine Docker pronta per il deploy.
#
# IMPORTANTE: questo script NON chiede e NON incorpora segreti
# (API key, JWT). I segreti vivono nel `.env` al deploy (§16).
# L'immagine deve restare "pulita" e riutilizzabile.
#
# Uso:
#   ./build.sh            # interattivo, premi invio per accettare i default
#   ./build.sh --yes      # accetta tutti i default, non chiede nulla
#   ./build.sh --help     # mostra l'aiuto

set -euo pipefail

# ---------- Default ----------

DEFAULT_APP_NAME="nutricoach"
DEFAULT_FOOD_CONVENTION="crudo"   # crudo | cotto
DEFAULT_COACH_MODEL="haiku"       # haiku | sonnet
DEFAULT_INCLUDE_OFF="n"           # s | n
DEFAULT_LANG="it"                 # it | en

# Mapping nomi modello -> id reale Anthropic.
MODEL_HAIKU="claude-haiku-4-5-20251001"
MODEL_SONNET="claude-sonnet-4-6"

CONFIG_FILE="build.config"

# ---------- Argomenti CLI ----------

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y)
      ASSUME_YES=1
      ;;
    --help|-h)
      sed -n '2,18p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "argomento sconosciuto: $arg" >&2
      echo "usa --help" >&2
      exit 2
      ;;
  esac
done

# ---------- Helpers ----------

ask() {
  # ask "prompt" "default" -> stampa il valore (default se enter o --yes)
  local prompt="$1"
  local default="$2"
  if [ "$ASSUME_YES" -eq 1 ]; then
    echo "$default"
    return
  fi
  local answer
  read -r -p "$prompt [$default]: " answer
  echo "${answer:-$default}"
}

bold() { printf '\033[1m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }

# ---------- Banner ----------

bold "NutriCoach — build interattivo"
dim   "Cinque scelte di progetto, poi costruiamo l'immagine."
dim   "(invio per accettare il default; nessun segreto richiesto)"
echo

# ---------- 1. Nome app / tag immagine ----------

APP_NAME=$(ask "Nome app (tag immagine)" "$DEFAULT_APP_NAME")
if ! echo "$APP_NAME" | grep -qE '^[a-z0-9][a-z0-9_.-]*$'; then
  echo "nome immagine non valido: '$APP_NAME' (solo a-z 0-9 . _ -)" >&2
  exit 2
fi

# ---------- 2. Convenzione alimenti ----------

FOOD_CONVENTION=$(ask "Convenzione alimenti (crudo / cotto)" "$DEFAULT_FOOD_CONVENTION")
case "$FOOD_CONVENTION" in
  crudo) : ;;
  cotto)
    echo
    echo "ATTENZIONE: il seed 'cotto' non e' incluso in v1 (PROJECT.md §6 +"
    echo "  §14: la convenzione del progetto e' 'crudo')."
    echo "  Rilanciare con 'crudo' o attendere la v2 con seed alternativo." >&2
    exit 2
    ;;
  *) echo "convenzione non valida: $FOOD_CONVENTION (atteso crudo|cotto)" >&2; exit 2 ;;
esac

# ---------- 3. Modello coach ----------

COACH_MODEL_NAME=$(ask "Modello coach (haiku / sonnet)" "$DEFAULT_COACH_MODEL")
case "$COACH_MODEL_NAME" in
  haiku)  COACH_MODEL_ID="$MODEL_HAIKU"  ;;
  sonnet) COACH_MODEL_ID="$MODEL_SONNET" ;;
  *) echo "modello non valido: $COACH_MODEL_NAME (atteso haiku|sonnet)" >&2; exit 2 ;;
esac

# ---------- 4. Open Food Facts ----------

INCLUDE_OFF=$(ask "Includere Open Food Facts? (s/n)" "$DEFAULT_INCLUDE_OFF")
case "$INCLUDE_OFF" in
  n|no|N) INCLUDE_OFF="no" ;;
  s|si|y|yes|Y)
    echo
    echo "ATTENZIONE: OFF non e' incluso in v1 (PROJECT.md §14)."
    echo "  L'importer e' predisposto per la v2, con la sua attribuzione ODbL"
    echo "  da gestire allora. Rilanciare con 'n' o attendere la v2." >&2
    exit 2
    ;;
  *) echo "risposta non valida: $INCLUDE_OFF (atteso s|n)" >&2; exit 2 ;;
esac

# ---------- 5. Lingua ----------

SEED_LANG=$(ask "Lingua dei contenuti e dei seed" "$DEFAULT_LANG")
case "$SEED_LANG" in
  it) : ;;
  en)
    echo
    echo "ATTENZIONE: in v1 e' incluso solo il seed in italiano." >&2
    echo "  Rilanciare con 'it' o attendere la v2." >&2
    exit 2
    ;;
  *) echo "lingua non valida: $SEED_LANG (atteso it|en)" >&2; exit 2 ;;
esac

# ---------- Scrivi build.config (committabile, niente segreti) ----------

TIMESTAMP=$(date +%Y%m%d-%H%M)
cat > "$CONFIG_FILE" <<EOF
# NutriCoach build.config (autogenerato da build.sh, Fase 0).
# Committabile: NON contiene segreti.
# I segreti (ANTHROPIC_API_KEY, JWT_SECRET, JWT_REFRESH_SECRET) stanno nel
# .env del deploy (§16).
APP_NAME=$APP_NAME
FOOD_CONVENTION=$FOOD_CONVENTION
COACH_MODEL_NAME=$COACH_MODEL_NAME
COACH_MODEL_ID=$COACH_MODEL_ID
INCLUDE_OFF=$INCLUDE_OFF
SEED_LANG=$SEED_LANG
BUILT_AT=$TIMESTAMP
EOF

echo
bold "Configurazione:"
sed 's/^/  /' "$CONFIG_FILE"
echo

# ---------- Build ----------

IMAGE_LATEST="${APP_NAME}:latest"
IMAGE_DATED="${APP_NAME}:${TIMESTAMP}"

bold "Building image -> $IMAGE_LATEST"
echo "  (anche taggata come $IMAGE_DATED)"
echo

docker build \
  --build-arg "APP_NAME=$APP_NAME" \
  --build-arg "FOOD_CONVENTION=$FOOD_CONVENTION" \
  --build-arg "COACH_MODEL_DEFAULT=$COACH_MODEL_ID" \
  --build-arg "SEED_LANG=$SEED_LANG" \
  -t "$IMAGE_LATEST" \
  -t "$IMAGE_DATED" \
  .

echo
bold "Fatto."
echo "  Immagine: $IMAGE_LATEST (+ $IMAGE_DATED)"
echo "  Config:   $CONFIG_FILE"
echo
dim "Prossimi passi:"
dim "  1. Trasferire l'immagine sul server (vedi DEPLOY-HETZNER.md §3)."
dim "  2. Creare il .env coi segreti (ANTHROPIC_API_KEY, JWT_SECRET, ...)"
dim "     sul server."
dim "  3. docker run -d --env-file .env -v <vol>:/data -p ...:8000"
dim "     $IMAGE_LATEST"
