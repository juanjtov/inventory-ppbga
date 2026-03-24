#!/bin/bash
# venv_activate.sh

# Activate virtual environment
source venv/bin/activate

# Export environment variables from .env
if [ -f .env ]; then
  #export $(grep -v '^#' .env | xargs)
  set -a      # auto export all variables
  source .env # or: . .env
  set +a
fi

# Install dependencies
if [ -f requirements.txt ]; then
  echo "Installing dependencies..."
  pip install --upgrade pip
  pip install -r requirements.txt
fi

echo "✅ Virtual environment activated with all environment variables loaded."