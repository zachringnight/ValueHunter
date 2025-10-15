# Setting Up GitHub Repository Secret for CFBD API

This guide explains how to add the required `CFBD_API_KEY` repository secret for GitHub Actions workflows.

## Overview

The ValueHunter repository uses GitHub Actions to automatically fetch college football data from the CollegeFootballData (CFBD) API. To authenticate with the CFBD API, you need to configure a repository secret.

## Prerequisites

1. **Repository Admin Access**: You must have admin access to the GitHub repository
2. **CFBD API Key**: You need a valid API key from [CollegeFootballData.com](https://collegefootballdata.com/key)

## Step-by-Step Instructions

### 1. Get Your CFBD API Key

If you don't already have an API key:

1. Visit https://collegefootballdata.com/key
2. Sign up for a free account (if you don't have one)
3. Generate your API key
4. Copy the API key - you'll need it in the next step

### 2. Add the Repository Secret

1. **Navigate to Repository Settings**:
   - Go to your repository on GitHub: `https://github.com/zachringnight/ValueHunter`
   - Click on the **Settings** tab (you need admin access to see this)

2. **Access Secrets Configuration**:
   - In the left sidebar, expand **Secrets and variables**
   - Click on **Actions**

3. **Create New Secret**:
   - Click the **New repository secret** button
   - Fill in the following details:
     - **Name**: `CFBD_API_KEY` (must be exactly this name)
     - **Secret**: Paste your CFBD API key
   - Click **Add secret**

### 3. Verify the Secret

After adding the secret:

1. Go to the **Actions** tab in your repository
2. Select the "Fetch CFB data (Direct API)" workflow
3. Click **Run workflow**
4. Provide the required inputs (season year and season type)
5. The workflow should run successfully if the secret is configured correctly

## Workflows That Use This Secret

The following GitHub Actions workflows require the `CFBD_API_KEY` secret:

1. **Fetch CFB data (Direct API)** (`.github/workflows/cfb-data-fetch.yml`)
   - Fetches game and team data directly from CFBD API
   - Runs on manual trigger or scheduled

2. **Publish Reports** (`.github/workflows/publish_reports.yml`)
   - Fetches CFBD data and runs integrated analysis
   - Generates weekly reports and top mismatches

## Security Best Practices

### ✅ Do's

- **Keep your API key private**: Never commit API keys to the repository
- **Use repository secrets**: Always use GitHub Secrets for sensitive data
- **Rotate keys regularly**: Periodically generate new API keys
- **Monitor usage**: Check your CFBD API usage to detect unauthorized use

### ❌ Don'ts

- **Never hardcode API keys** in source code, scripts, or configuration files
- **Don't share API keys** in pull requests, issues, or public communications
- **Don't commit `.env` files** containing API keys
- **Don't log API keys** in workflow outputs

## Troubleshooting

### Problem: Workflow fails with "Missing CFBD_API_KEY environment variable"

**Solution**: 
- Verify the secret is named exactly `CFBD_API_KEY` (case-sensitive)
- Ensure you have added the secret at the repository level, not organization level
- Check that the workflow has permission to access secrets

### Problem: API authentication errors

**Solution**:
- Verify your API key is valid at https://collegefootballdata.com/key
- Check if your API key has expired or been revoked
- Generate a new API key and update the repository secret

### Problem: "secrets.CFBD_API_KEY not found" error

**Solution**:
- Confirm you have admin access to the repository
- Re-add the secret following the steps above
- Ensure there are no typos in the secret name

## For Local Development

For running scripts locally (outside of GitHub Actions):

1. Set the environment variable in your shell:
   ```bash
   export CFBD_API_KEY="your-api-key-here"
   ```

2. Or add it to your shell profile (e.g., `~/.bashrc`, `~/.zshrc`):
   ```bash
   echo 'export CFBD_API_KEY="your-api-key-here"' >> ~/.bashrc
   source ~/.bashrc
   ```

3. For Python scripts, the API key is read from the `CFBD_API_KEY` environment variable

## Additional Resources

- [GitHub Encrypted Secrets Documentation](https://docs.github.com/en/actions/security-guides/encrypted-secrets)
- [CFBD API Documentation](https://api.collegefootballdata.com/api/docs/)
- [Repository README - Setting Up Your API Key](../README.md#setting-up-your-api-key)

## Support

If you encounter issues:
1. Review this guide carefully
2. Check the [FAQ.md](../FAQ.md) for common questions
3. Open an issue on GitHub with details about your problem

---

**Last Updated**: 2025-10-15
