/**
 * LawPro Fast Converter - Renderer Script
 * =========================================
 * UI 로직 및 이벤트 처리
 */

// ============================================================
// 상태
// ============================================================
const state = {
    selectedFolder: null,
    isConverting: false,
    totalFiles: 0,
    processedFiles: 0,
    successCount: 0,
    failCount: 0,
    outputFolder: null
};

// 에디터 상태
const editorState = {
    currentFile: null,      // 현재 열린 파일 경로
    currentType: 'html',    // html 또는 markdown
    isModified: false,      // 수정 여부
    viewMode: 'visual',     // visual 또는 code
    selectedCell: null      // 현재 선택된 표 셀
};

// ============================================================
// DOM 요소
// ============================================================
const elements = {
    // 네비게이션
    navConvert: document.getElementById('navConvert'),
    navReview: document.getElementById('navReview'),
    navEditor: document.getElementById('navEditor'),
    navSettings: document.getElementById('navSettings'),

    // 페이지
    pageConvert: document.getElementById('pageConvert'),
    pageReview: document.getElementById('pageReview'),
    pageEditor: document.getElementById('pageEditor'),
    pageSettings: document.getElementById('pageSettings'),

    // 변환 페이지
    dropZone: document.getElementById('dropZone'),
    dropText: document.getElementById('dropText'),
    selectedFolder: document.getElementById('selectedFolder'),
    upstageKeyInput: document.getElementById('upstageKeyInput'),
    saveUpstageKey: document.getElementById('saveUpstageKey'),
    startConvert: document.getElementById('startConvert'),
    stopConvert: document.getElementById('stopConvert'),
    progressSection: document.getElementById('progressSection'),
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    logArea: document.getElementById('logArea'),
    clearLog: document.getElementById('clearLog'),
    resultSummary: document.getElementById('resultSummary'),
    resultSuccess: document.getElementById('resultSuccess'),
    resultFail: document.getElementById('resultFail'),
    resultTime: document.getElementById('resultTime'),
    openOutputFolder: document.getElementById('openOutputFolder'),

    // 출력 옵션
    chkCleanHtml: document.getElementById('chkCleanHtml'),
    chkMarkdown: document.getElementById('chkMarkdown'),

    // AI 검수 페이지
    connectClaude: document.getElementById('connectClaude'),
    claudeConnectionBadge: document.getElementById('claudeConnectionBadge'),
    claudeMessage: document.getElementById('claudeMessage'),
    geminiKeyInput: document.getElementById('geminiKeyInput'),
    geminiModelSelect: document.getElementById('geminiModelSelect'),
    saveGeminiKey: document.getElementById('saveGeminiKey'),
    geminiConnectionBadge: document.getElementById('geminiConnectionBadge'),
    openaiKeyInput: document.getElementById('openaiKeyInput'),
    openaiModelSelect: document.getElementById('openaiModelSelect'),
    saveOpenaiKey: document.getElementById('saveOpenaiKey'),
    openaiConnectionBadge: document.getElementById('openaiConnectionBadge'),
    reviewFolderPath: document.getElementById('reviewFolderPath'),
    selectReviewFolder: document.getElementById('selectReviewFolder'),
    startReview: document.getElementById('startReview'),
    reviewAISelect: document.getElementById('reviewAISelect'),
    reviewLogArea: document.getElementById('reviewLogArea'),

    // 설정 페이지
    pythonInfo: document.getElementById('pythonInfo'),
    installDeps: document.getElementById('installDeps'),
    installOutput: document.getElementById('installOutput'),
    settingsUpstageKey: document.getElementById('settingsUpstageKey'),
    settingsSaveUpstage: document.getElementById('settingsSaveUpstage'),
    settingsGeminiKey: document.getElementById('settingsGeminiKey'),
    settingsSaveGemini: document.getElementById('settingsSaveGemini'),
    settingsConnectClaude: document.getElementById('settingsConnectClaude'),
    settingsClaudeStatus: document.getElementById('settingsClaudeStatus'),

    // 상태 표시
    pythonStatus: document.getElementById('pythonStatus'),
    claudeStatus: document.getElementById('claudeStatus'),
    appVersion: document.getElementById('appVersion'),

    // 크레딧 관련
    creditBalance: document.getElementById('creditBalance'),
    creditAdminBadge: document.getElementById('creditAdminBadge'),
    buyCreditsBtn: document.getElementById('buyCreditsBtn'),
    creditModal: document.getElementById('creditModal'),
    closeCreditModal: document.getElementById('closeCreditModal'),
    userEmailInput: document.getElementById('userEmailInput'),
    saveUserEmail: document.getElementById('saveUserEmail'),
    modalCreditBalance: document.getElementById('modalCreditBalance'),

    // 에디터 관련
    editorOpenFile: document.getElementById('editorOpenFile'),
    editorSaveFile: document.getElementById('editorSaveFile'),
    editorFileName: document.getElementById('editorFileName'),
    tabHtml: document.getElementById('tabHtml'),
    tabMarkdown: document.getElementById('tabMarkdown'),
    htmlEditorPanel: document.getElementById('htmlEditorPanel'),
    markdownEditorPanel: document.getElementById('markdownEditorPanel'),
    htmlCodeEditor: document.getElementById('htmlCodeEditor'),
    htmlPreview: document.getElementById('htmlPreview'),
    htmlRefresh: document.getElementById('htmlRefresh'),
    mdCodeEditor: document.getElementById('mdCodeEditor'),
    mdPreview: document.getElementById('mdPreview'),

    // WYSIWYG 에디터 요소
    visualEditor: document.getElementById('visualEditor'),
    visualEditorWrapper: document.getElementById('visualEditorWrapper'),
    codeEditorWrapper: document.getElementById('codeEditorWrapper'),
    btnVisualView: document.getElementById('btnVisualView'),
    btnCodeView: document.getElementById('btnCodeView'),
    fontSizeSelect: document.getElementById('fontSizeSelect'),
    btnBold: document.getElementById('btnBold'),
    btnItalic: document.getElementById('btnItalic'),
    btnUnderline: document.getElementById('btnUnderline'),
    btnAlignLeft: document.getElementById('btnAlignLeft'),
    btnAlignCenter: document.getElementById('btnAlignCenter'),
    btnAlignRight: document.getElementById('btnAlignRight'),
    btnAddRowAbove: document.getElementById('btnAddRowAbove'),
    btnAddRowBelow: document.getElementById('btnAddRowBelow'),
    btnAddColLeft: document.getElementById('btnAddColLeft'),
    btnAddColRight: document.getElementById('btnAddColRight'),
    btnDeleteRow: document.getElementById('btnDeleteRow'),
    btnDeleteCol: document.getElementById('btnDeleteCol'),
    btnMergeCells: document.getElementById('btnMergeCells'),
    btnSplitCell: document.getElementById('btnSplitCell'),
    btnBorderTop: document.getElementById('btnBorderTop'),
    btnBorderBottom: document.getElementById('btnBorderBottom'),
    btnBorderLeft: document.getElementById('btnBorderLeft'),
    btnBorderRight: document.getElementById('btnBorderRight'),
    btnBorderAll: document.getElementById('btnBorderAll'),
    btnBorderNone: document.getElementById('btnBorderNone')
};

