import React from "react";
import Sidebar from "./Sidebar.tsx";
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

      <div
        className="main-content"
        style={{
          marginLeft: sidebarCollapsed ? '80px' : '260px',
          transition: 'margin-left 0.3s ease',
          width: `calc(100% - ${sidebarCollapsed ? '80px' : '260px'})`
        }}
      >
        <Outlet />
      </div>
    </div>
  );
};

export default MainLayout;
