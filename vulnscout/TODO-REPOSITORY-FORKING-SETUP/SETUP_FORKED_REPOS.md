# VulnScout Repository Forking & Setup

Complete guide to fork all VulnScout security tools into a centralized repository structure.

## Quick Start

### 1. Fork All Repositories to Your GitHub Organization

**Option A: Using GitHub CLI** (Automated)
```bash
# Replace YOUR_ORG with your GitHub organization
gh repo fork commixproject/commix --org YOUR_ORG --clone=false
gh repo fork r0ot-h3r0/ghauri --org YOUR_ORG --clone=false
gh repo fork EnableSecurity/wafw00f --org YOUR_ORG --clone=false
gh repo fork GerbenJavado/LinkFinder --org YOUR_ORG --clone=false
gh repo fork devanshbatham/ParamSpider --org YOUR_ORG --clone=false
gh repo fork s0md3v/Arjun --org YOUR_ORG --clone=false
gh repo fork nsonaniya2010/SubDomainizer --org YOUR_ORG --clone=false
gh repo fork ticarpi/jwt_tool --org YOUR_ORG --clone=false
gh repo fork wireghoul/dotdotpwn --org YOUR_ORG --clone=false
gh repo fork tomnomnom/anew --org YOUR_ORG --clone=false
```

**Option B: Manual Fork (GUI)**
- Visit each repository link in `FORKING_GUIDE.md`
- Click "Fork" button
- Select your organization as destination

### 2. Clone All Forks Locally

```bash
# Create directory for cloned tools
mkdir -p ~/vulnscout-forks

# Run the clone script
bash clone-all-tools.sh ~/vulnscout-forks YOUR_ORG
```

The script will:
- Clone all 10 repositories
- Create directory structure documentation
- Generate installation scripts
- Show clone summary

### 3. Install Forked Tools

```bash
# Activate virtual environment
source ~/.vulnscout-env/bin/activate

# Install from local clones (recommended)
pip install -r requirements-forked.txt

# OR install from GitHub organization
pip install -r requirements-forked-github.txt
```

## File Structure After Setup

```
vulnscout/
├── install-all-tools.sh          # Main installation script
├── clone-all-tools.sh             # Clone forked repos script
├── FORKING_GUIDE.md               # Detailed forking guide
├── PYTHON_PACKAGES.md             # Python packages overview
├── requirements-forked.txt        # Install from local clones
├── requirements-forked-github.txt # Install from GitHub org
└── vulnscout-forks/              # Cloned repositories
    ├── commix/
    ├── ghauri/
    ├── wafw00f/
    ├── LinkFinder/
    ├── paramspider/
    ├── arjun/
    ├── SubDomainizer/
    ├── jwt-tool/
    ├── dotdotpwn/
    └── anew/
```

## Repository Overview

### 10 Tools Being Forked

| # | Tool | Type | Purpose |
|---|------|------|---------|
| 1 | **commix** | Python | Command Injection Testing |
| 2 | **ghauri** | Python | SQL Injection Scanning |
| 3 | **wafw00f** | Python | WAF Fingerprinting |
| 4 | **LinkFinder** | Python | Endpoint Discovery |
| 5 | **paramspider** | Python | Parameter Discovery |
| 6 | **arjun** | Python | Parameter Fuzzing |
| 7 | **SubDomainizer** | Python | Subdomain Extraction |
| 8 | **jwt-tool** | Python | JWT Testing |
| 9 | **dotdotpwn** | Perl/Python | Path Traversal Testing |
| 10 | **anew** | Go | Output Filtering |

## Installation Methods

### Method 1: Local Clones (Recommended)
```bash
cd ~/vulnscout-forks
source ~/.vulnscout-env/bin/activate
pip install -r ../requirements-forked.txt
```

**Advantages:**
- Fast installation
- No internet required after cloning
- Easy to modify tools locally
- Offline access

### Method 2: From GitHub Organization
```bash
source ~/.vulnscout-env/bin/activate
pip install -r requirements-forked-github.txt
```

**Advantages:**
- Always latest version from your fork
- No local storage needed
- Easy to update
- Share across team

### Method 3: Direct Installation (One Tool)
```bash
# From local clone
pip install ~/vulnscout-forks/commix

# From GitHub
pip install git+https://github.com/YOUR_ORG/commix.git
```

