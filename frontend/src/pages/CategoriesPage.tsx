import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Modal from '../components/ui/Modal';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import {
  Tag,
  Plus,
  Edit2,
  Trash2,
  ChevronRight,
  ChevronDown,
  FolderPlus,
  Shield,
  AlertCircle
} from 'lucide-react';

interface CategoryItem {
  id: string;
  name: string;
  parent_id: string | null;
  is_system: boolean;
  is_protected: boolean;
  icon: string | null;
  color: string | null;
  subcategories?: CategoryItem[];
}

export default function CategoriesPage() {
  const queryClient = useQueryClient();
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  
  // Modal states
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [parentForNew, setParentForNew] = useState<string | null>(null);
  const [editingCategory, setEditingCategory] = useState<CategoryItem | null>(null);
  const [deletingCategory, setDeletingCategory] = useState<CategoryItem | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [color, setColor] = useState('#F59E0B');
  const [formError, setFormError] = useState('');

  const { data: categories = [], isLoading, error } = useQuery<CategoryItem[]>({
    queryKey: ['categories'],
    queryFn: async () => {
      const res = await api.get('/categories');
      return res.data;
    },
  });

  const toggleExpand = (id: string) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const createMutation = useMutation({
    mutationFn: async (payload: { name: string; parent_id?: string | null; color?: string }) => {
      return api.post('/categories', payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to create category');
    },
  });

  const updateMutation = useMutation({
    mutationFn: async ({ id, payload }: { id: string; payload: { name?: string; color?: string } }) => {
      return api.patch(`/categories/${id}`, payload);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to update category');
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      return api.delete(`/categories/${id}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['categories'] });
      setDeletingCategory(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to delete category (it may be in use or protected)');
      setDeletingCategory(null);
    },
  });

  const closeModals = () => {
    setIsAddModalOpen(false);
    setParentForNew(null);
    setEditingCategory(null);
    setName('');
    setColor('#F59E0B');
    setFormError('');
  };

  const handleOpenAdd = (parentId: string | null = null) => {
    setParentForNew(parentId);
    setName('');
    setColor('#F59E0B');
    setFormError('');
    setIsAddModalOpen(true);
  };

  const handleOpenEdit = (cat: CategoryItem) => {
    setEditingCategory(cat);
    setName(cat.name);
    setColor(cat.color || '#F59E0B');
    setFormError('');
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Category name is required');
      return;
    }

    if (editingCategory) {
      updateMutation.mutate({
        id: editingCategory.id,
        payload: { name: name.trim(), color },
      });
    } else {
      createMutation.mutate({
        name: name.trim(),
        parent_id: parentForNew,
        color,
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Categories</h1>
          <p className="text-sm text-text-secondary mt-1">
            Organize expenses with 1-level nested categories. Protected categories cannot be deleted.
          </p>
        </div>
        <Button onClick={() => handleOpenAdd(null)}>
          <Plus className="w-4 h-4 mr-2" />
          Add Root Category
        </Button>
      </div>

      {/* Main Content */}
      <Card>
        {isLoading ? (
          <div className="space-y-4 p-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        ) : error ? (
          <div className="p-8 text-center text-accent-expense">
            <AlertCircle className="w-8 h-8 mx-auto mb-2" />
            <p>Failed to load categories</p>
          </div>
        ) : categories.length === 0 ? (
          <div className="p-8 text-center text-text-secondary">
            <Tag className="w-10 h-10 mx-auto mb-2 opacity-50" />
            <p className="font-medium">No categories found</p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {categories.map((cat) => {
              const isExp = expanded[cat.id] ?? true;
              const hasSubs = cat.subcategories && cat.subcategories.length > 0;

              return (
                <div key={cat.id} className="p-4 transition hover:bg-surface-elevated/50">
                  {/* Root Row */}
                  <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <button
                        onClick={() => toggleExpand(cat.id)}
                        className={`p-1 rounded text-text-secondary hover:text-text-primary ${!hasSubs ? 'invisible' : ''}`}
                      >
                        {isExp ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                      </button>

                      <div
                        className="w-3.5 h-3.5 rounded-full flex-shrink-0"
                        style={{ backgroundColor: cat.color || '#F59E0B' }}
                      />

                      <div className="flex items-center space-x-2">
                        <span className="font-semibold text-text-primary">{cat.name}</span>
                        {cat.is_protected && (
                          <Badge variant="neutral" className="flex items-center space-x-1 text-xs">
                            <Shield className="w-3 h-3 mr-1 text-primary-500" />
                            Protected
                          </Badge>
                        )}
                        {hasSubs && (
                          <span className="text-xs text-text-muted">
                            ({cat.subcategories?.length} subcategories)
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center space-x-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenAdd(cat.id)}
                        title="Add Subcategory"
                      >
                        <FolderPlus className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleOpenEdit(cat)}
                        title="Edit Category"
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      {!cat.is_protected && (
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setDeletingCategory(cat)}
                          className="text-accent-expense hover:bg-accent-expense/10"
                          title="Delete Category"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      )}
                    </div>
                  </div>

                  {/* Subcategories list */}
                  {hasSubs && isExp && (
                    <div className="mt-3 ml-8 pl-4 border-l-2 border-border space-y-2">
                      {cat.subcategories?.map((sub) => (
                        <div
                          key={sub.id}
                          className="flex items-center justify-between py-2 px-3 rounded-lg bg-surface hover:bg-surface-elevated transition"
                        >
                          <div className="flex items-center space-x-3">
                            <div
                              className="w-2.5 h-2.5 rounded-full"
                              style={{ backgroundColor: sub.color || cat.color || '#F59E0B' }}
                            />
                            <span className="text-sm font-medium text-text-primary">{sub.name}</span>
                            {sub.is_protected && (
                              <Badge variant="neutral" className="text-[10px]">
                                Protected
                              </Badge>
                            )}
                          </div>

                          <div className="flex items-center space-x-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleOpenEdit(sub)}
                              title="Edit Subcategory"
                            >
                              <Edit2 className="w-3.5 h-3.5" />
                            </Button>
                            {!sub.is_protected && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setDeletingCategory(sub)}
                                className="text-accent-expense hover:bg-accent-expense/10"
                                title="Delete Subcategory"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Add / Edit Modal */}
      <Modal
        isOpen={isAddModalOpen || !!editingCategory}
        onClose={closeModals}
        title={
          editingCategory
            ? `Edit Category: ${editingCategory.name}`
            : parentForNew
            ? 'Add Subcategory'
            : 'Add Root Category'
        }
      >
        <form onSubmit={handleSubmit} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <Input
            label="Category Name"
            placeholder="e.g. Groceries, Gym, Rent"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />

          <div>
            <label className="block text-sm font-medium text-text-primary mb-2">Color Tag</label>
            <div className="flex items-center space-x-3">
              <input
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="w-10 h-10 p-0 rounded border border-border cursor-pointer bg-transparent"
              />
              <span className="text-xs text-text-secondary font-mono">{color}</span>
            </div>
          </div>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button
              type="submit"
              isLoading={createMutation.isPending || updateMutation.isPending}
            >
              {editingCategory ? 'Save Changes' : 'Create Category'}
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={!!deletingCategory}
        onClose={() => setDeletingCategory(null)}
        title="Delete Category"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to delete <span className="font-semibold text-text-primary">"{deletingCategory?.name}"</span>?
          </p>
          <p className="text-xs text-text-muted">
            Note: You cannot delete a category if it currently has transactions associated with it or if it is a protected system category.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setDeletingCategory(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={deleteMutation.isPending}
              onClick={() => deletingCategory && deleteMutation.mutate(deletingCategory.id)}
            >
              Confirm Delete
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