// ============================================================
// 초기화
// ============================================================
async function init() {
    // 버전 표시
    elements.appVersion.textContent = `v${window.lawpro.appVersion}`;

    // 저장된 설정 로드
    await loadSavedSettings();

    // Python 상태 확인
    await checkPythonStatus();

    // Claude 연결 상태 확인
    await checkClaudeStatus();

    // 크레딧 잔액 로드
    await loadCreditBalance();

    // 이벤트 리스너 등록
    setupEventListeners();

    // IPC 리스너 등록
    setupIPCListeners();
}

async function loadSavedSettings() {
    // Upstage 키
    const upstageKey = await window.lawpro.getUpstageKey();
    if (upstageKey) {
        elements.upstageKeyInput.value = upstageKey;
        if (elements.settingsUpstageKey) elements.settingsUpstageKey.value = upstageKey;
    }

    // Gemini 키
    const geminiKey = await window.lawpro.getGeminiKey();
    if (geminiKey) {
        elements.geminiKeyInput.value = geminiKey;
        if (elements.settingsGeminiKey) elements.settingsGeminiKey.value = geminiKey;
        elements.geminiConnectionBadge.textContent = '설정됨';
        elements.geminiConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
    }

    // Gemini 모델
    const geminiModel = await window.lawpro.getGeminiModel();
    elements.geminiModelSelect.value = geminiModel;

    // OpenAI 키
    const openaiKey = await window.lawpro.getOpenaiKey();
    if (openaiKey) {
        elements.openaiKeyInput.value = openaiKey;
        elements.openaiConnectionBadge.textContent = '설정됨';
        elements.openaiConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
    }

    // OpenAI 모델
    const openaiModel = await window.lawpro.getOpenaiModel();
    elements.openaiModelSelect.value = openaiModel;

    // 출력 옵션
    const outputOptions = await window.lawpro.getOutputOptions();
    elements.chkCleanHtml.checked = outputOptions.generateCleanHtml;
    elements.chkMarkdown.checked = outputOptions.generateMarkdown;

    // 마지막 폴더
    const lastFolder = await window.lawpro.getLastFolder();
    if (lastFolder) {
        elements.reviewFolderPath.value = lastFolder;
        elements.startReview.disabled = false;
    }
}

async function checkPythonStatus() {
    const result = await window.lawpro.checkPython();

    if (result.installed) {
        elements.pythonStatus.textContent = '정상';
        elements.pythonStatus.className = 'text-green-400';

        let html = `<p><span class="text-gray-400">버전:</span> <span class="text-green-400">${result.version}</span></p>`;
        html += `<p><span class="text-gray-400">명령어:</span> <span class="text-gray-300">${result.command}</span></p>`;

        if (result.missingPackages && result.missingPackages.length > 0) {
            html += `<p class="text-yellow-400 mt-2">누락된 패키지: ${result.missingPackages.join(', ')}</p>`;
            elements.installDeps.classList.remove('hidden');
        }

        elements.pythonInfo.innerHTML = html;
    } else {
        elements.pythonStatus.textContent = '미설치';
        elements.pythonStatus.className = 'text-red-400';
        elements.pythonInfo.innerHTML = `<p class="text-red-400">${result.error}</p>`;
        elements.startConvert.disabled = true;
    }
}

async function checkClaudeStatus() {
    const result = await window.lawpro.checkClaudeStatus();

    if (result.connected) {
        elements.claudeStatus.textContent = '연결됨';
        elements.claudeStatus.className = 'text-green-400';
        elements.claudeConnectionBadge.textContent = '연결됨';
        elements.claudeConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
        elements.connectClaude.textContent = '재설정';
    }
}

