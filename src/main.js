/**
 * LawPro Fast Converter - Electron Main Process
 * ================================================
 *
 * Features:
 * - Python 변환 엔진 실행 및 IPC 통신
 * - 원클릭 Claude Desktop MCP 설정
 * - Gemini API 키 관리
 * - 자동 업데이트 (선택적)
 */

const { app, BrowserWindow, ipcMain, dialog, shell, Menu } = require('electron');
const path = require('path');
const fs = require('fs');
const os = require('os');
const { spawn, execSync } = require('child_process');
const Store = require('electron-store');

// 환경변수 로드 (.env 파일)
require('dotenv').config({ path: path.join(__dirname, '..', '.env') });

// ============================================================
// 설정 저장소
// ============================================================
const store = new Store({
    name: 'lawpro-config',
    encryptionKey: 'lawpro-secure-key-2024', // 암호화 키
    defaults: {
        upstageKey: '',
        geminiKey: '',
        openaiKey: '',
        userEmail: '',
        lastFolder: '',
        claudeConnected: false,
        geminiModel: 'flash-2.0',
        openaiModel: 'gpt-4o',
        selectedAI: 'claude',  // claude, gemini, openai
        generateCleanHtml: true,
        generateMarkdown: true,
        theme: 'dark'
    }
});

// ============================================================
// 전역 변수
// ============================================================
let mainWindow = null;
let pythonProcess = null;

// 경로 설정
const isDev = !app.isPackaged;
const enginePath = isDev
    ? path.join(__dirname, '..', 'engine')
    : path.join(process.resourcesPath, 'engine');

// ============================================================
// 윈도우 생성
// ============================================================
function createWindow() {
    mainWindow = new BrowserWindow({
        width: 1200,
        height: 800,
        minWidth: 900,
        minHeight: 600,
        backgroundColor: '#1a1a2e',
        titleBarStyle: 'hiddenInset',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        },
        icon: path.join(__dirname, '..', 'resources', 'icon.png')
    });

    mainWindow.loadFile(path.join(__dirname, 'index.html'));

    // 개발 모드에서 DevTools 열기
    if (isDev) {
        mainWindow.webContents.openDevTools();
    }

    // 외부 링크 처리
    mainWindow.webContents.setWindowOpenHandler(({ url }) => {
        shell.openExternal(url);
        return { action: 'deny' };
    });

    mainWindow.on('closed', () => {
        mainWindow = null;
        if (pythonProcess) {
            pythonProcess.kill();
        }
    });
}

// ============================================================
// 앱 메뉴
// ============================================================
function createMenu() {
    const template = [
        {
            label: 'LawPro',
            submenu: [
                { label: '정보', role: 'about' },
                { type: 'separator' },
                { label: '환경설정', accelerator: 'CmdOrCtrl+,', click: () => mainWindow?.webContents.send('open-settings') },
                { type: 'separator' },
                { label: '종료', role: 'quit' }
            ]
        },
        {
            label: '파일',
            submenu: [
                {
                    label: '폴더 열기',
                    accelerator: 'CmdOrCtrl+O',
                    click: async () => {
                        const result = await dialog.showOpenDialog(mainWindow, {
                            properties: ['openDirectory']
                        });
                        if (!result.canceled && result.filePaths[0]) {
                            mainWindow?.webContents.send('folder-selected', result.filePaths[0]);
                        }
                    }
                },
                { type: 'separator' },
                {
                    label: '출력 폴더 열기',
                    click: () => {
                        const lastFolder = store.get('lastFolder');
                        if (lastFolder) {
                            shell.openPath(path.join(lastFolder, 'Converted_HTML'));
                        }
                    }
                }
            ]
        },
        {
            label: '도움말',
            submenu: [
                {
                    label: 'GitHub',
                    click: () => shell.openExternal('https://github.com/lawpro/fast-converter')
                },
                {
                    label: 'Upstage API 문서',
                    click: () => shell.openExternal('https://developers.upstage.ai/')
                }
            ]
        }
    ];

    const menu = Menu.buildFromTemplate(template);
    Menu.setApplicationMenu(menu);
}

// ============================================================
// Python 실행 유틸리티
// ============================================================
function getPythonCommand() {
    // 시스템에 설치된 Python 찾기
    const commands = ['python3', 'python', 'py'];

    for (const cmd of commands) {
        try {
            const result = execSync(`${cmd} --version`, { encoding: 'utf-8', stdio: 'pipe' });
            if (result.includes('Python 3')) {
                return cmd;
            }
        } catch (e) {
            continue;
        }
    }

    return null;
}

