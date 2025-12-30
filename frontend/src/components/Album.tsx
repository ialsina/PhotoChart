import { useState, useEffect } from "react";
import { api } from "../api";
import type { Album } from "../types";

export function Album() {
  const [albums, setAlbums] = useState<Album[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showEditModal, setShowEditModal] = useState(false);
  const [editingAlbum, setEditingAlbum] = useState<Album | null>(null);
  const [formData, setFormData] = useState({ name: "", description: "" });
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  useEffect(() => {
    loadAlbums();
  }, []);

  const loadAlbums = async () => {
    try {
      setLoading(true);
      setError(null);
      const allAlbums = await api.getAllAlbums();
      setAlbums(allAlbums);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load albums");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const newAlbum = await api.createAlbum({
        name: formData.name,
        description: formData.description || "",
      });
      setAlbums([newAlbum, ...albums]);
      setShowCreateModal(false);
      setFormData({ name: "", description: "" });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create album");
    }
  };

  const handleEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingAlbum) return;
    try {
      const updatedAlbum = await api.updateAlbum(editingAlbum.id, {
        name: formData.name,
        description: formData.description || "",
      });
      setAlbums(
        albums.map((a) => (a.id === updatedAlbum.id ? updatedAlbum : a))
      );
      setShowEditModal(false);
      setEditingAlbum(null);
      setFormData({ name: "", description: "" });
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to update album");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteAlbum(id);
      setAlbums(albums.filter((a) => a.id !== id));
      setDeleteConfirm(null);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete album");
    }
  };

  const openEditModal = (album: Album) => {
    setEditingAlbum(album);
    setFormData({ name: album.name, description: album.description || "" });
    setShowEditModal(true);
  };

  const closeModals = () => {
    setShowCreateModal(false);
    setShowEditModal(false);
    setEditingAlbum(null);
    setFormData({ name: "", description: "" });
    setDeleteConfirm(null);
  };

  return (
    <div className="album">
      <div className="album-header">
        <h2>Albums</h2>
        <button
          className="create-button"
          onClick={() => setShowCreateModal(true)}
        >
          + Create Album
        </button>
      </div>

      {loading ? (
        <div className="loading">Loading...</div>
      ) : error ? (
        <div className="error">Error: {error}</div>
      ) : (
        <div className="albums-list">
          {albums.length === 0 ? (
            <p className="empty-state">No albums found. Create your first album!</p>
          ) : (
            albums.map((album) => (
              <div key={album.id} className="album-card">
                <div className="album-header-card">
                  <h3 className="album-name">{album.name}</h3>
                  <div className="album-actions">
                    <button
                      className="edit-button"
                      onClick={() => openEditModal(album)}
                      title="Edit album"
                    >
                      ✏️
                    </button>
                    <button
                      className="delete-button"
                      onClick={() => setDeleteConfirm(album.id)}
                      title="Delete album"
                    >
                      🗑️
                    </button>
                  </div>
                </div>
                {album.description && (
                  <p className="album-description">{album.description}</p>
                )}
                <div className="album-footer">
                  <span className="album-photos-count">
                    {album.photos_count} photo{album.photos_count !== 1 ? "s" : ""}
                  </span>
                  <span className="album-date">
                    Created: {new Date(album.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Create Modal */}
      {showCreateModal && (
        <div className="modal-overlay" onClick={closeModals}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Create Album</h3>
              <button className="modal-close" onClick={closeModals}>
                ×
              </button>
            </div>
            <form onSubmit={handleCreate} className="album-form">
              <div className="form-group">
                <label htmlFor="create-name">Name *</label>
                <input
                  id="create-name"
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  required
                  placeholder="Enter album name"
                />
              </div>
              <div className="form-group">
                <label htmlFor="create-description">Description</label>
                <textarea
                  id="create-description"
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  placeholder="Enter album description (optional)"
                  rows={4}
                />
              </div>
              <div className="form-actions">
                <button type="button" onClick={closeModals} className="cancel-button">
                  Cancel
                </button>
                <button type="submit" className="submit-button">
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Modal */}
      {showEditModal && editingAlbum && (
        <div className="modal-overlay" onClick={closeModals}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Edit Album</h3>
              <button className="modal-close" onClick={closeModals}>
                ×
              </button>
            </div>
            <form onSubmit={handleEdit} className="album-form">
              <div className="form-group">
                <label htmlFor="edit-name">Name *</label>
                <input
                  id="edit-name"
                  type="text"
                  value={formData.name}
                  onChange={(e) =>
                    setFormData({ ...formData, name: e.target.value })
                  }
                  required
                  placeholder="Enter album name"
                />
              </div>
              <div className="form-group">
                <label htmlFor="edit-description">Description</label>
                <textarea
                  id="edit-description"
                  value={formData.description}
                  onChange={(e) =>
                    setFormData({ ...formData, description: e.target.value })
                  }
                  placeholder="Enter album description (optional)"
                  rows={4}
                />
              </div>
              <div className="form-actions">
                <button type="button" onClick={closeModals} className="cancel-button">
                  Cancel
                </button>
                <button type="submit" className="submit-button">
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {deleteConfirm !== null && (
        <div className="modal-overlay" onClick={() => setDeleteConfirm(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>Delete Album</h3>
              <button
                className="modal-close"
                onClick={() => setDeleteConfirm(null)}
              >
                ×
              </button>
            </div>
            <div className="delete-confirmation">
              <p>
                Are you sure you want to delete "{albums.find((a) => a.id === deleteConfirm)?.name}"?
              </p>
              <p className="delete-warning">This action cannot be undone.</p>
              <div className="form-actions">
                <button
                  type="button"
                  onClick={() => setDeleteConfirm(null)}
                  className="cancel-button"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={() => handleDelete(deleteConfirm)}
                  className="delete-confirm-button"
                >
                  Delete
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
