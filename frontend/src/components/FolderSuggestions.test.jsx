import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import FolderSuggestions from './FolderSuggestions';
import { buildReviewForm } from '../pages/ReviewPage';

const recommendations = [
  {
    folder_id: 4,
    path: ['University', 'Year 2', 'Semester 1', 'Database Systems'],
    score: 0.75,
    reason: '1 similar document is already here',
    is_new: false,
  },
  { folder_id: null, path: ['University', 'Database Systems'], score: 0.45, reason: 'New folder', is_new: true },
];

describe('FolderSuggestions (AI suggested folder)', () => {
  it('shows each folder with its reason and marks the best existing one', () => {
    render(<FolderSuggestions recommendations={recommendations} selected={recommendations[0].path} onPick={() => {}} />);
    expect(screen.getByText('University / Year 2 / Semester 1 / Database Systems')).toBeInTheDocument();
    expect(screen.getByText('Best match')).toBeInTheDocument();
    expect(screen.getByText('Existing folder')).toBeInTheDocument();
    expect(screen.getByText('New folder', { selector: '.badge' })).toBeInTheDocument();
    expect(screen.getByText('1 similar document is already here')).toBeInTheDocument();
    expect(screen.getAllByRole('button')[0]).toHaveAttribute('aria-pressed', 'true');
  });

  it('picks a folder when clicked', async () => {
    const onPick = vi.fn();
    const user = userEvent.setup();
    render(<FolderSuggestions recommendations={recommendations} selected={[]} onPick={onPick} />);
    await user.click(screen.getByText('University / Database Systems'));
    expect(onPick).toHaveBeenCalledWith(['University', 'Database Systems']);
  });

  it('renders nothing without recommendations', () => {
    const { container } = render(<FolderSuggestions recommendations={[]} onPick={() => {}} />);
    expect(container).toBeEmptyDOMElement();
  });

  it('pre-fills the review form with the best suggested folder', () => {
    const form = buildReviewForm({
      original_name: 'lab.txt',
      suggestions: { title: 'Lab 5', suggested_folder_path: ['University', 'Database Systems'] },
      folder_recommendations: recommendations,
    });
    expect(form.folder_path).toEqual(['University', 'Year 2', 'Semester 1', 'Database Systems']);
  });
});