// ============================================================
// IPC 핸들러: 문서 변환
// ============================================================
ipcMain.handle('start-conversion', async (event, { folderPath, apiKey, generateClean, generateMarkdown }) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();

        if (!pythonCmd) {
            reject(new Error('Python 3이 설치되어 있지 않습니다.'));
            return;
        }

        const scriptPath = path.join(enginePath, 'main.py');

        if (!fs.existsSync(scriptPath)) {
            reject(new Error(`엔진 스크립트를 찾을 수 없습니다: ${scriptPath}`));
            return;
        }

        // 마지막 폴더 저장
        store.set('lastFolder', folderPath);

        // 출력 옵션 (기본값 사용)
        const cleanOpt = generateClean !== undefined ? generateClean : store.get('generateCleanHtml', true);
        const mdOpt = generateMarkdown !== undefined ? generateMarkdown : store.get('generateMarkdown', true);

        // Python 프로세스 시작 (추가 인자 포함)
        const args = [
            scriptPath,
            folderPath,
            apiKey || '',
            cleanOpt ? 'true' : 'false',
            mdOpt ? 'true' : 'false'
        ];

        pythonProcess = spawn(pythonCmd, args, {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        pythonProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                try {
                    const json = JSON.parse(line);
                    mainWindow?.webContents.send('conversion-log', json);
                } catch (e) {
                    // JSON이 아닌 출력은 로그로 처리
                    mainWindow?.webContents.send('conversion-log', {
                        type: 'log',
                        msg: line
                    });
                }
            }
        });

        pythonProcess.stderr.on('data', (data) => {
            mainWindow?.webContents.send('conversion-log', {
                type: 'error',
                msg: data.toString()
            });
        });

        pythonProcess.on('close', (code) => {
            pythonProcess = null;
            resolve({ success: code === 0, code });
        });

        pythonProcess.on('error', (err) => {
            pythonProcess = null;
            reject(err);
        });
    });
});

// 변환 중단
ipcMain.handle('stop-conversion', async () => {
    if (pythonProcess) {
        pythonProcess.kill();
        pythonProcess = null;
        return { success: true };
    }
    return { success: false, msg: '실행 중인 작업이 없습니다' };
});

// ============================================================
// IPC 핸들러: Claude Desktop MCP 설정 (원클릭)
// ============================================================
ipcMain.handle('setup-claude-mcp', async () => {
    try {
        const platform = os.platform();
        let configPath = '';

        // OS별 Claude Desktop 설정 파일 경로
        if (platform === 'win32') {
            configPath = path.join(process.env.APPDATA, 'Claude', 'claude_desktop_config.json');
        } else if (platform === 'darwin') {
            configPath = path.join(os.homedir(), 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
        } else if (platform === 'linux') {
            configPath = path.join(os.homedir(), '.config', 'claude', 'claude_desktop_config.json');
        } else {
            throw new Error(`지원하지 않는 OS: ${platform}`);
        }

        // MCP 서버 스크립트 경로
        const mcpScript = path.join(enginePath, 'mcp_server.py');

        if (!fs.existsSync(mcpScript)) {
            throw new Error('MCP 서버 스크립트를 찾을 수 없습니다');
        }

        // Python 명령어 확인
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            throw new Error('Python 3이 설치되어 있지 않습니다');
        }

        // 기존 설정 읽기 또는 새로 생성
        let config = {};
        const configDir = path.dirname(configPath);

        if (fs.existsSync(configPath)) {
            try {
                const content = fs.readFileSync(configPath, 'utf-8');
                config = JSON.parse(content);
            } catch (e) {
                // 파싱 실패시 백업 후 새로 생성
                const backupPath = configPath + '.backup.' + Date.now();
                fs.copyFileSync(configPath, backupPath);
                config = {};
            }
        } else {
            // 디렉토리가 없으면 생성
            fs.mkdirSync(configDir, { recursive: true });
        }

        // mcpServers 설정 추가/업데이트
        if (!config.mcpServers) {
            config.mcpServers = {};
        }

        // LawPro MCP 서버 설정
        config.mcpServers['lawpro-converter'] = {
            command: pythonCmd,
            args: [mcpScript],
            env: {
                LAWPRO_OUTPUT_DIR: path.join(os.homedir(), 'Documents', 'LawPro_Output')
            }
        };

        // 설정 파일 저장
        fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');

        // 상태 저장
        store.set('claudeConnected', true);

        return {
            success: true,
            configPath,
            message: 'Claude Desktop MCP 설정이 완료되었습니다. Claude Desktop을 재시작해주세요.'
        };

    } catch (error) {
        return {
            success: false,
            error: error.message
        };
    }
});

