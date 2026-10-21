import { createContext, useContext, useEffect, useState } from 'react';
import { api, write } from '../services/api';

const AuthContext = createContext(null);

export function AuthProvider({children}) {
  const [user,setUser]=useState(null);
  const [loading,setLoading]=useState(true);
  async function refresh() {
    try {
      const value=await api('/auth/me');
      setUser(value);
      const selected=localStorage.getItem('knowledge-workspace-id');
      if (!selected || !value.workspaces.some(w=>w.id===selected)) {
        localStorage.setItem('knowledge-workspace-id',value.workspaces[0]?.id || '');
      }
    } catch { setUser(null); }
    finally { setLoading(false); }
  }
  useEffect(()=>{
    refresh();
    const clear=()=>setUser(null);
    window.addEventListener('auth-required',clear);
    return ()=>window.removeEventListener('auth-required',clear);
  },[]);
  async function authenticate(mode,values) {
    const value=await write(`/auth/${mode}`,values);
    setUser(value);
    localStorage.setItem('knowledge-workspace-id',value.workspaces[0]?.id || '');
  }
  async function logout() {
    await write('/auth/logout',{});
    setUser(null);
  }
  const workspaceId=localStorage.getItem('knowledge-workspace-id');
  const workspace=user?.workspaces.find(w=>w.id===workspaceId) || user?.workspaces[0];
  return <AuthContext.Provider value={{user,loading,workspace,authenticate,logout,refresh}}>{children}</AuthContext.Provider>;
}

export const useAuth=()=>useContext(AuthContext);
