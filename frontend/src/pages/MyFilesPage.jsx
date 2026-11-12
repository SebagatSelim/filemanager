// "My files": a OneDrive-style file explorer (reviewer feedback).
// Open folders, go back with the breadcrumb, and create / rename / delete / summarise folders and files.
// The open folder is kept in the URL (?folder=12) so the browser Back button works.
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import ActionMenu from '../components/files/ActionMenu';
import RenameModal from '../components/files/RenameModal';
import { CategoryBadge, FileIcon } from '../components/Badges';
import { EmptyState, ErrorState, SkeletonList } from '../components/Feedback';
import { createFolder, getFolders } from '../api/folders';
import { listDocuments } from '../api/documents';
import { getApiError } from '../api/client';
import { useToast } from '../context/ToastContext';
import useFileActions from '../hooks/useFileActions';
import { formatBytes, formatDate, plural } from '../utils/format';
import { ancestorIds, countDocumentsDeep, findFolderById } from '../utils/folders';
import { folderSegmentError } from '../utils/validation';

const VIEW_KEY = 'fileai_myfiles_view';

function readView() {
  try {
    return window.localStorage.getItem(VIEW_KEY) === 'grid' ? 'grid' : 'list';
  } catch {
    return 'list';
  }
}

export default function MyFilesPage() {
  const toast = useToast();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const folderId = params.get('folder') || '';

  const [tree, setTree] = useState({ loading: true, error: null, data: [] });
  const [files, setFiles] = useState({ loading: false, error: null, items: [] });
  const [reloadKey, setReloadKey] = useState(0);
  const [filter, setFilter] = useState('');
  const [sort, setSort] = useState('name');
  const [view, setView] = useState(readView);
  const [newFolderOpen, setNewFolderOpen] = useState(false);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);
  const actions = useFileActions({ onChanged: reload });

  // "Create or upload > New folder" in the sidebar opens /files?new=1
  useEffect(() => {
    if (params.get('new') !== '1') return;
    setNewFolderOpen(true);
    const next = new URLSearchParams(params);
    next.delete('new');
    setParams(next, { replace: true });
  }, [params, setParams]);

  // Load the folder tree (all folders of the user).
  useEffect(() => {
    let cancelled = false;
    getFolders()
      .then((data) => !cancelled && setTree({ loading: false, error: null, data }))
      .catch((err) => !cancelled && setTree({ loading: false, error: getApiError(err), data: [] }));
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  // Load the files inside the open folder.
  useEffect(() => {
    if (!folderId) {
      setFiles({ loading: false, error: null, items: [] });
      return undefined;
    }
    let cancelled = false;
    setFiles((f) => ({ ...f, loading: true, error: null }));
    listDocuments({ folder_id: folderId, per_page: 100, sort: 'name', order: 'asc' })
      .then((data) => !cancelled && setFiles({ loading: false, error: null, items: data.items || [] }))
      .catch((err) => !cancelled && setFiles({ loading: false, error: getApiError(err), items: [] }));
    return () => {
      cancelled = true;
    };
  }, [folderId, reloadKey]);

  const current = folderId ? findFolderById(tree.data, folderId) : null;
  const breadcrumb = useMemo(() => {
    if (!current) return [];
    const ids = ancestorIds(tree.data, current.folder_id) || [];
    return [...ids.map((id) => findFolderById(tree.data, id)), current].filter(Boolean);
  }, [tree.data, current]);

  const subfolders = current ? current.children || [] : tree.data;

  // Filter by name (like OneDrive's "Filter by name") and sort.
  const text = filter.trim().toLowerCase();
  const byName = (a, b) => a.name.localeCompare(b.name);
  const byModified = (a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || ''));
  const shownFolders = subfolders.filter((f) => f.name.toLowerCase().includes(text)).sort(byName);
  const shownFiles = files.items
    .filter((d) => `${d.name} ${d.title || ''}`.toLowerCase().includes(text))
    .sort(sort === 'modified' ? byModified : byName);

  const openFolder = (folder) => {
    setFilter('');
    setParams(folder ? { folder: String(folder.folder_id) } : {});
  };

  const changeView = (next) => {
    setView(next);
    try {
      window.localStorage.setItem(VIEW_KEY, next);
    } catch {
      /* storage unavailable: keep the choice for this visit only */
    }
  };

  const saveNewFolder = async (name) => {
    await createFolder({ name, parentFolderId: current ? current.folder_id : null });
    toast.success(`Folder “${name}” created.`);
    setNewFolderOpen(false);
    reload();
  };

  const folderMenu = (folder) => [
    { label: 'Open', icon: 'bi-folder2-open', onClick: () => openFolder(folder) },
    { label: 'Summarise with AI', icon: 'bi-stars', onClick: () => actions.summariseFolder(folder) },
    { label: 'Rename', icon: 'bi-input-cursor-text', onClick: () => actions.renameFolder(folder) },
    { label: 'Delete', icon: 'bi-trash3', danger: true, onClick: () => actions.deleteFolder(folder) },
  ];
  const fileMenu = (doc) => [
    { label: 'Open', icon: 'bi-eye', onClick: () => navigate(`/documents/${doc.file_id}`) },
    { label: 'Download', icon: 'bi-download', onClick: () => actions.downloadFile(doc) },
    { label: 'Rename', icon: 'bi-input-cursor-text', onClick: () => actions.renameFile(doc) },
    { label: 'Delete', icon: 'bi-trash3', danger: true, onClick: () => actions.deleteFile(doc) },
  ];

  const loading = tree.loading || files.loading;
  const isEmpty = !loading && !shownFolders.length && !shownFiles.length;

  if (tree.error) {
    return (
      <div className="card fa-card">
        <ErrorState title="Couldn't load your files" message={tree.error.message} onRetry={reload} />
      </div>
    );
  }

  return (
    <div className="fa-page">
      {/* Breadcrumb: My files > University > Year 2 */}
      <nav aria-label="Folder path" className="mb-3">
        <ol className="breadcrumb fa-breadcrumb mb-0">
          <li className={`breadcrumb-item ${!current ? 'active' : ''}`}>
            {current ? (
              <button type="button" className="btn btn-link p-0" onClick={() => openFolder(null)}>
                My files
              </button>
            ) : (
              'My files'
            )}
          </li>
          {breadcrumb.map((folder, i) => (
            <li key={folder.folder_id} className={`breadcrumb-item ${i === breadcrumb.length - 1 ? 'active' : ''}`}>
              {i === breadcrumb.length - 1 ? (
                folder.name
              ) : (
                <button type="button" className="btn btn-link p-0" onClick={() => openFolder(folder)}>
                  {folder.name}
                </button>
              )}
            </li>
          ))}
        </ol>
      </nav>

      {/* Toolbar */}
      <div className="card fa-card mb-3">
        <div className="card-body py-2 d-flex flex-wrap align-items-center gap-2">
          <button type="button" className="btn btn-sm btn-primary" onClick={() => setNewFolderOpen(true)}>
            <i className="bi bi-folder-plus me-1" aria-hidden="true" />
            New folder
          </button>
          <Link to="/upload" className="btn btn-sm btn-light">
            <i className="bi bi-cloud-arrow-up me-1" aria-hidden="true" />
            Upload
          </Link>
          {current && (
            <>
              <span className="vr d-none d-sm-block" />
              <button type="button" className="btn btn-sm btn-light" onClick={() => actions.summariseFolder(current)}>
                <i className="bi bi-stars me-1 fa-text-cyan" aria-hidden="true" />
                Summarise with AI
              </button>
              <button type="button" className="btn btn-sm btn-light" onClick={() => actions.renameFolder(current)}>
                <i className="bi bi-input-cursor-text me-1" aria-hidden="true" />
                Rename
              </button>
              <button type="button" className="btn btn-sm btn-light text-danger" onClick={() => actions.deleteFolder(current)}>
                <i className="bi bi-trash3 me-1" aria-hidden="true" />
                Delete
              </button>
            </>
          )}
          <div className="ms-auto d-flex align-items-center gap-2">
            <input
              type="search"
              className="form-control form-control-sm fa-filter-input"
              placeholder="Filter by name"
              aria-label="Filter by name"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            <select
              className="form-select form-select-sm w-auto"
              aria-label="Sort by"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
            >
              <option value="name">Name</option>
              <option value="modified">Modified</option>
            </select>
            <div className="btn-group btn-group-sm" role="group" aria-label="View mode">
              <button
                type="button"
                className={`btn ${view === 'list' ? 'btn-primary' : 'btn-light'}`}
                onClick={() => changeView('list')}
                aria-pressed={view === 'list'}
                title="List view"
              >
                <i className="bi bi-list-ul" aria-hidden="true" />
                <span className="visually-hidden">List view</span>
              </button>
              <button
                type="button"
                className={`btn ${view === 'grid' ? 'btn-primary' : 'btn-light'}`}
                onClick={() => changeView('grid')}
                aria-pressed={view === 'grid'}
                title="Tiles view"
              >
                <i className="bi bi-grid-3x2-gap" aria-hidden="true" />
                <span className="visually-hidden">Tiles view</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {folderId && !tree.loading && !current && (
        <div className="card fa-card">
          <EmptyState
            icon="bi-folder-x"
            title="Folder not found"
            action={
              <button type="button" className="btn btn-outline-primary btn-sm" onClick={() => openFolder(null)}>
                Back to My files
              </button>
            }
          >
            It may have been renamed or deleted.
          </EmptyState>
        </div>
      )}

      {loading && !shownFolders.length && !shownFiles.length && (
        <div className="card fa-card">
          <div className="card-body">
            <SkeletonList rows={5} />
          </div>
        </div>
      )}

      {files.error && (
        <div className="card fa-card mb-3">
          <ErrorState compact title="Couldn't load the files" message={files.error.message} onRetry={reload} />
        </div>
      )}

      {isEmpty && (!folderId || current) && (
        <div className="card fa-card">
          {text ? (
            <EmptyState icon="bi-funnel" title="Nothing matches this filter">
              Try another name, or use AI Search to look inside your documents.
            </EmptyState>
          ) : (
            <EmptyState
              icon="bi-folder2-open"
              title={current ? 'This folder is empty' : 'No folders yet'}
              action={
                <Link to="/upload" className="btn btn-primary btn-sm">
                  Upload a document
                </Link>
              }
            >
              Upload a document and the AI will suggest which folder it belongs in.
            </EmptyState>
          )}
        </div>
      )}

      {/* List view (like OneDrive): Name | Modified | Size | Category | ⋯ */}
      {!isEmpty && view === 'list' && (shownFolders.length > 0 || shownFiles.length > 0) && (
        <div className={`card fa-card ${loading ? 'fa-loading-dim' : ''}`}>
          <div>
            <table className="table table-hover align-middle mb-0 fa-table fa-explorer">
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col" className="d-none d-md-table-cell">Modified</th>
                  <th scope="col" className="d-none d-sm-table-cell text-end">Size</th>
                  <th scope="col" className="d-none d-lg-table-cell">Category</th>
                  <th scope="col" className="text-end">
                    <span className="visually-hidden">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {shownFolders.map((folder) => (
                  <tr key={`folder-${folder.folder_id}`} className="fa-clickable" onClick={() => openFolder(folder)}>
                    <td className="fa-name-cell">
                      <div className="d-flex align-items-center gap-3 min-w-0">
                        <i className="bi bi-folder-fill fa-folder-icon fs-3" aria-hidden="true" />
                        <button
                          type="button"
                          className="btn btn-link p-0 fw-semibold text-body text-truncate text-decoration-none"
                          onClick={(e) => {
                            e.stopPropagation();
                            openFolder(folder);
                          }}
                        >
                          {folder.name}
                        </button>
                      </div>
                    </td>
                    <td className="d-none d-md-table-cell small text-muted">—</td>
                    <td className="d-none d-sm-table-cell small text-muted text-end text-nowrap">
                      {plural(countDocumentsDeep(folder), 'file')}
                      {folder.children?.length ? ` · ${plural(folder.children.length, 'folder')}` : ''}
                    </td>
                    <td className="d-none d-lg-table-cell" />
                    <td className="text-end">
                      <ActionMenu label={`Actions for folder ${folder.name}`} actions={folderMenu(folder)} />
                    </td>
                  </tr>
                ))}
                {shownFiles.map((doc) => (
                  <tr
                    key={`file-${doc.file_id}`}
                    className="fa-clickable"
                    onClick={() => navigate(`/documents/${doc.file_id}`)}
                  >
                    <td className="fa-name-cell">
                      <div className="d-flex align-items-center gap-3 min-w-0">
                        <FileIcon type={doc.file_type} name={doc.name} size={34} />
                        <div className="min-w-0">
                          <Link
                            to={`/documents/${doc.file_id}`}
                            className="fw-semibold d-block text-truncate text-body"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {doc.name}
                          </Link>
                          {doc.title && <div className="small text-muted text-truncate">{doc.title}</div>}
                        </div>
                      </div>
                    </td>
                    <td className="d-none d-md-table-cell small text-nowrap">{formatDate(doc.updated_at)}</td>
                    <td className="d-none d-sm-table-cell small text-end text-nowrap">{formatBytes(doc.file_size_bytes)}</td>
                    <td className="d-none d-lg-table-cell">
                      <CategoryBadge category={doc.category} />
                    </td>
                    <td className="text-end">
                      <ActionMenu label={`Actions for ${doc.name}`} actions={fileMenu(doc)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tiles view */}
      {!isEmpty && view === 'grid' && (
        <div className={`row g-3 ${loading ? 'fa-loading-dim' : ''}`}>
          {shownFolders.map((folder) => (
            <div key={`folder-${folder.folder_id}`} className="col-6 col-md-4 col-xl-3">
              <div className="card fa-card fa-tile h-100" onClick={() => openFolder(folder)} role="presentation">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start">
                    <i className="bi bi-folder-fill fa-folder-icon fa-tile-icon" aria-hidden="true" />
                    <ActionMenu label={`Actions for folder ${folder.name}`} actions={folderMenu(folder)} />
                  </div>
                  <button
                    type="button"
                    className="btn btn-link p-0 fw-semibold text-body text-truncate d-block text-decoration-none mw-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      openFolder(folder);
                    }}
                  >
                    {folder.name}
                  </button>
                  <div className="small text-muted">{plural(countDocumentsDeep(folder), 'file')}</div>
                </div>
              </div>
            </div>
          ))}
          {shownFiles.map((doc) => (
            <div key={`file-${doc.file_id}`} className="col-6 col-md-4 col-xl-3">
              <div className="card fa-card fa-tile h-100" onClick={() => navigate(`/documents/${doc.file_id}`)} role="presentation">
                <div className="card-body">
                  <div className="d-flex justify-content-between align-items-start">
                    <FileIcon type={doc.file_type} name={doc.name} size={44} />
                    <ActionMenu label={`Actions for ${doc.name}`} actions={fileMenu(doc)} />
                  </div>
                  <Link
                    to={`/documents/${doc.file_id}`}
                    className="fw-semibold text-body text-truncate d-block mt-2"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {doc.name}
                  </Link>
                  <div className="small text-muted">
                    {formatDate(doc.updated_at)} · {formatBytes(doc.file_size_bytes)}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <RenameModal
        key={newFolderOpen ? 'new-open' : 'new-closed'}
        item={newFolderOpen ? { kind: 'folder', name: '' } : null}
        title={current ? `New folder in “${current.name}”` : 'New folder'}
        submitLabel="Create folder"
        validate={folderSegmentError}
        onSave={saveNewFolder}
        onClose={() => setNewFolderOpen(false)}
      />
      {actions.dialogs}
    </div>
  );
}