// ============================================================
// 이벤트 리스너
// ============================================================
function setupEventListeners() {
    // 네비게이션
    elements.navConvert.addEventListener('click', () => showPage('convert'));
    elements.navReview.addEventListener('click', () => showPage('review'));
    elements.navEditor.addEventListener('click', () => showPage('editor'));
    elements.navSettings.addEventListener('click', () => showPage('settings'));

    // 드롭존
    setupDropZone();

    // 변환 버튼
    elements.startConvert.addEventListener('click', startConversion);
    elements.stopConvert.addEventListener('click', stopConversion);

    // 출력 옵션 저장
    elements.chkCleanHtml.addEventListener('change', saveOutputOptions);
    elements.chkMarkdown.addEventListener('change', saveOutputOptions);

    // API 키 저장
    elements.saveUpstageKey.addEventListener('click', saveUpstageKey);
    if (elements.settingsSaveUpstage) {
        elements.settingsSaveUpstage.addEventListener('click', saveUpstageKeyFromSettings);
    }
    elements.saveGeminiKey.addEventListener('click', saveGeminiKey);
    if (elements.settingsSaveGemini) {
        elements.settingsSaveGemini.addEventListener('click', saveGeminiKeyFromSettings);
    }
    elements.saveOpenaiKey.addEventListener('click', saveOpenaiKey);

    // Claude 연결
    elements.connectClaude.addEventListener('click', connectClaude);
    if (elements.settingsConnectClaude) {
        elements.settingsConnectClaude.addEventListener('click', connectClaude);
    }

    // 모델 변경
    elements.geminiModelSelect.addEventListener('change', async () => {
        await window.lawpro.setGeminiModel(elements.geminiModelSelect.value);
    });
    elements.openaiModelSelect.addEventListener('change', async () => {
        await window.lawpro.setOpenaiModel(elements.openaiModelSelect.value);
    });

    // 검수 폴더 선택
    elements.selectReviewFolder.addEventListener('click', selectReviewFolder);
    elements.startReview.addEventListener('click', startReview);

    // 로그 지우기
    elements.clearLog.addEventListener('click', () => {
        elements.logArea.innerHTML = '<p class="text-gray-500">대기 중...</p>';
    });

    // 출력 폴더 열기
    elements.openOutputFolder.addEventListener('click', openOutputFolder);

    // 패키지 설치
    elements.installDeps.addEventListener('click', installPackages);
}

function setupDropZone() {
    const dropZone = elements.dropZone;

    // 클릭으로 폴더 선택
    dropZone.addEventListener('click', async () => {
        const result = await window.lawpro.selectFolder();
        if (!result.canceled) {
            setSelectedFolder(result.path);
        }
    });

    // 드래그 앤 드롭
    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            const path = files[0].path;
            setSelectedFolder(path);
        }
    });
}

function setupIPCListeners() {
    // 변환 로그
    window.lawpro.onConversionLog((data) => {
        handleConversionLog(data);
    });

    // Gemini 로그
    window.lawpro.onGeminiLog((data) => {
        handleReviewLog(data);
    });

    // OpenAI 로그
    window.lawpro.onOpenaiLog((data) => {
        handleReviewLog(data);
    });

    // 폴더 선택 (메뉴에서)
    window.lawpro.onFolderSelected((path) => {
        setSelectedFolder(path);
    });

    // 설정 열기 (메뉴에서)
    window.lawpro.onOpenSettings(() => {
        showPage('settings');
    });

    // 패키지 설치 로그
    window.lawpro.onInstallLog((msg) => {
        elements.installOutput.classList.remove('hidden');
        elements.installOutput.textContent += msg;
        elements.installOutput.scrollTop = elements.installOutput.scrollHeight;
    });
}

// ============================================================
// 페이지 네비게이션
// ============================================================
function showPage(pageName) {
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('bg-primary-600/20', 'text-primary-400');
        btn.classList.add('hover:bg-gray-700', 'text-gray-300');
    });

    const pageEl = document.getElementById(`page${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`);
    const navEl = document.getElementById(`nav${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`);

    if (pageEl) pageEl.classList.remove('hidden');
    if (navEl) {
        navEl.classList.remove('hover:bg-gray-700', 'text-gray-300');
        navEl.classList.add('bg-primary-600/20', 'text-primary-400');
    }
}

// ============================================================
// 변환 기능
// ============================================================
function setSelectedFolder(path) {
    state.selectedFolder = path;
    elements.selectedFolder.textContent = path;
    elements.selectedFolder.classList.remove('hidden');
    elements.dropText.textContent = '폴더가 선택되었습니다';
    elements.startConvert.disabled = false;

    elements.reviewFolderPath.value = path;
    elements.startReview.disabled = false;
}

