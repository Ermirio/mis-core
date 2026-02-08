import React from "react";
import { Outlet } from "react-router-dom";

const AdminLayout: React.FC = () => {
    return (
        <div className="admin-layout flex flex-col h-full w-full bg-neutral-900 text-neutral-200">
            <header className="admin-header flex items-center justify-between px-6 py-4 border-b border-neutral-800 bg-neutral-950">
                <div>
                    <h1 className="text-xl font-bold text-neutral-100 tracking-tight">MIS-CORE <span className="text-emerald-500">ADMIN</span></h1>
                    <p className="text-xs text-neutral-500 uppercase tracking-widest">High Performance Configuration</p>
                </div>
                <div className="flex items-center gap-4">
                    <span className="text-xs text-neutral-600">System Mode: <span className="text-emerald-400 font-mono">ONLINE</span></span>
                </div>
            </header>

            <main className="admin-content flex-1 overflow-auto p-6">
                <Outlet />
            </main>
        </div>
    );
};

export default AdminLayout;
