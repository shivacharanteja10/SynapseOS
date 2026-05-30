"""Domain exceptions used by SynapseOS."""


class SynapseOSError(Exception):
    """Base class for all expected application errors."""


class DependencyUnavailableError(SynapseOSError):
    """Raised when a configured external dependency cannot be reached."""


class ResourceNotFoundError(SynapseOSError):
    """Raised when a requested resource does not exist."""


class ApprovalRequiredError(SynapseOSError):
    """Raised when a workflow must pause for human approval."""


class WorkflowExecutionError(SynapseOSError):
    """Raised when the multi-agent graph cannot complete successfully."""
