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
    failCount: 0
};

// ============================================================
// DOM 요소
// ============================================================
const elements = {
    // 네비게이션
    navConvert: document.getElementById('navConvert'),
    navReview: document.getElementById('navReview'),
    navSettings: document.getElementById('navSettings'),

    // 페이지
    pageConvert: document.getElementById('pageConvert'),
    pageReview: document.getElementById('pageReview'),
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

    // AI 검수 페이지
    connectClaude: document.getElementById('connectClaude'),
    claudeConnectionBadge: document.getElementById('claudeConnectionBadge'),
    claudeMessage: document.getElementById('claudeMessage'),
    geminiKeyInput: document.getElementById('geminiKeyInput'),
    geminiModelSelect: document.getElementById('geminiModelSelect'),
    saveGeminiKey: document.getElementById('saveGeminiKey'),
    geminiConnectionBadge: document.getElementById('geminiConnectionBadge'),
    reviewFolderPath: document.getElementById('reviewFolderPath'),
    selectReviewFolder: document.getElementById('selectReviewFolder'),
    startGeminiReview: document.getElementById('startGeminiReview'),
    geminiLogArea: document.getElementById('geminiLogArea'),

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
    appVersion: document.getElementById('appVersion')
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
        elements.settingsUpstageKey.value = upstageKey;
    }

    // Gemini 키
    const geminiKey = await window.lawpro.getGeminiKey();
    if (geminiKey) {
        elements.geminiKeyInput.value = geminiKey;
        elements.settingsGeminiKey.value = geminiKey;
        elements.geminiConnectionBadge.textContent = '설정됨';
        elements.geminiConnectionBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
    }

    // Gemini 모델
    const geminiModel = await window.lawpro.getGeminiModel();
    elements.geminiModelSelect.value = geminiModel;

    // 마지막 폴더
    const lastFolder = await window.lawpro.getLastFolder();
    if (lastFolder) {
        elements.reviewFolderPath.value = lastFolder;
        elements.startGeminiReview.disabled = false;
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
        elements.claudeConnectionBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-600/20 text-green-400';
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
    elements.navSettings.addEventListener('click', () => showPage('settings'));

    // 드롭존
    setupDropZone();

    // 변환 버튼
    elements.startConvert.addEventListener('click', startConversion);
    elements.stopConvert.addEventListener('click', stopConversion);

    // API 키 저장
    elements.saveUpstageKey.addEventListener('click', saveUpstageKey);
    elements.settingsSaveUpstage.addEventListener('click', saveUpstageKeyFromSettings);
    elements.saveGeminiKey.addEventListener('click', saveGeminiKey);
    elements.settingsSaveGemini.addEventListener('click', saveGeminiKeyFromSettings);

    // Claude 연결
    elements.connectClaude.addEventListener('click', connectClaude);
    elements.settingsConnectClaude.addEventListener('click', connectClaude);

    // Gemini 모델 변경
    elements.geminiModelSelect.addEventListener('change', async () => {
        await window.lawpro.setGeminiModel(elements.geminiModelSelect.value);
    });

    // 검수 폴더 선택
    elements.selectReviewFolder.addEventListener('click', selectReviewFolder);
    elements.startGeminiReview.addEventListener('click', startGeminiReview);

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
            // Electron에서 드래그된 파일의 경로 가져오기
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
        handleGeminiLog(data);
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
    // 모든 페이지 숨기기
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));

    // 모든 네비게이션 버튼 비활성화
    document.querySelectorAll('.nav-btn').forEach(btn => {
        btn.classList.remove('bg-primary-600/20', 'text-primary-400');
        btn.classList.add('hover:bg-gray-700', 'text-gray-300');
    });

    // 선택된 페이지 표시
    const pageEl = document.getElementById(`page${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`);
    const navEl = document.getElementById(`nav${pageName.charAt(0).toUpperCase() + pageName.slice(1)}`);

    if (pageEl) {
        pageEl.classList.remove('hidden');
    }

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

    // 검수 폴더도 설정
    elements.reviewFolderPath.value = path;
    elements.startGeminiReview.disabled = false;
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

    // UI 업데이트
    elements.startConvert.classList.add('hidden');
    elements.stopConvert.classList.remove('hidden');
    elements.progressSection.classList.remove('hidden');
    elements.resultSummary.classList.add('hidden');
    elements.logArea.innerHTML = '';

    addLog('info', '변환을 시작합니다...');

    try {
        const apiKey = elements.upstageKeyInput.value;
        const result = await window.lawpro.startConversion(state.selectedFolder, apiKey);

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
                addLog('success', `${data.file} (${data.method}, ${data.time}초)`);
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

    // 출력 폴더 저장
    state.outputFolder = data.output_folder;
}

