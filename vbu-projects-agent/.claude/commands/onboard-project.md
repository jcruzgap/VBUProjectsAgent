# Onboard New Project

Walk through the full project onboarding flow for VBU-Projects-Agent.

**Usage:** `/onboard-project <project-id> <"Project Name">`

## Steps

Parse the arguments: first word = project-id, rest = project name.

1. Create the project scaffold:
```bash
vbu-agent project create --project <project-id> --name "<Project Name>"
```

2. Open `projects/<project-id>/project.yaml` and guide the user to fill in:
   - `azure_devops.organization`
   - `azure_devops.project`
   - `azure_devops.base_url`
   - `azure_devops.pat_env_var` (they set the actual PAT as an env var separately)
   - `progress_model.type` and milestones/stages
   - `revenue.monthly_revenue` and `revenue.total_contract_value`

3. Validate the configuration:
```bash
vbu-agent project validate --project <project-id>
vbu-agent doctor
```

4. Guide the user to set their PAT:
```
export <PAT_ENV_VAR>=<their-pat-value>
```

5. Test ADO connectivity (if PAT is available):
```bash
vbu-agent project sync-ado --project <project-id>
```

6. Generate first Slack status to confirm everything works:
```bash
vbu-agent project slack-status --project <project-id>
```
