"""Why an upload was rejected. Messages are shown to the admin, so they name the problem
and the location (e.g. a JSON path) but never echo file contents."""


class UploadRejectedError(Exception):
    """Base class: the upload cannot be stored."""


class FileTooLargeError(UploadRejectedError):
    pass


class UnsupportedFileTypeError(UploadRejectedError):
    pass


class InvalidUploadError(UploadRejectedError):
    """Malformed file or content that breaks the course rules."""


class CourseExistsError(UploadRejectedError):
    """The course (or one of its module/lesson ids) is already stored."""


class UnknownTargetError(UploadRejectedError):
    """Notes were tagged with a course, module or lesson that does not exist or match."""
