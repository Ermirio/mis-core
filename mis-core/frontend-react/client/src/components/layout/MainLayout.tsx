import React from "react";
import SidebarLegacy from "./Sidebar.tsx";
import SidebarV2 from "./SidebarV2.tsx";
import "./MainLayout.css";
import { Outlet } from "react-router-dom";

/**
 * Feature flag (frontend-only) — permite alternar entre Sidebar legado e V2
 * sem deploy de backend. Valores aceitos em localStorage.sidebarVariant:
 *   "v2"     → novo (ISA-101, agrupado)
 *   "legacy" → antigo
 * Default = "v2" (novo é o padrão; time rollback-friendly).
 */
function useSidebarVariant(): "v2" | "legacy" {
  const [v] = React.useState<"v2" | "legacy">(() => {
    try {
      const stored = window.localStorage.getItem("sidebarVariant");
      return stored === "legacy" ? "legacy" : "v2";
    } catch {
      return "v2";
    }
  });
  return v;
}

const MainLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);
  const variant = useSidebarVariant();

  const SidebarComponent = variant === "v2" ? SidebarV2 : SidebarLegacy;

  // Sidebar legado usa position:fixed; precisa de classes extras para margin-left no content
  const layoutClass = [
    "main-layout",
    "bg-neutral-100 dark:bg-neutral-900",
    variant === "legacy" ? "main-layout--fixed-sidebar" : "",
    variant === "legacy" && sidebarCollapsed ? "main-layout--collapsed" : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={layoutClass}>
      <SidebarComponent
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <div className="main-content">
        <Outlet />
      </div>
    </div>
  );
};

export default MainLayout;
