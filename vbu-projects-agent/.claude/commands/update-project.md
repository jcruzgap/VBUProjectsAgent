# Update Project Context

Run the daily context update workflow for a VBU project.

**Usage:** `/update-project <project-id>`

## What this does

1. Reads all files from `projects/<project-id>/input/`
2. Uses Claude to extract structured facts (status updates, risks, decisions, milestone changes)
3. Reconciles extracted facts against existing context files
4. Detects conflicts and records them in `conflicts.md`
5. Snapshots context before writing (safety-first)
6. Updates the correct `context/*.md` files surgically
7. Archives processed inputs and emits a change summary

## Steps

```bash
# Dry run first — preview changes without writing anything
vbu-agent project update --project $ARGUMENTS --dry-run

# Show the proposed changes and ask if user wants to apply
```

Then if the user confirms, run:

```bash
vbu-agent project update --project $ARGUMENTS
```

After updating, offer to generate a Slack status:

```bash
vbu-agent project slack-status --project $ARGUMENTS
```
