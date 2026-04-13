#!/bin/bash
if [ -f save.json ]; then
    mv save.json "save.json.bak.$(date +%Y%m%d_%H%M%S)"
fi
source ./.venv/bin/activate
python3 main.py
