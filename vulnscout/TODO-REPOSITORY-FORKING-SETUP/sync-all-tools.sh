#!/bin/bash

################################################################################
# VulnScout - Sync Forked Tools with Upstream
# Syncs all forked repositories with their original upstream versions
# Usage: bash sync-all-tools.sh [tools_dir]
################################################################################

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
TOOLS_DIR="${1:-./vulnscout-forks}"

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

# Map of tools to their original repositories
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

print_header "VulnScout Tools - Upstream Sync"
print_info "Syncing tools from: $TOOLS_DIR"
echo ""

# Initialize counters
total=0
success_count=0
failed_count=0
skipped_count=0

# Iterate through each tool directory
for tool_dir in "$TOOLS_DIR"/*; do
    if [ -d "$tool_dir" ]; then
        tool_name=$(basename "$tool_dir")

        # Skip if not a git repository
        if [ ! -d "$tool_dir/.git" ]; then
            print_warning "Skipping $tool_name (not a git repository)"
            ((skipped_count++))
            continue
        fi

        ((total++))
        upstream_url="${UPSTREAM_REPOS[$tool_name]}"

        print_info "[$((success_count+failed_count+1))/$((${#UPSTREAM_REPOS[@]}))] Syncing $tool_name..."

        cd "$tool_dir"

        # Get current branch (main or master)
        current_branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
        default_branch="main"

        # Try to detect the correct default branch
        if git rev-parse origin/master &>/dev/null; then
            default_branch="master"
        elif git rev-parse origin/main &>/dev/null; then
            default_branch="main"
        fi

        # Add upstream remote if it doesn't exist
        if ! git remote | grep -q upstream; then
            print_info "  Adding upstream remote..."
            if git remote add upstream "$upstream_url" 2>/dev/null; then
                print_success "  Added upstream remote"
            else
                print_warning "  Failed to add upstream remote"
            fi
        else
            print_info "  Upstream remote already exists"
        fi

        # Fetch from upstream
        print_info "  Fetching from upstream..."
        if git fetch upstream; then
            print_success "  Fetched successfully"
        else
            print_error "  Failed to fetch from upstream"
            ((failed_count++))
            cd - > /dev/null
            continue
        fi

        # Merge upstream changes
        print_info "  Merging upstream/$default_branch to origin/$default_branch..."
        if git checkout "$default_branch" 2>/dev/null; then
            if git merge "upstream/$default_branch" --no-edit; then
                print_success "  Merged successfully"

                # Push to origin
                if git push origin "$default_branch" 2>/dev/null; then
                    print_success "  Pushed to origin"
                    ((success_count++))
                else
                    print_warning "  Failed to push to origin (may require authentication)"
                    ((failed_count++))
                fi
            else
                print_warning "  Merge conflict detected"
                print_info "  Please resolve conflicts manually in $tool_dir"
                ((failed_count++))
            fi
        else
            print_error "  Failed to checkout $default_branch"
            ((failed_count++))
        fi

        cd - > /dev/null
        echo ""
    fi
done

# Print summary
print_header "Sync Summary"
echo "Total repositories: $total"
echo -e "${GREEN}Successfully synced: $success_count${NC}"
if [ $failed_count -gt 0 ]; then
    echo -e "${RED}Failed: $failed_count${NC}"
fi
if [ $skipped_count -gt 0 ]; then
    echo -e "${YELLOW}Skipped: $skipped_count${NC}"
fi
echo ""

if [ $failed_count -eq 0 ] && [ $success_count -gt 0 ]; then
    print_success "All repositories synced successfully!"
    print_info "Run 'bash install-from-forks.sh' to reinstall with latest versions"
else
    print_warning "Some syncs failed. Please check manually."
fi

echo ""
print_info "Next steps:"
echo "  1. Review any merge conflicts"
echo "  2. Test updated tools"
echo "  3. Commit any changes to your forks"
echo "  4. Reinstall: pip install --upgrade -r requirements-forked.txt"
