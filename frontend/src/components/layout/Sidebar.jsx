import { useCallback, useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router-dom';
import BrandLogo from '../BrandLogo';
import StorageWidget from '../StorageWidget';
import { useWorkspace } from '../../context/WorkspaceContext';
import useClickOutside from '../../hooks/useClickOutside';
import useSignOut from '../../hooks/useSignOut';

const REVIEW_ROUTE = /^\/documents\/[^/]+\/review\/?$/;

/** `active` (optional boolean) overrides NavLink's own prefix matching. */
function NavItem({ to, icon, label, badge, end = false, onNavigate, active }) {
  const content = (
    <>
      <span className="fa-nav-icon" aria-hidden="true">
        <i className={`bi ${icon}`} />
      </span>
      <span className="flex-grow-1">{label}</span>
      {badge > 0 && (
        <span className="fa-nav-badge" title={`${badge} documents need attention`}>
          {badge > 99 ? '99+' : badge}
          <span className="visually-hidden"> documents need attention</span>
        </span>
      )}
    </>
  );
  if (active !== undefined) {
    return (
      <Link
        to={to}
        className={`fa-nav-link ${active ? 'active' : ''}`}
        aria-current={active ? 'page' : undefined}
        onClick={onNavigate}
      >
        {content}
      </Link>
    );
  }
  return (
    <NavLink
      to={to}
      end={end}
      className={({ isActive }) => `fa-nav-link ${isActive ? 'active' : ''}`}
      onClick={onNavigate}
    >
      {content}
    </NavLink>
  );
}

/** OneDrive-style "+ Create or upload" button with a small menu. */
function CreateMenu({ onNavigate }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const close = useCallback(() => setOpen(false), []);
  useClickOutside(ref, close, open);
  const pick = () => {
    close();
    onNavigate?.();
  };
  return (
    <div className="dropdown fa-create-menu" ref={ref}>
      <button
        type="button"
        className="btn btn-primary fa-btn-gradient w-100 fa-create-button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <i className="bi bi-plus-lg me-2" aria-hidden="true" />
        Create or upload
      </button>
      {open && (
        <div className="dropdown-menu show fa-dropdown w-100" role="menu">
          <Link to="/upload" className="dropdown-item" role="menuitem" onClick={pick}>
            <i className="bi bi-cloud-arrow-up me-2" aria-hidden="true" />
            Upload files
          </Link>
          <Link to="/files?new=1" className="dropdown-item" role="menuitem" onClick={pick}>
            <i className="bi bi-folder-plus me-2" aria-hidden="true" />
            New folder
          </Link>
        </div>
      )}
    </div>
  );
}

export default function Sidebar({ open, onClose }) {
  const { stats, loading } = useWorkspace();
  const signOut = useSignOut();
  const { pathname } = useLocation();
  // The per-document review page belongs to the Review Queue section, not Documents.
  const onReviewPage = REVIEW_ROUTE.test(pathname);
  // Review queue = documents awaiting review + documents whose processing failed.
  const reviewCount = (stats?.awaiting_review || 0) + (stats?.failed || 0);

  return (
    <aside id="fa-sidebar" className={`fa-sidebar ${open ? 'show' : ''}`} aria-label="Main navigation">
      <div className="fa-sidebar-header">
        <Link to="/" className="text-decoration-none" onClick={onClose} aria-label="FileAI dashboard">
          <BrandLogo size={38} />
        </Link>
        <button type="button" className="btn fa-sidebar-close d-lg-none" onClick={onClose} aria-label="Close menu">
          <i className="bi bi-x-lg" aria-hidden="true" />
        </button>
      </div>

      <div className="px-3 pt-1 pb-2">
        <CreateMenu onNavigate={onClose} />
      </div>

      <nav className="fa-sidebar-nav">
        <div className="fa-nav-section">Main menu</div>
        <NavItem to="/" end icon="bi-house-door" label="Home" onNavigate={onClose} />
        <NavItem to="/files" icon="bi-folder2" label="My files" onNavigate={onClose} />
        <NavItem to="/search" icon="bi-stars" label="AI Search" onNavigate={onClose} />
        <NavItem
          to="/review"
          icon="bi-cpu"
          label="Review Queue"
          badge={reviewCount}
          onNavigate={onClose}
          active={onReviewPage ? true : undefined}
        />

        <NavItem to="/recycle-bin" icon="bi-trash3" label="Recycle bin" onNavigate={onClose} />

        <div className="fa-nav-section">Browse files by</div>
        <NavItem
          to="/documents"
          icon="bi-file-earmark-text"
          label="All documents"
          onNavigate={onClose}
          active={onReviewPage ? false : undefined}
        />
        <NavItem to="/categories" icon="bi-tags" label="Categories" onNavigate={onClose} />
      </nav>

      <div className="fa-sidebar-footer">
        <NavItem to="/settings" icon="bi-person-gear" label="Profile & Settings" onNavigate={onClose} />
        <button type="button" className="fa-nav-link w-100" onClick={signOut}>
          <span className="fa-nav-icon" aria-hidden="true">
            <i className="bi bi-box-arrow-right" />
          </span>
          <span className="flex-grow-1 text-start">Sign out</span>
        </button>
        <div className="mt-3">
          <StorageWidget
            variant="dark"
            usedBytes={stats?.storage_used_bytes}
            quotaBytes={stats?.storage_quota_bytes}
            loading={loading && !stats}
          />
        </div>
      </div>
    </aside>
  );
}