// Claude 연결 상태 확인
ipcMain.handle('check-claude-status', async () => {
    const platform = os.platform();
    let configPath = '';

    if (platform === 'win32') {
        configPath = path.join(process.env.APPDATA, 'Claude', 'claude_desktop_config.json');
    } else if (platform === 'darwin') {
        configPath = path.join(os.homedir(), 'Library', 'Application Support', 'Claude', 'claude_desktop_config.json');
    } else {
        configPath = path.join(os.homedir(), '.config', 'claude', 'claude_desktop_config.json');
    }

    try {
        if (fs.existsSync(configPath)) {
            const content = fs.readFileSync(configPath, 'utf-8');
            const config = JSON.parse(content);

            const isConnected = config.mcpServers && config.mcpServers['lawpro-converter'];
            return {
                connected: isConnected,
                configPath
            };
        }
    } catch (e) {
        // 무시
    }

    return { connected: false };
});

// ============================================================
// IPC 핸들러: Gemini 설정
// ============================================================
ipcMain.handle('save-gemini-key', async (event, key) => {
    store.set('geminiKey', key);
    return { success: true };
});

ipcMain.handle('get-gemini-key', async () => {
    return store.get('geminiKey', '');
});

ipcMain.handle('set-gemini-model', async (event, model) => {
    store.set('geminiModel', model);
    return { success: true };
});

ipcMain.handle('get-gemini-model', async () => {
    return store.get('geminiModel', 'flash-2.0');
});

// Gemini 검수 실행
ipcMain.handle('run-gemini-review', async (event, { folderPath }) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();

        if (!pythonCmd) {
            reject(new Error('Python 3이 설치되어 있지 않습니다.'));
            return;
        }

        const apiKey = store.get('geminiKey');
        if (!apiKey) {
            reject(new Error('Gemini API 키가 설정되지 않았습니다.'));
            return;
        }

        const model = store.get('geminiModel', 'flash-2.0');
        const scriptPath = path.join(enginePath, 'gemini_agent.py');

        const geminiProcess = spawn(pythonCmd, [scriptPath, folderPath, apiKey, model], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        geminiProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                try {
                    const json = JSON.parse(line);
                    mainWindow?.webContents.send('gemini-log', json);
                } catch (e) {
                    mainWindow?.webContents.send('gemini-log', { type: 'log', msg: line });
                }
            }
        });

        geminiProcess.stderr.on('data', (data) => {
            mainWindow?.webContents.send('gemini-log', { type: 'error', msg: data.toString() });
        });

        geminiProcess.on('close', (code) => {
            resolve({ success: code === 0, code });
        });

        geminiProcess.on('error', (err) => {
            reject(err);
        });
    });
});

// ============================================================
// IPC 핸들러: OpenAI 설정
// ============================================================
ipcMain.handle('save-openai-key', async (event, key) => {
    store.set('openaiKey', key);
    return { success: true };
});

ipcMain.handle('get-openai-key', async () => {
    return store.get('openaiKey', '');
});

ipcMain.handle('set-openai-model', async (event, model) => {
    store.set('openaiModel', model);
    return { success: true };
});

ipcMain.handle('get-openai-model', async () => {
    return store.get('openaiModel', 'gpt-4o');
});

// OpenAI 검수 실행
ipcMain.handle('run-openai-review', async (event, { folderPath }) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();

        if (!pythonCmd) {
            reject(new Error('Python 3이 설치되어 있지 않습니다.'));
            return;
        }

        const apiKey = store.get('openaiKey');
        if (!apiKey) {
            reject(new Error('OpenAI API 키가 설정되지 않았습니다.'));
            return;
        }

        const model = store.get('openaiModel', 'gpt-4o');
        const scriptPath = path.join(enginePath, 'openai_agent.py');

        const openaiProcess = spawn(pythonCmd, [scriptPath, folderPath, apiKey, model], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        openaiProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n').filter(Boolean);
            for (const line of lines) {
                try {
                    const json = JSON.parse(line);
                    mainWindow?.webContents.send('openai-log', json);
                } catch (e) {
                    mainWindow?.webContents.send('openai-log', { type: 'log', msg: line });
                }
            }
        });

        openaiProcess.stderr.on('data', (data) => {
            mainWindow?.webContents.send('openai-log', { type: 'error', msg: data.toString() });
        });

        openaiProcess.on('close', (code) => {
            resolve({ success: code === 0, code });
        });

        openaiProcess.on('error', (err) => {
            reject(err);
        });
    });
});

