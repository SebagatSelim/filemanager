// "Recent files" list on the Home page, like OneDrive's Home (teacher feedback:
// "on the dashboard we can't see which files are ours").
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ActionMenu from './ActionMenu';
import { FileIcon } from '../Badges';
import { EmptyState, SkeletonList } from '../Feedback';
import { formatBytes, formatRelativeTime } from '../../utils/format';
import { displayPath } from '../../utils/folders';

const SHOW = 10;

/** docs = most recently changed documents; actions = useFileActions() */
export default function RecentFiles({ docs, loading, actions }) {
  const navigate = useNavigate();
  const [filter, setFilter] = useState('');

  const text = filter.trim().toLowerCase();
  const shown = docs.filter((d) => `${d.name} ${d.title || ''} ${d.folder_path || ''}`.toLowerCase().includes(text));

  return (
    <div className="card fa-card">
      <div className="card-header fa-card-header flex-wrap gap-2">
        <div>
          <h2 className="fa-card-title mb-0">Recent files</h2>
          <div className="fa-card-subtitle">Your latest uploaded and edited documents</div>
        </div>
        <div className="d-flex align-items-center gap-2 ms-auto">
          <input
            type="search"
            className="form-control form-control-sm fa-filter-input"
            placeholder="Filter by name"
            aria-label="Filter recent files by name"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <Link to="/documents" className="small text-nowrap">
            View all
          </Link>
        </div>
      </div>

      {loading && !docs.length && (
        <div className="card-body">
          <SkeletonList rows={5} />
        </div>
      )}
      {!loading && !docs.length && (
        <EmptyState icon="bi-clock-history" title="No files yet" compact>
          Files you upload and approve will be listed here.
        </EmptyState>
      )}
      {docs.length > 0 && !shown.length && (
        <EmptyState icon="bi-funnel" title="No recent file matches this name" compact />
      )}

      {shown.length > 0 && (
        <div>
          <table className="table table-hover align-middle mb-0 fa-table fa-explorer">
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col" className="d-none d-sm-table-cell">Modified</th>
                <th scope="col" className="d-none d-lg-table-cell">Location</th>
                <th scope="col" className="d-none d-md-table-cell text-end">Size</th>
                <th scope="col" className="text-end">
                  <span className="visually-hidden">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {shown.slice(0, SHOW).map((doc) => (
                <tr key={doc.file_id} className="fa-clickable" onClick={() => navigate(`/documents/${doc.file_id}`)}>
                  <td className="fa-name-cell">
                    <div className="d-flex align-items-center gap-3 min-w-0">
                      <FileIcon type={doc.file_type} name={doc.name} size={32} />
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
                  <td className="d-none d-sm-table-cell small text-nowrap">{formatRelativeTime(doc.updated_at)}</td>
                  <td className="d-none d-lg-table-cell small text-truncate fa-folder-cell">
                    {doc.folder_id ? (
                      <Link to={`/files?folder=${doc.folder_id}`} className="fa-link-muted" onClick={(e) => e.stopPropagation()}>
                        <i className="bi bi-folder2 me-1" aria-hidden="true" />
                        {displayPath(doc.folder_path)}
                      </Link>
                    ) : (
                      <span className="text-muted">Not filed</span>
                    )}
                  </td>
                  <td className="d-none d-md-table-cell small text-end text-nowrap">{formatBytes(doc.file_size_bytes)}</td>
                  <td className="text-end">
                    <ActionMenu
                      label={`Actions for ${doc.name}`}
                      actions={[
                        { label: 'Open', icon: 'bi-eye', onClick: () => navigate(`/documents/${doc.file_id}`) },
                        { label: 'Download', icon: 'bi-download', onClick: () => actions.downloadFile(doc) },
                        { label: 'Rename', icon: 'bi-input-cursor-text', onClick: () => actions.renameFile(doc) },
                        { label: 'Delete', icon: 'bi-trash3', danger: true, onClick: () => actions.deleteFile(doc) },
                      ]}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
