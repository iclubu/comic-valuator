#!/usr/bin/env bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 -m streamlit run app.py --server.port 8502