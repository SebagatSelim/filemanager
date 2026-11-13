// "AI suggested folder" card on the review page (teacher feedback: when a file is uploaded,
// the AI should say which of your EXISTING folders it belongs in).
// recommendations = [{ folder_id, path: [...], score, reason, is_new }] from GET /documents/{id}/analysis
import { formatPercent } from '../utils/format';
import { displayPath } from '../utils/folders';

const sameFolder = (a = [], b = []) =>
  a.length === b.length && a.every((name, i) => name.trim().toLowerCase() === String(b[i] || '').trim().toLowerCase());

export default function FolderSuggestions({ recommendations = [], selected = [], onPick, disabled = false }) {
  if (!recommendations.length) return null;
  return (
    <div className="fa-reco mb-4" aria-label="AI folder suggestions">
      <div className="d-flex align-items-center gap-2 mb-2">
        <i className="bi bi-stars fa-text-cyan" aria-hidden="true" />
        <span className="fw-semibold">AI suggested folder</span>
        <span className="small text-muted">· pick one, or type your own below</span>
      </div>
      <div className="d-grid gap-2">
        {recommendations.map((option, index) => {
          const active = sameFolder(option.path, selected);
          return (
            <button
              key={option.path.join('/')}
              type="button"
              className={`fa-reco-option ${active ? 'active' : ''}`}
              onClick={() => onPick([...option.path])}
              disabled={disabled}
              aria-pressed={active}
            >
              <i className={`bi ${option.is_new ? 'bi-folder-plus' : 'bi-folder-fill'} fa-folder-icon fs-4`} aria-hidden="true" />
              <span className="min-w-0 flex-grow-1 text-start">
                <span className="d-flex flex-wrap align-items-center gap-2">
                  <span className="fw-semibold text-truncate">{displayPath(option.path)}</span>
                  {index === 0 && <span className="badge rounded-pill text-bg-success">Best match</span>}
                  <span className={`badge rounded-pill ${option.is_new ? 'text-bg-warning' : 'fa-badge-soft'}`}>
                    {option.is_new ? 'New folder' : 'Existing folder'}
                  </span>
                </span>
                <span className="small text-muted d-block">{option.reason}</span>
              </span>
              <span className="small fw-semibold text-nowrap">{formatPercent(option.score)} match</span>
              {active && <i className="bi bi-check-circle-fill text-success" aria-hidden="true" />}
            </button>
          );
        })}
      </div>
    </div>
  );
}
