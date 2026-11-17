import { matchPath } from 'react-router-dom';

// Order matters: more specific patterns first.
const PAGE_TITLES = [
  ['/documents/:id/review', 'AI Analysis & Metadata'],
  ['/documents/:id', 'Document Details'],
  ['/documents', 'All documents'],
  ['/upload', 'Upload Files'],
  ['/search', 'AI Search'],
  ['/review', 'Review Queue'],
  ['/files', 'My files'],
  ['/recycle-bin', 'Recycle bin'],
  ['/categories', 'Categories'],
  ['/settings', 'Profile & Settings'],
  ['/', 'Home'],
];

export function getPageTitle(pathname) {
  const match = PAGE_TITLES.find(([pattern]) => matchPath({ path: pattern, end: true }, pathname));
  return match ? match[1] : 'FileAI';
}