async function openOutputFolder() {
    if (state.outputFolder) {
        await window.lawpro.openFolder(state.outputFolder);
    } else if (state.selectedFolder) {
        await window.lawpro.openFolder(state.selectedFolder + '/Converted_HTML');
    }
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
            elements.claudeConnectionBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-600/20 text-green-400';

            elements.claudeMessage.textContent = result.message;
            elements.claudeMessage.className = 'mt-3 text-sm text-center text-green-400';
            elements.claudeMessage.classList.remove('hidden');

            elements.settingsClaudeStatus.textContent = result.message;
            elements.settingsClaudeStatus.className = 'text-green-400';
        } else {
            elements.claudeMessage.textContent = result.error;
            elements.claudeMessage.className = 'mt-3 text-sm text-center text-red-400';
            elements.claudeMessage.classList.remove('hidden');

            elements.settingsClaudeStatus.textContent = result.error;
            elements.settingsClaudeStatus.className = 'text-red-400';
        }
    } catch (error) {
        elements.claudeMessage.textContent = error.message;
        elements.claudeMessage.className = 'mt-3 text-sm text-center text-red-400';
        elements.claudeMessage.classList.remove('hidden');
    }

    elements.connectClaude.disabled = false;
    elements.connectClaude.textContent = '원클릭 연결하기';
}

async function saveGeminiKey() {
    const key = elements.geminiKeyInput.value.trim();
    if (!key) {
        alert('Gemini API 키를 입력해주세요');
        return;
    }

    await window.lawpro.saveGeminiKey(key);
    elements.settingsGeminiKey.value = key;

    elements.geminiConnectionBadge.textContent = '설정됨';
    elements.geminiConnectionBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-600/20 text-green-400';

    alert('Gemini API 키가 저장되었습니다');
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
    elements.geminiConnectionBadge.className = 'px-3 py-1 rounded-full text-xs bg-green-600/20 text-green-400';

    alert('Gemini API 키가 저장되었습니다');
}

async function selectReviewFolder() {
    const result = await window.lawpro.selectFolder();
    if (!result.canceled) {
        elements.reviewFolderPath.value = result.path;
        elements.startGeminiReview.disabled = false;
    }
}

async function startGeminiReview() {
    const folderPath = elements.reviewFolderPath.value;
    if (!folderPath) {
        alert('폴더를 선택해주세요');
        return;
    }

    elements.startGeminiReview.disabled = true;
    elements.startGeminiReview.textContent = '검수 중...';
    elements.geminiLogArea.innerHTML = '';

    addGeminiLog('info', 'Gemini 검수를 시작합니다...');

    try {
        const result = await window.lawpro.runGeminiReview(folderPath);

        if (result.success) {
            addGeminiLog('success', '모든 검수가 완료되었습니다!');
        } else {
            addGeminiLog('warning', '일부 파일 검수에 실패했습니다');
        }
    } catch (error) {
        addGeminiLog('error', `오류 발생: ${error.message}`);
    }

    elements.startGeminiReview.disabled = false;
    elements.startGeminiReview.textContent = 'Gemini 검수 시작';
}

function handleGeminiLog(data) {
    switch (data.type) {
        case 'init':
            addGeminiLog('info', `총 ${data.total}개 파일 발견 (모델: ${data.model})`);
            break;

        case 'progress':
            if (data.status === 'success') {
                addGeminiLog('success', `${data.file} (${data.time}초)`);
            } else if (data.status === 'skipped') {
                addGeminiLog('warning', `${data.file}: ${data.msg}`);
            } else {
                addGeminiLog('error', `${data.file}: ${data.error}`);
            }
            break;

        case 'complete':
            addGeminiLog('info', `완료: 성공 ${data.success}, 실패 ${data.fail}, 스킵 ${data.skipped}`);
            break;

        case 'error':
            addGeminiLog('error', data.msg);
            break;

        case 'log':
            addGeminiLog('info', data.msg);
            break;
    }
}

// ============================================================
// API 키 저장
// ============================================================
async function saveUpstageKey() {
    const key = elements.upstageKeyInput.value.trim();
    await window.lawpro.saveUpstageKey(key);
    elements.settingsUpstageKey.value = key;
    alert('Upstage API 키가 저장되었습니다');
}

async function saveUpstageKeyFromSettings() {
    const key = elements.settingsUpstageKey.value.trim();
    await window.lawpro.saveUpstageKey(key);
    elements.upstageKeyInput.value = key;
    alert('Upstage API 키가 저장되었습니다');
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

function addGeminiLog(type, message) {
    const logEntry = document.createElement('p');
    logEntry.className = `log-${type}`;

    const time = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    logEntry.textContent = `[${time}] ${message}`;

    elements.geminiLogArea.appendChild(logEntry);
    elements.geminiLogArea.scrollTop = elements.geminiLogArea.scrollHeight;
}

// ============================================================
// 앱 시작
// ============================================================
document.addEventListener('DOMContentLoaded', init);
