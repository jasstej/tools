#!/bin/bash

################################################################################
# VulnScout - Clone All Forked Tools
# Clones all security tools from your GitHub organization into a local directory
# Usage: bash clone-all-tools.sh [target_dir] [organization_name]
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TARGET_DIR="${1:-.}"
ORG_NAME="${2:-vulnscout-tools}"
GITHUB_USERNAME=""

# Parse command line arguments
show_help() {
    cat << EOF
${BLUE}VulnScout Tool Cloner${NC}

Usage: bash clone-all-tools.sh [target_dir] [org_name]

Arguments:
  target_dir  - Directory to clone all tools into (default: current directory)
  org_name    - GitHub organization name (default: vulnscout-tools)

Examples:
  # Clone to ~/vulnscout-forks with default org
  bash clone-all-tools.sh ~/vulnscout-forks

  # Clone to ~/my-tools with custom org
  bash clone-all-tools.sh ~/my-tools my-security-org

  # Clone to current directory
  bash clone-all-tools.sh . my-org

${YELLOW}Note:${NC} Update ORG_NAME variable in script to use your GitHub organization.

EOF
}

# Print functions
print_header() {
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================================${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Main repositories to clone
declare -a REPOS=(
    "commix"
    "ghauri"
    "wafw00f"
    "LinkFinder"
    "paramspider"
    "arjun"
    "SubDomainizer"
    "jwt-tool"
    "dotdotpwn"
    "anew"
)

# Alternative names mapping (if your fork names differ)
declare -A REPO_NAMES=(
    ["commix"]="commix"
    ["ghauri"]="ghauri"
    ["wafw00f"]="wafw00f"
    ["LinkFinder"]="LinkFinder"
    ["paramspider"]="paramspider"
    ["arjun"]="arjun"
    ["SubDomainizer"]="SubDomainizer"
    ["jwt-tool"]="jwt-tool"
    ["dotdotpwn"]="dotdotpwn"
    ["anew"]="anew"
)

# Check if target directory exists
if [ ! -d "$TARGET_DIR" ]; then
    print_info "Creating target directory: $TARGET_DIR"
    mkdir -p "$TARGET_DIR"
fi

print_header "VulnScout Tool Cloner"
print_info "Organization: $ORG_NAME"
print_info "Target Directory: $(cd "$TARGET_DIR" && pwd)"
print_info "Total repositories to clone: ${#REPOS[@]}"
echo ""

# Clone each repository
clone_count=0
success_count=0
failed_count=0

for repo in "${REPOS[@]}"; do
    repo_name="${REPO_NAMES[$repo]:-$repo}"
    repo_url="https://github.com/$ORG_NAME/$repo_name.git"
    target_path="$TARGET_DIR/$repo"

    print_info "[$((clone_count+1))/${#REPOS[@]}] Cloning $repo_name..."

    if [ -d "$target_path" ]; then
        print_warning "$repo already exists at $target_path"
        print_info "Updating existing repository..."
        cd "$target_path"
        if git fetch origin && git pull origin main 2>/dev/null || git pull origin master 2>/dev/null; then
            print_success "Updated $repo"
            ((success_count++))
        else
            print_warning "Failed to update $repo"
            ((failed_count++))
        fi
        cd - > /dev/null
    else
        if git clone "$repo_url" "$target_path" 2>/dev/null; then
            print_success "Cloned $repo to $target_path"
            ((success_count++))
        else
            print_error "Failed to clone $repo from $repo_url"
            print_warning "Make sure:"
            print_warning "  1. Repository exists in $ORG_NAME organization"
            print_warning "  2. You have access to the repository"
            print_warning "  3. Your SSH key is configured (if using SSH)"
            ((failed_count++))
        fi
    fi

    ((clone_count++))
    echo ""
done

# Generate summary
print_header "Clone Summary"
echo "Total Processed: $clone_count"
echo -e "${GREEN}Successful: $success_count${NC}"
if [ $failed_count -gt 0 ]; then
    echo -e "${RED}Failed: $failed_count${NC}"
fi
echo ""

# Create directory structure documentation
print_info "Creating directory structure file..."
ls_file="$TARGET_DIR/DIRECTORY_STRUCTURE.md"

cat > "$ls_file" << 'EOF'
# VulnScout Tools Directory Structure

This directory contains all VulnScout security tools.

## Directory Listing

```
EOF

if command -v tree &> /dev/null; then
    tree -L 1 -d "$TARGET_DIR" >> "$ls_file" 2>/dev/null || ls -la "$TARGET_DIR" >> "$ls_file"
else
    ls -la "$TARGET_DIR" >> "$ls_file"
fi

cat >> "$ls_file" << 'EOF'
```

## Tools Overview

### Core Tools
- **commix** - Command Injection Testing Tool
- **ghauri** - SQL Injection Vulnerability Scanner
- **wafw00f** - WAF Fingerprinting Tool
- **LinkFinder** - Endpoint Discovery from JavaScript

### Utility Tools
- **paramspider** - Parameter Discovery Spider
- **arjun** - HTTP Parameter Fuzzer
- **SubDomainizer** - Subdomain Discovery from JavaScript

### Support Tools
- **jwt-tool** - JWT Testing Toolkit
- **dotdotpwn** - Directory Traversal Scanner
- **anew** - Unique Finding Manager

## Installation

### Install all packages
```bash
cd $(dirname $(pwd))/clone-all-tools.sh
source ~/.vulnscout-env/bin/activate
pip install -r requirements-forked.txt
```

### Install individual package
```bash
source ~/.vulnscout-env/bin/activate
pip install ~/path/to/vulnscout-forks/commix
```

## Updating Tools

### Update all repositories
```bash
for dir in */; do
    if [ -d "$dir/.git" ]; then
        echo "Updating $dir..."
        cd "$dir"
        git pull origin main 2>/dev/null || git pull origin master 2>/dev/null
        cd ..
    fi
done
```

### Update specific tool
```bash
cd commix
git pull origin main
```

## Maintenance

- Keep all repositories in sync with upstream
- Check for security updates periodically
- Document any custom changes in each repository
EOF

print_success "Created directory structure file: $ls_file"
echo ""

# Create a requirements file for pip installation
print_info "Creating requirements-forked.txt..."
req_file="$TARGET_DIR/../requirements-forked.txt"

cat > "$req_file" << 'EOF'
# VulnScout Forked Tools - Installation Requirements
# Install from local clones: pip install -r requirements-forked.txt
# Make sure you're in the virtual environment: source ~/.vulnscout-env/bin/activate

# Core Tools
./vulnscout-forks/commix
./vulnscout-forks/ghauri
./vulnscout-forks/wafw00f
./vulnscout-forks/LinkFinder

# Utility Tools
./vulnscout-forks/paramspider
./vulnscout-forks/arjun
./vulnscout-forks/SubDomainizer

# Support Tools
./vulnscout-forks/jwt-tool
./vulnscout-forks/dotdotpwn
./vulnscout-forks/anew
EOF

print_success "Created requirements file: $req_file"
echo ""

# Create installation script
install_script="$TARGET_DIR/install-from-forks.sh"
cat > "$install_script" << 'INSTALL_SCRIPT'
#!/bin/bash

# VulnScout - Install from Forked Repositories
# This script installs all tools from the local cloned forks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PATH="$HOME/.vulnscout-env"

echo "=========================================="
echo "Installing VulnScout Tools from Forks"
echo "=========================================="
echo ""

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_PATH"
fi

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_PATH/bin/activate"

echo "Upgrading pip..."
pip install --upgrade pip setuptools wheel

echo ""
echo "Installing tools from local forks..."
echo ""

# Install each tool
for tool_dir in "$SCRIPT_DIR"/*; do
    if [ -d "$tool_dir" ] && [ -f "$tool_dir/setup.py" ]; then
        tool_name=$(basename "$tool_dir")
        echo "Installing $tool_name..."
        pip install "$tool_dir" 2>/dev/null && echo "✓ $tool_name installed" || echo "✗ Failed to install $tool_name"
    fi
done

echo ""
echo "=========================================="
echo "Installation complete!"
echo "Virtual environment: $VENV_PATH"
echo "To activate: source $VENV_PATH/bin/activate"
echo "=========================================="
INSTALL_SCRIPT

chmod +x "$install_script"
print_success "Created installation script: $install_script"
echo ""

# Final instructions
print_header "Next Steps"
echo ""
print_info "1. Verify clone was successful:"
echo "   ls -la $TARGET_DIR/"
echo ""
print_info "2. Update fork names in this script if needed"
echo ""
print_info "3. Install tools from local forks:"
echo "   bash $install_script"
echo ""
print_info "4. Or install from GitHub organization:"
echo "   pip install git+https://github.com/$ORG_NAME/commix.git"
echo ""
print_info "5. See FORKING_GUIDE.md for more details"
echo ""

if [ $success_count -eq ${#REPOS[@]} ]; then
    print_success "All repositories cloned successfully!"
else
    print_warning "$failed_count repositories failed to clone"
fi
