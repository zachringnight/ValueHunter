# Admin Quick Start - Repository Secret Setup

**For Repository Administrators Only**

## Required Action: Add CFBD_API_KEY Secret

To enable automated data fetching via GitHub Actions, you must configure the `CFBD_API_KEY` repository secret.

### Quick Steps

1. **Get API Key**: https://collegefootballdata.com/key
2. **Add Secret**:
   - Go to: `Settings` → `Secrets and variables` → `Actions`
   - Click: `New repository secret`
   - Name: `CFBD_API_KEY`
   - Value: Your CFBD API key
   - Click: `Add secret`

3. **Test**: Run the "Fetch CFB data (Direct API)" workflow from the Actions tab

### Important Notes

- ⚠️ The secret name must be exactly: `CFBD_API_KEY` (case-sensitive)
- 🔒 Never commit API keys to the repository
- ✅ The workflows are already configured to use this secret
- 📖 See [SETUP_REPOSITORY_SECRET.md](SETUP_REPOSITORY_SECRET.md) for detailed instructions

### Workflows That Require This Secret

- `.github/workflows/cfb-data-fetch.yml` - Fetches CFB data
- `.github/workflows/publish_reports.yml` - Generates weekly reports

---

**Need Help?** See the [detailed setup guide](SETUP_REPOSITORY_SECRET.md) or open an issue.
