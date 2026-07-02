# Onboard New Project

Create and configure a new project in the shared workspace.

**Usage:** `/onboard-project <project-id> <"Project Name">`

## Steps

Parse the arguments: first word = project-id, rest = project name.

1. Create the project by copying the `_example` template:
```bash
vbu-agent project new --project <project-id> --name "<Project Name>"
```

2. Open `projects/<project-id>/project.yaml` and help the user fill in the three
   Azure DevOps fields: `organization`, `project`, `base_url`.

3. Add the PAT to `.env` (never to YAML). The variable name is printed by
   `project new` — e.g. `MY_PROJECT_ADO_PAT=...`.

4. Confirm setup:
```bash
vbu-agent doctor
```

5. Pull metrics and generate the first Slack status:
```bash
vbu-agent project sync-ado --project <project-id>
vbu-agent project slack-status --project <project-id>
```
