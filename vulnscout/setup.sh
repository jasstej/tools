#!/bin/bash

##############################################################################
# VulnScout - Quick Setup Script
# One-liner setup for impatient users
##############################################################################

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Starting VulnScout Setup...${NC}\n"

# Make scripts executable
chmod +x "$(dirname "$0")/install-all-tools.sh"
chmod +x "$(dirname "$0")/update-all-tools.sh"

# Run full installation
bash "$(dirname "$0")/install-all-tools.sh"

echo -e "\n${GREEN}Done! Run ./update-all-tools.sh to keep tools updated.${NC}\n"
