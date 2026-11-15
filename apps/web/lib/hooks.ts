"use client";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api } from "./api";
import type { Event, Health, Summary } from "@/types";
export const useSummary = (days = 30) =>
  useQuery({
    queryKey: ["summary", days],
    queryFn: () => api<Summary>(`/dashboard/summary?days=${days}`),
  });
export const useHealth = () =>
  useQuery({
    queryKey: ["health"],
    queryFn: () => api<Health>("/health"),
    refetchInterval: 30000,
  });
export function useEventStream() {
  const client = useQueryClient();
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    const stream = new EventSource("/api/v1/events/stream");
    let timer: ReturnType<typeof setTimeout>;
    stream.onopen = () => setConnected(true);
    stream.onmessage = () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        void client.invalidateQueries();
      }, 200);
    };
    stream.onerror = () => setConnected(false);
    return () => {
      clearTimeout(timer);
      stream.close();
    };
  }, [client]);
  return connected;
}
export const useEvents = () =>
  useQuery({
    queryKey: ["events"],
    queryFn: () => api<Event[]>("/events?limit=40"),
    refetchInterval: 10000,
  });
