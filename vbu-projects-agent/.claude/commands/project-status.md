# Project Status

Get the current delivery status for a VBU project and produce outputs.

**Usage:** `/project-status <project-id>`

## Steps

1. Show current computed metrics:
```bash
vbu-agent project status --project $ARGUMENTS
```

2. Generate Slack status message:
```bash
vbu-agent project slack-status --project $ARGUMENTS
```

3. Offer to generate full HTML report:
```bash
vbu-agent project report --project $ARGUMENTS --open
```
