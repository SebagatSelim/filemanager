// "⋯" button that opens a small menu of actions (like the right-click menu in OneDrive).
// actions = [{ label, icon, onClick, danger? }]
import { useCallback, useRef, useState } from 'react';
import useClickOutside from '../../hooks/useClickOutside';

export default function ActionMenu({ actions, label = 'More actions' }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, close, open);

  return (
    <div className="dropdown fa-action-menu" ref={ref}>
      <button
        type="button"
        className="btn btn-sm fa-icon-button"
        aria-label={label}
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={(event) => {
          event.stopPropagation(); // don't also open the row
          setOpen((v) => !v);
        }}
      >
        <i className="bi bi-three-dots" aria-hidden="true" />
      </button>
      {open && (
        <div className="dropdown-menu dropdown-menu-end show fa-dropdown" role="menu">
          {actions.map((action) => (
            <button
              key={action.label}
              type="button"
              role="menuitem"
              className={`dropdown-item ${action.danger ? 'text-danger' : ''}`}
              onClick={(event) => {
                event.stopPropagation();
                close();
                action.onClick();
              }}
            >
              <i className={`bi ${action.icon} me-2`} aria-hidden="true" />
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
