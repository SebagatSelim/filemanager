// "Summarise with AI": an overview of everything inside a folder (and its subfolders).
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import Modal from '../Modal';
import { CategoryBadge, FileIcon } from '../Badges';
import { ErrorState, LoadingState } from '../Feedback';
import { getFolderSummary } from '../../api/folders';
import { getApiError } from '../../api/client';
import { formatBytes, plural } from '../../utils/format';

export default function FolderSummaryModal({ folder, onClose }) {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    if (!folder) return undefined;
    let cancelled = false;
    getFolderSummary(folder.folder_id)
      .then((data) => !cancelled && setState({ loading: false, error: null, data }))
      .catch((err) => !cancelled && setState({ loading: false, error: getApiError(err), data: null }));
    return () => {
      cancelled = true;
    };
  }, [folder]);

  const data = state.data;

  return (
    <Modal show={Boolean(folder)} title={`AI summary · ${folder?.name || ''}`} icon="bi-stars" size="lg" onClose={onClose}>
      {state.loading && <LoadingState label="Reading the folder…" />}
      {state.error && <ErrorState compact title="Couldn't summarise this folder" message={state.error.message} />}
      {data && (
        <>
          <p className="mb-3 fa-summary-text">{data.overview}</p>

          <div className="d-flex flex-wrap gap-2 mb-3 small">
            <span className="fa-chip">
              <i className="bi bi-file-earmark-text me-1" aria-hidden="true" />
              {plural(data.document_count, 'document')}
            </span>
            <span className="fa-chip">
              <i className="bi bi-folder2 me-1" aria-hidden="true" />
              {plural(data.subfolder_count, 'subfolder')}
            </span>
            <span className="fa-chip">
              <i className="bi bi-hdd me-1" aria-hidden="true" />
              {formatBytes(data.total_size_bytes)}
            </span>
            {Object.entries(data.file_types).map(([type, count]) => (
              <span key={type} className="fa-chip">
                {count} {type}
              </span>
            ))}
          </div>

          {data.categories.length > 0 && (
            <div className="d-flex flex-wrap gap-2 mb-3">
              {data.categories.map((c) => (
                <span key={c.category} className="d-inline-flex align-items-center gap-1 small">
                  <CategoryBadge category={c.category} />
                  <span className="text-muted">× {c.count}</span>
                </span>
              ))}
            </div>
          )}

          {data.top_keywords.length > 0 && (
            <p className="small mb-3">
              <span className="fw-semibold">Main topics: </span>
              {data.top_keywords.join(', ')}
            </p>
          )}

          {data.documents.length > 0 && (
            <>
              <h3 className="h6 fw-bold mt-4">What&apos;s inside</h3>
              <ul className="list-unstyled mb-0 d-grid gap-2">
                {data.documents.map((doc) => (
                  <li key={doc.file_id} className="d-flex gap-2">
                    <FileIcon type={doc.file_type} name={doc.name} size={30} />
                    <div className="min-w-0">
                      <Link to={`/documents/${doc.file_id}`} className="fw-semibold small d-block text-truncate" onClick={onClose}>
                        {doc.title || doc.name}
                      </Link>
                      {doc.summary && <div className="small text-muted fa-clamp-2">{doc.summary}</div>}
                    </div>
                  </li>
                ))}
              </ul>
              {data.document_count > data.documents.length && (
                <p className="small text-muted mt-2 mb-0">
                  …and {plural(data.document_count - data.documents.length, 'more document')}.
                </p>
              )}
            </>
          )}

          <p className="small text-muted mt-3 mb-0">
            <i className="bi bi-info-circle me-1" aria-hidden="true" />
            {data.source === 'openai' ? 'Written by OpenAI GPT' : 'Written by the built-in AI'} from the documents&apos;
            titles, keywords and summaries.
          </p>
        </>
      )}
    </Modal>
  );
}
