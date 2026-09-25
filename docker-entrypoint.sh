#!/bin/sh
# Container entrypoint:
#   no arguments        -> start the web interface
#   --option arguments  -> run the poster CLI (e.g. --city Paris --country France)
#   anything else       -> run that command (e.g. python, sh)
set -e

if [ "$#" -eq 0 ]; then
    exec map2plotter-web --host 0.0.0.0 --port "${PORT:-8000}"
fi

case "$1" in
    -*) exec map2plotter "$@" ;;
esac

exec "$@"
