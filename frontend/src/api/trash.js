import api from './client';

// Recycle bin (OneDrive-style): deleted documents can be restored or deleted for good.

/** POST /api/documents/{id}/trash -> document (status DELETED) */
export async function moveToRecycleBin(fileId) {
  const { data } = await api.post(`/documents/${fileId}/trash`);
  return data;
}

/** POST /api/documents/{id}/restore -> document (back in its old folder) */
export async function restoreDocument(fileId) {
  const { data } = await api.post(`/documents/${fileId}/restore`);
  return data;
}

/** GET /api/trash -> { items, total } */
export async function listRecycleBin() {
  const { data } = await api.get('/trash');
  return data;
}

/** DELETE /api/trash -> { deleted } (permanent) */
export async function emptyRecycleBin() {
  const { data } = await api.delete('/trash');
  return data;
}