async function startConversion() {
    if (!state.selectedFolder) {
        addLog('error', '폴더를 먼저 선택해주세요');
        return;
    }

    state.isConverting = true;
    state.processedFiles = 0;
    state.successCount = 0;
    state.failCount = 0;

    elements.startConvert.classList.add('hidden');
    elements.stopConvert.classList.remove('hidden');
    elements.progressSection.classList.remove('hidden');
    elements.resultSummary.classList.add('hidden');
    elements.logArea.innerHTML = '';

    addLog('info', '변환을 시작합니다...');
    addLog('info', `출력 옵션: View HTML (필수), Clean HTML (${elements.chkCleanHtml.checked ? 'O' : 'X'}), Markdown (${elements.chkMarkdown.checked ? 'O' : 'X'})`);

    try {
        const apiKey = elements.upstageKeyInput.value;
        const generateClean = elements.chkCleanHtml.checked;
        const generateMarkdown = elements.chkMarkdown.checked;

        const result = await window.lawpro.startConversion(
            state.selectedFolder,
            apiKey,
            generateClean,
            generateMarkdown
        );

        if (result.success) {
            addLog('success', '모든 변환이 완료되었습니다!');
        } else {
            addLog('warning', '일부 파일 변환에 실패했습니다');
        }
    } catch (error) {
        addLog('error', `오류 발생: ${error.message}`);
    }

    state.isConverting = false;
    elements.startConvert.classList.remove('hidden');
    elements.stopConvert.classList.add('hidden');
}

async function stopConversion() {
    try {
        await window.lawpro.stopConversion();
        addLog('warning', '변환이 중단되었습니다');
    } catch (error) {
        addLog('error', `중단 실패: ${error.message}`);
    }

    state.isConverting = false;
    elements.startConvert.classList.remove('hidden');
    elements.stopConvert.classList.add('hidden');
}

function handleConversionLog(data) {
    switch (data.type) {
        case 'init':
            state.totalFiles = data.total;
            addLog('info', `총 ${data.total}개 파일 발견 (워커: ${data.workers}개)`);
            break;

        case 'progress':
            state.processedFiles++;
            updateProgress();

            if (data.status === 'success') {
                state.successCount++;
                const outputs = data.outputs ? ` [${data.outputs.join(', ')}]` : '';
                addLog('success', `${data.file} (${data.method}, ${data.time}초)${outputs}`);
            } else {
                state.failCount++;
                addLog('error', `${data.file}: ${data.error}`);
            }
            break;

        case 'complete':
            showResult(data);
            break;

        case 'error':
            addLog('error', data.msg);
            break;

        case 'warning':
            addLog('warning', data.msg);
            break;

        case 'log':
            addLog('info', data.msg);
            break;
    }
}

function updateProgress() {
    const percent = state.totalFiles > 0
        ? Math.round((state.processedFiles / state.totalFiles) * 100)
        : 0;

    elements.progressBar.style.width = `${percent}%`;
    elements.progressText.textContent = `${state.processedFiles} / ${state.totalFiles}`;
}

function showResult(data) {
    elements.resultSummary.classList.remove('hidden');
    elements.resultSuccess.textContent = data.success;
    elements.resultFail.textContent = data.fail;
    elements.resultTime.textContent = `${data.total_time}초`;
    state.outputFolder = data.output_folder;
}

async function openOutputFolder() {
    if (state.outputFolder) {
        await window.lawpro.openFolder(state.outputFolder);
    } else if (state.selectedFolder) {
        await window.lawpro.openFolder(state.selectedFolder + '/Converted_HTML');
    }
}

async function saveOutputOptions() {
    const generateClean = elements.chkCleanHtml.checked;
    const generateMarkdown = elements.chkMarkdown.checked;
    await window.lawpro.setOutputOptions(generateClean, generateMarkdown);
}

// ============================================================
// AI 연결 기능
// ============================================================
async function connectClaude() {
    elements.connectClaude.disabled = true;
    elements.connectClaude.textContent = '연결 중...';

    try {
        const result = await window.lawpro.setupClaudeMcp();

        if (result.success) {
            elements.claudeStatus.textContent = '연결됨';
            elements.claudeStatus.className = 'text-green-400';
            elements.claudeConnectionBadge.textContent = '연결됨';
            elements.claudeConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';

            elements.claudeMessage.textContent = result.message;
            elements.claudeMessage.className = 'mt-2 text-xs text-center text-green-400';
            elements.claudeMessage.classList.remove('hidden');
        } else {
            elements.claudeMessage.textContent = result.error;
            elements.claudeMessage.className = 'mt-2 text-xs text-center text-red-400';
            elements.claudeMessage.classList.remove('hidden');
        }
    } catch (error) {
        elements.claudeMessage.textContent = error.message;
        elements.claudeMessage.className = 'mt-2 text-xs text-center text-red-400';
        elements.claudeMessage.classList.remove('hidden');
    }

    elements.connectClaude.disabled = false;
    elements.connectClaude.textContent = '원클릭 연결';
}

async function saveGeminiKey() {
    const key = elements.geminiKeyInput.value.trim();
    if (!key) {
        alert('Gemini API 키를 입력해주세요');
        return;
    }

    await window.lawpro.saveGeminiKey(key);
    if (elements.settingsGeminiKey) elements.settingsGeminiKey.value = key;

    elements.geminiConnectionBadge.textContent = '설정됨';
    elements.geminiConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
}

async function saveGeminiKeyFromSettings() {
    const key = elements.settingsGeminiKey.value.trim();
    if (!key) {
        alert('Gemini API 키를 입력해주세요');
        return;
    }

    await window.lawpro.saveGeminiKey(key);
    elements.geminiKeyInput.value = key;

    elements.geminiConnectionBadge.textContent = '설정됨';
    elements.geminiConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
}

async function saveOpenaiKey() {
    const key = elements.openaiKeyInput.value.trim();
    if (!key) {
        alert('OpenAI API 키를 입력해주세요');
        return;
    }

    await window.lawpro.saveOpenaiKey(key);
    elements.openaiConnectionBadge.textContent = '설정됨';
    elements.openaiConnectionBadge.className = 'px-2 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
}

