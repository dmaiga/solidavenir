#!/bin/bash
set -e

echo "=============================="
echo " Starting Hedera Service"
echo "=============================="

# Go to the hedera_service/src folder
cd "$(dirname "$0")/../../hedera_service/src" || exit

# Install dependencies if needed
if [ ! -d "node_modules" ]; then
    echo " Installing dependencies..."
    npm install
fi

# Start the service
echo "Starting Hedera service..."
npm start
