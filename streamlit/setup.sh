#!/bin/bash

# Create required directories with secure permissions
mkdir -p data backups keys
chmod 700 data backups keys

# Generate secure random keys if they don't exist
if [ ! -f .env ]; then
    echo "Generating secure keys..."
    JWT_SECRET=$(openssl rand -hex 32)
    ENCRYPTION_KEY=$(openssl rand -base64 32)
    
    # Create .env file with secure permissions
    cat > .env << EOF
JWT_SECRET=$JWT_SECRET
ENCRYPTION_KEY=$ENCRYPTION_KEY
EOF
    chmod 600 .env
    echo "Created .env file with secure keys"
fi

# Create directories inside the container with correct permissions
docker-compose up -d --no-start
docker-compose run --rm budget-planner mkdir -p /app/data /app/backups /app/keys
docker-compose down

echo "Setup complete! You can now start the application with:"
echo "docker-compose up -d"
echo ""
echo "Important security notes:"
echo "1. Keep your .env file secure and backup it safely"
echo "2. The application is configured to only accept local connections"
echo "3. All data is encrypted at rest"
echo "4. Regular backups are recommended"
