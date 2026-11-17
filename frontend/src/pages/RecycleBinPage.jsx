// Recycle bin (like OneDrive): deleted documents wait here. Restore them, or delete them for good.
import { useCallback, useEffect, useState } from 'react';
import ConfirmModal from '../components/ConfirmModal';
import { FileIcon } from '../components/Badges';
import { EmptyState, ErrorState, SkeletonList } from '../components/Feedback';
import { deleteDocument } from '../api/documents';
import { emptyRecycleBin, listRecycleBin, restoreDocument } from '../api/trash';
import { getApiError } from '../api/client';
import { useToast } from '../context/ToastContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { formatBytes, formatDate, plural } from '../utils/format';
import { displayPath } from '../utils/folders';

export default function RecycleBinPage() {
  const toast = useToast();
  const { refresh } = useWorkspace();
  const [state, setState] = useState({ loading: true, error: null, items: [] });
  const [reloadKey, setReloadKey] = useState(0);
  const [confirm, setConfirm] = useState(null); // { doc } to delete one, { all: true } to empty the bin
  const [busy, setBusy] = useState(false);

  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
    refresh();
  }, [refresh]);

  useEffect(() => {
    let cancelled = false;
    listRecycleBin()
      .then((data) => !cancelled && setState({ loading: false, error: null, items: data.items || [] }))
      .catch((err) => !cancelled && setState({ loading: false, error: getApiError(err), items: [] }));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const restore = async (doc) => {
    try {
      const restored = await restoreDocument(doc.file_id);
      toast.success(`“${doc.name}” restored to ${displayPath(restored.folder_path, 'My files')}.`);
      reload();
    } catch (err) {
      toast.error(getApiError(err).message);
    }
  };

  const deleteForever = async () => {
    setBusy(true);
    try {
      if (confirm.all) {
        const result = await emptyRecycleBin();
        toast.success(`Recycle bin emptied (${plural(result.deleted, 'document')} deleted).`);
      } else {
        await deleteDocument(confirm.doc.file_id);
        toast.success(`“${confirm.doc.name}” was permanently deleted.`);
      }
      setConfirm(null);
      reload();
    } catch (err) {
      toast.error(getApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const items = state.items;

  return (
    <div className="fa-page">
      <div className="d-flex flex-column flex-md-row align-items-md-center justify-content-between gap-2 mb-3">
        <div>
          <h2 className="h5 fw-bold mb-0">
            Recycle bin {!state.loading && <span className="text-muted fw-normal">({items.length})</span>}
          </h2>
          <p className="text-muted small mb-0">Deleted files stay here until you restore them or empty the bin.</p>
        </div>
        <button
          type="button"
          className="btn btn-outline-danger btn-sm"
          onClick={() => setConfirm({ all: true })}
          disabled={!items.length}
        >
          <i className="bi bi-trash3 me-1" aria-hidden="true" />
          Empty recycle bin
        </button>
      </div>

      <div className="card fa-card">
        {state.loading && (
          <div className="card-body">
            <SkeletonList rows={4} />
          </div>
        )}
        {state.error && <ErrorState title="Couldn't load the Recycle bin" message={state.error.message} onRetry={reload} />}
        {!state.loading && !state.error && !items.length && (
          <EmptyState icon="bi-trash3" title="The Recycle bin is empty">
            When you delete a file or folder, its documents appear here for you to restore.
          </EmptyState>
        )}
        {items.length > 0 && (
          <div>
            <table className="table align-middle mb-0 fa-table fa-explorer">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col" className="d-none d-md-table-cell">Original location</th>
                  <th scope="col" className="d-none d-sm-table-cell">Deleted</th>
                  <th scope="col" className="d-none d-lg-table-cell text-end">Size</th>
                  <th scope="col" className="text-end">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((doc) => (
                  <tr key={doc.file_id}>
                    <td className="fa-name-cell">
                      <div className="d-flex align-items-center gap-3 min-w-0">
                        <FileIcon type={doc.file_type} name={doc.name} size={34} />
                        <div className="min-w-0">
                          <div className="fw-semibold text-truncate">{doc.name}</div>
                          {doc.title && <div className="small text-muted text-truncate">{doc.title}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="d-none d-md-table-cell small text-muted fa-folder-cell">
                      {displayPath(doc.deleted_from_path, 'My files')}
                    </td>
                    <td className="d-none d-sm-table-cell small text-nowrap">{formatDate(doc.deleted_at)}</td>
                    <td className="d-none d-lg-table-cell small text-end text-nowrap">{formatBytes(doc.file_size_bytes)}</td>
                    <td className="text-end text-nowrap">
                      <button type="button" className="btn btn-sm btn-light me-1" onClick={() => restore(doc)}>
                        <i className="bi bi-arrow-counterclockwise me-1" aria-hidden="true" />
                        Restore
                      </button>
                      <button
                        type="button"
                        className="btn btn-sm btn-light text-danger"
                        onClick={() => setConfirm({ doc })}
                        aria-label={`Delete ${doc.name} permanently`}
                      >
                        <i className="bi bi-x-circle" aria-hidden="true" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <ConfirmModal
        show={Boolean(confirm)}
        title={confirm?.all ? 'Empty the Recycle bin?' : 'Delete permanently?'}
        confirmLabel="Delete permanently"
        busy={busy}
        onConfirm={deleteForever}
        onCancel={() => setConfirm(null)}
        icon="bi-trash3"
      >
        {confirm?.all ? (
          <>All {plural(items.length, 'document')} in the Recycle bin will be deleted for good. This can&apos;t be undone.</>
        ) : (
          <>
            <strong>{confirm?.doc?.name}</strong> will be deleted for good. This can&apos;t be undone.
          </>
        )}
      </ConfirmModal>
    </div>
  );
}
