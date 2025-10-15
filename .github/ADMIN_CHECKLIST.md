# Repository Setup Checklist for Administrators

This checklist helps repository administrators ensure the ValueHunter repository is properly configured for automated workflows.

## Initial Setup

### ✅ Step 1: Configure CFBD API Key Secret

**Status**: 🔴 Required - Must be completed before running workflows

**Action Required**:
1. Obtain CFBD API key from https://collegefootballdata.com/key
2. Add repository secret:
   - Navigate to: `Settings` → `Secrets and variables` → `Actions`
   - Click: `New repository secret`
   - Name: `CFBD_API_KEY`
   - Value: Your CFBD API key
   - Click: `Add secret`

**Documentation**: See [SETUP_REPOSITORY_SECRET.md](SETUP_REPOSITORY_SECRET.md)

**Verification**:
- [ ] Secret named `CFBD_API_KEY` is added to repository
- [ ] "Fetch CFB data (Direct API)" workflow runs successfully
- [ ] No authentication errors in workflow logs

### ✅ Step 2: Optional Secrets (if using Notion integration)

**Status**: 🟡 Optional - Only needed for Notion integration

**Action** (if using Notion):
1. Add `NOTION_TOKEN` secret
2. Add `NOTION_DATABASE_ID` secret

**Documentation**: See workflow file comments in `.github/workflows/publish_reports.yml`

## Workflow Configuration

### Available Workflows

1. **Fetch CFB data (Direct API)** (`.github/workflows/cfb-data-fetch.yml`)
   - ✅ Configured to use `CFBD_API_KEY` secret
   - Trigger: Manual (workflow_dispatch)
   - Purpose: Fetch game and team data

2. **Publish Reports** (`.github/workflows/publish_reports.yml`)
   - ✅ Configured to use `CFBD_API_KEY` secret
   - Trigger: Manual (workflow_dispatch)
   - Purpose: Generate weekly reports and top mismatches

3. **Jekyll GH Pages** (`.github/workflows/jekyll-gh-pages.yml`)
   - No secrets required
   - Trigger: Push to main/master
   - Purpose: Deploy documentation site

## Security Checklist

- [ ] API keys are stored as repository secrets, never in code
- [ ] `.gitignore` includes patterns for sensitive files
- [ ] No secrets are logged in workflow outputs
- [ ] Team members understand secret management practices
- [ ] API key rotation schedule is documented

## Testing & Verification

After setup, verify:

1. **Test CFBD API Fetch**:
   - [ ] Go to Actions tab
   - [ ] Run "Fetch CFB data (Direct API)" workflow
   - [ ] Check workflow completes successfully
   - [ ] Verify artifacts are generated

2. **Test Report Generation**:
   - [ ] Run "Publish Reports" workflow
   - [ ] Check reports are generated
   - [ ] Verify data integration works

3. **Local Development**:
   - [ ] Developers can set `CFBD_API_KEY` environment variable
   - [ ] Scripts run successfully with local API key

## Maintenance

### Regular Tasks

- [ ] **Monthly**: Review API key usage
- [ ] **Quarterly**: Rotate API keys
- [ ] **As Needed**: Update documentation

### When to Update Secrets

- API key is compromised or exposed
- API key expires
- Switching to a different CFBD account
- Team member leaves with access to secrets

## Troubleshooting

Common issues and solutions:

1. **Workflow fails with "Missing CFBD_API_KEY"**
   - ✅ Verify secret name is exactly `CFBD_API_KEY` (case-sensitive)
   - ✅ Check secret is at repository level, not organization

2. **API authentication errors**
   - ✅ Verify API key is valid at https://collegefootballdata.com/key
   - ✅ Generate new key if expired

3. **Workflows can't access secrets**
   - ✅ Ensure workflows have proper permissions
   - ✅ Check repository settings allow workflows

## Documentation Links

- [Admin Quick Start](ADMIN_QUICK_START.md) - Fast setup guide
- [Setup Repository Secret](SETUP_REPOSITORY_SECRET.md) - Detailed instructions
- [Main README](../README.md) - Project documentation
- [How to Run](../HOW_TO_RUN.md) - Usage guide

## Support

For issues or questions:
1. Review this checklist
2. Check documentation links above
3. Open a GitHub issue with details

---

**Last Updated**: 2025-10-15  
**Maintained By**: Repository Administrators
