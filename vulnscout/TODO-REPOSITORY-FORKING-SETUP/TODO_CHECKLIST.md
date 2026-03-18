# TODO: Repository Forking & Centralized Setup

Complete checklist for setting up all VulnScout security tools with forked repositories.

## 🎯 Setup Checklist

### Phase 1: GitHub Organization Setup (5 min)
- [ ] Create GitHub organization (or use existing)
- [ ] Organization name: `_____________________`
- [ ] Visit: https://github.com/organizations/new

### Phase 2: Fork All Repositories (15-20 min)

**Option A: Using GitHub CLI (Automated)**
```bash
gh auth login
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

**Repositories to Fork** (if doing manually):
- [ ] commix - https://github.com/commixproject/commix
- [ ] ghauri - https://github.com/r0ot-h3r0/ghauri
- [ ] wafw00f - https://github.com/EnableSecurity/wafw00f
- [ ] LinkFinder - https://github.com/GerbenJavado/LinkFinder
- [ ] paramspider - https://github.com/devanshbatham/ParamSpider
- [ ] arjun - https://github.com/s0md3v/Arjun
- [ ] SubDomainizer - https://github.com/nsonaniya2010/SubDomainizer
- [ ] jwt-tool - https://github.com/ticarpi/jwt_tool
- [ ] dotdotpwn - https://github.com/wireghoul/dotdotpwn
- [ ] anew - https://github.com/tomnomnom/anew

### Phase 3: Automated Setup (20-30 min)
```bash
cd ~/Documents/github/tools/vulnscout/TODO-REPOSITORY-FORKING-SETUP
bash setup-everything.sh ~/vulnscout-forks YOUR_ORG
```

- [ ] Virtual environment created
- [ ] All repositories cloned
- [ ] All tools installed
- [ ] Setup completed successfully

### Phase 4: Verification (5 min)
```bash
bash verify-setup.sh ~/vulnscout-forks
```

- [ ] All system tools verified
- [ ] Virtual environment validated
- [ ] All 10 repositories present
- [ ] Upstream remotes configured
- [ ] Tools installed and working

### Phase 5: Configure Synchronization (5 min)
```bash
bash configure-upstream.sh ~/vulnscout-forks
```

- [ ] Upstream remotes configured for all repos
- [ ] Test sync: `cd ~/vulnscout-forks/commix && git fetch upstream`

### Phase 6: Setup Automatic Syncing (5 min)
```bash
# Add to crontab (runs daily at midnight)
crontab -e
# Add line: 0 0 * * * bash ~/Documents/github/tools/vulnscout/sync-all-tools.sh ~/vulnscout-forks
```

- [ ] Cron job added for daily sync
- [ ] Automatic upstream syncing enabled

### Phase 7: Team Setup (Optional)
- [ ] Add team members to organization
- [ ] Configure branch protection rules
- [ ] Setup GitHub Actions workflows
- [ ] Enable audit logging

---

## 📂 Directory Structure After Setup

```
$HOME/vulnscout-forks/          ← All cloned repositories
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

$HOME/.vulnscout-env/           ← Python virtual environment (150MB)
├── bin/
├── lib/
├── include/
└── ...

~/Documents/github/tools/vulnscout/  ← VulnScout scripts & docs
├── setup-everything.sh          ⭐ Master setup script
├── clone-all-tools.sh
├── sync-all-tools.sh
├── verify-setup.sh
├── configure-upstream.sh
└── ... (documentation files)
```

---

## 🚀 Quick Commands Reference

### Activate Virtual Environment
```bash
source ~/.vulnscout-env/bin/activate
```

### List Installed Tools
```bash
source ~/.vulnscout-env/bin/activate
pip list | grep -E "commix|ghauri|wafw00f|LinkFinder|paramspider|arjun|SubDomainizer|jwt|dotdotpwn|anew"
```

### Update All Tools
```bash
bash ~/Documents/github/tools/vulnscout/sync-all-tools.sh ~/vulnscout-forks
```

### Reinstall Tools After Update
```bash
source ~/.vulnscout-env/bin/activate
pip install --upgrade -r ~/Documents/github/tools/vulnscout/requirements-forked.txt
```

### Test a Tool
```bash
source ~/.vulnscout-env/bin/activate
commix --version
ghauri --version
wafw00f --version
```

---

## 📚 Documentation Files

Read in this order:

1. **README_FORKING_SETUP.md** - Overview and quick start
2. **FORKING_GUIDE.md** - Detailed forking procedures
3. **SETUP_FORKED_REPOS.md** - Installation and troubleshooting
4. **PYTHON_PACKAGES.md** - Tool information
5. **FILE_INDEX.md** - Complete file reference

All files in: `~/Documents/github/tools/vulnscout/`

---

## ⏱️ Total Time Estimate

| Phase | Duration | Status |
|-------|----------|--------|
| GitHub Setup | 5 min | ⏳ TODO |
| Fork Repos | 15-20 min | ⏳ TODO |
| Auto Setup | 20-30 min | ⏳ TODO |
| Verification | 5 min | ⏳ TODO |
| Configure Sync | 10 min | ⏳ TODO |
| Team Setup | Optional | ⏳ TODO |
| **TOTAL** | **55-70 min** | ⏳ TODO |

---

## 📋 10 Tools Being Forked

| # | Tool | Purpose | Priority |
|---|------|---------|----------|
| 1 | commix | Command Injection Testing | High |
| 2 | ghauri | SQL Injection Scanning | High |
| 3 | wafw00f | WAF Fingerprinting | High |
| 4 | LinkFinder | Endpoint Discovery | High |
| 5 | paramspider | Parameter Discovery | Medium |
| 6 | arjun | Parameter Fuzzing | Medium |
| 7 | SubDomainizer | Subdomain Extraction | Medium |
| 8 | jwt-tool | JWT Testing | Optional |
| 9 | dotdotpwn | Path Traversal Testing | Optional |
| 10 | anew | Output Filtering | Optional |

---

## ✅ Success Criteria

Setup is complete when:
- [ ] All 10 repositories cloned to ~/vulnscout-forks/
- [ ] Python virtual environment exists at ~/.vulnscout-env
- [ ] All tools installed in virtual environment
- [ ] `verify-setup.sh` passes all checks
- [ ] Can activate venv and run: `commix --version`
- [ ] Upstream remotes configured for all repos
- [ ] Cron job running for daily sync

---

## 🆘 Troubleshooting

### Clone Failed
```bash
cd vulnscout/
bash clone-all-tools.sh ~/vulnscout-forks YOUR_ORG
```

### Installation Failed
```bash
source ~/.vulnscout-env/bin/activate
pip install --upgrade pip
pip install -r requirements-forked.txt -v
```

### Need to Verify
```bash
bash verify-setup.sh ~/vulnscout-forks
```

### Need to Update
```bash
bash sync-all-tools.sh ~/vulnscout-forks
```

---

## 📞 Support Resources

- **Setup Issues**: See SETUP_FORKED_REPOS.md - Troubleshooting
- **Forking Help**: See FORKING_GUIDE.md
- **Tool Info**: See PYTHON_PACKAGES.md
- **File Reference**: See FILE_INDEX.md

---

## 🎯 Next Action

**👉 Start with Phase 1: Create GitHub organization**

Once organization is created, proceed to Phase 2: Fork all repositories

---

**Last Updated**: March 2026
**Status**: Ready to Execute
**Total Files**: 9 new + 1 modified
**Total Documentation**: 9 comprehensive guides
