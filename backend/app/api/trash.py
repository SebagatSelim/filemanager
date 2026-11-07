"""Recycle bin endpoints (OneDrive-style delete / restore / empty)."""
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from ..errors import APIError
from ..extensions import db
from ..models import File
from ..serializers import document_json
from ..services import audit
from ..services.index import bump
from ..services.trash import delete_forever, move_to_trash, remove_stored_files, restore
from .helpers import current_user_id, get_owned_file

bp = Blueprint("trash", __name__)


@bp.post("/documents/<int:file_id>/trash")
@jwt_required()
def trash_document(file_id: int):
    """Move a document to the Recycle bin."""
    file = get_owned_file(file_id)
    if file.status in ("UPLOADED", "PROCESSING"):
        raise APIError(409, "STILL_PROCESSING", "The document is still being analysed. Please wait a moment.")
    move_to_trash(file)
    audit.record(file.user_id, "DELETE", file.file_id, f"{file.display_name} moved to the Recycle bin")
    db.session.commit()
    bump(file.user_id)
    return jsonify(document_json(file))


@bp.post("/documents/<int:file_id>/restore")
@jwt_required()
def restore_document(file_id: int):
    """Take a document out of the Recycle bin and put it back in its old folder."""
    file = get_owned_file(file_id)
    if file.status != "DELETED":
        raise APIError(409, "NOT_IN_RECYCLE_BIN", "This document is not in the Recycle bin.")
    restore(file)
    audit.record(file.user_id, "UPDATE", file.file_id, f"{file.display_name} restored from the Recycle bin")
    db.session.commit()
    bump(file.user_id)
    return jsonify(document_json(file))


@bp.get("/trash")
@jwt_required()
def list_trash():
    files = (File.query.filter_by(user_id=current_user_id(), status="DELETED")
             .order_by(File.deleted_at.desc(), File.file_id.desc()).all())
    return jsonify({"items": [document_json(f) for f in files], "total": len(files)})


@bp.delete("/trash")
@jwt_required()
def empty_trash():
    """Permanently delete everything in the Recycle bin."""
    user_id = current_user_id()
    files = File.query.filter_by(user_id=user_id, status="DELETED").all()
    keys = [delete_forever(f) for f in files]
    if files:
        audit.record(user_id, "DELETE", None, f"Recycle bin emptied ({len(files)} documents)")
    db.session.commit()
    remove_stored_files(keys)
    bump(user_id)
    return jsonify({"deleted": len(files)})