// ============================================================
// IPC 핸들러: AI 선택 및 출력 옵션
// ============================================================
ipcMain.handle('set-selected-ai', async (event, ai) => {
    store.set('selectedAI', ai);
    return { success: true };
});

ipcMain.handle('get-selected-ai', async () => {
    return store.get('selectedAI', 'claude');
});

ipcMain.handle('set-output-options', async (event, { generateClean, generateMarkdown }) => {
    store.set('generateCleanHtml', generateClean);
    store.set('generateMarkdown', generateMarkdown);
    return { success: true };
});

ipcMain.handle('get-output-options', async () => {
    return {
        generateCleanHtml: store.get('generateCleanHtml', true),
        generateMarkdown: store.get('generateMarkdown', true)
    };
});

// ============================================================
// IPC 핸들러: Upstage API 키 (관리자 전용 - 환경변수 우선)
// ============================================================
ipcMain.handle('save-upstage-key', async (event, key) => {
    // 환경변수가 설정되어 있으면 저장 불가
    if (process.env.UPSTAGE_API_KEY) {
        return { success: false, error: 'Environment variable is set' };
    }
    store.set('upstageKey', key);
    return { success: true };
});

ipcMain.handle('get-upstage-key', async () => {
    // 환경변수 우선, 없으면 저장된 값 사용
    return process.env.UPSTAGE_API_KEY || store.get('upstageKey', '');
});

// ============================================================
// IPC 핸들러: 유틸리티
// ============================================================
// 폴더 선택 다이얼로그
ipcMain.handle('select-folder', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
        title: '변환할 문서가 있는 폴더를 선택하세요'
    });

    if (result.canceled) {
        return { canceled: true };
    }

    const folderPath = result.filePaths[0];
    store.set('lastFolder', folderPath);

    return {
        canceled: false,
        path: folderPath
    };
});

// 폴더 열기
ipcMain.handle('open-folder', async (event, folderPath) => {
    if (folderPath && fs.existsSync(folderPath)) {
        shell.openPath(folderPath);
        return { success: true };
    }
    return { success: false, error: '폴더가 존재하지 않습니다' };
});

// 마지막 폴더 가져오기
ipcMain.handle('get-last-folder', async () => {
    return store.get('lastFolder', '');
});

// JSON 파일 읽기 (수정 검토용)
ipcMain.handle('read-json-file', async (event, filePath) => {
    try {
        if (!fs.existsSync(filePath)) {
            return null;
        }
        const content = fs.readFileSync(filePath, 'utf-8');
        return JSON.parse(content);
    } catch (err) {
        console.error('JSON 읽기 실패:', err);
        return null;
    }
});

// JSON 파일 쓰기 (수정 검토용)
ipcMain.handle('write-json-file', async (event, filePath, data) => {
    try {
        const dir = path.dirname(filePath);
        if (!fs.existsSync(dir)) {
            fs.mkdirSync(dir, { recursive: true });
        }
        fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
        return { success: true };
    } catch (err) {
        throw new Error(`JSON 저장 실패: ${err.message}`);
    }
});

// ============================================================
// IPC 핸들러: 오류 학습 시스템
// ============================================================
// 수정 내역 수집
ipcMain.handle('collect-corrections', async (event, corrections) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ success: false, error: 'Python not found' });
            return;
        }

        const scriptPath = path.join(enginePath, 'error_learning.py');

        // 각 수정 내역을 Python 스크립트로 전달
        const collectProcess = spawn(pythonCmd, [
            scriptPath,
            'collect-batch'
        ], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        // stdin으로 데이터 전달
        collectProcess.stdin.write(JSON.stringify(corrections));
        collectProcess.stdin.end();

        let output = '';
        collectProcess.stdout.on('data', (data) => { output += data.toString(); });
        collectProcess.stderr.on('data', (data) => { console.error('collect error:', data.toString()); });

        collectProcess.on('close', (code) => {
            resolve({ success: code === 0, count: corrections.length });
        });
    });
});

