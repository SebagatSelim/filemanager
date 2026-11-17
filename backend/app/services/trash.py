"""Recycle bin (OneDrive-style): deleted documents wait here until they are restored or deleted for good."""
from flask import current_app

from ..extensions import db
from ..models import AuditLog, DocumentMetadata, File, utcnow
from .folders import clean_segments, ensure_folder_path, path_string
from .storage import get_storage


def move_to_trash(file: File) -> None:
    """Hide the document in the Recycle bin and remember its folder so it can be restored there."""
    if file.status == "DELETED":
        return
    file.deleted_from_path = path_string(file.folder)
    file.deleted_at = utcnow()
    file.folder = None
    file.status = "DELETED"


def restore(file: File) -> None:
    """Put a document back in the folder it was deleted from (the folder is re-created if needed)."""
    meta = file.meta
    if meta is not None and meta.is_user_approved:
        file.status = "STORED"
    elif meta is not None and meta.title:
        file.status = "AWAITING_REVIEW"
    else:
        file.status = "FAILED"
    segments = clean_segments(file.deleted_from_path or "")
    file.folder = ensure_folder_path(file.user_id, segments) if segments else None
    file.deleted_at = None
    file.deleted_from_path = None
    file.updated_at = utcnow()


def delete_forever(file: File) -> str:
    """Remove the database rows for a document. Returns its storage key; call remove_stored_files() after commit."""
    AuditLog.query.filter_by(file_id=file.file_id).update({"file_id": None})
    DocumentMetadata.query.filter_by(duplicate_of_file_id=file.file_id).update(
        {"duplicate_of_file_id": None, "duplicate_type": None, "duplicate_score": None})
    key = file.storage_key
    db.session.delete(file)
    return key


def remove_stored_files(keys: list[str]) -> None:
    """Delete the actual files from local storage / S3 (after the database commit succeeded)."""
    for key in keys:
        try:
            get_storage().delete(key)
        except Exception:
            current_app.logger.exception("Could not delete stored object %s", key)