async function selectReviewFolder() {
    const result = await window.lawpro.selectFolder();
    if (!result.canceled) {
        elements.reviewFolderPath.value = result.path;
        elements.startReview.disabled = false;
    }
}

async function startReview() {
    const folderPath = elements.reviewFolderPath.value;
    if (!folderPath) {
        alert('폴더를 선택해주세요');
        return;
    }

    const selectedAI = elements.reviewAISelect.value;

    elements.startReview.disabled = true;
    elements.startReview.textContent = '검수 중...';
    elements.reviewLogArea.innerHTML = '';

    addReviewLog('info', `${selectedAI.toUpperCase()} 검수를 시작합니다...`);

    try {
        let result;
        if (selectedAI === 'gemini') {
            result = await window.lawpro.runGeminiReview(folderPath);
        } else if (selectedAI === 'openai') {
            result = await window.lawpro.runOpenaiReview(folderPath);
        }

        if (result.success) {
            addReviewLog('success', '모든 검수가 완료되었습니다!');
        } else {
            addReviewLog('warning', '일부 파일 검수에 실패했습니다');
        }
    } catch (error) {
        addReviewLog('error', `오류 발생: ${error.message}`);
    }

    elements.startReview.disabled = false;
    elements.startReview.textContent = '검수 시작';
}

function handleReviewLog(data) {
    switch (data.type) {
        case 'init':
            addReviewLog('info', `총 ${data.total}개 파일 발견 (모델: ${data.model})`);
            break;

        case 'progress':
            if (data.status === 'success') {
                addReviewLog('success', `${data.file} (${data.time}초)`);
            } else if (data.status === 'skipped') {
                addReviewLog('warning', `${data.file}: ${data.msg}`);
            } else {
                addReviewLog('error', `${data.file}: ${data.error}`);
            }
            break;

        case 'complete':
            addReviewLog('info', `완료: 성공 ${data.success}, 실패 ${data.fail}, 스킵 ${data.skipped}`);
            break;

        case 'error':
            addReviewLog('error', data.msg);
            break;

        case 'log':
            addReviewLog('info', data.msg);
            break;
    }
}

// ============================================================
// API 키 저장
// ============================================================
async function saveUpstageKey() {
    const key = elements.upstageKeyInput.value.trim();
    await window.lawpro.saveUpstageKey(key);
    if (elements.settingsUpstageKey) elements.settingsUpstageKey.value = key;
}

async function saveUpstageKeyFromSettings() {
    const key = elements.settingsUpstageKey.value.trim();
    await window.lawpro.saveUpstageKey(key);
    elements.upstageKeyInput.value = key;
}

// ============================================================
// 패키지 설치
// ============================================================
async function installPackages() {
    elements.installDeps.disabled = true;
    elements.installDeps.textContent = '설치 중...';
    elements.installOutput.classList.remove('hidden');
    elements.installOutput.textContent = '';

    try {
        const result = await window.lawpro.installPackages();

        if (result.success) {
            addLog('success', '패키지 설치가 완료되었습니다');
            await checkPythonStatus();
        } else {
            addLog('error', '패키지 설치에 실패했습니다');
        }
    } catch (error) {
        addLog('error', `설치 오류: ${error.message}`);
    }

    elements.installDeps.disabled = false;
    elements.installDeps.textContent = '필수 패키지 설치';
}

// ============================================================
// 유틸리티
// ============================================================
function addLog(type, message) {
    const logEntry = document.createElement('p');
    logEntry.className = `log-${type}`;

    const time = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    logEntry.textContent = `[${time}] ${message}`;

    elements.logArea.appendChild(logEntry);
    elements.logArea.scrollTop = elements.logArea.scrollHeight;
}

function addReviewLog(type, message) {
    const logEntry = document.createElement('p');
    logEntry.className = `log-${type}`;

    const time = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    logEntry.textContent = `[${time}] ${message}`;

    elements.reviewLogArea.appendChild(logEntry);
    elements.reviewLogArea.scrollTop = elements.reviewLogArea.scrollHeight;
}

// ============================================================
// 크레딧 관리
// ============================================================
async function loadCreditBalance() {
    try {
        // 사용자 이메일 로드
        const email = await window.lawpro.getUserEmail();
        if (email) {
            elements.userEmailInput.value = email;
        }

        // 잔액 로드
        const balance = await window.lawpro.getCreditBalance();
        updateCreditDisplay(balance);
    } catch (e) {
        console.error('크레딧 로드 실패:', e);
    }
}

function updateCreditDisplay(balance) {
    // 사이드바 잔액
    if (balance.is_admin) {
        elements.creditBalance.textContent = '무제한';
        elements.creditAdminBadge.classList.remove('hidden');
        elements.buyCreditsBtn.classList.add('hidden');
    } else {
        elements.creditBalance.textContent = `${balance.credits.toLocaleString()}원`;
        elements.creditAdminBadge.classList.add('hidden');
        elements.buyCreditsBtn.classList.remove('hidden');
    }

    // 모달 잔액
    if (elements.modalCreditBalance) {
        if (balance.is_admin) {
            elements.modalCreditBalance.textContent = '무제한 (관리자)';
        } else {
            elements.modalCreditBalance.textContent = `${balance.credits.toLocaleString()}원`;
        }
    }
}

function openCreditModal() {
    elements.creditModal.classList.remove('hidden');
    loadCreditBalance();
}

function closeCreditModal() {
    elements.creditModal.classList.add('hidden');
}

