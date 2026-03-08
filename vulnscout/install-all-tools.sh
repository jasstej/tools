#!/bin/bash

##############################################################################
# VulnScout - Universal Tool Installation & Update Script
# Installs all security reconnaissance tools and dependencies
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
            print_error "Unsupported Linux distribution. Only Debian/Ubuntu is fully supported."
            exit 1
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PACKAGE_MANAGER="brew"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    print_success "Detected OS: $OS (Package Manager: $PACKAGE_MANAGER)"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Install system dependencies
install_dependencies() {
    print_header "Installing System Dependencies"
    
    if [[ $PACKAGE_MANAGER == "apt" ]]; then
        print_info "Updating package lists..."
        sudo apt-get update
        print_info "Upgrading existing packages..."
        sudo apt-get upgrade -y
        
        print_info "Installing build essentials and dependencies..."
        sudo apt-get install -y \
            build-essential \
            curl \
            wget \
            git \
            vim \
            jq \
            python3 \
            python3-pip \
            python3-venv \
            golang-go \
            git-all \
            masscan \
            nmap \
            dnsutils \
            whois \
            uuid-runtime
            
        print_success "System dependencies installed"
        
    elif [[ $PACKAGE_MANAGER == "brew" ]]; then
        print_info "Updating Homebrew..."
        brew update
        print_info "Upgrading existing packages..."
        brew upgrade
        
        print_info "Installing dependencies..."
        brew install \
            curl \
            wget \
            git \
            vim \
            jq \
            python3 \
            go \
            nmap \
            bind \
            whois \
            coreutils
            
        print_success "System dependencies installed"
    fi
}

# Install Go-based tools
install_go_tools() {
    print_header "Installing Go-based Tools"
    
    # Check if Go is installed
    if ! command_exists go; then
        print_error "Go is not installed. Please install Go first."
        exit 1
    fi
    
    print_info "Go version: $(go version)"
    
    # Create Go bin directory if it doesn't exist
    mkdir -p ~/go/bin
    export PATH=$PATH:~/go/bin
    
    # Add to shell profile
    if [[ $OS == "linux" ]]; then
        SHELL_PROFILE="$HOME/.bashrc"
    else
        SHELL_PROFILE="$HOME/.zprofile"
    fi
    
    if ! grep -q "export PATH=.*go/bin" "$SHELL_PROFILE"; then
        echo "export PATH=$PATH:~/go/bin" >> "$SHELL_PROFILE"
        print_success "Added Go bin to PATH in $SHELL_PROFILE"
    fi
    
    # Install tools
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
        tool_name=$(echo $tool | awk -F'/' '{print $(NF-1)}')
        print_info "Installing $tool_name..."
        if go install -v "$tool" 2>/dev/null; then
            print_success "Installed $tool_name"
        else
            print_warning "Failed to install $tool_name"
        fi
    done
}

# Install Python-based tools
install_python_tools() {
    print_header "Installing Python-based Tools"
    
    # Check if pip is installed
    if ! command_exists pip3; then
        print_error "pip3 is not installed"
        exit 1
    fi
    
    print_info "Updating pip..."
    pip3 install --upgrade pip setuptools wheel
    
    # Python packages to install
    local packages=(
        "LinkFinder"
        "commix"
        "dotdotpwn"
        "wafw00f"
        "paramspider"
        "ghauri"
        "jwt-tool"
        "arjun"
        "SubDomainizer"
        "anew"
    )
    
    for package in "${packages[@]}"; do
        print_info "Installing $package..."
        if pip3 install "$package" 2>/dev/null; then
            print_success "Installed $package"
        else
            print_warning "Failed to install $package (may not exist or may need special installation)"
        fi
    done
}

# Install utility tools from GitHub
install_github_tools() {
    print_header "Installing GitHub-based Tools"
    
    mkdir -p ~/security-tools
    cd ~/security-tools
    
    # Tools to clone and install
    local repos=(
        "D35m0nd142/LFISuite:LFISuite"
        "vladko312/SSTImap:SSTImap"
        "sa7mon/S3Scanner:S3Scanner"
        "swisskyrepo/SSRFmap:SSRFmap"
        "Sh1Yo/x8:x8"
        "wireghoul/dotdotpwn:dotdotpwn"
    )
    
    for repo in "${repos[@]}"; do
        IFS=':' read -r repo_path tool_name <<< "$repo"
        repo_url="https://github.com/$repo_path.git"
        
        if [ ! -d "$tool_name" ]; then
            print_info "Cloning $tool_name..."
            if git clone "$repo_url" 2>/dev/null; then
                print_success "Cloned $tool_name"
            else
                print_warning "Failed to clone $tool_name"
            fi
        else
            print_info "Updating $tool_name..."
            cd "$tool_name"
            git pull 2>/dev/null
            cd ..
        fi
    done
    
    cd - > /dev/null
}

# Verify installations
verify_installations() {
    print_header "Verifying Installations"
    
    local tools=(
        "subfinder"
        "httpx"
        "katana"
        "nuclei"
        "assetfinder"
        "waybackurls"
        "gf"
        "amass"
        "curl"
        "jq"
        "git"
        "python3"
        "pip3"
    )
    
    for tool in "${tools[@]}"; do
        if command_exists "$tool"; then
            if [[ "$tool" == "python3" ]] || [[ "$tool" == "pip3" ]]; then
                version=$($tool --version 2>&1)
            else
                version=$($tool --version 2>&1 | head -n 1)
            fi
            echo -e "${GREEN}✓${NC} $tool: $version"
        else
            echo -e "${YELLOW}✗${NC} $tool: Not found"
        fi
    done
}

# Display usage information
show_usage() {
    cat << EOF

${BLUE}VulnScout Tool Installation Complete!${NC}

${YELLOW}Quick Start Guide:${NC}

1. Load Go environment (Linux):
   ${BLUE}source ~/.bashrc${NC}

2. Load Go environment (macOS):
   ${BLUE}source ~/.zprofile${NC}

3. Update all tools:
   ${BLUE}./update-all-tools.sh${NC}

4. Verify installations:
   ${BLUE}which subfinder httpx katana nuclei${NC}

5. Start using VulnScout:
   ${BLUE}cd c:\\Users\\spector\\Documents\\Tools\\VulnScout${NC}

${YELLOW}Important Notes:${NC}
- Some tools require additional API keys (Shodan, SecurityTrails, etc.)
- Configure ~/.config/subfinder/provider-config.yaml for API keys
- Use 'anew' to manage unique findings across scans
- Install optional tools at: ~/security-tools/

${YELLOW}Useful Commands:${NC}
- subfinder -d example.com -all -recursive
- httpx -l domains.txt -status-code
- katana -u https://example.com -d 5 -ps
- nuclei -l hosts.txt -t ~/nuclei-templates/

EOF
}

# Main installation flow
main() {
    print_header "VulnScout - Universal Installation Script"
    echo "This script will install all security reconnaissance tools"
    echo ""
    
    detect_os
    
    echo ""
    print_warning "This script requires sudo privileges for system package management"
    echo "Press Enter to continue or Ctrl+C to cancel..."
    read -r
    
    install_dependencies
    install_go_tools
    install_python_tools
    install_github_tools
    verify_installations
    
    echo ""
    show_usage
    print_success "Installation completed successfully!"
}

# Run main function
main
