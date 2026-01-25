/**
 * LawPro Fast Converter - Preload Script
 * ========================================
 * 렌더러 프로세스와 메인 프로세스 간의 안전한 통신 브릿지
 */

const { contextBridge, ipcRenderer } = require('electron');

// 앱 버전 (하드코딩)
const appVersion = '1.0.0';

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

    // Gemini 3.0 Flash 자동 교정 (변환 시 적용)
    setGeminiCorrection: (enabled) =>
        ipcRenderer.invoke('set-gemini-correction', enabled),

    getGeminiCorrection: () =>
        ipcRenderer.invoke('get-gemini-correction'),

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

    // JSON 파일 읽기/쓰기 (수정 검토용)
    readJsonFile: (filePath) =>
        ipcRenderer.invoke('read-json-file', filePath),

    writeJsonFile: (filePath, data) =>
        ipcRenderer.invoke('write-json-file', filePath, data),

    // ========================================
    // 오류 학습 시스템
    // ========================================
    // 수정 내역 수집 (로컬 저장)
    collectCorrections: (corrections) =>
        ipcRenderer.invoke('collect-corrections', corrections),

    // 학습 데이터 통계 조회
    getLearningStats: () =>
        ipcRenderer.invoke('get-learning-stats'),

    // 서버와 동기화
    syncLearningData: () =>
        ipcRenderer.invoke('sync-learning-data'),

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
    // 에디터 파일 작업
    // ========================================
    editorOpenFile: () =>
        ipcRenderer.invoke('editor-open-file'),

    editorReadFile: (filePath) =>
        ipcRenderer.invoke('editor-read-file', filePath),

    editorSaveFile: (filePath, content) =>
        ipcRenderer.invoke('editor-save-file', filePath, content),

    editorSaveAs: (content, defaultName) =>
        ipcRenderer.invoke('editor-save-as', content, defaultName),

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
    appVersion: appVersion
});
