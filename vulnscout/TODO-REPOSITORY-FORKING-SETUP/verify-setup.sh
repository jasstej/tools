#!/bin/bash

################################################################################
# VulnScout - Verification Script
# Checks if all components are installed correctly
# Usage: bash verify-setup.sh [tools_dir]
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Defaults
TOOLS_DIR="${1:-$HOME/vulnscout-forks}"
VENV_PATH="$HOME/.vulnscout-env"
CHECKS_PASSED=0
CHECKS_FAILED=0

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

print_check() {
    echo -n "  [$1/...] $2"
}

print_pass() {
    echo -e "${GREEN}✓${NC}"
    ((CHECKS_PASSED++))
}

print_fail() {
    echo -e "${RED}✗${NC}"
    ((CHECKS_FAILED++))
}

print_warn() {
    echo -e "${YELLOW}⚠${NC}"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# Verification functions
verify_system_tools() {
    print_section "Verifying System Tools"

    print_check "1" "Git is installed: "
    command -v git &> /dev/null && print_pass || { print_fail; }

    print_check "2" "Python 3 is installed: "
    command -v python3 &> /dev/null && print_pass || { print_fail; }

    print_check "3" "pip3 is installed: "
    command -v pip3 &> /dev/null && print_pass || { print_fail; }
}

verify_venv() {
    print_section "Verifying Virtual Environment"

    print_check "1" "venv directory exists at $VENV_PATH: "
    [ -d "$VENV_PATH" ] && print_pass || { print_fail; return 1; }

    print_check "2" "venv bin/activate exists: "
    [ -f "$VENV_PATH/bin/activate" ] && print_pass || { print_fail; return 1; }

    print_check "3" "venv python3 exists: "
    [ -f "$VENV_PATH/bin/python3" ] && print_pass || { print_fail; return 1; }

    # Check if we can activate
    print_check "4" "venv can be activated: "
    if bash -c "source $VENV_PATH/bin/activate && python3 --version &> /dev/null"; then
        print_pass
    else
        print_fail
    fi
}

verify_repositories() {
    print_section "Verifying Cloned Repositories"

    if [ ! -d "$TOOLS_DIR" ]; then
        print_error "Tools directory not found: $TOOLS_DIR"
        print_info "Run: bash clone-all-tools.sh $TOOLS_DIR"
        return 1
    fi

    local repos_found=0
    local repos_expected=10

    # List of expected repos
    local expected_repos=(
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

    print_info "Expected repositories: ${#expected_repos[@]}"
    echo ""

    for repo in "${expected_repos[@]}"; do
        print_check "$((repos_found+1))" "Repository '$repo' exists: "

        if [ -d "$TOOLS_DIR/$repo" ]; then
            print_pass
            ((repos_found++))

            # Check if it's a git repo
            if [ -d "$TOOLS_DIR/$repo/.git" ]; then
                echo -n "    └─ Is git repository: "
                print_pass
            else
                echo -n "    └─ Is git repository: "
                print_warn
            fi
        else
            print_fail
        fi
    done

    echo ""
    print_info "Found: $repos_found/$repos_expected repositories"

    if [ $repos_found -eq $repos_expected ]; then
        print_success "All repositories present"
        return 0
    else
        print_error "$((repos_expected - repos_found)) repositories missing"
        return 1
    fi
}

verify_installations() {
    print_section "Verifying Tool Installations"

    # Activate venv
    source "$VENV_PATH/bin/activate" 2>/dev/null || true

    local tools_found=0
    local tools_checked=0

    # List of core tools to check
    local tools_to_check=(
        "commix"
        "ghauri"
        "wafw00f"
        "LinkFinder"
        "paramspider"
        "arjun"
        "SubDomainizer"
        "jwt-tool"
    )

    for tool in "${tools_to_check[@]}"; do
        ((tools_checked++))
        print_check "$tools_checked" "Tool '$tool' is installed: "

        # Try to import as Python package
        if python3 -c "import pkg_resources; pkg_resources.get_distribution('$tool')" 2>/dev/null; then
            print_pass
            ((tools_found++))
        else
            # Try to execute command
            if command -v "$tool" &> /dev/null 2>&1; then
                print_pass
                ((tools_found++))
            else
                print_warn
            fi
        fi
    done

    echo ""
    if [ $tools_found -gt 0 ]; then
        print_info "Tools installed: ~$tools_found (some may show as not found if not in PATH)"
    else
        print_info "No tools found installed yet"
        print_info "Run installation: pip install -r requirements-forked.txt"
    fi
}

verify_upstream_remotes() {
    print_section "Verifying Upstream Remotes"

    if [ ! -d "$TOOLS_DIR" ]; then
        print_error "Tools directory not found"
        return 1
    fi

    local remotes_found=0
    local repos_checked=0

    for repo_dir in "$TOOLS_DIR"/*; do
        if [ -d "$repo_dir/.git" ]; then
            ((repos_checked++))
            repo_name=$(basename "$repo_dir")

            if cd "$repo_dir" && git remote | grep -q upstream; then
                print_check "$repos_checked" "Upstream remote for '$repo_name': "
                print_pass
                ((remotes_found++))
            else
                print_check "$repos_checked" "Upstream remote for '$repo_name': "
                print_warn
            fi
            cd - > /dev/null
        fi
    done

    echo ""
    print_info "Repos with upstream: $remotes_found/$repos_checked"

    if [ $remotes_found -lt $repos_checked ]; then
        print_info "Configure remotes with: bash configure-upstream.sh $TOOLS_DIR"
    fi
}

generate_report() {
    print_section "Verification Report"

    local total=$((CHECKS_PASSED + CHECKS_FAILED))

    echo "Checks Passed: ${GREEN}$CHECKS_PASSED${NC}"
    echo "Checks Failed: ${RED}$CHECKS_FAILED${NC}"
    echo "Total Checks: $total"
    echo ""

    if [ $CHECKS_FAILED -eq 0 ]; then
        print_success "All checks passed! Setup is complete."
        return 0
    else
        print_error "$CHECKS_FAILED check(s) failed"
        return 1
    fi
}

show_recommendations() {
    print_section "Recommendations"

    if [ ! -d "$TOOLS_DIR" ]; then
        print_info "1. Clone repositories:"
        echo "   bash clone-all-tools.sh $TOOLS_DIR"
    fi

    if [ -d "$VENV_PATH" ]; then
        print_info "2. Activate virtual environment:"
        echo "   source $VENV_PATH/bin/activate"
        echo ""
        print_info "3. Install all tools:"
        echo "   pip install -r requirements-forked.txt"
    fi

    print_info "4. Configure upstream remotes:"
    echo "   bash configure-upstream.sh $TOOLS_DIR"
    echo ""

    print_info "5. Setup automatic sync (add to crontab):"
    echo "   0 0 * * * bash $(pwd)/sync-all-tools.sh $TOOLS_DIR"
}

# Main
main() {
    print_header "VulnScout Setup Verification"
    echo ""
    print_info "Verification Date: $(date)"
    print_info "Tools Directory: $TOOLS_DIR"
    print_info "Virtual Environment: $VENV_PATH"
    echo ""

    verify_system_tools
    verify_venv
    verify_repositories
    verify_installations
    verify_upstream_remotes

    echo ""
    generate_report
    local report_status=$?

    echo ""
    show_recommendations

    echo ""
    echo "For more information, see: README_FORKING_SETUP.md"
    echo ""

    return $report_status
}

# Run
main
