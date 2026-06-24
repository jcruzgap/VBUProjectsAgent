"""Typed, actionable ADO error hierarchy."""


class AdoError(Exception):
    """Base class for all ADO errors."""
    remediation: str = "Check your Azure DevOps configuration."

    def __init__(self, message: str, remediation: str | None = None) -> None:
        super().__init__(message)
        if remediation:
            self.remediation = remediation


class AdoPatMissing(AdoError):
    remediation = (
        "Set the ADO PAT environment variable referenced in project.yaml "
        "(azure_devops.pat_env_var). "
        "Example: export PROJECT_ALPHA_ADO_PAT=<your-pat>"
    )


class AdoAuthError(AdoError):
    remediation = (
        "Your ADO PAT was rejected (HTTP 401/403). "
        "Regenerate the PAT in Azure DevOps and ensure it has the correct scopes "
        "(Work Items: Read). Do NOT log the PAT value."
    )


class AdoPatExpired(AdoError):
    remediation = (
        "Your ADO PAT has expired (HTTP 401 with expiry signal). "
        "Renew it in Azure DevOps > Personal access tokens."
    )


class AdoWiqlError(AdoError):
    remediation = (
        "The WIQL query in project.yaml is invalid. "
        "Review the 'work_items.wiql' field and test it in Azure DevOps."
    )


class AdoNetworkError(AdoError):
    remediation = (
        "Could not reach Azure DevOps after retries. "
        "Check network connectivity and run 'vbu-agent doctor' for diagnostics."
    )
