#!/bin/sh
# Container entrypoint:
#   no arguments        -> start the web interface
#   --option arguments  -> run the poster CLI (e.g. --city Paris --country France)
#   anything else       -> run that command (e.g. python, sh)
set -e

if [ "$#" -eq 0 ]; then
    exec python web_app.py --host 0.0.0.0 --port "${PORT:-8000}"
fi

case "$1" in
    -*) exec python create_map_poster.py "$@" ;;
esac

exec "$@"
