class JobError(Exception):
    status_code = 400


class InvalidImageError(JobError):
    status_code = 400


class ImageTooLargeError(JobError):
    status_code = 413


class RateLimitExceededError(JobError):
    status_code = 429


class DownloadUnavailableError(JobError):
    status_code = 410
