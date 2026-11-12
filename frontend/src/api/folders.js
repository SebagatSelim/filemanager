import api from './client';

/** GET /api/folders -> folder tree */
export async function getFolders() {
  const { data } = await api.get('/folders');
  return Array.isArray(data) ? data : [];
}

/** POST /api/folders { name, parent_folder_id } -> 201 folder; 409 FOLDER_EXISTS */
export async function createFolder({ name, parentFolderId = null }) {
  const { data } = await api.post('/folders', { name, parent_folder_id: parentFolderId });
  return data;
}

/** PATCH /api/folders/{id} { name } -> folder; 409 FOLDER_EXISTS */
export async function renameFolder(folderId, name) {
  const { data } = await api.patch(`/folders/${folderId}`, { name });
  return data;
}

/** DELETE /api/folders/{id} -> { deleted_folders, documents_moved_to_recycle_bin } */
export async function deleteFolder(folderId) {
  const { data } = await api.delete(`/folders/${folderId}`);
  return data;
}

/** GET /api/folders/{id}/summary -> AI overview of everything in the folder (and its subfolders) */
export async function getFolderSummary(folderId) {
  const { data } = await api.get(`/folders/${folderId}/summary`);
  return data;
}
