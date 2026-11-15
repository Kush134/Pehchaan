import { create } from "zustand";
type Toast = { id: number; text: string; kind: "success" | "error" };
export const useUI = create<{
  toasts: Toast[];
  notify: (text: string, kind?: Toast["kind"]) => void;
  dismiss: (id: number) => void;
  demoScene: number;
  setDemoScene: (scene: number) => void;
}>((set) => ({
  toasts: [],
  demoScene: -1,
  setDemoScene: (demoScene) => set({ demoScene }),
  notify: (text, kind = "success") => {
    const id = Date.now();
    set((s) => ({ toasts: [...s.toasts, { id, text, kind }] }));
    setTimeout(
      () => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
      6500,
    );
  },
  dismiss: (id) =>
    set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));