// 학습 데이터 통계 조회
ipcMain.handle('get-learning-stats', async () => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ total: 0, by_source: {} });
            return;
        }

        const scriptPath = path.join(enginePath, 'error_learning.py');
        const statsProcess = spawn(pythonCmd, [scriptPath, 'stats'], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        statsProcess.stdout.on('data', (data) => { output += data.toString(); });

        statsProcess.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                resolve(result.data || { total: 0 });
            } catch (e) {
                resolve({ total: 0, by_source: {} });
            }
        });
    });
});

// 서버와 동기화
ipcMain.handle('sync-learning-data', async () => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ success: false, error: 'Python not found' });
            return;
        }

        const scriptPath = path.join(enginePath, 'error_learning.py');

        // 먼저 서버로 업로드
        const syncProcess = spawn(pythonCmd, [scriptPath, 'sync'], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        syncProcess.stdout.on('data', (data) => { output += data.toString(); });

        syncProcess.on('close', (code) => {
            // 그 다음 서버에서 다운로드
            const fetchProcess = spawn(pythonCmd, [scriptPath, 'fetch'], {
                cwd: enginePath,
                env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
            });

            let fetchOutput = '';
            fetchProcess.stdout.on('data', (data) => { fetchOutput += data.toString(); });

            fetchProcess.on('close', (fetchCode) => {
                resolve({
                    success: true,
                    sync_result: output,
                    fetch_result: fetchOutput
                });
            });
        });
    });
});

// Python 상태 확인
ipcMain.handle('check-python', async () => {
    const pythonCmd = getPythonCommand();

    if (!pythonCmd) {
        return {
            installed: false,
            error: 'Python 3을 찾을 수 없습니다'
        };
    }

    try {
        const version = execSync(`${pythonCmd} --version`, { encoding: 'utf-8' });

        // 필수 패키지 확인
        const packages = ['pandas', 'pdfplumber', 'requests'];
        const missing = [];

        for (const pkg of packages) {
            try {
                execSync(`${pythonCmd} -c "import ${pkg}"`, { stdio: 'pipe' });
            } catch (e) {
                missing.push(pkg);
            }
        }

        return {
            installed: true,
            version: version.trim(),
            command: pythonCmd,
            missingPackages: missing
        };

    } catch (e) {
        return {
            installed: false,
            error: e.message
        };
    }
});

// 패키지 설치
ipcMain.handle('install-packages', async () => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        const requirementsPath = path.join(enginePath, 'requirements.txt');

        const installProcess = spawn(pythonCmd, ['-m', 'pip', 'install', '-r', requirementsPath], {
            cwd: enginePath
        });

        let output = '';

        installProcess.stdout.on('data', (data) => {
            output += data.toString();
            mainWindow?.webContents.send('install-log', data.toString());
        });

        installProcess.stderr.on('data', (data) => {
            output += data.toString();
            mainWindow?.webContents.send('install-log', data.toString());
        });

        installProcess.on('close', (code) => {
            resolve({ success: code === 0, output });
        });

        installProcess.on('error', (err) => {
            reject(err);
        });
    });
});

// ============================================================
// IPC 핸들러: 에디터 파일 작업
// ============================================================
ipcMain.handle('editor-open-file', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: [
            { name: 'Web Documents', extensions: ['html', 'htm', 'md', 'markdown'] },
            { name: 'HTML Files', extensions: ['html', 'htm'] },
            { name: 'Markdown Files', extensions: ['md', 'markdown'] },
            { name: 'All Files', extensions: ['*'] }
        ]
    });

    if (result.canceled || result.filePaths.length === 0) {
        return null;
    }

    const filePath = result.filePaths[0];
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const ext = path.extname(filePath).toLowerCase();
        return {
            path: filePath,
            name: path.basename(filePath),
            content: content,
            type: ['.md', '.markdown'].includes(ext) ? 'markdown' : 'html'
        };
    } catch (err) {
        throw new Error(`파일 읽기 실패: ${err.message}`);
    }
});

ipcMain.handle('editor-read-file', async (event, filePath) => {
    try {
        const content = fs.readFileSync(filePath, 'utf-8');
        const ext = path.extname(filePath).toLowerCase();
        return {
            path: filePath,
            name: path.basename(filePath),
            content: content,
            type: ['.md', '.markdown'].includes(ext) ? 'markdown' : 'html'
        };
    } catch (err) {
        throw new Error(`파일 읽기 실패: ${err.message}`);
    }
});

