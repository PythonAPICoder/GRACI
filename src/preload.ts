import { contextBridge, ipcRenderer } from 'electron';

// Define the API interface for type safety
interface GraciAPI {
  version: () => Promise<string>;
}

// Expose only the narrow API needed for getting application version
contextBridge.exposeInMainWorld('api', {
    version: async () => {
        return await ipcRenderer.invoke('graci:get-app-version');
    },
} as GraciAPI);