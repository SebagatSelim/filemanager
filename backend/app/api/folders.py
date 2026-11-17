"""Folder tree, folder rename / delete / AI summary, and categories (FR-05)."""
import sqlalchemy as sa
from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required

from ..errors import APIError, not_found, validation_error
from ..extensions import db
from ..models import DocumentMetadata, File, Folder
from ..services import audit
from ..services.folder_summary import summarise_folder
from ..services.folders import clean_segments, folder_and_subfolder_ids, folder_paths, user_folders
from ..services.index import bump
from ..services.trash import move_to_trash
from .helpers import current_user_id, json_body

bp = Blueprint("folders", __name__)


def _owned_folder(folder_id: int) -> Folder:
    """Fetch a folder only if it belongs to the signed-in user (404 otherwise)."""
    folder = db.session.get(Folder, folder_id)
    if folder is None or folder.user_id != current_user_id():
        raise not_found("Folder not found.")
    return folder


@bp.get("/folders")
@jwt_required()
def folder_tree():
    user_id = current_user_id()
    folders = user_folders(user_id)
    paths = folder_paths(user_id)
    counts = dict(db.session.execute(
        sa.select(File.folder_id, sa.func.count(File.file_id))
        .where(File.user_id == user_id, File.status == "STORED", File.folder_id.is_not(None))
        .group_by(File.folder_id)
    ).all())
    nodes = {
        f.folder_id: {"folder_id": f.folder_id, "name": f.name, "parent_folder_id": f.parent_folder_id,
                      "path": "/".join(paths[f.folder_id]), "document_count": counts.get(f.folder_id, 0), "children": []}
        for f in folders
    }
    roots = []
    for node in nodes.values():
        parent = nodes.get(node["parent_folder_id"])
        (parent["children"] if parent else roots).append(node)
    for node in nodes.values():
        node["children"].sort(key=lambda n: n["name"].lower())
    roots.sort(key=lambda n: n["name"].lower())
    return jsonify(roots)


@bp.post("/folders")
@jwt_required()
def create_folder():
    user_id = current_user_id()
    data = json_body()
    names = clean_segments([data.get("name") or ""])
    if not names:
        raise validation_error("Folder name is required.", {"name": "Required"})
    parent_id = data.get("parent_folder_id")
    if parent_id is not None:
        parent = db.session.get(Folder, int(parent_id))
        if parent is None or parent.user_id != user_id:
            raise not_found("Parent folder not found.")
    siblings = Folder.query.filter_by(user_id=user_id, parent_folder_id=parent_id).all()
    if any(f.name.lower() == names[0].lower() for f in siblings):
        raise APIError(409, "FOLDER_EXISTS", "A folder with this name already exists here.", {"name": "Already exists"})
    folder = Folder(user_id=user_id, parent_folder_id=parent_id, name=names[0])
    db.session.add(folder)
    db.session.commit()
    path = "/".join(folder_paths(user_id)[folder.folder_id])
    return jsonify({"folder_id": folder.folder_id, "name": folder.name, "parent_folder_id": parent_id,
                    "path": path, "document_count": 0, "children": []}), 201


@bp.patch("/folders/<int:folder_id>")
@jwt_required()
def rename_folder(folder_id: int):
    folder = _owned_folder(folder_id)
    names = clean_segments([json_body().get("name") or ""])
    if not names:
        raise validation_error("Folder name is required.", {"name": "Required"})
    new_name = names[0]
    siblings = Folder.query.filter_by(user_id=folder.user_id, parent_folder_id=folder.parent_folder_id).all()
    if any(f.folder_id != folder.folder_id and f.name.lower() == new_name.lower() for f in siblings):
        raise APIError(409, "FOLDER_EXISTS", "A folder with this name already exists here.", {"name": "Already exists"})
    old_name = folder.name
    folder.name = new_name
    audit.record(folder.user_id, "UPDATE", None, f'Folder "{old_name}" renamed to "{new_name}"')
    db.session.commit()
    bump(folder.user_id)  # folder names are part of the search index
    return jsonify({"folder_id": folder.folder_id, "name": folder.name, "parent_folder_id": folder.parent_folder_id,
                    "path": "/".join(folder_paths(folder.user_id)[folder.folder_id])})


@bp.delete("/folders/<int:folder_id>")
@jwt_required()
def delete_folder(folder_id: int):
    """Delete a folder and its subfolders. Their documents go to the Recycle bin (they can be restored)."""
    folder = _owned_folder(folder_id)
    user_id = folder.user_id
    path = "/".join(folder_paths(user_id)[folder.folder_id])
    ids = folder_and_subfolder_ids(user_id, folder.folder_id)
    files = File.query.filter(File.user_id == user_id, File.folder_id.in_(ids)).all()
    for file in files:
        move_to_trash(file)
    # Delete the deepest folders first so no folder is removed before its children.
    for fid in reversed(ids):
        Folder.query.filter_by(folder_id=fid).delete()
    audit.record(user_id, "DELETE", None, f'Folder "{path}" ({len(files)} documents moved to the Recycle bin)')
    db.session.commit()
    bump(user_id)
    return jsonify({"deleted_folders": len(ids), "documents_moved_to_recycle_bin": len(files)})


@bp.get("/folders/<int:folder_id>/summary")
@jwt_required()
def folder_summary(folder_id: int):
    """AI summary of everything in the folder, including its subfolders."""
    folder = _owned_folder(folder_id)
    ids = folder_and_subfolder_ids(folder.user_id, folder.folder_id)
    files = (File.query.filter(File.user_id == folder.user_id, File.folder_id.in_(ids), File.status == "STORED")
             .order_by(File.uploaded_at.desc()).all())
    path = "/".join(folder_paths(folder.user_id)[folder.folder_id])
    data = summarise_folder(folder.name, path, files, subfolder_count=len(ids) - 1)
    data["folder_id"] = folder.folder_id
    return jsonify(data)


@bp.get("/categories")
@jwt_required()
def categories():
    user_id = current_user_id()
    rows = db.session.execute(
        sa.select(DocumentMetadata.category, sa.func.count(File.file_id))
        .join(File, File.file_id == DocumentMetadata.file_id)
        .where(File.user_id == user_id, File.status == "STORED", DocumentMetadata.category.is_not(None))
        .group_by(DocumentMetadata.category)
        .order_by(sa.func.count(File.file_id).desc())
    ).all()
    return jsonify([{"category": category, "count": count} for category, count in rows])
