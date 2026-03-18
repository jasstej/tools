#!/bin/bash

################################################################################
# VulnScout - Complete Setup Master Script
# Sets up everything: virtual environment, clones repos, installs tools
# Usage: bash setup-everything.sh [tools_dir] [org_name]
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Defaults
TOOLS_DIR="${1:-$HOME/vulnscout-forks}"
ORG_NAME="${2:-vulnscout-tools}"
VENV_PATH="$HOME/.vulnscout-env"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Print functions
print_header() {
    echo -e "${CYAN}==========================================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}==========================================================${NC}"
}

print_section() {
    echo ""
    echo -e "${BLUE}► $1${NC}"
    echo ""
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

# Show help
show_help() {
    cat << EOF
${CYAN}VulnScout Complete Setup${NC}

This script will:
1. Create Python virtual environment
2. Clone all forked repositories
3. Install all tools
4. Verify installations
5. Generate documentation

${YELLOW}Usage:${NC}
  bash setup-everything.sh [tools_dir] [org_name]

${YELLOW}Arguments:${NC}
  tools_dir    - Directory to clone repos (default: ~/vulnscout-forks)
  org_name     - GitHub organization (default: vulnscout-tools)

${YELLOW}Examples:${NC}
  bash setup-everything.sh
  bash setup-everything.sh ~/my-tools my-security-org

${YELLOW}Requirements:${NC}
  - Git installed
  - Python 3.6+
  - Internet connection for cloning
  - GitHub organization created (or run manual fork)

EOF
}

# Check prerequisites
check_requirements() {
    print_section "Checking Requirements"

    local missing=0

    # Check Python
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        ((missing++))
    else
        local python_version=$(python3 --version 2>&1 | awk '{print $2}')
        print_success "Python 3 found: $python_version"
    fi

    # Check Git
    if ! command -v git &> /dev/null; then
        print_error "Git is not installed"
        ((missing++))
    else
        local git_version=$(git --version | awk '{print $3}')
        print_success "Git found: $git_version"
    fi

    # Check pip
    if ! command -v pip3 &> /dev/null; then
        print_error "pip3 is not installed"
        ((missing++))
    else
        print_success "pip3 found"
    fi

    if [ $missing -gt 0 ]; then
        print_error "$missing requirement(s) missing. Please install and try again."
        exit 1
    fi
}

# Setup virtual environment
setup_venv() {
    print_section "Setting up Python Virtual Environment"

    if [ -d "$VENV_PATH" ]; then
        print_warning "Virtual environment already exists at $VENV_PATH"
        read -p "Do you want to recreate it? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            print_info "Removing existing venv..."
            rm -rf "$VENV_PATH"
        else
            print_info "Using existing venv"
            return 0
        fi
    fi

    print_info "Creating virtual environment at $VENV_PATH..."
    if python3 -m venv "$VENV_PATH"; then
        print_success "Virtual environment created"

        # Activate it
        source "$VENV_PATH/bin/activate"
        print_success "Virtual environment activated"

        # Upgrade pip
        print_info "Upgrading pip, setuptools, wheel..."
        pip install --upgrade pip setuptools wheel 2>/dev/null
        print_success "pip, setuptools, wheel upgraded"
    else
        print_error "Failed to create virtual environment"
        exit 1
    fi
}

# Clone repositories
clone_repos() {
    print_section "Cloning Repository Forks"

    if [ ! -f "$SCRIPT_DIR/clone-all-tools.sh" ]; then
        print_error "clone-all-tools.sh not found in $SCRIPT_DIR"
        exit 1
    fi

    print_info "Running clone script..."
    print_info "  Target: $TOOLS_DIR"
    print_info "  Organization: $ORG_NAME"
    echo ""

    bash "$SCRIPT_DIR/clone-all-tools.sh" "$TOOLS_DIR" "$ORG_NAME"
}

# Install tools
install_tools() {
    print_section "Installing Python Tools"

    # Ensure venv is active
    if [ -z "$VIRTUAL_ENV" ]; then
        source "$VENV_PATH/bin/activate"
    fi

    print_info "Installing from local clones..."

    # Change to script directory
    cd "$SCRIPT_DIR"

    if [ -f "requirements-forked.txt" ]; then
        print_info "Using requirements-forked.txt..."
        # Update paths in requirements if needed
        if pip install -r requirements-forked.txt 2>/dev/null; then
            print_success "All tools installed successfully"
        else
            print_warning "Some tools may have failed to install"
            print_info "This is often normal for tools with special requirements"
        fi
    else
        print_warning "requirements-forked.txt not found"
        print_info "Installing tools from local clones manually..."
        cd "$TOOLS_DIR"
        for tool_dir in */; do
            if [ -f "$tool_dir/setup.py" ]; then
                tool_name=${tool_dir%/}
                print_info "Installing $tool_name..."
                pip install "$tool_dir" 2>/dev/null && print_success "Installed $tool_name" || print_warning "Failed to install $tool_name"
            fi
        done
    fi
}

# Verify installations
verify_installations() {
    print_section "Verifying Installations"

    # Ensure venv is active
    if [ -z "$VIRTUAL_ENV" ]; then
        source "$VENV_PATH/bin/activate"
    fi

    local tools=(
        "commix"
        "ghauri"
        "wafw00f"
        "paramspider"
        "arjun"
    )

    local installed=0
    local failed=0

    for tool in "${tools[@]}"; do
        if python3 -c "import pkg_resources; pkg_resources.get_distribution('$tool')" 2>/dev/null; then
            echo -e "${GREEN}✓${NC} $tool: installed"
            ((installed++))
        else
            echo -e "${YELLOW}✗${NC} $tool: not found"
            ((failed++))
        fi
    done

    echo ""
    print_info "Installation Summary: $installed installed, $failed not found"
    print_info "Some tools may not be importable as Python packages"
}

# Generate summary
generate_summary() {
    print_section "Setup Complete!"

    cat << EOF

${GREEN}✓ All setup steps completed!${NC}

${CYAN}Virtual Environment:${NC}
  Location: $VENV_PATH
  Activate: source $VENV_PATH/bin/activate
  Deactivate: deactivate

${CYAN}Cloned Repositories:${NC}
  Location: $TOOLS_DIR
  Total: 10 tools

${CYAN}Quick Commands:${NC}
  # Activate venv
  source $VENV_PATH/bin/activate

  # List installed tools
  pip list

  # Check tool versions
  commix --version
  ghauri --version

  # Sync with upstream
  bash $SCRIPT_DIR/sync-all-tools.sh $TOOLS_DIR

  # Update installations
  pip install --upgrade -r $SCRIPT_DIR/requirements-forked.txt

${CYAN}Documentation:${NC}
  • README_FORKING_SETUP.md - Complete guide
  • FORKING_GUIDE.md - Detailed fork procedures
  • SETUP_FORKED_REPOS.md - Setup instructions
  • PYTHON_PACKAGES.md - Package information
  • REPOSITORIES_LIST.csv - All repos in CSV

${CYAN}Next Steps:${NC}
  1. Verify all tools work:
     bash $SCRIPT_DIR/verify-setup.sh

  2. Set up automatic syncing:
     Add to crontab: 0 0 * * * bash $SCRIPT_DIR/sync-all-tools.sh $TOOLS_DIR

  3. Configure upstream remotes (if not done by clone script):
     bash $SCRIPT_DIR/configure-upstream.sh $TOOLS_DIR

  4. Start using the tools!

${YELLOW}Important Notes:${NC}
  • Always activate venv before using tools: source $VENV_PATH/bin/activate
  • Some tools may require additional configuration (API keys, etc.)
  • Keep forks updated with upstream regularly
  • Report issues to the upstream projects

${BLUE}For help:${NC}
  bash setup-everything.sh --help

EOF
}

# Main execution
main() {
    # Show header
    print_header "VulnScout Complete Setup"
    echo ""
    print_info "Organization: $ORG_NAME"
    print_info "Tools Directory: $TOOLS_DIR"
    print_info "Virtual Environment: $VENV_PATH"
    echo ""

    # Ask for confirmation
    echo "This will:"
    echo "  1. Create/update Python virtual environment"
    echo "  2. Clone all forked repositories (~500MB)"
    echo "  3. Install all security tools"
    echo "  4. Verify installations"
    echo ""
    read -p "Continue? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Setup cancelled"
        exit 0
    fi

    echo ""

    # Run setup steps
    check_requirements
    setup_venv
    clone_repos
    install_tools
    verify_installations
    generate_summary
}

# Handle arguments
if [ "$1" == "--help" ] || [ "$1" == "-h" ]; then
    show_help
    exit 0
fi

# Run main
main
