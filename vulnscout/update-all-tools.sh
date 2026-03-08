#!/bin/bash

##############################################################################
# VulnScout - Tool Update & Upgrade Script
# Updates and upgrades all installed security reconnaissance tools
# Compatible with: Linux (Debian/Ubuntu), macOS
##############################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
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

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v apt-get &> /dev/null; then
            PACKAGE_MANAGER="apt"
        else
            print_error "Unsupported Linux distribution"
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PACKAGE_MANAGER="brew"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    print_success "Detected OS: $OS"
}

# Update system packages
update_system_packages() {
    print_header "Updating System Packages"
    
    if [[ $PACKAGE_MANAGER == "apt" ]]; then
        print_info "Updating package lists..."
        sudo apt-get update
        
        print_info "Upgrading packages..."
        sudo apt-get upgrade -y
        
        print_info "Auto-removing old packages..."
        sudo apt-get autoremove -y
        
        print_success "System packages updated"
        
    elif [[ $PACKAGE_MANAGER == "brew" ]]; then
        print_info "Updating Homebrew..."
        brew update
        
        print_info "Upgrading packages..."
        brew upgrade
        
        print_info "Cleaning up..."
        brew cleanup
        
        print_success "System packages updated"
    fi
}

# Update Go tools
update_go_tools() {
    print_header "Updating Go-based Tools"
    
    # Ensure Go bin is in PATH
    export PATH=$PATH:~/go/bin
    
    local tools=(
        "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
        "github.com/projectdiscovery/httpx/cmd/httpx@latest"
        "github.com/projectdiscovery/katana/cmd/katana@latest"
        "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
        "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
        "github.com/projectdiscovery/dnsx/cmd/dnsx@latest"
        "github.com/tomnomnom/assetfinder@latest"
        "github.com/tomnomnom/waybackurls@latest"
        "github.com/tomnomnom/gf@latest"
        "github.com/tomnomnom/httprobe@latest"
        "github.com/projectdiscovery/notify/cmd/notify@latest"
        "github.com/OWASP/Amass/v3/...@latest"
    )
    
    for tool in "${tools[@]}"; do
        tool_name=$(echo $tool | awk -F'/' '{print $(NF)}' | cut -d'@' -f1)
        print_info "Updating $tool_name..."
        
        if go install -v "$tool" 2>&1 | grep -q "go get"; then
            print_success "Updated $tool_name"
        else
            print_warning "No updates available for $tool_name or failed to update"
        fi
    done
}

# Update Python tools
update_python_tools() {
    print_header "Updating Python-based Tools"
    
    print_info "Upgrading pip..."
    pip3 install --upgrade pip setuptools wheel
    
    local packages=(
        "LinkFinder"
        "commix"
        "wafw00f"
        "paramspider"
        "ghauri"
        "jwt-tool"
        "arjun"
        "SubDomainizer"
        "anew"
    )
    
    for package in "${packages[@]}"; do
        print_info "Updating $package..."
        if pip3 install --upgrade "$package" 2>/dev/null; then
            print_success "Updated $package"
        else
            print_warning "Failed to update $package"
        fi
    done
}

# Update GitHub-based tools
update_github_tools() {
    print_header "Updating GitHub-based Tools"
    
    if [ ! -d ~/security-tools ]; then
        print_warning "~/security-tools directory not found. Skipping GitHub tools update."
        return
    fi
    
    cd ~/security-tools
    
    for dir in */; do
        tool_name="${dir%/}"
        if [ -d "$tool_name/.git" ]; then
            print_info "Updating $tool_name..."
            cd "$tool_name"
            if git pull 2>/dev/null; then
                print_success "Updated $tool_name"
                
                # Install if it has setup.py
                if [ -f "setup.py" ]; then
                    pip3 install -e . 2>/dev/null
                fi
                
                # Install if it has requirements.txt
                if [ -f "requirements.txt" ]; then
                    pip3 install -r requirements.txt 2>/dev/null
                fi
            else
                print_warning "Failed to update $tool_name"
            fi
            cd ..
        fi
    done
    
    cd - > /dev/null
}

# Show updated versions
show_versions() {
    print_header "Installed Tool Versions"
    
    local tools=(
        "subfinder"
        "httpx"
        "katana"
        "nuclei"
        "assetfinder"
        "waybackurls"
        "gf"
        "amass"
    )
    
    for tool in "${tools[@]}"; do
        if command -v "$tool" &> /dev/null; then
            version=$($tool --version 2>&1 | head -n 1)
            echo -e "${GREEN}✓${NC} $tool: $version"
        else
            echo -e "${YELLOW}✗${NC} $tool: Not found"
        fi
    done
}

# Show completion message
show_completion() {
    cat << EOF

${GREEN}✓ All updates completed successfully!${NC}

${YELLOW}Next Steps:${NC}
1. Reload your shell: ${BLUE}source ~/.bashrc${NC} (Linux) or ${BLUE}source ~/.zprofile${NC} (macOS)
2. Verify tools: ${BLUE}subfinder --version${NC}
3. Start scanning: ${BLUE}cd ~/VulnScout${NC}

${YELLOW}Tips:${NC}
- Update frequently using this script
- Override Go version caching: ${BLUE}go clean -modcache${NC}
- Check for new Nuclei templates: ${BLUE}nuclei -update${NC}
- Keep API configs updated: ${BLUE}~/.config/subfinder/provider-config.yaml${NC}

EOF
}

# Main update flow
main() {
    print_header "DorkVault - Tool Update Script"
    echo "This script will update all security reconnaissance tools"
    echo ""
    
    detect_os
    
    echo ""
    print_warning "This script requires sudo privileges"
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r
    
    update_system_packages
    update_go_tools
    update_python_tools
    update_github_tools
    show_versions
    
    echo ""
    show_completion
    print_success "Tool updates completed!"
}

# Run main function
main
