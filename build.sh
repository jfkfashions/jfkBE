#!/usr/bin/env bash

# build.sh - Build script for Render deployment
# This script runs during the build phase on Render

set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Running database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete!"