async function saveUserEmail() {
    const email = elements.userEmailInput.value.trim();
    if (!email) {
        alert('이메일을 입력해주세요');
        return;
    }

    try {
        const result = await window.lawpro.setUserEmail(email);
        if (result.is_admin) {
            alert('관리자 계정으로 인식되었습니다. 무제한 사용 가능합니다.');
        } else {
            alert('이메일이 저장되었습니다.');
        }
        await loadCreditBalance();
    } catch (e) {
        alert('이메일 저장 실패: ' + e.message);
    }
}

async function purchaseCredits(packageId) {
    try {
        // 테스트 모드: 바로 크레딧 추가
        const result = await window.lawpro.addCredits(packageId);
        if (result.success) {
            alert(`크레딧 충전 완료: ${result.credits_added.toLocaleString()}원`);
            await loadCreditBalance();
        } else {
            alert('충전 실패: ' + result.message);
        }
    } catch (e) {
        alert('충전 오류: ' + e.message);
    }
}

// 크레딧 이벤트 리스너 설정
function setupCreditEventListeners() {
    // 모달 열기/닫기
    elements.buyCreditsBtn?.addEventListener('click', openCreditModal);
    elements.closeCreditModal?.addEventListener('click', closeCreditModal);

    // 모달 외부 클릭으로 닫기
    elements.creditModal?.addEventListener('click', (e) => {
        if (e.target === elements.creditModal) {
            closeCreditModal();
        }
    });

    // 이메일 저장
    elements.saveUserEmail?.addEventListener('click', saveUserEmail);

    // 패키지 구매
    document.querySelectorAll('.credit-package').forEach(btn => {
        btn.addEventListener('click', () => {
            const packageId = btn.dataset.package;
            if (confirm('해당 크레딧 패키지를 구매하시겠습니까?')) {
                purchaseCredits(packageId);
            }
        });
    });
}

// ============================================================
// 에디터 기능
// ============================================================
function setupEditorEventListeners() {
    // 파일 열기/저장
    elements.editorOpenFile?.addEventListener('click', openEditorFile);
    elements.editorSaveFile?.addEventListener('click', saveEditorFile);

    // 탭 전환
    elements.tabHtml?.addEventListener('click', () => switchEditorTab('html'));
    elements.tabMarkdown?.addEventListener('click', () => switchEditorTab('markdown'));

    // 뷰 모드 전환
    elements.btnVisualView?.addEventListener('click', () => switchViewMode('visual'));
    elements.btnCodeView?.addEventListener('click', () => switchViewMode('code'));

    // 비주얼 에디터 변경 감지
    elements.visualEditor?.addEventListener('input', () => {
        editorState.isModified = true;
        elements.editorSaveFile.disabled = false;
        syncVisualToCode();
        updateHtmlPreview();
    });

    // 코드 에디터 변경 감지
    let htmlTimeout;
    elements.htmlCodeEditor?.addEventListener('input', () => {
        editorState.isModified = true;
        elements.editorSaveFile.disabled = false;
        clearTimeout(htmlTimeout);
        htmlTimeout = setTimeout(() => {
            syncCodeToVisual();
            updateHtmlPreview();
        }, 500);
    });

    // Markdown 에디터
    let mdTimeout;
    elements.mdCodeEditor?.addEventListener('input', () => {
        editorState.isModified = true;
        elements.editorSaveFile.disabled = false;
        clearTimeout(mdTimeout);
        mdTimeout = setTimeout(updateMarkdownPreview, 300);
    });

    // 새로고침 버튼
    elements.htmlRefresh?.addEventListener('click', updateHtmlPreview);

    // 텍스트 서식
    elements.fontSizeSelect?.addEventListener('change', (e) => {
        if (e.target.value) {
            execCommand('fontSize', e.target.value);
            e.target.value = '';
        }
    });
    elements.btnBold?.addEventListener('click', () => execCommand('bold'));
    elements.btnItalic?.addEventListener('click', () => execCommand('italic'));
    elements.btnUnderline?.addEventListener('click', () => execCommand('underline'));

    // 정렬
    elements.btnAlignLeft?.addEventListener('click', () => execCommand('justifyLeft'));
    elements.btnAlignCenter?.addEventListener('click', () => execCommand('justifyCenter'));
    elements.btnAlignRight?.addEventListener('click', () => execCommand('justifyRight'));

    // 표 편집
    elements.btnAddRowAbove?.addEventListener('click', () => tableAction('addRowAbove'));
    elements.btnAddRowBelow?.addEventListener('click', () => tableAction('addRowBelow'));
    elements.btnAddColLeft?.addEventListener('click', () => tableAction('addColLeft'));
    elements.btnAddColRight?.addEventListener('click', () => tableAction('addColRight'));
    elements.btnDeleteRow?.addEventListener('click', () => tableAction('deleteRow'));
    elements.btnDeleteCol?.addEventListener('click', () => tableAction('deleteCol'));
    elements.btnMergeCells?.addEventListener('click', () => tableAction('mergeCells'));
    elements.btnSplitCell?.addEventListener('click', () => tableAction('splitCell'));

    // 테두리 편집
    elements.btnBorderTop?.addEventListener('click', () => borderAction('top'));
    elements.btnBorderBottom?.addEventListener('click', () => borderAction('bottom'));
    elements.btnBorderLeft?.addEventListener('click', () => borderAction('left'));
    elements.btnBorderRight?.addEventListener('click', () => borderAction('right'));
    elements.btnBorderAll?.addEventListener('click', () => borderAction('all'));
    elements.btnBorderNone?.addEventListener('click', () => borderAction('none'));

    // 셀 선택 추적
    elements.visualEditor?.addEventListener('click', (e) => {
        const cell = e.target.closest('td, th');
        if (cell) {
            editorState.selectedCell = cell;
            highlightSelectedCell(cell);
        }
    });
}

