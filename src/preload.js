/**
 * LawPro Fast Converter - Preload Script
 * ========================================
 * 렌더러 프로세스와 메인 프로세스 간의 안전한 통신 브릿지
 */

const { contextBridge, ipcRenderer } = require('electron');

// API를 window.lawpro로 노출
contextBridge.exposeInMainWorld('lawpro', {
    // ========================================
    // 문서 변환
    // ========================================
    startConversion: (folderPath, apiKey, generateClean, generateMarkdown) =>
        ipcRenderer.invoke('start-conversion', { folderPath, apiKey, generateClean, generateMarkdown }),

    stopConversion: () =>
        ipcRenderer.invoke('stop-conversion'),

    onConversionLog: (callback) => {
        const handler = (event, data) => callback(data);
        ipcRenderer.on('conversion-log', handler);
        return () => ipcRenderer.removeListener('conversion-log', handler);
    },

    // ========================================
    // Claude MCP 연결
    // ========================================
    setupClaudeMcp: () =>
        ipcRenderer.invoke('setup-claude-mcp'),

    checkClaudeStatus: () =>
        ipcRenderer.invoke('check-claude-status'),

    // ========================================
    // Gemini 설정 및 실행
    // ========================================
    saveGeminiKey: (key) =>
        ipcRenderer.invoke('save-gemini-key', key),

    getGeminiKey: () =>
        ipcRenderer.invoke('get-gemini-key'),

    setGeminiModel: (model) =>
        ipcRenderer.invoke('set-gemini-model', model),

    getGeminiModel: () =>
        ipcRenderer.invoke('get-gemini-model'),

    runGeminiReview: (folderPath) =>
        ipcRenderer.invoke('run-gemini-review', { folderPath }),

    onGeminiLog: (callback) => {
        const handler = (event, data) => callback(data);
        ipcRenderer.on('gemini-log', handler);
        return () => ipcRenderer.removeListener('gemini-log', handler);
    },

    // ========================================
    // OpenAI 설정 및 실행
    // ========================================
    saveOpenaiKey: (key) =>
        ipcRenderer.invoke('save-openai-key', key),

    getOpenaiKey: () =>
        ipcRenderer.invoke('get-openai-key'),

    setOpenaiModel: (model) =>
        ipcRenderer.invoke('set-openai-model', model),

    getOpenaiModel: () =>
        ipcRenderer.invoke('get-openai-model'),

    runOpenaiReview: (folderPath) =>
        ipcRenderer.invoke('run-openai-review', { folderPath }),

    onOpenaiLog: (callback) => {
        const handler = (event, data) => callback(data);
        ipcRenderer.on('openai-log', handler);
        return () => ipcRenderer.removeListener('openai-log', handler);
    },

    // ========================================
    // AI 선택 및 출력 옵션
    // ========================================
    setSelectedAI: (ai) =>
        ipcRenderer.invoke('set-selected-ai', ai),

    getSelectedAI: () =>
        ipcRenderer.invoke('get-selected-ai'),

    setOutputOptions: (generateClean, generateMarkdown) =>
        ipcRenderer.invoke('set-output-options', { generateClean, generateMarkdown }),

    getOutputOptions: () =>
        ipcRenderer.invoke('get-output-options'),

    // ========================================
    // Upstage 설정
    // ========================================
    saveUpstageKey: (key) =>
        ipcRenderer.invoke('save-upstage-key', key),

    getUpstageKey: () =>
        ipcRenderer.invoke('get-upstage-key'),

    // ========================================
    // 파일/폴더 작업
    // ========================================
    selectFolder: () =>
        ipcRenderer.invoke('select-folder'),

    openFolder: (path) =>
        ipcRenderer.invoke('open-folder', path),

    getLastFolder: () =>
        ipcRenderer.invoke('get-last-folder'),

    onFolderSelected: (callback) => {
        const handler = (event, path) => callback(path);
        ipcRenderer.on('folder-selected', handler);
        return () => ipcRenderer.removeListener('folder-selected', handler);
    },

    // ========================================
    // 시스템 상태
    // ========================================
    checkPython: () =>
        ipcRenderer.invoke('check-python'),

    installPackages: () =>
        ipcRenderer.invoke('install-packages'),

    onInstallLog: (callback) => {
        const handler = (event, data) => callback(data);
        ipcRenderer.on('install-log', handler);
        return () => ipcRenderer.removeListener('install-log', handler);
    },

    // ========================================
    // 설정 모달
    // ========================================
    onOpenSettings: (callback) => {
        const handler = () => callback();
        ipcRenderer.on('open-settings', handler);
        return () => ipcRenderer.removeListener('open-settings', handler);
    },

    // ========================================
    // 크레딧 관리
    // ========================================
    setUserEmail: (email) =>
        ipcRenderer.invoke('set-user-email', email),

    getUserEmail: () =>
        ipcRenderer.invoke('get-user-email'),

    getCreditBalance: () =>
        ipcRenderer.invoke('get-credit-balance'),

    getCreditPackages: () =>
        ipcRenderer.invoke('get-credit-packages'),

    addCredits: (packageId, transactionId) =>
        ipcRenderer.invoke('add-credits', packageId, transactionId),

    checkCredits: (pageCount) =>
        ipcRenderer.invoke('check-credits', pageCount),

    // ========================================
    // 시스템 정보
    // ========================================
    platform: process.platform,
    appVersion: require('../package.json').version
});
