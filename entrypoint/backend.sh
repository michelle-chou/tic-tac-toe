#!/bin/bash

cd /app/backend &&
python -m pip install --user -r requirements.txt &&
python -m flask run -p 3001 -h '0.0.0.0' &