## Keeping Forks Updated

### Manual Sync (One Tool)
```bash
cd ~/vulnscout-forks/commix
git remote add upstream https://github.com/commixproject/commix.git
git fetch upstream
git merge upstream/main
git push origin main
```

### Sync All Tools
```bash
#!/bin/bash
cd ~/vulnscout-forks

for dir in */; do
    if [ -d "$dir/.git" ]; then
        echo "Updating $dir..."
        cd "$dir"

        # Add upstream if not exists
        git remote add upstream https://github.com/ORIGINAL_OWNER/$dir.git 2>/dev/null || true

        # Sync with upstream
        git fetch upstream
        git merge upstream/main 2>/dev/null || git merge upstream/master 2>/dev/null || true
        git push origin main 2>/dev/null || git push origin master 2>/dev/null || true

        cd ..
    fi
done
```

### Use GitHub Sync Button (GUI)
Each fork on GitHub has a "Sync fork" button for quick synchronization.

## Virtual Environment Management

### Activate
```bash
source ~/.vulnscout-env/bin/activate
```

### Deactivate
```bash
deactivate
```

### Check Status
```bash
which python3  # Should show ~/.vulnscout-env/bin/python3
```

### List Installed Packages
```bash
pip list
```

## Troubleshooting

### Clone Failed
```bash
# Check GitHub organization exists
gh org list

# Check you have write access
gh repo view --jq .permissions.admin

# Re-run with specific org
bash clone-all-tools.sh ~/vulnscout-forks YOUR_ORG
```

### Installation Failed
```bash
# Ensure venv is activated
source ~/.vulnscout-env/bin/activate

# Upgrade pip
pip install --upgrade pip

# Try installing specific tool
pip install ~/vulnscout-forks/commix -v
```

### SSH vs HTTPS Issues
```bash
# If using SSH, ensure keys are configured
ssh -T git@github.com

# For HTTPS, use personal token if private repos
# Set git config
git config --global credential.helper store
```

## Maintenance Checklist

- [ ] All 10 repositories forked
- [ ] All repositories cloned locally
- [ ] Virtual environment created
- [ ] All tools installed successfully
- [ ] Upstream remotes configured
- [ ] GitHub Actions workflows added
- [ ] Documentation updated in each fork
- [ ] Weekly sync schedule set
- [ ] Team access configured
- [ ] Backup strategy planned

## Advanced: GitHub Actions CI/CD

### Auto-update Forks
Add to `.github/workflows/sync.yml` in each fork:

```yaml
name: Sync with Upstream

on:
  schedule:
    - cron: '0 0 * * 0'
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Sync fork
        run: |
          git remote add upstream ORIGINAL_REPO_URL || true
          git fetch upstream
          git checkout main || git checkout master
          git merge upstream/main || git merge upstream/master || true
          git push origin main || git push origin master || true
```

## Security Considerations

- **Access Control**: Set branch protection rules on main/master
- **Signing**: Enable commit signing for security patches
- **Auditing**: Enable GitHub audit logs
- **Secrets**: Never commit API keys or credentials
- **Dependencies**: Keep tool dependencies updated

## Additional Resources

- [FORKING_GUIDE.md](./FORKING_GUIDE.md) - Detailed forking instructions
- [PYTHON_PACKAGES.md](./PYTHON_PACKAGES.md) - Package information
- [install-all-tools.sh](./install-all-tools.sh) - Main installer
- [clone-all-tools.sh](./clone-all-tools.sh) - Clone script

## Quick Reference

```bash
# Full setup from scratch
mkdir -p ~/vulnscout-forks
bash ./clone-all-tools.sh ~/vulnscout-forks YOUR_ORG
source ~/.vulnscout-env/bin/activate
pip install -r ./requirements-forked.txt

# Verify installation
pip list | grep -E "commix|ghauri|wafw00f"

# Check tool versions
commix --version
ghauri --version
wafw00f --version

# Sync all tools
bash ./sync-all-tools.sh
```

## Support

For issues with:
- **Forking**: See FORKING_GUIDE.md
- **Installation**: See install-all-tools.sh
- **Cloning**: See clone-all-tools.sh
- **Packages**: See PYTHON_PACKAGES.md
