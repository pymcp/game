#!/bin/bash
mkdir -p saves
if [ -f saves/save.json ]; then
    mv saves/save.json "saves/save.json.bak.$(date +%Y%m%d_%H%M%S)"
fi
source ./.venv/bin/activate
python3 main.py
