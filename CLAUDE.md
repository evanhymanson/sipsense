## Making AI powered whiskey app called SipSense

# Trying to learn fullstack development and also workflow for making production level code

# Need FastAPI backend and some type of friendly user facing front-end -- I am not familair with frontend development at all, I only know basic javascript, html, and css.

# Need some type of database with with many different whiskey choices but category, and the ability to make machine learning models for recommendations, I also want to learn pytorch based workflows for this and deploy them to the app.

# Lets get started.

---

## Git Workflow (MUST FOLLOW)

**Never commit directly to `main`.** All work goes through feature branches and pull requests.

### For every task:
1. **Create a feature branch** before making any changes:
   ```
   git checkout main && git pull
   git checkout -b feature/<short-description>
   ```
2. **Do the work** — make commits on the feature branch
3. **Push and open a PR**:
   ```
   git push -u origin feature/<short-description>
   gh pr create --title "..." --body "..."
   ```
4. **User reviews and merges** the PR on GitHub
5. **After merge**, switch back to main:
   ```
   git checkout main && git pull
   ```

### Branch naming:
- Features: `feature/<name>` (e.g. `feature/onboarding-redesign`)
- Fixes: `fix/<name>` (e.g. `fix/deploy-secrets`)
- Chores: `chore/<name>` (e.g. `chore/cleanup-env-files`)

### Deploy flow:
- Merging to `main` auto-deploys to **production** (CI tests must pass first)
- Can also manually trigger production deploy via GitHub Actions workflow dispatch
