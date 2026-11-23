import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useAuth } from '../context/AuthContext';
import Card from '../components/ui/Card';
import Button from '../components/ui/Button';
import Input from '../components/ui/Input';
import Modal from '../components/ui/Modal';
import Badge from '../components/ui/Badge';
import Skeleton from '../components/ui/Skeleton';
import {
  Users,
  Plus,
  UserPlus,
  LogOut,
  Trash2,
  Crown,
  CheckCircle,
  Clock,
  ShieldAlert
} from 'lucide-react';

interface GroupMember {
  id: string;
  username: string;
  email: string;
  status: 'active' | 'invited';
  joined_at: string | null;
  is_creator: boolean;
}

interface GroupSummary {
  id: number | string;
  name: string;
  description?: string | null;
  creator_id?: number;
  creator_username?: string | null;
  created_by?: string;
  created_at: string;
  member_count: number;
  is_creator?: boolean;
  user_status?: string;
  my_status?: 'active' | 'invited';
}

interface GroupDetail extends GroupSummary {
  members: GroupMember[];
}

export default function GroupsPage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [selectedGroupId, setSelectedGroupId] = useState<string | null>(null);

  // Modals
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isInviteModalOpen, setIsInviteModalOpen] = useState(false);
  const [deletingGroup, setDeletingGroup] = useState<GroupSummary | null>(null);
  const [leavingGroup, setLeavingGroup] = useState<GroupSummary | null>(null);

  // Form states
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [inviteUsername, setInviteUsername] = useState('');
  const [formError, setFormError] = useState('');

  // Fetch groups list
  const { data: groups = [], isLoading } = useQuery<GroupSummary[]>({
    queryKey: ['groups'],
    queryFn: async () => {
      const res = await api.get('/groups');
      return res.data;
    },
  });

  // Fetch active selected group details
  const { data: selectedGroup, isLoading: isLoadingDetail } = useQuery<GroupDetail>({
    queryKey: ['group-detail', selectedGroupId],
    queryFn: async () => {
      const res = await api.get(`/groups/${selectedGroupId}`);
      return res.data;
    },
    enabled: !!selectedGroupId,
  });

  const createGroupMutation = useMutation({
    mutationFn: async (payload: { name: string; description?: string }) => {
      return api.post('/groups', payload);
    },
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      closeModals();
      setSelectedGroupId(res.data.id.toString());
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to create group');
    },
  });

  const inviteMemberMutation = useMutation({
    mutationFn: async ({ groupId, username }: { groupId: string; username: string }) => {
      return api.post(`/groups/${groupId}/invite`, { username });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['group-detail', selectedGroupId] });
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      closeModals();
    },
    onError: (err: any) => {
      setFormError(err.response?.data?.message || 'Failed to invite user (user may not exist, is already in group, or block in place)');
    },
  });

  const acceptInviteMutation = useMutation({
    mutationFn: async (groupId: string) => {
      return api.post(`/groups/${groupId}/accept`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      queryClient.invalidateQueries({ queryKey: ['group-detail', selectedGroupId] });
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to accept group invite');
    },
  });

  const leaveGroupMutation = useMutation({
    mutationFn: async (groupId: string) => {
      return api.post(`/groups/${groupId}/leave`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      setSelectedGroupId(null);
      setLeavingGroup(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to leave group');
      setLeavingGroup(null);
    },
  });

  const deleteGroupMutation = useMutation({
    mutationFn: async (groupId: string) => {
      return api.delete(`/groups/${groupId}`);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['groups'] });
      if (selectedGroupId === deletingGroup?.id.toString()) {
        setSelectedGroupId(null);
      }
      setDeletingGroup(null);
    },
    onError: (err: any) => {
      alert(err.response?.data?.message || 'Failed to delete group');
      setDeletingGroup(null);
    },
  });

  const closeModals = () => {
    setIsCreateModalOpen(false);
    setIsInviteModalOpen(false);
    setName('');
    setDescription('');
    setInviteUsername('');
    setFormError('');
  };

  const handleCreateGroup = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) {
      setFormError('Group name is required');
      return;
    }
    createGroupMutation.mutate({
      name: name.trim(),
      description: description.trim() || undefined,
    });
  };

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedGroupId || !inviteUsername.trim()) {
      setFormError('Username is required');
      return;
    }
    inviteMemberMutation.mutate({
      groupId: selectedGroupId,
      username: inviteUsername.trim().toLowerCase(),
    });
  };

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-text-primary">Permanent Groups</h1>
          <p className="text-sm text-text-secondary mt-1">
            Group rooms for roommates, trips, and projects with creator succession logic.
          </p>
        </div>
        <Button onClick={() => { closeModals(); setIsCreateModalOpen(true); }}>
          <Plus className="w-4 h-4 mr-2" />
          Create Group
        </Button>
      </div>

      {/* Main Grid: Groups List & Group Detail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Groups List */}
        <div className="lg:col-span-1 space-y-3">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-text-secondary">
            Your Groups ({groups.length})
          </h2>

          {isLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-20 w-full" />
              <Skeleton className="h-20 w-full" />
            </div>
          ) : groups.length === 0 ? (
            <Card className="p-8 text-center text-text-secondary">
              <Users className="w-10 h-10 mx-auto mb-2 opacity-40" />
              <p className="text-sm font-medium">No groups yet</p>
              <p className="text-xs text-text-muted mt-1 mb-3">
                Create a group to easily share expenses with frequent companions.
              </p>
              <Button size="sm" onClick={() => { closeModals(); setIsCreateModalOpen(true); }}>
                Create Group
              </Button>
            </Card>
          ) : (
            <div className="space-y-2">
              {groups.map((grp) => {
                const isSelected = selectedGroupId === grp.id.toString();
                const isInvited = grp.user_status === 'invited' || grp.my_status === 'invited';
                const isCreator = grp.is_creator || (user?.username && grp.creator_username === user?.username);

                return (
                  <Card
                    key={grp.id}
                    onClick={() => setSelectedGroupId(grp.id.toString())}
                    className={`p-4 cursor-pointer transition border-2 ${
                      isSelected
                        ? 'border-primary-500 bg-primary-500/5'
                        : 'border-transparent hover:border-border hover:bg-surface-elevated/40'
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex items-center space-x-3">
                        <div className="p-2 rounded-lg bg-surface-elevated text-primary-500">
                          <Users className="w-4 h-4" />
                        </div>
                        <div>
                          <h3 className="font-semibold text-text-primary text-sm flex items-center space-x-1.5">
                            <span>{grp.name}</span>
                            {isCreator && (
                              <span title="Creator">
                                <Crown className="w-3.5 h-3.5 text-primary-500" />
                              </span>
                            )}
                          </h3>
                          <p className="text-xs text-text-muted">
                            {grp.member_count} member{grp.member_count !== 1 ? 's' : ''}
                          </p>
                        </div>
                      </div>

                      {isInvited && (
                        <Button
                          size="sm"
                          className="text-xs h-7 px-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            acceptInviteMutation.mutate(grp.id.toString());
                          }}
                        >
                          Join
                        </Button>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </div>

        {/* Right: Selected Group Detail */}
        <div className="lg:col-span-2">
          {!selectedGroupId ? (
            <Card className="p-12 text-center text-text-secondary h-full flex flex-col items-center justify-center">
              <Users className="w-12 h-12 mb-3 opacity-30" />
              <p className="text-sm font-medium">Select a group to see members and actions</p>
            </Card>
          ) : isLoadingDetail || !selectedGroup ? (
            <Card className="p-6 space-y-4">
              <Skeleton className="h-8 w-48" />
              <Skeleton className="h-24 w-full" />
            </Card>
          ) : (
            <Card className="p-6 space-y-6">
              {/* Header */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
                <div>
                  <div className="flex items-center space-x-2">
                    <h2 className="text-xl font-bold text-text-primary">{selectedGroup.name}</h2>
                    {selectedGroup.is_creator && (
                      <Badge variant="primary" className="text-xs">
                        Admin
                      </Badge>
                    )}
                  </div>
                  {selectedGroup.description && (
                    <p className="text-sm text-text-secondary mt-1">{selectedGroup.description}</p>
                  )}
                  <p className="text-xs text-text-muted mt-1">
                    Created by @{selectedGroup.created_by} on{' '}
                    {new Date(selectedGroup.created_at).toLocaleDateString()}
                  </p>
                </div>

                <div className="flex items-center space-x-2">
                  <Button size="sm" onClick={() => setIsInviteModalOpen(true)}>
                    <UserPlus className="w-4 h-4 mr-1.5" />
                    Invite
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="text-accent-expense border-accent-expense/30 hover:bg-accent-expense/10"
                    onClick={() => setLeavingGroup(selectedGroup)}
                  >
                    <LogOut className="w-4 h-4 mr-1.5" />
                    Leave
                  </Button>
                  {selectedGroup.is_creator && (
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-accent-expense hover:bg-accent-expense/10"
                      onClick={() => setDeletingGroup(selectedGroup)}
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
              </div>

              {/* Members List */}
              <div>
                <h3 className="text-sm font-semibold uppercase tracking-wider text-text-secondary mb-3">
                  Members ({selectedGroup.members.length})
                </h3>

                <div className="divide-y divide-border rounded-lg border border-border overflow-hidden">
                  {selectedGroup.members.map((m) => (
                    <div
                      key={m.id}
                      className="p-3.5 flex items-center justify-between bg-surface hover:bg-surface-elevated transition"
                    >
                      <div className="flex items-center space-x-3">
                        <div className="w-8 h-8 rounded-full bg-primary-500/10 text-primary-500 flex items-center justify-center font-bold text-xs uppercase">
                          {m.username.slice(0, 2)}
                        </div>
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="font-semibold text-text-primary text-sm">
                              @{m.username}
                            </span>
                            {m.is_creator && (
                              <span title="Creator">
                                <Crown className="w-3.5 h-3.5 text-primary-500" />
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-text-muted">
                            {m.status === 'active' ? (
                              `Joined ${m.joined_at ? new Date(m.joined_at).toLocaleDateString() : ''}`
                            ) : (
                              'Invite pending'
                            )}
                          </span>
                        </div>
                      </div>

                      <Badge variant={m.status === 'active' ? 'income' : 'neutral'}>
                        {m.status === 'active' ? 'Active' : 'Invited'}
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* Create Group Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={closeModals}
        title="Create Permanent Group"
      >
        <form onSubmit={handleCreateGroup} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <Input
            label="Group Name"
            placeholder="e.g. Goa Trip 2026, Flat 402 Roommates"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
            autoFocus
          />

          <Input
            label="Description (Optional)"
            placeholder="e.g. Shared household expenses & rent"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button type="submit" isLoading={createGroupMutation.isPending}>
              Create Group
            </Button>
          </div>
        </form>
      </Modal>

      {/* Invite Member Modal */}
      <Modal
        isOpen={isInviteModalOpen}
        onClose={closeModals}
        title={`Invite to ${selectedGroup?.name}`}
      >
        <form onSubmit={handleInvite} className="space-y-4">
          {formError && (
            <div className="p-3 text-sm rounded bg-accent-expense/10 text-accent-expense border border-accent-expense/20">
              {formError}
            </div>
          )}

          <Input
            label="Username to Invite"
            placeholder="e.g. bob"
            value={inviteUsername}
            onChange={(e) => setInviteUsername(e.target.value)}
            required
            autoFocus
          />

          <p className="text-xs text-text-muted">
            The user will receive an in-app notification and invitation to join this group.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" type="button" onClick={closeModals}>
              Cancel
            </Button>
            <Button type="submit" isLoading={inviteMemberMutation.isPending}>
              Send Invite
            </Button>
          </div>
        </form>
      </Modal>

      {/* Leave Group Modal */}
      <Modal
        isOpen={!!leavingGroup}
        onClose={() => setLeavingGroup(null)}
        title="Leave Group"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to leave <span className="font-semibold text-text-primary">"{leavingGroup?.name}"</span>?
          </p>
          {leavingGroup?.is_creator && (
            <div className="p-3 rounded-lg bg-primary-500/10 border border-primary-500/20 text-xs text-text-primary">
              <span className="font-bold text-primary-500">Creator Succession:</span> Since you created this group,
              creator status will automatically pass to the earliest-joined active member. If no other members remain, the group will be cleanly deleted.
            </div>
          )}

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setLeavingGroup(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={leaveGroupMutation.isPending}
              onClick={() => leavingGroup && leaveGroupMutation.mutate(leavingGroup.id.toString())}
            >
              Confirm Leave
            </Button>
          </div>
        </div>
      </Modal>

      {/* Delete Group Modal */}
      <Modal
        isOpen={!!deletingGroup}
        onClose={() => setDeletingGroup(null)}
        title="Delete Group"
      >
        <div className="space-y-4">
          <p className="text-sm text-text-secondary">
            Are you sure you want to permanently delete <span className="font-semibold text-text-primary">"{deletingGroup?.name}"</span>?
          </p>
          <p className="text-xs text-text-muted">
            All member relationships for this group will be deleted. Individual transaction histories will not be affected.
          </p>

          <div className="flex justify-end space-x-3 pt-4 border-t border-border">
            <Button variant="outline" onClick={() => setDeletingGroup(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              className="bg-accent-expense hover:bg-accent-expense/90"
              isLoading={deleteGroupMutation.isPending}
              onClick={() => deletingGroup && deleteGroupMutation.mutate(deletingGroup.id.toString())}
            >
              Delete Group
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
