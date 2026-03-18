#!/bin/bash

################################################################################
# VulnScout - Configure Upstream Remotes
# Configures upstream remotes for all cloned repositories
# Usage: bash configure-upstream.sh [tools_dir]
################################################################################

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
TOOLS_DIR="${1:-.}"

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

# Map of repos to their upstream URLs
declare -A UPSTREAM_REPOS=(
    ["commix"]="https://github.com/commixproject/commix.git"
    ["ghauri"]="https://github.com/r0ot-h3r0/ghauri.git"
    ["wafw00f"]="https://github.com/EnableSecurity/wafw00f.git"
    ["LinkFinder"]="https://github.com/GerbenJavado/LinkFinder.git"
    ["paramspider"]="https://github.com/devanshbatham/ParamSpider.git"
    ["arjun"]="https://github.com/s0md3v/Arjun.git"
    ["SubDomainizer"]="https://github.com/nsonaniya2010/SubDomainizer.git"
    ["jwt-tool"]="https://github.com/ticarpi/jwt_tool.git"
    ["dotdotpwn"]="https://github.com/wireghoul/dotdotpwn.git"
    ["anew"]="https://github.com/tomnomnom/anew.git"
)

# Check if tools directory exists
if [ ! -d "$TOOLS_DIR" ]; then
    print_error "Tools directory not found: $TOOLS_DIR"
    exit 1
fi

print_header "VulnScout - Configure Upstream Remotes"
print_info "Tools Directory: $(cd "$TOOLS_DIR" && pwd)"
echo ""

# Initialize counters
total=0
success_count=0
failed_count=0
skipped_count=0

# Iterate through each repository
for repo_name in "${!UPSTREAM_REPOS[@]}"; do
    upstream_url="${UPSTREAM_REPOS[$repo_name]}"
    repo_path="$TOOLS_DIR/$repo_name"

    ((total++))

    print_info "[$total/${#UPSTREAM_REPOS[@]}] Configuring $repo_name..."

    # Check if repository exists
    if [ ! -d "$repo_path" ]; then
        print_warning "Repository not found: $repo_path"
        ((skipped_count++))
        continue
    fi

    # Check if it's a git repository
    if [ ! -d "$repo_path/.git" ]; then
        print_warning "Not a git repository: $repo_path"
        ((skipped_count++))
        continue
    fi

    cd "$repo_path"

    # Check if upstream already exists
    if git remote | grep -q upstream; then
        print_warning "Upstream remote already configured"

        # Show current upstream
        current_upstream=$(git remote get-url upstream)
        if [ "$current_upstream" = "$upstream_url" ]; then
            print_success "Upstream matches expected URL"
            ((success_count++))
        else
            print_warning "Upstream URL differs from expected"
            echo "  Current:  $current_upstream"
            echo "  Expected: $upstream_url"

            # Ask to update
            read -p "  Update upstream remote? (y/n) " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                if git remote set-url upstream "$upstream_url"; then
                    print_success "Updated upstream remote"
                    ((success_count++))
                else
                    print_error "Failed to update upstream remote"
                    ((failed_count++))
                fi
            else
                print_warning "Skipped update"
                ((skipped_count++))
            fi
        fi
    else
        # Add upstream remote
        if git remote add upstream "$upstream_url"; then
            print_success "Added upstream remote"

            # Fetch from upstream
            if git fetch upstream; then
                print_success "Fetched from upstream"
                ((success_count++))
            else
                print_warning "Failed to fetch from upstream"
                ((failed_count++))
            fi
        else
            print_error "Failed to add upstream remote"
            ((failed_count++))
        fi
    fi

    cd - > /dev/null
    echo ""
done

# Print summary
print_header "Configuration Summary"
echo "Total Repositories: $total"
echo -e "${GREEN}Configured: $success_count${NC}"
if [ $failed_count -gt 0 ]; then
    echo -e "${RED}Failed: $failed_count${NC}"
fi
if [ $skipped_count -gt 0 ]; then
    echo -e "${YELLOW}Skipped: $skipped_count${NC}"
fi
echo ""

if [ $failed_count -eq 0 ]; then
    print_success "All upstream remotes configured successfully!"
else
    print_warning "$failed_count repository(ies) failed configuration"
fi

echo ""
print_info "Next steps:"
echo "  1. Test upstream remotes:"
echo "     cd $TOOLS_DIR/commix && git fetch upstream"
echo ""
echo "  2. Sync with upstream:"
echo "     bash sync-all-tools.sh $TOOLS_DIR"
echo ""
echo "  3. Setup automatic daily sync:"
echo "     Add to crontab: 0 0 * * * bash $(pwd)/sync-all-tools.sh $TOOLS_DIR"
