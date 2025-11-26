#!/bin/bash

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up SevenSplit Development Environment...${NC}"

# 1. Python Virtual Environment Setup
echo -e "\n${BLUE}[Python]${NC} Checking virtual environment..."
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# 2. Install Backend Dependencies
echo -e "\n${BLUE}[Backend]${NC} Installing dependencies..."
if [ -f "backend/requirements.txt" ]; then
    pip install -r backend/requirements.txt
else
    echo "Warning: backend/requirements.txt not found."
fi

# 3. Install Mock Exchange Dependencies
echo -e "\n${BLUE}[Mock Exchange]${NC} Installing dependencies..."
if [ -f "mock-exchange/requirements.txt" ]; then
    pip install -r mock-exchange/requirements.txt
else
    echo "Warning: mock-exchange/requirements.txt not found."
fi

# 4. Install Frontend Dependencies
echo -e "\n${BLUE}[Frontend]${NC} Installing dependencies..."
cd frontend
if [ -f "package.json" ]; then
    npm install
else
    echo "Warning: frontend/package.json not found."
fi
cd ..

echo -e "\n${GREEN}✓ Setup complete!${NC}"
echo -e "You can now run the project using: ${BLUE}./run-dev.sh${NC}"