// 뷰 모드 전환
function switchViewMode(mode) {
    editorState.viewMode = mode;

    if (mode === 'visual') {
        elements.btnVisualView.classList.add('bg-primary-600', 'text-white');
        elements.btnVisualView.classList.remove('bg-gray-700', 'text-gray-300');
        elements.btnCodeView.classList.remove('bg-primary-600', 'text-white');
        elements.btnCodeView.classList.add('bg-gray-700', 'text-gray-300');
        elements.visualEditorWrapper.classList.remove('hidden');
        elements.codeEditorWrapper.classList.add('hidden');
        syncCodeToVisual();
    } else {
        elements.btnCodeView.classList.add('bg-primary-600', 'text-white');
        elements.btnCodeView.classList.remove('bg-gray-700', 'text-gray-300');
        elements.btnVisualView.classList.remove('bg-primary-600', 'text-white');
        elements.btnVisualView.classList.add('bg-gray-700', 'text-gray-300');
        elements.codeEditorWrapper.classList.remove('hidden');
        elements.visualEditorWrapper.classList.add('hidden');
        syncVisualToCode();
    }
}

// 비주얼 → 코드 동기화
function syncVisualToCode() {
    if (elements.visualEditor && elements.htmlCodeEditor) {
        elements.htmlCodeEditor.value = elements.visualEditor.innerHTML;
    }
}

// 코드 → 비주얼 동기화
function syncCodeToVisual() {
    if (elements.visualEditor && elements.htmlCodeEditor) {
        elements.visualEditor.innerHTML = elements.htmlCodeEditor.value;
    }
}

// execCommand 래퍼
function execCommand(command, value = null) {
    elements.visualEditor?.focus();
    document.execCommand(command, false, value);
    editorState.isModified = true;
    elements.editorSaveFile.disabled = false;
    syncVisualToCode();
    updateHtmlPreview();
}

// 현재 선택된 셀 찾기
function getSelectedCell() {
    const selection = window.getSelection();
    if (selection.rangeCount > 0) {
        let node = selection.anchorNode;
        while (node && node !== elements.visualEditor) {
            if (node.nodeName === 'TD' || node.nodeName === 'TH') {
                return node;
            }
            node = node.parentNode;
        }
    }
    return editorState.selectedCell;
}

// 셀 하이라이트
function highlightSelectedCell(cell) {
    // 기존 하이라이트 제거
    elements.visualEditor?.querySelectorAll('td, th').forEach(c => {
        c.style.outline = '';
    });
    if (cell) {
        cell.style.outline = '2px solid #6366f1';
    }
}

// 표 편집 액션
function tableAction(action) {
    const cell = getSelectedCell();
    if (!cell) {
        alert('표의 셀을 먼저 선택해주세요');
        return;
    }

    const row = cell.closest('tr');
    const table = cell.closest('table');
    if (!row || !table) return;

    const cellIndex = Array.from(row.cells).indexOf(cell);
    const rowIndex = Array.from(table.rows).indexOf(row);

    switch (action) {
        case 'addRowAbove': {
            const newRow = table.insertRow(rowIndex);
            for (let i = 0; i < row.cells.length; i++) {
                const newCell = newRow.insertCell();
                newCell.innerHTML = '&nbsp;';
                newCell.style.border = '1px solid #ccc';
            }
            break;
        }
        case 'addRowBelow': {
            const newRow = table.insertRow(rowIndex + 1);
            for (let i = 0; i < row.cells.length; i++) {
                const newCell = newRow.insertCell();
                newCell.innerHTML = '&nbsp;';
                newCell.style.border = '1px solid #ccc';
            }
            break;
        }
        case 'addColLeft': {
            Array.from(table.rows).forEach(r => {
                const newCell = r.insertCell(cellIndex);
                newCell.innerHTML = '&nbsp;';
                newCell.style.border = '1px solid #ccc';
            });
            break;
        }
        case 'addColRight': {
            Array.from(table.rows).forEach(r => {
                const newCell = r.insertCell(cellIndex + 1);
                newCell.innerHTML = '&nbsp;';
                newCell.style.border = '1px solid #ccc';
            });
            break;
        }
        case 'deleteRow': {
            if (table.rows.length > 1) {
                table.deleteRow(rowIndex);
            }
            break;
        }
        case 'deleteCol': {
            if (row.cells.length > 1) {
                Array.from(table.rows).forEach(r => {
                    if (r.cells[cellIndex]) {
                        r.deleteCell(cellIndex);
                    }
                });
            }
            break;
        }
        case 'mergeCells': {
            const selection = window.getSelection();
            if (selection.rangeCount > 0) {
                // 간단한 병합: colspan 증가
                const colspan = parseInt(cell.getAttribute('colspan') || 1);
                cell.setAttribute('colspan', colspan + 1);
                // 오른쪽 셀 삭제
                if (row.cells[cellIndex + colspan]) {
                    row.deleteCell(cellIndex + colspan);
                }
            }
            break;
        }
        case 'splitCell': {
            const colspan = parseInt(cell.getAttribute('colspan') || 1);
            if (colspan > 1) {
                cell.setAttribute('colspan', colspan - 1);
                const newCell = row.insertCell(cellIndex + 1);
                newCell.innerHTML = '&nbsp;';
                newCell.style.border = '1px solid #ccc';
            }
            break;
        }
    }

    editorState.isModified = true;
    elements.editorSaveFile.disabled = false;
    syncVisualToCode();
    updateHtmlPreview();
}

