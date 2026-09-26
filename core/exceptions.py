"""
Centralized application exception hierarchy (SRS section 16.4).

Every layer converts low-level exceptions (sqlite3.Error, OSError, etc.)
into one of these before they reach the UI, so the presentation layer
only ever has to handle a small, known set of error types.
"""


class ApplicationError(Exception):
    """Base class for all known/expected application errors."""
    user_message = "Something went wrong. Please try again."

    def __init__(self, message: str | None = None, *, field: str | None = None):
        self.field = field
        super().__init__(message or self.user_message)


class ValidationError(ApplicationError):
    user_message = "Please check the highlighted fields and try again."


class AuthenticationError(ApplicationError):
    user_message = "Invalid username or password."


class AuthorizationError(ApplicationError):
    user_message = "You do not have permission to perform this action."


class NotFoundError(ApplicationError):
    user_message = "The requested record could not be found."


class DuplicateRecordError(ApplicationError):
    user_message = "A record with this value already exists."


class DatabaseOperationError(ApplicationError):
    user_message = "Unable to connect to the database. Please check the connection and try again."


class DocumentProcessingError(ApplicationError):
    user_message = "The document could not be read automatically. Please enter the details manually."


class PDFGenerationError(ApplicationError):
    user_message = "The bill could not be generated. Please try again or choose another save location."


class NotificationError(ApplicationError):
    user_message = "The reminder could not be delivered, but it has been saved."


class ServiceUnavailableError(ApplicationError):
    user_message = "This service is currently unavailable. Please try again later."


class BackupError(ApplicationError):
    user_message = "The backup could not be completed. Please check the destination folder and try again."


class ExportError(ApplicationError):
    user_message = "The Excel file could not be created. Please try again or choose another save location."
