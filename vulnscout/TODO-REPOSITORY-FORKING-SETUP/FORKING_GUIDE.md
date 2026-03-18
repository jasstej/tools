# VulnScout Repository Forking Guide

Complete guide for forking all VulnScout dependencies into a central GitHub organization.

## All Repositories to Fork

### Core Tools (High Priority)

1. **commix** - Command Injection Testing
   - Original: https://github.com/commixproject/commix
   - Fork as: `vulnscout-commix` or `commix`
   - Language: Python

2. **ghauri** - SQL Injection Scanner
   - Original: https://github.com/r0ot-h3r0/ghauri
   - Fork as: `vulnscout-ghauri` or `ghauri`
   - Language: Python

3. **wafw00f** - WAF Fingerprinting
   - Original: https://github.com/EnableSecurity/wafw00f
   - Fork as: `vulnscout-wafw00f` or `wafw00f`
   - Language: Python

4. **LinkFinder** - Endpoint Discovery
   - Original: https://github.com/GerbenJavado/LinkFinder
   - Fork as: `vulnscout-linkfinder` or `LinkFinder`
   - Language: Python

### Utility Tools (Medium Priority)

5. **paramspider** - Parameter Discovery
   - Original: https://github.com/devanshbatham/ParamSpider
   - Fork as: `vulnscout-paramspider` or `paramspider`
   - Language: Python

6. **arjun** - HTTP Parameter Fuzzer
   - Original: https://github.com/s0md3v/Arjun
   - Fork as: `vulnscout-arjun` or `arjun`
   - Language: Python

7. **SubDomainizer** - Subdomain Extraction
   - Original: https://github.com/nsonaniya2010/SubDomainizer
   - Fork as: `vulnscout-subdomainizer` or `SubDomainizer`
   - Language: Python

### Support Tools (Optional)

8. **jwt-tool** - JWT Testing
   - Original: https://github.com/ticarpi/jwt_tool
   - Fork as: `vulnscout-jwt-tool` or `jwt-tool`
   - Language: Python

9. **dotdotpwn** - Path Traversal Scanner
   - Original: https://github.com/wireghoul/dotdotpwn
   - Fork as: `vulnscout-dotdotpwn` or `dotdotpwn`
   - Language: Perl/Python

10. **anew** - Output Filtering Utility
    - Original: https://github.com/tomnomnom/anew
    - Fork as: `vulnscout-anew` or `anew`
    - Language: Go

## GitHub Organization Setup

### Step 1: Create GitHub Organization
1. Go to https://github.com/organizations/new
2. Create organization: `vulnscout-tools` or similar
3. Set organization name and billing email

### Step 2: Fork Repositories

You have two options:

#### Option A: Manual Fork (GUI)
1. Visit each original repository link above
2. Click **Fork** button
3. Select your organization as destination
4. Optionally add prefix: `vulnscout-` to repository name

#### Option B: GitHub CLI (Automated)
```bash
# Install GitHub CLI if not already installed
# https://cli.github.com

# Login to GitHub
gh auth login

# Fork all repositories to YOUR_ORG
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

### Step 3: Local Mirror Setup

See `clone-all-tools.sh` script in this directory for setting up local mirrors.

## Repository Organization

### Recommended Directory Structure
```
~/vulnscout-forks/
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

### Setup Commands
```bash
# Create master directory
mkdir -p ~/vulnscout-forks
cd ~/vulnscout-forks

# Run the clone script (see below)
bash ~/path/to/clone-all-tools.sh
```

## Installing from Forked Repos

### Method 1: From Local Clones
```bash
pip install ~/vulnscout-forks/commix
pip install ~/vulnscout-forks/ghauri
pip install ~/vulnscout-forks/wafw00f
# ... etc
```

### Method 2: From GitHub Organization
```bash
pip install git+https://github.com/YOUR_ORG/commix.git
pip install git+https://github.com/YOUR_ORG/ghauri.git
pip install git+https://github.com/YOUR_ORG/wafw00f.git
# ... etc
```

### Method 3: Using requirements-forked.txt
See `requirements-forked.txt` in this directory for complete installation.

## Maintaining Forks

### Sync with Upstream
Keep forks updated with original repositories:

```bash
cd ~/vulnscout-forks/commix
git remote add upstream https://github.com/commixproject/commix.git
git fetch upstream
git merge upstream/main
git push origin main
```

### Automated Sync (GitHub Actions)
Add to `.github/workflows/sync-upstream.yml` in each fork:

```yaml
name: Sync Upstream

on:
  schedule:
    - cron: '0 0 * * 0'  # Weekly sync
  workflow_dispatch:

jobs:
  sync:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Sync fork with upstream
        run: |
          git config --global user.name "GitHub Action"
          git config --global user.email "action@github.com"
          git remote add upstream ${{ github.event.repository.clone_url }}
          git fetch upstream
          git checkout main
          git merge upstream/main
          git push origin main
```

## Modification Tracking

### Changes Log (each fork should have)
```markdown
# Changes from Original

## Security Patches
- [Date] Security patch for XYZ (CVE-xxxx)

## Performance Improvements
- [Date] Optimized ABC

## Bug Fixes
- [Date] Fixed issue with XYZ

## Custom Additions
- [Date] Added custom feature ABC
```

## Version Control

### Git Tags
Tag each fork with upstream version:
```bash
git tag -a vulnscout-v1.0.0-commix-1.0.5 -m "Based on commix v1.0.5"
git push origin vulnscout-v1.0.0-commix-1.0.5
```

## Documentation

### README Updates
Update README.md in each fork to include:
```markdown
# [Tool Name] - VulnScout Edition

This is a fork of [original repo link] maintained by the VulnScout project.

## Original Repository
- [Link to original]

## Changes from Original
[See CHANGES.md]

## Installation
```bash
pip install git+https://github.com/YOUR_ORG/[tool-name].git
```
```

## CI/CD Integration

### GitHub Actions Template
Create `.github/workflows/ci.yml` in each fork to:
- Run tests from original project
- Check for upstream updates
- Validate forks are still compatible
- Publish release notes

## Checklist for Each Fork

- [ ] Fork created in your organization
- [ ] Default branch set (usually `main` or `master`)
- [ ] Branch protection rules added
- [ ] README.md updated with fork information
- [ ] CHANGES.md or CHANGELOG.md created
- [ ] Upstream remote configured
- [ ] GitHub Actions workflow added
- [ ] Documentation updated
- [ ] Installation tested
- [ ] Version tagged

## Quick Reference Commands

```bash
# Clone all forks locally
bash clone-all-tools.sh

# Activate environment
source ~/.vulnscout-env/bin/activate

# Install from local forks
pip install -r requirements-forked.txt

# Check all installations
pip list | grep -E "commix|ghauri|wafw00f|LinkFinder|paramspider|arjun|SubDomainizer|jwt|dotdotpwn|anew"
```

## Support & Issues

- Report security issues to original authors first
- Document any custom changes clearly
- Keep forks in sync with upstream when possible
- Coordinate with team on major modifications
