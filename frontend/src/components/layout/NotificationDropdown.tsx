import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Bell, Check, ExternalLink } from 'lucide-react';
import { api } from '../../lib/api';
import { formatDateTime } from '../../lib/utils';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';

interface NotificationItem {
  id: number;
  user_id: number;
  type: string;
  payload: {
    message: string;
    [key: string]: any;
  };
  is_read: boolean;
  created_at: string;
}

interface NotificationListResponse {
  items: NotificationItem[];
  total: number;
  unread_count: number;
}

export function NotificationDropdown() {
  const [isOpen, setIsOpen] = useState(false);
  const queryClient = useQueryClient();

  // 1. Poll unread count every 30 seconds (FR-082)
  const { data: countData } = useQuery<{ unread_count: number }>({
    queryKey: ['notifications-unread-count'],
    queryFn: () => api.get('/notifications/unread-count'),
    refetchInterval: 30000,
  });

  // 2. Fetch list when dropdown is opened
  const { data: listData, isLoading } = useQuery<NotificationListResponse>({
    queryKey: ['notifications-list'],
    queryFn: () => api.get('/notifications?limit=20'),
    enabled: isOpen,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: number) => api.post(`/notifications/${id}/read`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    },
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => api.post('/notifications/read-all'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['notifications-unread-count'] });
      queryClient.invalidateQueries({ queryKey: ['notifications-list'] });
    },
  });

  const unreadCount = countData?.unread_count || 0;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="relative p-1.5 rounded-control text-text-muted hover:text-text hover:bg-surface-2 transition-colors focus:outline-none"
        title="Notifications"
      >
        <Bell className="h-4 w-4" />
        {unreadCount > 0 && (
          <span className="absolute -top-0.5 -right-0.5 flex h-4 min-w-[16px] px-1 items-center justify-center rounded-full bg-accent text-[9px] font-bold text-accent-text">
            {unreadCount > 9 ? '9+' : unreadCount}
          </span>
        )}
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-panel border border-border bg-surface shadow-xl z-50 overflow-hidden animate-in fade-in zoom-in-95 duration-100">
            <div className="flex items-center justify-between px-3.5 py-2.5 border-b border-border bg-surface-2/50">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-text">Notifications</span>
                {unreadCount > 0 && (
                  <Badge variant="warning">{unreadCount} unread</Badge>
                )}
              </div>
              {unreadCount > 0 && (
                <button
                  onClick={() => markAllReadMutation.mutate()}
                  className="text-[11px] text-accent hover:underline flex items-center gap-1"
                >
                  <Check className="h-3 w-3" /> Mark all read
                </button>
              )}
            </div>

            <div className="max-h-80 overflow-y-auto divide-y divide-border">
              {isLoading ? (
                <div className="p-4 text-center text-xs text-text-muted">Loading...</div>
              ) : listData?.items.length === 0 ? (
                <div className="p-6 text-center text-xs text-text-muted">
                  No notifications yet.
                </div>
              ) : (
                listData?.items.map((n) => (
                  <div
                    key={n.id}
                    onClick={() => {
                      if (!n.is_read) markReadMutation.mutate(n.id);
                    }}
                    className={`p-3 text-xs transition-colors cursor-pointer hover:bg-surface-2/60 ${
                      !n.is_read ? 'bg-accent/5' : ''
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <p className={`text-xs ${!n.is_read ? 'font-medium text-text' : 'text-text-muted'}`}>
                        {n.payload.message || 'New notification'}
                      </p>
                      {!n.is_read && (
                        <span className="h-1.5 w-1.5 rounded-full bg-accent flex-shrink-0 mt-1" />
                      )}
                    </div>
                    <span className="text-[10px] text-text-muted/80 mt-1 block">
                      {formatDateTime(n.created_at)}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
