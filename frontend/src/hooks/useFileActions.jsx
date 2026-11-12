// Rename / delete / summarise for files and folders, shared by the Home page and My files.
//
// const actions = useFileActions({ onChanged: reload });
// actions.renameFile(doc)  actions.deleteFile(doc)  actions.downloadFile(doc)
// actions.renameFolder(folder)  actions.deleteFolder(folder)  actions.summariseFolder(folder)
// ...and render {actions.dialogs} once in the page.
import { useState } from 'react';
import ConfirmModal from '../components/ConfirmModal';
import FolderSummaryModal from '../components/files/FolderSummaryModal';
import RenameModal from '../components/files/RenameModal';
import { updateDocument } from '../api/documents';
import { deleteFolder as deleteFolderApi, renameFolder as renameFolderApi } from '../api/folders';
import { moveToRecycleBin } from '../api/trash';
import { getApiError } from '../api/client';
import { useToast } from '../context/ToastContext';
import { useWorkspace } from '../context/WorkspaceContext';
import { downloadDocument } from '../utils/download';
import { plural } from '../utils/format';
import { filenameError, folderSegmentError } from '../utils/validation';

export default function useFileActions({ onChanged }) {
  const toast = useToast();
  const { refresh } = useWorkspace();
  const [renaming, setRenaming] = useState(null); // { kind, id, name }
  const [deleting, setDeleting] = useState(null); // { kind, id, name }
  const [busy, setBusy] = useState(false);
  const [summaryFolder, setSummaryFolder] = useState(null);

  const changed = () => {
    refresh(); // sidebar counts and storage
    onChanged?.();
  };

  const saveRename = async (newName) => {
    if (renaming.kind === 'folder') {
      await renameFolderApi(renaming.id, newName);
    } else {
      await updateDocument(renaming.id, { filename: newName });
    }
    toast.success(`Renamed to “${newName}”.`);
    setRenaming(null);
    changed();
  };

  const confirmDelete = async () => {
    setBusy(true);
    try {
      if (deleting.kind === 'folder') {
        const result = await deleteFolderApi(deleting.id);
        const moved = result.documents_moved_to_recycle_bin;
        toast.success(
          moved ? `Folder deleted. ${plural(moved, 'document')} moved to the Recycle bin.` : 'Folder deleted.',
        );
      } else {
        await moveToRecycleBin(deleting.id);
        toast.success(`“${deleting.name}” moved to the Recycle bin.`);
      }
      setDeleting(null);
      changed();
    } catch (err) {
      toast.error(getApiError(err).message);
    } finally {
      setBusy(false);
    }
  };

  const downloadFile = async (doc) => {
    try {
      await downloadDocument(doc.file_id);
    } catch (err) {
      toast.error(getApiError(err).message);
    }
  };

  const dialogs = (
    <>
      <RenameModal
        key={renaming ? `rename-${renaming.kind}-${renaming.id}` : 'rename-closed'}
        item={renaming}
        validate={renaming?.kind === 'folder' ? folderSegmentError : filenameError}
        onSave={saveRename}
        onClose={() => setRenaming(null)}
      />
      <ConfirmModal
        show={Boolean(deleting)}
        title={deleting?.kind === 'folder' ? 'Delete this folder?' : 'Delete this file?'}
        confirmLabel="Delete"
        busy={busy}
        onConfirm={confirmDelete}
        onCancel={() => setDeleting(null)}
        icon="bi-trash3"
      >
        <strong>{deleting?.name}</strong>
        {deleting?.kind === 'folder'
          ? ' and its subfolders will be deleted. The documents inside go to the Recycle bin, so you can restore them.'
          : ' will be moved to the Recycle bin. You can restore it from there.'}
      </ConfirmModal>
      <FolderSummaryModal
        key={summaryFolder ? `summary-${summaryFolder.folder_id}` : 'summary-closed'}
        folder={summaryFolder}
        onClose={() => setSummaryFolder(null)}
      />
    </>
  );

  return {
    renameFile: (doc) => setRenaming({ kind: 'file', id: doc.file_id, name: doc.name }),
    deleteFile: (doc) => setDeleting({ kind: 'file', id: doc.file_id, name: doc.name }),
    downloadFile,
    renameFolder: (folder) => setRenaming({ kind: 'folder', id: folder.folder_id, name: folder.name }),
    deleteFolder: (folder) => setDeleting({ kind: 'folder', id: folder.folder_id, name: folder.name }),
    summariseFolder: (folder) => setSummaryFolder(folder),
    dialogs,
  };
}
