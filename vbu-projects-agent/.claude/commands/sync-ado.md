# Sync Azure DevOps Metrics

Pull the latest work item data from Azure DevOps and recompute delivery metrics.

**Usage:** `/sync-ado <project-id>`

## Steps

```bash
vbu-agent project sync-ado --project $ARGUMENTS
```

This will:
- Execute the configured WIQL query against Azure DevOps
- Batch-fetch work item details (up to 200 per batch)
- Compute progress using the configured strategy (staged_tags, test_case_milestones, etc.)
- Persist metrics and milestones to the SQLite database
- Update the project's health in the registry

After syncing, run:
```bash
vbu-agent project status --project $ARGUMENTS
```

**Note:** Requires the ADO PAT environment variable to be set.
See `azure_devops.pat_env_var` in `projects/<project-id>/project.yaml`.
