#!/bin/bash

# KEEPTHECHANGE.com Backend Startup Script

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}   KEEPTHECHANGE.com Backend Startup   ${NC}"
echo -e "${BLUE}========================================${NC}"

# Check Python version
echo -e "${YELLOW}Checking Python version...${NC}"
python_version=$(python3 --version | cut -d' ' -f2)
if [[ $python_version != 3.10* && $python_version != 3.11* && $python_version != 3.12* ]]; then
    echo -e "${RED}Error: Python 3.10+ required. Found: $python_version${NC}"
    exit 1
fi
echo -e "${GREEN}Python $python_version detected${NC}"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${YELLOW}Activating virtual environment...${NC}"
source venv/bin/activate

# Install/upgrade pip
echo -e "${YELLOW}Upgrading pip...${NC}"
pip install --upgrade pip

# Install dependencies
echo -e "${YELLOW}Installing dependencies...${NC}"
pip install -r requirements.txt

# Check for .env file
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}Creating .env file from template...${NC}"
    cp .env.example .env
    echo -e "${RED}Please update .env file with your configuration${NC}"
    exit 1
fi

# Load environment variables
echo -e "${YELLOW}Loading environment variables...${NC}"
export $(grep -v '^#' .env | xargs)

# Check database connection
echo -e "${YELLOW}Checking database connection...${NC}"
if command -v psql &> /dev/null; then
    if psql "$DATABASE_URL" -c "\q" 2>/dev/null; then
        echo -e "${GREEN}Database connection successful${NC}"
    else
        echo -e "${RED}Database connection failed${NC}"
        echo -e "${YELLOW}Creating database if it doesn't exist...${NC}"
        
        # Extract database name from URL
        dbname=$(echo $DATABASE_URL | sed -n 's/.*\/\([^\/]*\)$/\1/p')
        if [ -n "$dbname" ]; then
            createdb "$dbname" 2>/dev/null || true
        fi
    fi
else
    echo -e "${YELLOW}PostgreSQL client not found, skipping database check${NC}"
fi

# Run database migrations
echo -e "${YELLOW}Running database migrations...${NC}"
alembic upgrade head

# Create admin user if not exists
echo -e "${YELLOW}Creating admin user...${NC}"
python -c "
import asyncio
import sys
sys.path.append('.')
from app.core.database import init_db
from app.models.user import User
from app.core.security import get_password_hash
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

async def create_admin():
    async with AsyncSession(init_db.engine) as session:
        result = await session.execute(select(User).where(User.email == 'admin@keepthechange.com'))
        admin = result.scalar_one_or_none()
        
        if not admin:
            admin = User(
                email='admin@keepthechange.com',
                password_hash=get_password_hash('Admin123!'),
                first_name='Admin',
                last_name='User',
                subscription_tier='elite',
                email_verified=True
            )
            session.add(admin)
            await session.commit()
            print('Admin user created')
        else:
            print('Admin user already exists')

asyncio.run(create_admin())
"

# Start the application
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Starting KEEPTHECHANGE.com backend...${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${YELLOW}Environment: $ENVIRONMENT${NC}"
echo -e "${YELLOW}Host: $HOST${NC}"
echo -e "${YELLOW}Port: $PORT${NC}"
echo -e "${YELLOW}Database: $DATABASE_URL${NC}"
echo -e "${BLUE}========================================${NC}"

if [ "$ENVIRONMENT" = "production" ]; then
    # Production mode with gunicorn
    echo -e "${GREEN}Starting in production mode with gunicorn...${NC}"
    gunicorn main:app \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind $HOST:$PORT \
        --timeout 120 \
        --keep-alive 5 \
        --access-logfile - \
        --error-logfile -
else
    # Development mode with auto-reload
    echo -e "${GREEN}Starting in development mode with auto-reload...${NC}"
    uvicorn main:app \
        --host $HOST \
        --port $PORT \
        --reload \
        --reload-dir . \
        --log-level info
fi