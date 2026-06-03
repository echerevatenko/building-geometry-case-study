import { createContext, useContext } from "react";

// Context + hook live here (no component export) so the provider file stays
// fast-refresh friendly. useToast() returns notify(message, kind?).
export const ToastContext = createContext(() => {});

export const useToast = () => useContext(ToastContext);
