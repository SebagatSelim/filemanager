// Small dialog with one text box, used to rename a file or folder (and to name a new folder).
import { useState } from 'react';
import Modal from '../Modal';
import { getApiError } from '../../api/client';

/**
 * item     = { kind: 'file' | 'folder', name } or null (closed)
 * validate = (value) => error message or null
 * onSave   = async (value) => void   (throw to show the API error)
 * title / submitLabel are optional (default: "Rename file" / "Rename folder", "Rename")
 */
export default function RenameModal({ item, validate, onSave, onClose, title, submitLabel = 'Rename' }) {
  const [value, setValue] = useState(item?.name || '');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const submit = async (event) => {
    event.preventDefault();
    const problem = validate(value);
    if (problem) {
      setError(problem);
      return;
    }
    if (item.name && value.trim() === item.name) {
      onClose();
      return;
    }
    setBusy(true);
    try {
      await onSave(value.trim());
    } catch (err) {
      const apiError = getApiError(err);
      setError(apiError.fields.name || apiError.fields.filename || apiError.message);
      setBusy(false);
    }
  };

  return (
    <Modal
      show={Boolean(item)}
      title={title || (item?.kind === 'folder' ? 'Rename folder' : 'Rename file')}
      icon={item?.kind === 'folder' ? 'bi-folder2' : 'bi-input-cursor-text'}
      onClose={() => !busy && onClose()}
      closeDisabled={busy}
    >
      <form onSubmit={submit} noValidate>
        <label htmlFor="rename-value" className="form-label fa-label">
          {item?.name ? 'New name' : 'Name'}
        </label>
        <input
          id="rename-value"
          className={`form-control ${error ? 'is-invalid' : ''}`}
          value={value}
          onChange={(e) => {
            setValue(e.target.value);
            setError('');
          }}
          maxLength={item?.kind === 'folder' ? 100 : 255}
        />
        {error && <div className="invalid-feedback">{error}</div>}
        <div className="d-flex justify-content-end gap-2 mt-4">
          <button type="button" className="btn btn-light" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button type="submit" className="btn btn-primary" disabled={busy}>
            {busy && <span className="spinner-border spinner-border-sm me-2" aria-hidden="true" />}
            {submitLabel}
          </button>
        </div>
      </form>
    </Modal>
  );
}
