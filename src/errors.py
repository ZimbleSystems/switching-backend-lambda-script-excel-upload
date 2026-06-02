class ValidationError(Exception):
    def __init__(self, field: str, message: str):
        self.field = field
        self.message = message
        super().__init__(f"{field}: {message}")


class DependencyError(Exception):
    """Raised when a child references a parent id that does not exist
    in the database AND was not produced in this ingest run."""


class IngestError(Exception):
    pass
