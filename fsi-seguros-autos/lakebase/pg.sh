#!/bin/zsh
# Conecta a Lakebase seguros-siu (base siu) con tu identidad Databricks (OAuth, token de 1 h).
#   ./pg.sh                      → psql interactivo
#   ./pg.sh -f archivo.sql       → ejecuta archivo
#   ./pg.sh -c "SELECT 1"        → ejecuta sentencia
EP=projects/seguros-siu/branches/production/endpoints/primary
HOST=<LAKEBASE_HOST>
TOKEN=$(databricks postgres generate-database-credential $EP -p DEFAULT -o json | python3 -c "import sys,json;print(json.load(sys.stdin)['token'])")
PGPASSWORD=$TOKEN psql "host=$HOST port=5432 dbname=siu user=<tu_usuario> sslmode=require" -v ON_ERROR_STOP=1 "$@"