// 테두리 편집 액션
function borderAction(side) {
    const cell = getSelectedCell();
    if (!cell) {
        alert('표의 셀을 먼저 선택해주세요');
        return;
    }

    const borderStyle = '1px solid #000';
    const noBorder = 'none';

    switch (side) {
        case 'top':
            cell.style.borderTop = cell.style.borderTop === noBorder ? borderStyle : noBorder;
            break;
        case 'bottom':
            cell.style.borderBottom = cell.style.borderBottom === noBorder ? borderStyle : noBorder;
            break;
        case 'left':
            cell.style.borderLeft = cell.style.borderLeft === noBorder ? borderStyle : noBorder;
            break;
        case 'right':
            cell.style.borderRight = cell.style.borderRight === noBorder ? borderStyle : noBorder;
            break;
        case 'all':
            cell.style.borderTop = borderStyle;
            cell.style.borderBottom = borderStyle;
            cell.style.borderLeft = borderStyle;
            cell.style.borderRight = borderStyle;
            break;
        case 'none':
            cell.style.borderTop = noBorder;
            cell.style.borderBottom = noBorder;
            cell.style.borderLeft = noBorder;
            cell.style.borderRight = noBorder;
            break;
    }

    editorState.isModified = true;
    elements.editorSaveFile.disabled = false;
    syncVisualToCode();
    updateHtmlPreview();
}

async function openEditorFile() {
    try {
        const file = await window.lawpro.editorOpenFile();
        if (!file) return;

        editorState.currentFile = file.path;
        editorState.currentType = file.type;
        editorState.isModified = false;

        elements.editorFileName.textContent = file.name;
        elements.editorSaveFile.disabled = true;

        if (file.type === 'markdown') {
            switchEditorTab('markdown');
            elements.mdCodeEditor.value = file.content;
            updateMarkdownPreview();
        } else {
            switchEditorTab('html');
            elements.htmlCodeEditor.value = file.content;
            elements.visualEditor.innerHTML = file.content;
            updateHtmlPreview();
        }
    } catch (err) {
        alert('파일 열기 실패: ' + err.message);
    }
}

async function saveEditorFile() {
    // 비주얼 모드면 먼저 동기화
    if (editorState.viewMode === 'visual') {
        syncVisualToCode();
    }

    const content = editorState.currentType === 'markdown'
        ? elements.mdCodeEditor.value
        : elements.htmlCodeEditor.value;

    if (!editorState.currentFile) {
        const defaultName = editorState.currentType === 'markdown' ? 'document.md' : 'document.html';
        try {
            const result = await window.lawpro.editorSaveAs(content, defaultName);
            if (result) {
                editorState.currentFile = result.path;
                elements.editorFileName.textContent = result.name;
                editorState.isModified = false;
                elements.editorSaveFile.disabled = true;
                alert('저장 완료!');
            }
        } catch (err) {
            alert('저장 실패: ' + err.message);
        }
    } else {
        try {
            await window.lawpro.editorSaveFile(editorState.currentFile, content);
            editorState.isModified = false;
            elements.editorSaveFile.disabled = true;
            alert('저장 완료!');
        } catch (err) {
            alert('저장 실패: ' + err.message);
        }
    }
}

function switchEditorTab(tab) {
    editorState.currentType = tab;

    if (tab === 'html') {
        elements.tabHtml.classList.add('border-primary-500', 'text-primary-400');
        elements.tabHtml.classList.remove('border-transparent', 'text-gray-400');
        elements.tabMarkdown.classList.remove('border-primary-500', 'text-primary-400');
        elements.tabMarkdown.classList.add('border-transparent', 'text-gray-400');

        elements.htmlEditorPanel.classList.remove('hidden');
        elements.markdownEditorPanel.classList.add('hidden');
    } else {
        elements.tabMarkdown.classList.add('border-primary-500', 'text-primary-400');
        elements.tabMarkdown.classList.remove('border-transparent', 'text-gray-400');
        elements.tabHtml.classList.remove('border-primary-500', 'text-primary-400');
        elements.tabHtml.classList.add('border-transparent', 'text-gray-400');

        elements.markdownEditorPanel.classList.remove('hidden');
        elements.htmlEditorPanel.classList.add('hidden');
    }
}

function updateHtmlPreview() {
    const html = editorState.viewMode === 'visual'
        ? elements.visualEditor?.innerHTML || ''
        : elements.htmlCodeEditor?.value || '';

    const iframe = elements.htmlPreview;
    if (iframe) {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        doc.open();
        doc.write(html);
        doc.close();
    }
}

function updateMarkdownPreview() {
    const md = elements.mdCodeEditor?.value || '';
    if (typeof marked !== 'undefined' && elements.mdPreview) {
        elements.mdPreview.innerHTML = marked.parse(md);
    } else if (elements.mdPreview) {
        elements.mdPreview.textContent = md;
    }
}

// ============================================================
// 앱 시작
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
    init();
    setupCreditEventListeners();
    setupEditorEventListeners();
});
