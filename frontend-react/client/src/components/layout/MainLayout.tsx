import React from "react";
import Sidebar from "./Sidebar.tsx";
import "./MainLayout.css";
import { Outlet } from "react-router-dom";

const MainLayout: React.FC = () => {
  return (
    <div className="main-layout bg-neutral-100 dark:bg-neutral-900">
      <Sidebar />

      <div className="main-content">
        <Outlet />
      </div>
    </div>
  );
};

export default MainLayout;
