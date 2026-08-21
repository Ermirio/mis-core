import React from "react";
import Sidebar from "./SidebarV2.tsx";
import "./MainLayout.css";
import { Outlet } from "react-router-dom";

const MainLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = React.useState(false);

  return (
    <div className="main-layout bg-neutral-100 dark:bg-neutral-900">
      <Sidebar
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