ipcMain.handle('editor-save-file', async (event, filePath, content) => {
    try {
        fs.writeFileSync(filePath, content, 'utf-8');
        return { success: true, path: filePath };
    } catch (err) {
        throw new Error(`파일 저장 실패: ${err.message}`);
    }
});

ipcMain.handle('editor-save-as', async (event, content, defaultName) => {
    const ext = defaultName.endsWith('.md') ? 'md' : 'html';
    const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath: defaultName,
        filters: ext === 'md'
            ? [{ name: 'Markdown Files', extensions: ['md'] }]
            : [{ name: 'HTML Files', extensions: ['html', 'htm'] }]
    });

    if (result.canceled) {
        return null;
    }

    try {
        fs.writeFileSync(result.filePath, content, 'utf-8');
        return { success: true, path: result.filePath, name: path.basename(result.filePath) };
    } catch (err) {
        throw new Error(`파일 저장 실패: ${err.message}`);
    }
});

// ============================================================
// IPC 핸들러: 크레딧 관리
// ============================================================
ipcMain.handle('set-user-email', async (event, email) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            reject(new Error('Python 3이 설치되어 있지 않습니다.'));
            return;
        }

        const scriptPath = path.join(enginePath, 'credit_manager.py');
        const process = spawn(pythonCmd, [scriptPath, 'set-email', email], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        process.stdout.on('data', (data) => { output += data.toString(); });
        process.stderr.on('data', (data) => { output += data.toString(); });

        process.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                store.set('userEmail', email);
                resolve(result);
            } catch (e) {
                resolve({ success: false, error: output });
            }
        });
    });
});

ipcMain.handle('get-user-email', async () => {
    return store.get('userEmail', '');
});

ipcMain.handle('get-credit-balance', async () => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ credits: 0, is_admin: false, error: 'Python not found' });
            return;
        }

        const scriptPath = path.join(enginePath, 'credit_manager.py');
        const creditProcess = spawn(pythonCmd, [scriptPath, 'balance'], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        creditProcess.stdout.on('data', (data) => { output += data.toString(); });

        creditProcess.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                resolve(result);
            } catch (e) {
                resolve({ credits: 0, is_admin: false });
            }
        });
    });
});

ipcMain.handle('get-credit-packages', async () => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ packages: [] });
            return;
        }

        const scriptPath = path.join(enginePath, 'credit_manager.py');
        const creditProcess = spawn(pythonCmd, [scriptPath, 'packages'], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        creditProcess.stdout.on('data', (data) => { output += data.toString(); });

        creditProcess.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                resolve(result);
            } catch (e) {
                resolve({ packages: [] });
            }
        });
    });
});

ipcMain.handle('add-credits', async (event, packageId, transactionId) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            reject(new Error('Python 3이 설치되어 있지 않습니다.'));
            return;
        }

        const scriptPath = path.join(enginePath, 'credit_manager.py');
        const creditProcess = spawn(pythonCmd, [scriptPath, 'add', packageId], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        creditProcess.stdout.on('data', (data) => { output += data.toString(); });

        creditProcess.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                resolve(result);
            } catch (e) {
                resolve({ success: false, error: output });
            }
        });
    });
});

ipcMain.handle('check-credits', async (event, pageCount) => {
    return new Promise((resolve, reject) => {
        const pythonCmd = getPythonCommand();
        if (!pythonCmd) {
            resolve({ has_credits: false, message: 'Python not found' });
            return;
        }

        const scriptPath = path.join(enginePath, 'credit_manager.py');
        const creditProcess = spawn(pythonCmd, [scriptPath, 'check', String(pageCount)], {
            cwd: enginePath,
            env: { ...process.env, PYTHONIOENCODING: 'utf-8' }
        });

        let output = '';
        creditProcess.stdout.on('data', (data) => { output += data.toString(); });

        creditProcess.on('close', (code) => {
            try {
                const result = JSON.parse(output);
                resolve(result);
            } catch (e) {
                resolve({ has_credits: false });
            }
        });
    });
});

// ============================================================
// 앱 이벤트
// ============================================================
app.whenReady().then(() => {
    createWindow();
    createMenu();

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

app.on('before-quit', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
});

// 두 번째 인스턴스 방지
const gotTheLock = app.requestSingleInstanceLock();
if (!gotTheLock) {
    app.quit();
} else {
    app.on('second-instance', () => {
        if (mainWindow) {
            if (mainWindow.isMinimized()) mainWindow.restore();
            mainWindow.focus();
        }
    });
}
