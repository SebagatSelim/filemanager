// "Your folders" on the Home page: one tile per top-level folder, with Summarise / Rename / Delete.
import { Link, useNavigate } from 'react-router-dom';
import ActionMenu from './ActionMenu';
import { EmptyState, SkeletonList } from '../Feedback';
import { plural } from '../../utils/format';
import { countDocumentsDeep } from '../../utils/folders';

const SHOW = 8;

export default function FolderTiles({ folders, loading, actions }) {
  const navigate = useNavigate();
  const open = (folder) => navigate(`/files?folder=${folder.folder_id}`);

  return (
    <div className="card fa-card">
      <div className="card-header fa-card-header">
        <div>
          <h2 className="fa-card-title mb-0">Your folders</h2>
          <div className="fa-card-subtitle">Open a folder, or let the AI summarise what is inside</div>
        </div>
        <Link to="/files" className="small text-nowrap">
          Open My files
        </Link>
      </div>
      <div className="card-body">
        {loading && !folders.length && <SkeletonList rows={2} />}
        {!loading && !folders.length && (
          <EmptyState icon="bi-folder2" title="No folders yet" compact>
            The AI creates folders such as University / Year 2 when you approve your first upload.
          </EmptyState>
        )}
        {folders.length > 0 && (
          <div className="row g-3">
            {folders.slice(0, SHOW).map((folder) => (
              <div key={folder.folder_id} className="col-6 col-md-4 col-xl-3">
                <div className="fa-folder-card h-100" onClick={() => open(folder)} role="presentation">
                  <div className="d-flex justify-content-between align-items-start">
                    <i className="bi bi-folder-fill fa-folder-icon fa-tile-icon" aria-hidden="true" />
                    <ActionMenu
                      label={`Actions for folder ${folder.name}`}
                      actions={[
                        { label: 'Open', icon: 'bi-folder2-open', onClick: () => open(folder) },
                        { label: 'Summarise with AI', icon: 'bi-stars', onClick: () => actions.summariseFolder(folder) },
                        { label: 'Rename', icon: 'bi-input-cursor-text', onClick: () => actions.renameFolder(folder) },
                        { label: 'Delete', icon: 'bi-trash3', danger: true, onClick: () => actions.deleteFolder(folder) },
                      ]}
                    />
                  </div>
                  <button
                    type="button"
                    className="btn btn-link p-0 fw-semibold text-body text-truncate d-block text-decoration-none mw-100"
                    onClick={(e) => {
                      e.stopPropagation();
                      open(folder);
                    }}
                  >
                    {folder.name}
                  </button>
                  <div className="small text-muted">{plural(countDocumentsDeep(folder), 'document')}</div>
                  <button
                    type="button"
                    className="btn btn-sm fa-summary-chip mt-2"
                    onClick={(e) => {
                      e.stopPropagation();
                      actions.summariseFolder(folder);
                    }}
                  >
                    <i className="bi bi-stars me-1" aria-hidden="true" />
                    AI summary
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
        {folders.length > SHOW && (
          <Link to="/files" className="small d-inline-block mt-3">
            See all {folders.length} folders
          </Link>
        )}
      </div>
    </div>
  );
}
