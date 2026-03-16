# PowerTrader AI+ Project Management Scripts

This directory contains scripts for automating project management tasks and setting up the development workflow.

## Scripts Overview

### `create_github_issues.py`
Automatically creates GitHub issues from the TODO.md file to set up project management.

**Features:**
- Parses TODO.md structure to extract tasks
- Creates appropriately labeled GitHub issues
- Sets up project milestones and labels
- Maps tasks to development phases
- Generates standardized issue descriptions

**Usage:**
```bash
# Install required dependencies
pip install requests

# Run in dry-run mode to preview
python scripts/create_github_issues.py --token YOUR_TOKEN --owner YOUR_USERNAME --dry-run

# Create issues for real
python scripts/create_github_issues.py --token YOUR_TOKEN --owner YOUR_USERNAME
```

**Requirements:**
- GitHub Personal Access Token with repo permissions
- Python 3.7+ with requests library

## Project Setup Workflow

### Initial Setup (One-time)

1. **Create GitHub Personal Access Token**
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Create token with `repo` scope
   - Save token securely

2. **Run Project Setup Script**
   ```bash
   # Preview what will be created
   python scripts/create_github_issues.py --token YOUR_TOKEN --owner YOUR_USERNAME --dry-run

   # Create the project structure
   python scripts/create_github_issues.py --token YOUR_TOKEN --owner YOUR_USERNAME
   ```

3. **Set Up GitHub Project**
   - Go to your repository on GitHub
   - Click "Projects" tab
   - Create new project using templates from .github/PROJECT_SETUP.md
   - Configure project views and automation

4. **Configure Development Branches**
   ```bash
   # Create development branches for each phase
   git checkout -b development-phase1
   git push -u origin development-phase1

   git checkout main
   git checkout -b development-phase2
   git push -u origin development-phase2

   # Repeat for phase 3 and 4
   ```

### Ongoing Project Management

#### Weekly Issue Review
```bash
# Get current project status
gh issue list --label "phase-1-critical" --state open

# Review security issues
gh issue list --label "security" --state open

# Check milestone progress
gh api repos/:owner/:repo/milestones
```

#### Sprint Planning
1. Review completed issues from previous sprint
2. Select new issues for upcoming sprint
3. Assign developers to issues
4. Update project board with sprint assignments

#### Release Management
1. Create release branch when phase is complete
2. Run final testing and security scans
3. Merge to main branch with pull request
4. Tag release and update documentation

## Script Configuration

### Environment Variables
```bash
# Optional: Set as environment variables to avoid command line arguments
export GITHUB_TOKEN="your_token_here"
export GITHUB_REPO_OWNER="your_username"
export GITHUB_REPO_NAME="PowerTrader_AI"
```

### Custom Configuration
Edit the `create_github_issues.py` script to customize:
- Label colors and descriptions
- Milestone dates and descriptions
- Issue template formats
- Priority assignments

## Troubleshooting

### Common Issues

#### Authentication Errors
```
Error: GitHub API request failed - 401 Unauthorized
```
**Solution:** Verify your GitHub token has the correct permissions and hasn't expired.

#### Rate Limiting
```
Error: GitHub API request failed - 403 Forbidden
```
**Solution:** Wait for rate limit reset or use a GitHub token with higher rate limits.

#### Missing Dependencies
```
ImportError: No module named 'requests'
```
**Solution:** Install required dependencies:
```bash
pip install requests
```

#### Duplicate Issues
If issues already exist, the script will attempt to create duplicates. **Solution:** Delete existing issues or modify the script to check for existing issues before creating new ones.

### Debug Mode
Add debug output by modifying the script:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Integration with GitHub Actions

The scripts can be integrated with GitHub Actions for automated project management:

```yaml
# .github/workflows/project-sync.yml
name: Sync Project Issues

on:
  schedule:
    - cron: '0 9 * * MON'  # Every Monday at 9 AM

jobs:
  sync-issues:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    - name: Install dependencies
      run: pip install requests
    - name: Update project issues
      run: python scripts/create_github_issues.py --token ${{ secrets.GITHUB_TOKEN }} --owner ${{ github.repository_owner }}
      env:
        GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

## Security Considerations

### Token Security
- Never commit GitHub tokens to repository
- Use GitHub Secrets for automation
- Rotate tokens regularly
- Use minimal required permissions

### Script Security
- Review script code before execution
- Validate all input parameters
- Use HTTPS for all API calls
- Log security-relevant actions

## Contributing

To add new project management scripts:

1. Create script in this directory
2. Follow Python coding standards
3. Include comprehensive error handling
4. Add documentation to this README
5. Test with dry-run mode first
6. Submit pull request with script and documentation

---

**Last Updated:** March 16, 2026
**Next Review:** After Phase 1 completion
**Owner:** Development Team
