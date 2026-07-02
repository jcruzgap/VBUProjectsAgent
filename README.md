# VBU-Projects-Agent

A shared workspace for Velocity Business Unit Delivery Managers. It keeps project
context, measures delivery progress from Azure DevOps, and produces executive Slack
messages, HTML reports, and a portfolio dashboard.

Everyone on the team uses **one repo**. Your projects live under
`vbu-projects-agent/projects/` alongside everyone else's — clone once, add your own.

## Get started (3 steps)

1. **Clone the repo**
   ```bash
   git clone <repo-url>
   cd VBUProjectsAgent
   ```

2. **Run setup** (creates the venv, installs the tool, makes your `.env`)
   - Windows:  `./setup.ps1`
   - macOS/Linux:  `bash setup.sh`

3. **Add your key and your project**
   ```bash
   cd vbu-projects-agent
   # Windows: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
   # Edit .env and set ANTHROPIC_API_KEY
   vbu-agent project new --project my-project --name "My Project"
   ```
   Then edit `projects/my-project/project.yaml` (Azure DevOps org/project) and add
   your ADO PAT to `.env` as `MY_PROJECT_ADO_PAT=...`.

Run `vbu-agent doctor` any time to check your setup.

## Working with the team

- Each person works inside their **own** `projects/<id>/` folder and commits it.
- Look at `projects/_example/` for a template of every field.
- Because everyone stays in their own folder, merges are clean.

## Daily / weekly commands

```bash
vbu-agent project update --project <id>       # ingest notes into context
vbu-agent project slack-status --project <id> # copy-ready Slack status
vbu-agent project sync-ado --project <id>     # pull ADO metrics
vbu-agent project report --project <id> --open# HTML report
vbu-agent dashboard generate --open           # portfolio dashboard
vbu-agent project list                        # all projects + health
```

## Secrets

Secrets live only in `vbu-projects-agent/.env` (git-ignored). Never commit keys or
PATs. See `.env.example` for the template.
