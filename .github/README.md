# GitHub Configuration & Administration

This directory contains GitHub-specific configuration files and documentation for repository administrators.

## For Repository Administrators

### 🚀 Quick Start
Start here if you need to set up the repository for automated workflows:
- **[ADMIN_QUICK_START.md](ADMIN_QUICK_START.md)** - Fast 3-step setup guide

### 📋 Complete Guides
- **[ADMIN_CHECKLIST.md](ADMIN_CHECKLIST.md)** - Complete setup checklist for administrators
- **[SETUP_REPOSITORY_SECRET.md](SETUP_REPOSITORY_SECRET.md)** - Detailed guide for configuring CFBD_API_KEY secret

## Workflows

The repository uses GitHub Actions workflows for automation:

### 1. Fetch CFB Data (`workflows/cfb-data-fetch.yml`)
- **Purpose**: Fetches college football data from CFBD API
- **Trigger**: Manual (workflow_dispatch)
- **Required Secret**: `CFBD_API_KEY`
- **Outputs**: Game and team data artifacts

### 2. Publish Reports (`workflows/publish_reports.yml`)
- **Purpose**: Generates weekly reports and top mismatches
- **Trigger**: Manual (workflow_dispatch)
- **Required Secret**: `CFBD_API_KEY`
- **Optional Secrets**: `NOTION_TOKEN`, `NOTION_DATABASE_ID`
- **Outputs**: Weekly reports committed to repository

### 3. Jekyll GitHub Pages (`workflows/jekyll-gh-pages.yml`)
- **Purpose**: Deploys documentation site
- **Trigger**: Push to main/master branch
- **Required Secrets**: None

## Required Repository Secrets

| Secret Name | Required | Purpose | Setup Guide |
|------------|----------|---------|-------------|
| `CFBD_API_KEY` | ✅ Yes | Authenticate with CollegeFootballData API | [Setup Guide](SETUP_REPOSITORY_SECRET.md) |
| `NOTION_TOKEN` | ❌ Optional | Push reports to Notion | See workflow comments |
| `NOTION_DATABASE_ID` | ❌ Optional | Specify Notion database | See workflow comments |

## Security Best Practices

✅ **Do:**
- Store all sensitive credentials as repository secrets
- Follow the principle of least privilege
- Rotate API keys regularly
- Review secret access logs

❌ **Don't:**
- Commit API keys or secrets to the repository
- Share secrets in pull requests or issues
- Log secrets in workflow outputs
- Use personal API keys for shared workflows

## Documentation

For general project documentation, see:
- [Main README](../README.md)
- [How to Run](../HOW_TO_RUN.md)
- [FAQ](../FAQ.md)
- [Data Integration Guide](../DATA_INTEGRATION.md)

## Support

For questions or issues with repository configuration:
1. Review the documentation in this directory
2. Check existing GitHub issues
3. Open a new issue with the `admin` or `infrastructure` label

---

**Maintained By**: Repository Administrators  
**Last Updated**: 2025-10-15
