/**
 * TransGuide Web 应用
 * 极简风格的翻译工具
 * 前端版本: v1.1.0 - 支持 Excel/PPT
 */

// 版本信息
const APP_VERSION = 'v1.1.0';
const FRONTEND_BUILD_TIME = new Date().toISOString();
console.log(`[版本信息] 前端版本: ${APP_VERSION}, 构建时间: ${FRONTEND_BUILD_TIME}`);

// 常量定义
const UPLOAD_DIR = 'uploads';

// 全局状态
const state = {
    currentView: 'import',
    theme: localStorage.getItem('theme') || 'light',
    // 导入功能状态
    importFile: null,
    importData: null,
    // 文件翻译状态
    uploadedFile: null,
    fileBlocks: [],
    translations: {},
    // 用户认证状态
    user: JSON.parse(localStorage.getItem('user') || 'null'),
    authToken: localStorage.getItem('authToken') || null,
    // 历史记录状态
    historyPage: 1,
    historyLimit: 10,
    historyTotal: 0,
    historyData: []
};

// 获取请求头（包含用户认证）
function getAuthHeaders() {
    const headers = {
        'Content-Type': 'application/json'
    };
    if (state.user && state.user.id) {
        headers['X-User-ID'] = state.user.id;
    }
    return headers;
}

// DOM 元素
const elements = {
    themeToggle: document.getElementById('themeToggle'),
    navItems: document.querySelectorAll('.nav-item'),
    views: document.querySelectorAll('.view'),
    termsCount: document.getElementById('termsCount'),
    tmCount: document.getElementById('tmCount'),
    toast: document.getElementById('toast'),
    
    // 导入功能
    importUploadArea: document.getElementById('importUploadArea'),
    importFileInput: document.getElementById('importFileInput'),
    importPreview: document.getElementById('importPreview'),
    importFilename: document.getElementById('importFilename'),
    importStats: document.getElementById('importStats'),
    detectedTerms: document.getElementById('detectedTerms'),
    startImportBtn: document.getElementById('startImportBtn'),
    importResult: document.getElementById('importResult'),
    importedTerms: document.getElementById('importedTerms'),
    importedSegments: document.getElementById('importedSegments'),
    analyzingOverlay: document.getElementById('analyzingOverlay'),
    
    // 术语库
    termSearch: document.getElementById('termSearch'),
    termsList: document.getElementById('termsList'),
    
    // 翻译记忆
    memorySearch: document.getElementById('memorySearch'),
    memoryList: document.getElementById('memoryList'),
    
    // 文本翻译
    sourceText: document.getElementById('sourceText'),
    targetText: document.getElementById('targetText'),
    translateBtn: document.getElementById('translateBtn'),
    clearBtn: document.getElementById('clearBtn'),
    translationSource: document.getElementById('translationSource'),
    
    // 文件翻译
    fileUploadArea: document.getElementById('fileUploadArea'),
    fileInput: document.getElementById('fileInput'),
    filePreview: document.getElementById('filePreview'),
    previewFilename: document.getElementById('previewFilename'),
    previewList: document.getElementById('previewList'),
    translateFileBtn: document.getElementById('translateFileBtn'),
    outputMode: document.getElementById('outputMode'),
    batchSize: document.getElementById('batchSize'),
    downloadBtn: document.getElementById('downloadBtn'),
    translatingOverlay: document.getElementById('translatingOverlay'),
    textTranslatingOverlay: document.getElementById('textTranslatingOverlay'),

    // 历史记录
    historySection: document.getElementById('historySection'),
    historyList: document.getElementById('historyList'),
    refreshHistoryBtn: document.getElementById('refreshHistoryBtn'),
    historyPagination: document.getElementById('historyPagination'),
    historyPrevBtn: document.getElementById('historyPrevBtn'),
    historyNextBtn: document.getElementById('historyNextBtn'),
    paginationInfo: document.getElementById('paginationInfo'),

    // 用户认证
    loginBtn: document.getElementById('loginBtn'),
    userInfo: document.getElementById('userInfo'),
    userName: document.getElementById('userName'),
    userRole: document.getElementById('userRole')
};

// 初始化
function init() {
    // 设置主题
    document.documentElement.setAttribute('data-theme', state.theme);
    updateThemeIcon();

    // 初始化用户状态
    initUserState();

    // 绑定事件
    bindEvents();

    // 如果已登录，加载统计数据
    if (state.user) {
        loadStats();
    }
}

// 初始化用户状态
function initUserState() {
    if (state.user) {
        updateUserUI();
    } else {
        // 未登录，强制显示登录窗口
        showAuthModal(true);
    }
}

// 绑定事件
function bindEvents() {
    // 主题切换
    elements.themeToggle.addEventListener('click', toggleTheme);

    // 导航切换
    elements.navItems.forEach(item => {
        item.addEventListener('click', () => switchView(item.dataset.view));
    });

    // 导入功能事件
    bindImportEvents();

    // 术语库搜索
    elements.termSearch?.addEventListener('input', debounce(searchTerms, 300));

    // 翻译记忆搜索
    elements.memorySearch?.addEventListener('input', debounce(searchMemory, 300));

    // 文本翻译
    elements.translateBtn?.addEventListener('click', translateText);
    elements.clearBtn?.addEventListener('click', clearText);
    elements.sourceText?.addEventListener('keydown', (e) => {
        if (e.ctrlKey && e.key === 'Enter') {
            translateText();
        }
    });

    // 文件翻译事件
    bindFileTranslationEvents();

    // 术语库管理事件
    bindTermManagementEvents();
}

// 绑定术语管理事件
function bindTermManagementEvents() {
    // 添加术语按钮
    document.getElementById('addTermBtn')?.addEventListener('click', () => openTermModal());

    // 分类管理按钮
    document.getElementById('manageCategoriesBtn')?.addEventListener('click', openCategoryModal);

    // 术语弹窗关闭
    document.getElementById('closeTermModal')?.addEventListener('click', closeTermModal);
    document.getElementById('cancelTermBtn')?.addEventListener('click', closeTermModal);

    // 保存术语
    document.getElementById('saveTermBtn')?.addEventListener('click', saveTerm);

    // 分类弹窗关闭
    document.getElementById('closeCategoryModal')?.addEventListener('click', closeCategoryModal);

    // 添加分类
    document.getElementById('addCategoryBtn')?.addEventListener('click', addCategory);

    // 点击弹窗外部关闭
    document.getElementById('termModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'termModal') closeTermModal();
    });
    document.getElementById('categoryModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'categoryModal') closeCategoryModal();
    });

    // 翻译记忆管理事件
    document.getElementById('cleanupMemoryBtn')?.addEventListener('click', cleanupMemory);
    document.getElementById('showDuplicatesBtn')?.addEventListener('click', showDuplicates);
    document.getElementById('closeDuplicatesModal')?.addEventListener('click', closeDuplicatesModal);
    document.getElementById('duplicatesModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'duplicatesModal') closeDuplicatesModal();
    });

    // 用户认证事件
    elements.loginBtn?.addEventListener('click', () => {
        if (state.user) {
            logout();
        } else {
            showAuthModal();
        }
    });

    // 登录弹窗关闭（仅在已登录状态下允许关闭）
    document.getElementById('authModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'authModal') closeAuthModal();
    });

    // 登录/注册切换
    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', () => switchAuthTab(tab.dataset.tab));
    });

    // 登录按钮
    document.getElementById('doLoginBtn')?.addEventListener('click', doLogin);
    document.getElementById('loginPassword')?.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') doLogin();
    });

    // 注册按钮
    document.getElementById('doRegisterBtn')?.addEventListener('click', doRegister);

    // 管理员弹窗关闭
    document.getElementById('closeAdminModal')?.addEventListener('click', closeAdminModal);
    document.getElementById('adminModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'adminModal') closeAdminModal();
    });

    // 管理员标签切换
    document.querySelectorAll('.admin-tab').forEach(tab => {
        tab.addEventListener('click', () => switchAdminTab(tab.dataset.tab));
    });
}

// 绑定导入功能事件
function bindImportEvents() {
    if (!elements.importUploadArea) return;

    // 点击上传
    elements.importUploadArea.addEventListener('click', (e) => {
        if (e.target.tagName !== 'BUTTON') {
            elements.importFileInput.click();
        }
    });

    // 文件选择 - 支持多文件
    elements.importFileInput.addEventListener('change', (e) => {
        const files = Array.from(e.target.files);
        if (files.length > 0) {
            if (files.length === 1) {
                // 单文件 - 显示预览
                uploadImportFile(files[0]);
            } else {
                // 多文件 - 批量导入
                batchImportFiles(files);
            }
        }
    });

    // 拖拽上传 - 支持多文件
    elements.importUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.importUploadArea.style.borderColor = 'var(--accent-color)';
    });

    elements.importUploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        elements.importUploadArea.style.borderColor = '';
    });

    elements.importUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.importUploadArea.style.borderColor = '';
        const files = Array.from(e.dataTransfer.files);
        if (files.length > 0) {
            if (files.length === 1) {
                uploadImportFile(files[0]);
            } else {
                batchImportFiles(files);
            }
        }
    });

    // 开始导入
    elements.startImportBtn?.addEventListener('click', processImport);
}

// 绑定文件翻译事件
function bindFileTranslationEvents() {
    if (!elements.fileUploadArea) return;
    
    elements.fileUploadArea.addEventListener('click', () => elements.fileInput.click());
    
    elements.fileUploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.fileUploadArea.style.borderColor = 'var(--accent-color)';
    });
    
    elements.fileUploadArea.addEventListener('dragleave', (e) => {
        e.preventDefault();
        elements.fileUploadArea.style.borderColor = '';
    });
    
    elements.fileUploadArea.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.fileUploadArea.style.borderColor = '';
        const files = e.dataTransfer.files;
        if (files.length > 0) uploadTranslationFile(files[0]);
    });
    
    elements.fileInput?.addEventListener('change', (e) => {
        const file = e.target.files[0];
        if (file) uploadTranslationFile(file);
    });
    
    elements.translateFileBtn?.addEventListener('click', translateFile);
    elements.downloadBtn?.addEventListener('click', downloadTranslatedFile);

    // 历史记录事件
    elements.refreshHistoryBtn?.addEventListener('click', () => {
        state.historyPage = 1;
        loadTranslationHistory();
    });
    elements.historyPrevBtn?.addEventListener('click', () => {
        if (state.historyPage > 1) {
            state.historyPage--;
            loadTranslationHistory();
        }
    });
    elements.historyNextBtn?.addEventListener('click', () => {
        if (state.historyPage * state.historyLimit < state.historyTotal) {
            state.historyPage++;
            loadTranslationHistory();
        }
    });

    // 搜索框事件
    const historySearchInput = document.getElementById('historySearchInput');
    historySearchInput?.addEventListener('input', debounce(() => {
        state.historyPage = 1;
        loadTranslationHistory();
    }, 500));

    // 用户筛选事件（管理员）
    const historyUserFilter = document.getElementById('historyUserFilter');
    historyUserFilter?.addEventListener('change', () => {
        state.historyPage = 1;
        loadTranslationHistory();
    });
}

// 防抖函数
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ========================================
// 主题和导航
// ========================================

function toggleTheme() {
    state.theme = state.theme === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', state.theme);
    localStorage.setItem('theme', state.theme);
    updateThemeIcon();
}

function updateThemeIcon() {
    const icon = state.theme === 'light' ? '🌙' : '☀️';
    elements.themeToggle.querySelector('.theme-icon').textContent = icon;
}

function switchView(viewName) {
    state.currentView = viewName;

    // 更新导航
    elements.navItems.forEach(item => {
        item.classList.toggle('active', item.dataset.view === viewName);
    });

    // 更新视图
    elements.views.forEach(view => {
        view.classList.toggle('active', view.id === viewName + 'View');
    });

    // 加载对应视图数据
    if (viewName === 'terms') {
        loadTerms();
    } else if (viewName === 'memory') {
        loadMemory();
    } else if (viewName === 'history') {
        // 切换到翻译历史视图时加载历史记录
        loadTranslationHistory();
    }
}

// ========================================
// 统计数据
// ========================================

async function loadStats() {
    // 检查是否已登录
    if (!state.user) {
        return;
    }
    
    try {
        const response = await fetch('/api/stats', {
            headers: {
                'X-User-ID': state.user.id
            }
        });
        
        if (response.status === 401) {
            // 未登录，不显示错误
            return;
        }
        
        const data = await response.json();

        if (data.success && data.stats) {
            elements.termsCount.textContent = data.stats.terms_count || 0;
            elements.tmCount.textContent = data.stats.tm_count || 0;
        }
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

// ========================================
// 导入历史文件功能
// ========================================

async function uploadImportFile(file) {
    const formData = new FormData();
    formData.append('file', file);
    
    // 显示加载遮罩层
    if (elements.analyzingOverlay) {
        elements.analyzingOverlay.style.display = 'flex';
    }
    
    try {
        const response = await fetch('/api/import/upload', {
            method: 'POST',
            headers: {
                'X-User-ID': state.user.id
            },
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.importFile = data.filename;
            state.importData = data;
            
            // 显示预览
            renderImportPreview(data);
            
            // 显示 LLM 使用情况
            if (data.llm_used) {
                showToast(`AI 提取到 ${data.total_terms} 个术语`);
            } else {
                showToast(`检测到 ${data.total_pairs} 个双语对（AI 未启用）`);
            }
        } else {
            showToast('分析失败: ' + data.error);
        }
    } catch (error) {
        console.error('上传失败:', error);
        showToast('上传失败，请检查网络连接');
    } finally {
        // 隐藏加载遮罩层
        if (elements.analyzingOverlay) {
            elements.analyzingOverlay.style.display = 'none';
        }
    }
}

function renderImportPreview(data) {
    // 显示预览区域
    elements.importPreview.style.display = 'block';
    elements.importResult.style.display = 'none';
    
    // 文件名
    elements.importFilename.textContent = data.filename.replace(/^\d{8}_\d{6}_/, '');
    
    // 更新术语数量显示
    elements.detectedTerms.textContent = data.total_terms;
    
    // 渲染术语列表（优先显示）
    const termsList = document.getElementById('termsPreviewList');
    const terms = data.potential_terms || [];
    
    if (terms.length > 0) {
        // 显示所有术语，按分类分组
        const termsByCategory = {};
        terms.forEach(term => {
            const cat = term.category || '未分类';
            if (!termsByCategory[cat]) termsByCategory[cat] = [];
            termsByCategory[cat].push(term);
        });
        
        let termsHtml = '';
        for (const [category, catTerms] of Object.entries(termsByCategory)) {
            termsHtml += `
                <div class="terms-category">
                    <span class="category-label">${escapeHtml(category)}</span>
                    <div class="terms-items">
                        ${catTerms.map(term => `
                            <div class="term-item">
                                <span class="term-en">${escapeHtml(term.english)}</span>
                                <span class="term-arrow">→</span>
                                <span class="term-zh">${escapeHtml(term.chinese)}</span>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
        }
        termsList.innerHTML = termsHtml;
    } else {
        termsList.innerHTML = '<div class="no-terms">未提取到术语</div>';
    }
    
    // 渲染双语对（拆分成句子，折叠显示）
    const pairsList = document.getElementById('pairsPreviewList');
    const pairsSummary = document.querySelector('.pairs-summary span:first-child');
    if (pairsSummary) {
        pairsSummary.textContent = `双语对照句段 (${data.total_pairs} 对)`;
    }
    
    // 将段落拆分成句子
    const sentences = [];
    (data.pairs || []).forEach((pair, idx) => {
        const sourceSentences = splitIntoSentences(pair.source);
        const targetSentences = splitIntoSentences(pair.target);
        
        // 配对句子
        const minLen = Math.min(sourceSentences.length, targetSentences.length);
        for (let i = 0; i < minLen; i++) {
            if (sourceSentences[i].trim().length > 10 && targetSentences[i].trim().length > 5) {
                sentences.push({
                    index: idx,
                    source: sourceSentences[i].trim(),
                    target: targetSentences[i].trim()
                });
            }
        }
    });
    
    // 只显示前30个句子对
    const displaySentences = sentences.slice(0, 30);
    if (displaySentences.length > 0) {
        pairsList.innerHTML = displaySentences.map((sent, i) => `
            <div class="sentence-pair">
                <span class="sentence-index">${i + 1}</span>
                <div class="sentence-content">
                    <div class="sentence-en">${escapeHtml(sent.source)}</div>
                    <div class="sentence-zh">${escapeHtml(sent.target)}</div>
                </div>
            </div>
        `).join('');
        
        if (sentences.length > 30) {
            pairsList.innerHTML += `
                <div class="more-sentences">
                    还有 ${sentences.length - 30} 个句子对...
                </div>
            `;
        }
    } else {
        pairsList.innerHTML = '<div class="no-pairs">未检测到双语句段</div>';
    }
}

// 将文本拆分成句子
function splitIntoSentences(text) {
    if (!text) return [];
    // 按中英文句号、问号、感叹号拆分
    return text.split(/([。\.\?\!？！]+)/).filter(s => s.trim().length > 0);
}

async function processImport() {
    if (!state.importData) {
        showToast('请先上传文件');
        return;
    }
    
    elements.startImportBtn.disabled = true;
    elements.startImportBtn.textContent = '导入中...';
    
    showToast('正在导入术语和翻译记忆...');
    
    try {
        const response = await fetch('/api/import/process', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({
                filename: state.importFile,
                filepath: state.importData.filepath,
                pairs: state.importData.pairs,
                terms: state.importData.potential_terms
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 显示结果
            elements.importResult.style.display = 'block';
            elements.importedTerms.textContent = data.imported_terms;
            elements.importedSegments.textContent = data.imported_segments;
            
            showToast('导入完成！');
            
            // 刷新统计数据
            loadStats();
        } else {
            showToast('导入失败: ' + data.error);
        }
    } catch (error) {
        console.error('导入失败:', error);
        showToast('导入失败，请重试');
    } finally {
        elements.startImportBtn.disabled = false;
        elements.startImportBtn.textContent = '开始导入';
    }
}

// ========================================
// 术语库功能
// ========================================

// 术语数据
let allTerms = [];
let currentCategory = '';
let editingTerm = null;
let categories = [];

async function loadTerms() {
    try {
        elements.termsList.innerHTML = '<div class="loading">加载中...</div>';

        const response = await fetch('/api/terms', {
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            allTerms = data.terms;
            renderTerms(allTerms);
            loadCategories();
        } else {
            elements.termsList.innerHTML = '<div class="loading">加载失败</div>';
        }
    } catch (error) {
        console.error('加载术语失败:', error);
        elements.termsList.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderTerms(terms) {
        // 按分类筛选
        let filteredTerms = terms;
        if (currentCategory) {
            filteredTerms = terms.filter(t => t.category === currentCategory);
        }

        if (filteredTerms.length === 0) {
            elements.termsList.innerHTML = `
                <div class="empty-state">
                    <p>暂无术语</p>
                    <p class="hint">点击"添加术语"按钮手动添加，或在"导入历史文件"页面上传双语文件提取</p>
                </div>
            `;
            return;
        }

        elements.termsList.innerHTML = filteredTerms.map(term => `
            <div class="term-item" data-source="${escapeHtml(term.source)}">
                <div class="term-header">
                    <div class="term-main">
                        <span class="term-english">${escapeHtml(term.source)}</span>
                        <span class="term-arrow">→</span>
                        <span class="term-chinese">${escapeHtml(term.target)}</span>
                    </div>
                    <div class="term-actions">
                        <button class="term-btn" onclick="editTerm('${escapeHtml(term.source)}')">编辑</button>
                        <button class="term-btn delete" onclick="deleteTerm('${escapeHtml(term.source)}')">删除</button>
                    </div>
                </div>
                ${term.category || term.tags ? `
                    <div class="term-meta">
                        ${term.category ? `<span class="term-category">${escapeHtml(term.category)}</span>` : ''}
                        ${term.tags ? term.tags.split(',').map(tag => tag.trim() ? `<span class="term-tag">${escapeHtml(tag.trim())}</span>` : '').join('') : ''}
                    </div>
                ` : ''}
                ${term.notes ? `<div class="term-notes">${escapeHtml(term.notes)}</div>` : ''}
            </div>
        `).join('');
}

async function loadCategories() {
    try {
        const response = await fetch('/api/terms/categories', {
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            categories = data.categories;
            renderCategoryFilter();
            updateCategorySelect();
            renderCategoryList();
        }
    } catch (error) {
        console.error('加载分类失败:', error);
    }
}

function renderCategoryFilter() {
    const filterContainer = document.getElementById('categoryFilter');
    const categoryButtons = categories.map(cat => `
        <button class="category-btn ${currentCategory === cat.name ? 'active' : ''}" data-category="${escapeHtml(cat.name)}">
            ${escapeHtml(cat.name)} (${cat.term_count})
        </button>
    `).join('');

    filterContainer.innerHTML = `
        <button class="category-btn ${currentCategory === '' ? 'active' : ''}" data-category="">全部</button>
        ${categoryButtons}
    `;

    // 绑定点击事件
    filterContainer.querySelectorAll('.category-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            currentCategory = btn.dataset.category;
            renderCategoryFilter();
            renderTerms(allTerms);
        });
    });
}

function updateCategorySelect() {
    const select = document.getElementById('termCategory');
    const options = categories.map(cat =>
        `<option value="${escapeHtml(cat.name)}">${escapeHtml(cat.name)}</option>`
    ).join('');
    select.innerHTML = '<option value="">无分类</option>' + options;
}

function renderCategoryList() {
    const listContainer = document.getElementById('categoryList');
    if (categories.length === 0) {
        listContainer.innerHTML = '<p style="color: var(--text-tertiary); text-align: center; padding: 20px;">暂无分类</p>';
        return;
    }

    listContainer.innerHTML = categories.map(cat => `
        <div class="category-list-item">
            <div>
                <span class="category-list-name">${escapeHtml(cat.name)}</span>
                <span class="category-list-count">(${cat.term_count}个术语)</span>
            </div>
            <div class="category-list-actions">
                <button class="term-btn delete" onclick="deleteCategory('${escapeHtml(cat.name)}')">删除</button>
            </div>
        </div>
    `).join('');
}

// 打开添加术语弹窗
function openTermModal(term = null) {
    editingTerm = term;
    const modal = document.getElementById('termModal');
    const title = document.getElementById('termModalTitle');
    const sourceInput = document.getElementById('termSource');
    const targetInput = document.getElementById('termTarget');
    const categorySelect = document.getElementById('termCategory');
    const tagsInput = document.getElementById('termTags');
    const notesInput = document.getElementById('termNotes');

    if (term) {
        title.textContent = '编辑术语';
        sourceInput.value = term.source;
        sourceInput.disabled = true;
        targetInput.value = term.target;
        categorySelect.value = term.category || '';
        tagsInput.value = term.tags || '';
        notesInput.value = term.notes || '';
    } else {
        title.textContent = '添加术语';
        sourceInput.value = '';
        sourceInput.disabled = false;
        targetInput.value = '';
        categorySelect.value = '';
        tagsInput.value = '';
        notesInput.value = '';
    }

    modal.style.display = 'flex';
}

function closeTermModal() {
    document.getElementById('termModal').style.display = 'none';
    editingTerm = null;
}

async function saveTerm() {
    const source = document.getElementById('termSource').value.trim();
    const target = document.getElementById('termTarget').value.trim();
    const category = document.getElementById('termCategory').value;
    const tags = document.getElementById('termTags').value.trim();
    const notes = document.getElementById('termNotes').value.trim();

    if (!source || !target) {
        showToast('英文术语和中文译法不能为空');
        return;
    }

    try {
        let response;
        if (editingTerm) {
            // 更新术语
            response = await fetch(`/api/terms/${encodeURIComponent(source)}`, {
                method: 'PUT',
                headers: getAuthHeaders(),
                body: JSON.stringify({ target, category, tags, notes })
            });
        } else {
            // 添加新术语
            response = await fetch('/api/terms', {
                method: 'POST',
                headers: getAuthHeaders(),
                body: JSON.stringify({ source, target, category, tags, notes })
            });
        }

        const data = await response.json();
        if (data.success) {
            showToast(editingTerm ? '术语更新成功' : '术语添加成功');
            closeTermModal();
            loadTerms();
        } else {
            showToast(data.error || '操作失败');
        }
    } catch (error) {
        console.error('保存术语失败:', error);
        showToast('保存失败，请重试');
    }
}

// 编辑术语
window.editTerm = function(source) {
    const term = allTerms.find(t => t.source === source);
    if (term) {
        openTermModal(term);
    }
};

// 删除术语
window.deleteTerm = async function(source) {
    if (!confirm(`确定要删除术语 "${source}" 吗？`)) {
        return;
    }

    try {
        const response = await fetch(`/api/terms/${encodeURIComponent(source)}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            showToast('术语删除成功');
            loadTerms();
        } else {
            showToast(data.error || '删除失败');
        }
    } catch (error) {
        console.error('删除术语失败:', error);
        showToast('删除失败，请重试');
    }
};

// 分类管理
function openCategoryModal() {
    document.getElementById('categoryModal').style.display = 'flex';
    loadCategories();
}

function closeCategoryModal() {
    document.getElementById('categoryModal').style.display = 'none';
}

async function addCategory() {
    const nameInput = document.getElementById('newCategoryName');
    const name = nameInput.value.trim();

    if (!name) {
        showToast('分类名称不能为空');
        return;
    }

    try {
        const response = await fetch('/api/terms/categories', {
            method: 'POST',
            headers: getAuthHeaders(),
            body: JSON.stringify({ name })
        });
        const data = await response.json();

        if (data.success) {
            showToast('分类添加成功');
            nameInput.value = '';
            loadCategories();
        } else {
            showToast(data.error || '添加失败');
        }
    } catch (error) {
        console.error('添加分类失败:', error);
        showToast('添加失败，请重试');
    }
}

// 删除分类
window.deleteCategory = async function(name) {
    if (!confirm(`确定要删除分类 "${name}" 吗？该分类下的术语将变为无分类。`)) {
        return;
    }

    try {
        const response = await fetch(`/api/terms/categories/${encodeURIComponent(name)}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            showToast('分类删除成功');
            loadCategories();
            if (currentCategory === name) {
                currentCategory = '';
                renderTerms(allTerms);
            }
        } else {
            showToast(data.error || '删除失败');
        }
    } catch (error) {
        console.error('删除分类失败:', error);
        showToast('删除失败，请重试');
    }
};

async function searchTerms() {
    const query = elements.termSearch.value.trim();
    if (!query) {
        renderTerms(allTerms);
        return;
    }

    try {
        const response = await fetch(`/api/terms/search?q=${encodeURIComponent(query)}`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            // 搜索时临时显示结果，不改变 allTerms
            const filtered = currentCategory
                ? data.terms.filter(t => t.category === currentCategory)
                : data.terms;
            renderTerms(filtered, true);
        }
    } catch (error) {
        console.error('搜索术语失败:', error);
    }
}

// ========================================
// 翻译记忆功能
// ========================================

async function batchImportFiles(files) {
        // 隐藏单文件预览
        elements.importPreview.style.display = 'none';
        elements.importResult.style.display = 'none';

        // 显示批量导入进度
        elements.batchImportProgress.style.display = 'block';
        elements.batchImportResult.style.display = 'none';

        const progressText = document.getElementById('progressText');
        const progressFill = document.getElementById('progressFill');
        const progressFiles = document.getElementById('progressFiles');

        // 初始化进度显示
        progressText.textContent = `0/${files.length}`;
        progressFill.style.width = '0%';

        // 显示文件列表
        progressFiles.innerHTML = files.map((file, index) => `
            <div class="progress-file-item" id="file-${index}" data-index="${index}">
                <span class="file-name">${escapeHtml(file.name)}</span>
                <span class="file-status">等待中...</span>
            </div>
        `).join('');

        // 批量处理结果
        const results = [];

        // 逐个处理文件
        for (let i = 0; i < files.length; i++) {
            const file = files[i];
            const fileItem = document.getElementById(`file-${i}`);

            // 更新状态为处理中
            fileItem.classList.add('processing');
            fileItem.querySelector('.file-status').textContent = '分析中...';

            try {
                // 上传并分析文件
                const formData = new FormData();
                formData.append('file', file);

                const response = await fetch('/api/import/upload', {
                    method: 'POST',
                    headers: {
                        'X-User-ID': state.user.id
                    },
                    body: formData
                });

                const data = await response.json();

                if (data.success) {
                    // 自动导入
                    fileItem.querySelector('.file-status').textContent = '导入中...';

                    const importResponse = await fetch('/api/import/process', {
                        method: 'POST',
                        headers: { 
                            'Content-Type': 'application/json',
                            'X-User-ID': state.user.id
                        },
                        body: JSON.stringify({
                            filename: data.filename,
                            filepath: data.filepath,
                            pairs: data.pairs,
                            terms: data.potential_terms
                        })
                    });

                    const importData = await importResponse.json();

                    if (importData.success) {
                        fileItem.classList.remove('processing');
                        fileItem.classList.add('success');
                        fileItem.querySelector('.file-status').textContent =
                            `✓ 术语${importData.imported_terms} 句段${importData.imported_segments}`;

                        results.push({
                            filename: file.name,
                            success: true,
                            terms: importData.imported_terms,
                            segments: importData.imported_segments
                        });
                    } else {
                        throw new Error(importData.error);
                    }
                } else {
                    throw new Error(data.error);
                }
            } catch (error) {
                console.error(`处理文件 ${file.name} 失败:`, error);
                fileItem.classList.remove('processing');
                fileItem.classList.add('error');
                fileItem.querySelector('.file-status').textContent = '✗ 失败';

                results.push({
                    filename: file.name,
                    success: false,
                    error: error.message
                });
            }

            // 更新进度
            const progress = ((i + 1) / files.length) * 100;
            progressFill.style.width = `${progress}%`;
            progressText.textContent = `${i + 1}/${files.length}`;
        }

        // 显示批量导入结果
        showBatchImportResults(results);

        // 刷新统计数据
        loadStats();
    }

function showBatchImportResults(results) {
        elements.batchImportProgress.style.display = 'none';
        elements.batchImportResult.style.display = 'block';

        const successCount = results.filter(r => r.success).length;
        const totalTerms = results.filter(r => r.success).reduce((sum, r) => sum + r.terms, 0);
        const totalSegments = results.filter(r => r.success).reduce((sum, r) => sum + r.segments, 0);

        // 汇总统计
        const resultSummary = document.getElementById('resultSummary');
        resultSummary.innerHTML = `
            <div class="summary-item">
                <span class="summary-number">${successCount}/${results.length}</span>
                <span class="summary-label">成功/总数</span>
            </div>
            <div class="summary-item">
                <span class="summary-number">${totalTerms}</span>
                <span class="summary-label">术语导入</span>
            </div>
            <div class="summary-item">
                <span class="summary-number">${totalSegments}</span>
                <span class="summary-label">句段导入</span>
            </div>
        `;

        // 文件详情
        const resultFiles = document.getElementById('resultFiles');
        resultFiles.innerHTML = results.map(result => `
            <div class="result-file-item ${result.success ? 'success' : 'error'}">
                <div class="file-info">
                    <div class="file-name">${escapeHtml(result.filename)}</div>
                    <div class="file-stats">
                        ${result.success
                            ? `术语: ${result.terms} | 句段: ${result.segments}`
                            : `错误: ${escapeHtml(result.error)}`
                        }
                    </div>
                </div>
                <span class="file-status-icon">${result.success ? '✓' : '✗'}</span>
            </div>
        `).join('');

    showToast(`批量导入完成: ${successCount}/${results.length} 个文件成功`);
}

// ========================================
// 翻译记忆管理功能
// ========================================

async function loadMemory() {
    try {
        elements.memoryList.innerHTML = '<div class="loading">加载中...</div>';

        const response = await fetch('/api/memory', {
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            renderMemory(data.memory);
            loadMemoryStats();
        } else {
            elements.memoryList.innerHTML = '<div class="loading">加载失败</div>';
        }
    } catch (error) {
        console.error('加载翻译记忆失败:', error);
        elements.memoryList.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderMemory(memory) {
    if (memory.length === 0) {
        elements.memoryList.innerHTML = `
            <div class="empty-state">
                <p>暂无翻译记忆</p>
                <p class="hint">在"导入历史文件"页面上传双语文件建立记忆库</p>
            </div>
        `;
        return;
    }

    elements.memoryList.innerHTML = memory.map(item => `
        <div class="memory-item">
            <div class="memory-source">${escapeHtml(item.source || item.original)}</div>
            <div class="memory-target">${escapeHtml(item.target || item.translation)}</div>
        </div>
    `).join('');
}

async function loadMemoryStats() {
    try {
        const response = await fetch('/api/stats', {
            headers: {
                'X-User-ID': state.user.id
            }
        });
        const data = await response.json();

        if (data.success) {
            const stats = data.stats;
            const memoryStats = document.getElementById('memoryStats');
            memoryStats.innerHTML = `
                <div class="memory-stat-item">
                    <span class="memory-stat-number">${stats.tm_count || 0}</span>
                    <span class="memory-stat-label">总句段</span>
                </div>
                <div class="memory-stat-item">
                    <span class="memory-stat-number">${stats.source_files || 0}</span>
                    <span class="memory-stat-label">来源文件</span>
                </div>
            `;
        }
    } catch (error) {
        console.error('加载统计失败:', error);
    }
}

async function searchMemory() {
    const query = elements.memorySearch.value.trim();
    if (!query) {
        loadMemory();
        return;
    }

    try {
        const response = await fetch(`/api/memory/search?q=${encodeURIComponent(query)}`, {
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            renderMemory(data.memory);
        }
    } catch (error) {
        console.error('搜索翻译记忆失败:', error);
    }
}

// 清理低质量句段
async function cleanupMemory() {
    if (!confirm('确定要清理低质量句段吗？这将删除过短或过长的句段。')) {
        return;
    }

    try {
        showToast('正在清理...');
        const response = await fetch('/api/memory/cleanup', { 
            method: 'POST',
            headers: getAuthHeaders()
        });
        const data = await response.json();

        if (data.success) {
            showToast(`清理完成，删除了 ${data.deleted} 个低质量句段`);
            loadMemory();
        } else {
            showToast(data.error || '清理失败');
        }
    } catch (error) {
        console.error('清理失败:', error);
        showToast('清理失败，请重试');
    }
}

// 显示重复句段
async function showDuplicates() {
        try {
            showToast('正在查找重复句段...');
            const response = await fetch('/api/memory/duplicates', {
                headers: getAuthHeaders()
            });
            const data = await response.json();

            if (data.success) {
                renderDuplicates(data.duplicates);
                document.getElementById('duplicatesModal').style.display = 'flex';
            } else {
                showToast(data.error || '查找失败');
            }
        } catch (error) {
            console.error('查找重复句段失败:', error);
            showToast('查找失败，请重试');
        }
    }

    function renderDuplicates(duplicates) {
        const container = document.getElementById('duplicatesList');

        if (duplicates.length === 0) {
            container.innerHTML = '<p style="text-align: center; color: var(--text-tertiary); padding: 40px;">未发现重复句段</p>';
            return;
        }

        container.innerHTML = duplicates.map((group, index) => `
            <div class="duplicate-group">
                <div class="duplicate-group-header">
                    <span class="duplicate-group-title">重复组 ${index + 1} (${group.length} 个相似句段)</span>
                    <div class="duplicate-group-actions">
                        <button class="btn btn-small btn-primary" onclick="mergeDuplicates(${index})">合并</button>
                    </div>
                </div>
                ${group.map((item, i) => `
                    <div class="duplicate-item">
                        <input type="radio" name="keep-${index}" value="${item.id}" ${i === 0 ? 'checked' : ''}>
                        <div class="duplicate-item-content">
                            <div class="duplicate-item-source">${escapeHtml(item.original)}</div>
                            <div class="duplicate-item-target">${escapeHtml(item.translation)}</div>
                            ${item.similarity ? `<div class="duplicate-item-similarity">相似度: ${(item.similarity * 100).toFixed(1)}%</div>` : ''}
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('');

    // 保存当前重复组数据
    window.currentDuplicates = duplicates;
}

// 合并重复句段
window.mergeDuplicates = async function(groupIndex) {
    const group = window.currentDuplicates[groupIndex];
    if (!group) return;

    // 获取选中的保留项
    const radios = document.querySelectorAll(`input[name="keep-${groupIndex}"]:checked`);
    if (radios.length === 0) {
        showToast('请选择要保留的句段');
        return;
    }

    const keepId = parseInt(radios[0].value);
    const removeIds = group
        .filter(item => item.id !== keepId)
        .map(item => item.id);

    try {
        const response = await fetch('/api/memory/duplicates/merge', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ keep_id: keepId, remove_ids: removeIds })
        });

        const data = await response.json();
        if (data.success) {
            showToast('合并成功');
            // 刷新重复列表
            showDuplicates();
            loadMemory();
        } else {
            showToast(data.error || '合并失败');
        }
    } catch (error) {
        console.error('合并失败:', error);
        showToast('合并失败，请重试');
    }
};

function closeDuplicatesModal() {
    document.getElementById('duplicatesModal').style.display = 'none';
}

// ========================================
// 文本翻译功能
// ========================================

async function translateText() {
    const text = elements.sourceText.value.trim();
    if (!text) {
        showToast('请输入要翻译的文本');
        return;
    }
    
    elements.translateBtn.disabled = true;
    elements.translateBtn.textContent = '翻译中...';
    if (elements.textTranslatingOverlay) {
        elements.textTranslatingOverlay.style.display = 'flex';
    }
    
    try {
        const response = await fetch('/api/translate/text', {
            method: 'POST',
            headers: { 
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({ text })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // 清理翻译结果中的 <think> 标签
            let translation = data.translation || '';
            translation = translation.replace(/<think>[\s\S]*?<\/think>/gi, '').trim();
            elements.targetText.value = translation;
            
            // 显示翻译来源
            let sourceText = '';
            switch (data.source) {
                case 'tm':
                    sourceText = `翻译记忆 (相似度: ${(data.similarity * 100).toFixed(1)}%)`;
                    break;
                case 'llm':
                    sourceText = 'AI 翻译';
                    break;
                case 'non_english':
                    sourceText = '非英文内容';
                    break;
                default:
                    sourceText = '';
            }
            elements.translationSource.textContent = sourceText;
        } else {
            showToast('翻译失败: ' + data.error);
        }
    } catch (error) {
        console.error('翻译失败:', error);
        showToast('翻译失败，请检查网络连接');
    } finally {
        elements.translateBtn.disabled = false;
        elements.translateBtn.textContent = '翻译';
        if (elements.textTranslatingOverlay) {
            elements.textTranslatingOverlay.style.display = 'none';
        }
    }
}

function clearText() {
    elements.sourceText.value = '';
    elements.targetText.value = '';
    elements.translationSource.textContent = '';
    elements.sourceText.focus();
}

// ========================================
// 文件翻译功能
// ========================================

async function uploadTranslationFile(file) {
    console.log('[前端调试] ========== 开始上传文件 ==========');
    console.log('[前端调试] 文件名:', file.name);
    console.log('[前端调试] 文件类型:', file.type);
    console.log('[前端调试] 文件大小:', file.size);
    
    const formData = new FormData();
    formData.append('file', file);
    
    showToast('正在解析文件...');
    
    try {
        console.log('[前端调试] 发送请求到 /api/upload');
        const response = await fetch('/api/upload', {
            method: 'POST',
            headers: {
                'X-User-ID': state.user.id
            },
            body: formData
        });
        
        console.log('[前端调试] 响应状态:', response.status);
        const data = await response.json();
        console.log('[前端调试] 响应数据:', data);
        
        if (data.success) {
            state.uploadedFile = data.filename;  // 存储用的文件名（带时间戳）
            state.originalFilename = data.original_filename;  // 原始文件名
            state.fileBlocks = data.blocks;
            state.translations = {};
            state.indexMapping = data.index_mapping || {}; // 保存坐标映射
            state.downloadUrl = null; // 重置下载URL
            state.isChinaSheet = data.is_china_sheet || false; // 保存特殊结构标记

            console.log('[前端调试] 存储文件名:', state.uploadedFile);
            console.log('[前端调试] 原始文件名:', state.originalFilename);
            console.log('[前端调试] 坐标映射:', state.indexMapping);
            console.log('[前端调试] 是否中国表:', state.isChinaSheet);

            renderFilePreview(data.original_filename, data.blocks);
            showToast(`成功解析 ${data.total} 个文本块`);
        } else {
            console.error('[前端调试] 上传失败:', data.error);
            showToast('上传失败: ' + data.error);
        }
    } catch (error) {
        console.error('[前端调试] 上传异常:', error);
        showToast('上传失败，请检查网络连接');
    }
    console.log('[前端调试] ========== 上传结束 ==========');
}

// 分页状态
let previewPageState = {
    currentPage: 1,
    pageSize: 15,
    totalBlocks: 0,
    totalPages: 1
};

function renderFilePreview(filename, blocks) {
    elements.filePreview.style.display = 'block';
    elements.previewFilename.textContent = filename.replace(/^\d{8}_\d{6}_/, '');
    
    // 禁用下载按钮
    if (elements.downloadBtn) {
        elements.downloadBtn.style.opacity = '0.5';
        elements.downloadBtn.style.pointerEvents = 'none';
        state.downloadUrl = null;
    }
    
    // 保存所有块到状态
    state.allFileBlocks = blocks;
    
    // 初始化分页状态
    previewPageState.totalBlocks = blocks.length;
    previewPageState.totalPages = Math.ceil(blocks.length / previewPageState.pageSize);
    previewPageState.currentPage = 1;
    
    // 渲染当前页
    renderPreviewPage();
}

function renderPreviewPage() {
    const blocks = state.allFileBlocks;
    const startIdx = (previewPageState.currentPage - 1) * previewPageState.pageSize;
    const endIdx = Math.min(startIdx + previewPageState.pageSize, blocks.length);
    const displayBlocks = blocks.slice(startIdx, endIdx);

    let html = displayBlocks.map(block => {
        // 构建位置标签
        let locationTag = '';
        if (block.sheet !== undefined) {
            // Excel 文件
            locationTag = `<span class="location-tag excel-tag">${block.sheet} [${block.row + 1},${block.col + 1}]</span>`;
        } else if (block.slide !== undefined) {
            // PPT 文件
            locationTag = `<span class="location-tag ppt-tag">幻灯片 ${block.slide + 1}</span>`;
        }

        // 检查是否已有翻译
        const translation = state.translations[block.index];
        const translationContent = translation
            ? escapeHtml(translation)
            : '<em>等待翻译...</em>';

        return `
        <div class="preview-item" data-index="${block.index}">
            <span class="preview-index">${block.index + 1}</span>
            <div class="preview-content">
                ${locationTag}
                <div class="preview-text">${escapeHtml(block.text)}</div>
            </div>
            <div class="preview-translation" id="translation-${block.index}">
                ${translationContent}
            </div>
        </div>
    `}).join('');
    
    // 添加分页控件
    if (previewPageState.totalPages > 1) {
        html += renderPaginationControls();
    }
    
    elements.previewList.innerHTML = html;
    
    // 绑定分页按钮事件
    bindPaginationEvents();
}

function renderPaginationControls() {
    const { currentPage, totalPages, totalBlocks } = previewPageState;
    
    let controls = `
        <div class="preview-pagination" style="display: flex; justify-content: center; align-items: center; gap: 8px; padding: 16px; border-top: 1px solid var(--border-color);">
            <span style="color: var(--text-secondary); font-size: 13px; margin-right: 8px;">
                共 ${totalBlocks} 个文本块，第 ${currentPage}/${totalPages} 页
            </span>
            <button class="btn btn-sm" id="previewFirstPage" ${currentPage === 1 ? 'disabled' : ''}>首页</button>
            <button class="btn btn-sm" id="previewPrevPage" ${currentPage === 1 ? 'disabled' : ''}>上一页</button>
            <input type="number" id="previewPageInput" value="${currentPage}" min="1" max="${totalPages}" 
                   style="width: 60px; text-align: center; padding: 4px 8px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--bg-primary); color: var(--text-primary);">
            <button class="btn btn-sm" id="previewGoToPage">跳转</button>
            <button class="btn btn-sm" id="previewNextPage" ${currentPage === totalPages ? 'disabled' : ''}>下一页</button>
            <button class="btn btn-sm" id="previewLastPage" ${currentPage === totalPages ? 'disabled' : ''}>尾页</button>
        </div>
    `;
    
    return controls;
}

function bindPaginationEvents() {
    const totalPages = previewPageState.totalPages;
    
    // 首页
    document.getElementById('previewFirstPage')?.addEventListener('click', () => {
        if (previewPageState.currentPage !== 1) {
            previewPageState.currentPage = 1;
            renderPreviewPage();
        }
    });
    
    // 上一页
    document.getElementById('previewPrevPage')?.addEventListener('click', () => {
        if (previewPageState.currentPage > 1) {
            previewPageState.currentPage--;
            renderPreviewPage();
        }
    });
    
    // 下一页
    document.getElementById('previewNextPage')?.addEventListener('click', () => {
        if (previewPageState.currentPage < totalPages) {
            previewPageState.currentPage++;
            renderPreviewPage();
        }
    });
    
    // 尾页
    document.getElementById('previewLastPage')?.addEventListener('click', () => {
        if (previewPageState.currentPage !== totalPages) {
            previewPageState.currentPage = totalPages;
            renderPreviewPage();
        }
    });
    
    // 跳转
    document.getElementById('previewGoToPage')?.addEventListener('click', () => {
        const input = document.getElementById('previewPageInput');
        const page = parseInt(input.value);
        if (page >= 1 && page <= totalPages) {
            previewPageState.currentPage = page;
            renderPreviewPage();
        } else {
            showToast(`请输入 1-${totalPages} 之间的页码`);
        }
    });
    
    // 回车跳转
    document.getElementById('previewPageInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            document.getElementById('previewGoToPage')?.click();
        }
    });
}

// 创建批次分组
function createBatches(blocks, maxSize) {
    const batches = [];
    let currentBatch = [];
    let currentSize = 0;
    
    for (const block of blocks) {
        const blockSize = block.text.length;
        
        // 如果当前批次加上这个块会超限，先保存当前批次
        if (currentSize + blockSize > maxSize && currentBatch.length > 0) {
            batches.push(currentBatch);
            currentBatch = [];
            currentSize = 0;
        }
        
        currentBatch.push(block);
        currentSize += blockSize;
    }
    
    // 保存最后一个批次
    if (currentBatch.length > 0) {
        batches.push(currentBatch);
    }
    
    return batches;
}

// 下载翻译后的文件
async function downloadTranslatedFile() {
    if (!state.downloadUrl) {
        showToast('没有可下载的文件');
        return;
    }

    console.log('[下载] 开始下载文件:', state.downloadUrl);

    try {
        // 构建完整URL，添加user_id参数用于认证
        let fullUrl = state.downloadUrl.startsWith('http')
            ? state.downloadUrl
            : window.location.origin + state.downloadUrl;

        // 添加user_id参数
        const separator = fullUrl.includes('?') ? '&' : '?';
        fullUrl += `${separator}user_id=${state.user.id}`;

        // 创建一个临时的iframe来下载（避免页面跳转）
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = fullUrl;
        document.body.appendChild(iframe);

        // 3秒后移除iframe
        setTimeout(() => {
            document.body.removeChild(iframe);
        }, 3000);

        console.log('[下载] 下载已启动:', fullUrl);
        showToast('文件下载中...');
    } catch (error) {
        console.error('[下载] 下载失败:', error);
        showToast('下载失败: ' + error.message);
    }
}

async function translateFile() {
    console.log('[LLM链路] ========== 开始文件翻译流程 ==========');
    console.log('[LLM链路] 文件块数量:', state.fileBlocks.length);
    
    if (!state.uploadedFile || state.fileBlocks.length === 0) {
        showToast('请先上传文件');
        return;
    }
    
    elements.translateFileBtn.disabled = true;
    elements.translateFileBtn.textContent = '翻译中...';
    
    // 显示加载遮罩
    if (elements.translatingOverlay) {
        elements.translatingOverlay.style.display = 'flex';
    }
    
    showToast('开始翻译文件...');
    
    // 按字符数分批，从用户设置读取批次大小
    const USER_BATCH_SIZE = parseInt(elements.batchSize.value) || 60000;
    let currentBatchSize = USER_BATCH_SIZE;
    let hasAdjustedBatchSize = false; // 标记是否已调整过批次大小
    console.log('[LLM链路] 批次大小设置:', USER_BATCH_SIZE, '字符/批');
    
    // 使用队列管理所有待处理的批次（包括断点续传产生的子批次）
    let batches = createBatches(state.fileBlocks, currentBatchSize);
    console.log('[LLM链路] 初始批次数量:', batches.length, '各批次大小:', batches.map(b => b.length));
    
    let completed = 0;
    const total = state.fileBlocks.length;
    let batchIdx = 0;
    
    while (batchIdx < batches.length) {
        const batch = batches[batchIdx];
        console.log(`[LLM链路] --- 批次 ${batchIdx + 1}/${batches.length} (块 ${completed}-${completed + batch.length - 1}) ---`);
        console.log('[LLM链路] 批次文本索引:', batch.map(b => b.index));
        
        // 构建请求体，使用数字索引
        const indexMapping = {}; // 用于映射数字索引到原始索引
        const requestBody = { 
            texts: batch.map((b, i) => {
                const numericIndex = i; // 使用简单的数字索引
                indexMapping[numericIndex] = b.index; // 保存映射关系
                return { 
                    index: numericIndex, 
                    text: b.text 
                };
            }),
            start_index: 0 // 新增：起始索引偏移
        };
        console.log('[LLM链路] 索引映射:', indexMapping);
        console.log('[LLM链路] 请求体大小:', JSON.stringify(requestBody).length, '字符');
        
        showToast(`翻译批次 ${batchIdx + 1}/${batches.length}...`);
        
        try {
            console.log('[LLM链路] 发送请求到 /api/translate/batch...');
            const startTime = performance.now();
            const response = await fetch('/api/translate/batch', {
                method: 'POST',
                headers: { 
                    'Content-Type': 'application/json',
                    'X-User-ID': state.user.id
                },
                body: JSON.stringify(requestBody)
            });
            const endTime = performance.now();
            const duration = (endTime - startTime) / 1000;
            
            console.log('[LLM链路] 响应状态:', response.status, '耗时:', duration.toFixed(2), '秒');
            const data = await response.json();
            console.log('[LLM链路] 响应 success:', data.success, '翻译数量:', data.translations ? data.translations.length : 0, '耗时:', duration.toFixed(2), '秒');
            
            if (data.success && data.translations) {
                // 检查是否所有块都被翻译（截断检测）
                const expectedCount = batch.length;
                const actualCount = data.translations.length;
                const completionRate = actualCount / expectedCount;
                
                console.log(`[LLM链路] 期望翻译 ${expectedCount} 个块，实际返回 ${actualCount} 个块，完成率 ${(completionRate * 100).toFixed(1)}%`);
                
                // 更新翻译结果，使用索引映射还原原始索引
                for (const trans of data.translations) {
                    const originalIndex = indexMapping[trans.index];
                    if (originalIndex !== undefined) {
                        state.translations[originalIndex] = trans.translation;
                        
                        // 更新预览
                        const transEl = document.getElementById(`translation-${originalIndex}`);
                        if (transEl) {
                            transEl.textContent = trans.translation;
                        }
                    }
                }
                
                // 功能1: 截断检测 - 如果完成率低于90%且未调整过批次大小，调整到80%
                if (completionRate < 0.9 && !hasAdjustedBatchSize) {
                    const newBatchSize = Math.floor(USER_BATCH_SIZE * 0.8);
                    console.log(`[LLM链路] 检测到截断，批次大小从 ${currentBatchSize} 调整为 ${newBatchSize} (80%)`);
                    showToast(`检测到截断，后续批次调整为 ${newBatchSize} 字符/批`);
                    currentBatchSize = newBatchSize;
                    hasAdjustedBatchSize = true;
                }
                
                // 功能2: 断点续传 - 如果有未翻译的块，创建续传批次
                if (actualCount < expectedCount) {
                    const remainingBlocks = batch.slice(actualCount);
                    console.log(`[LLM链路] 断点续传：${actualCount}/${expectedCount} 完成，剩余 ${remainingBlocks.length} 个块`);
                    
                    // 将剩余块作为新批次插入队列（下一个位置）
                    if (remainingBlocks.length > 0) {
                        batches.splice(batchIdx + 1, 0, remainingBlocks);
                        console.log(`[LLM链路] 已将剩余 ${remainingBlocks.length} 个块插入队列`);
                    }
                }
                
                completed += actualCount;
                console.log('[LLM链路] 批次完成，累计完成:', completed, '/', total);
                batchIdx++; // 处理下一个批次
                
            } else {
                console.error('[LLM链路] 失败:', data.error);
                // 检查是否是额度用尽的错误
                if (data.quota_exceeded || (data.error && data.error.includes('额度已用尽'))) {
                    showToast('API额度已用尽，请等待5小时后重试');
                    // 中断翻译流程
                    break;
                } else {
                    showToast('翻译失败: ' + (data.error || '未知错误'));
                    batchIdx++; // 跳过这个批次，继续下一个
                }
            }
        } catch (error) {
            console.error(`[LLM链路] 批次 ${batchIdx + 1} 异常:`, error);
            showToast(`批次 ${batchIdx + 1} 翻译失败`);
            batchIdx++; // 跳过这个批次，继续下一个
        }
    }
    
    console.log('[LLM链路] ========== 翻译流程结束，总翻译数:', Object.keys(state.translations).length, '==========');
    
    // 导出文件
    console.log('[导出调试] ========== 开始导出文件 ==========');
    console.log('[导出调试] 文件名:', state.uploadedFile);
    console.log('[导出调试] 翻译条目数:', Object.keys(state.translations).length);
    console.log('[导出调试] 坐标映射:', state.indexMapping);
    console.log('[导出调试] 是否中国表:', state.isChinaSheet);
    console.log('[导出调试] 下载按钮元素:', elements.downloadBtn);
    
    // 转换翻译结果为坐标映射格式（用于Excel/PPT）
    const mappedTranslations = {};
    for (const [key, value] of Object.entries(state.translations)) {
        const numKey = parseInt(key);
        if (state.indexMapping && state.indexMapping[numKey]) {
            // 使用坐标映射
            const coord = state.indexMapping[numKey];
            mappedTranslations[`${coord[0]},${coord[1]},${coord[2]}`] = value;
        } else {
            // 使用原始索引
            mappedTranslations[key] = value;
        }
    }
    console.log('[导出调试] 映射后的翻译:', mappedTranslations);
    
    try {
        const response = await fetch('/api/translate/file', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({
                filename: state.uploadedFile,  // 存储用的文件名（带时间戳）
                original_filename: state.originalFilename,  // 原始文件名
                translations: mappedTranslations,
                mode: elements.outputMode.value,
                is_china_sheet: state.isChinaSheet
            })
        });
        
        const data = await response.json();
        console.log('[导出调试] 响应:', data);
        
        if (data.success) {
            showToast('翻译完成！');
            
            // 启用下载按钮
            if (elements.downloadBtn) {
                console.log('[导出调试] 启用下载按钮, URL:', data.download_url);
                state.downloadUrl = data.download_url; // 保存下载URL
                elements.downloadBtn.style.opacity = '1';
                elements.downloadBtn.style.pointerEvents = 'auto';
                console.log('[导出调试] 下载按钮已启用');
            } else {
                console.error('[导出调试] 下载按钮元素不存在!');
            }
        } else {
            console.error('[导出调试] 导出失败:', data.error);
            showToast('导出失败: ' + data.error);
        }
    } catch (error) {
        console.error('[导出调试] 导出异常:', error);
        showToast('导出失败，请重试');
    }
    console.log('[导出调试] ========== 导出结束 ==========');
    
    // 恢复按钮状态
    elements.translateFileBtn.disabled = false;
    elements.translateFileBtn.textContent = '翻译文件';
    
    // 隐藏加载遮罩
    if (elements.translatingOverlay) {
        elements.translatingOverlay.style.display = 'none';
    }
}

// ========================================
// 工具函数
// ========================================

function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.classList.add('show');
    
    setTimeout(() => {
        elements.toast.classList.remove('show');
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// ========================================
// 用户认证功能
// ========================================

function updateUserUI() {
    if (state.user) {
        elements.userInfo.style.display = 'flex';
        elements.userName.textContent = state.user.username;
        elements.userRole.textContent = state.user.role === 'admin' ? '管理员' : '用户';
        elements.loginBtn.textContent = '退出';
        elements.loginBtn.onclick = logout;

        // 如果是管理员，显示管理入口
        if (state.user.role === 'admin' || state.user.role === 'manager') {
            addAdminMenuItem();
        }
    } else {
        elements.userInfo.style.display = 'none';
        elements.loginBtn.textContent = '登录';
        elements.loginBtn.onclick = showAuthModal;
        removeAdminMenuItem();
    }
}

function addAdminMenuItem() {
    if (document.querySelector('.nav-item[data-view="admin"]')) return;

    const navSection = document.querySelector('.nav-section:last-child');
    const adminBtn = document.createElement('button');
    adminBtn.className = 'nav-item';
    adminBtn.dataset.view = 'admin';
    adminBtn.innerHTML = '<span>用户管理</span>';
    adminBtn.addEventListener('click', () => showAdminModal());
    navSection.appendChild(adminBtn);
}

function removeAdminMenuItem() {
    const adminItem = document.querySelector('.nav-item[data-view="admin"]');
    if (adminItem) adminItem.remove();
}

function showAuthModal(force = false) {
    const modal = document.getElementById('authModal');
    modal.style.display = 'flex';
    document.getElementById('loginError').textContent = '';
    document.getElementById('registerError').textContent = '';
    
    // 如果强制显示（未登录状态），添加强制显示类
    if (force) {
        modal.classList.add('auth-modal-forced');
    }
}

function closeAuthModal() {
    // 如果是强制显示状态（未登录），不允许关闭
    const modal = document.getElementById('authModal');
    if (modal.classList.contains('auth-modal-forced')) {
        return;
    }
    modal.style.display = 'none';
}

function switchAuthTab(tab) {
    document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.auth-tab[data-tab="${tab}"]`).classList.add('active');

    if (tab === 'login') {
        document.getElementById('loginForm').style.display = 'flex';
        document.getElementById('registerForm').style.display = 'none';
    } else {
        document.getElementById('loginForm').style.display = 'none';
        document.getElementById('registerForm').style.display = 'flex';
    }
}

async function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    const errorEl = document.getElementById('loginError');

    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }

    try {
        const response = await fetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        const data = await response.json();

        if (data.success) {
            state.user = data.user;
            localStorage.setItem('user', JSON.stringify(data.user));
            localStorage.setItem('userId', data.user.id);
            updateUserUI();
            // 移除强制显示类，允许关闭
            document.getElementById('authModal').classList.remove('auth-modal-forced');
            closeAuthModal();
            showToast('登录成功');
            // 加载统计数据
            loadStats();
        } else {
            errorEl.textContent = data.message || '登录失败';
        }
    } catch (error) {
        errorEl.textContent = '登录失败，请重试';
    }
}

async function doRegister() {
    const username = document.getElementById('registerUsername').value.trim();
    const password = document.getElementById('registerPassword').value;
    const email = document.getElementById('registerEmail').value.trim();
    const errorEl = document.getElementById('registerError');

    if (!username || !password) {
        errorEl.textContent = '请输入用户名和密码';
        return;
    }

    if (password.length < 6) {
        errorEl.textContent = '密码至少需要6个字符';
        return;
    }

    try {
        const response = await fetch('/api/auth/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password, email })
        });

        const data = await response.json();

        if (data.success) {
            showToast(data.message);
            switchAuthTab('login');
            document.getElementById('loginUsername').value = username;
        } else {
            errorEl.textContent = data.message || '注册失败';
        }
    } catch (error) {
        errorEl.textContent = '注册失败，请重试';
    }
}

function logout() {
    state.user = null;
    localStorage.removeItem('user');
    localStorage.removeItem('userId');
    updateUserUI();
    showToast('已退出登录');
}

// ========================================
// 管理员功能
// ========================================

function showAdminModal() {
    document.getElementById('adminModal').style.display = 'flex';
    loadPendingUsers();
}

function closeAdminModal() {
    document.getElementById('adminModal').style.display = 'none';
}

function switchAdminTab(tab) {
    document.querySelectorAll('.admin-tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`.admin-tab[data-tab="${tab}"]`).classList.add('active');

    if (tab === 'pending') {
        document.getElementById('pendingPanel').style.display = 'block';
        document.getElementById('allUsersPanel').style.display = 'none';
        loadPendingUsers();
    } else {
        document.getElementById('pendingPanel').style.display = 'none';
        document.getElementById('allUsersPanel').style.display = 'block';
        loadAllUsers();
    }
}

async function loadPendingUsers() {
    const container = document.getElementById('pendingList');
    container.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/admin/users/pending', {
            headers: { 'X-User-ID': state.user.id }
        });
        const data = await response.json();

        if (data.success) {
            renderPendingUsers(data.users);
        } else {
            container.innerHTML = `<div class="loading">${data.error || '加载失败'}</div>`;
        }
    } catch (error) {
        container.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderPendingUsers(users) {
    const container = document.getElementById('pendingList');

    if (users.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无待审批用户</p></div>';
        return;
    }

    container.innerHTML = users.map(user => `
        <div class="pending-item">
            <div class="pending-info">
                <span class="pending-username">${escapeHtml(user.username)}</span>
                <span class="pending-email">${escapeHtml(user.email || '无邮箱')}</span>
                <span class="pending-date">注册时间: ${new Date(user.created_at).toLocaleString()}</span>
            </div>
            <div class="pending-actions">
                <button class="btn btn-small btn-primary" onclick="approveUser(${user.id})">通过</button>
                <button class="btn btn-small btn-outline" onclick="rejectUser(${user.id})">拒绝</button>
            </div>
        </div>
    `).join('');
}

async function loadAllUsers() {
    const container = document.getElementById('usersList');
    container.innerHTML = '<div class="loading">加载中...</div>';

    try {
        const response = await fetch('/api/admin/users', {
            headers: { 'X-User-ID': state.user.id }
        });
        const data = await response.json();

        if (data.success) {
            renderAllUsers(data.users);
        } else {
            container.innerHTML = `<div class="loading">${data.error || '加载失败'}</div>`;
        }
    } catch (error) {
        container.innerHTML = '<div class="loading">加载失败</div>';
    }
}

function renderAllUsers(users) {
    const container = document.getElementById('usersList');

    if (users.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>暂无用户</p></div>';
        return;
    }

    const statusMap = {
        'approved': '已通过',
        'pending': '待审批',
        'rejected': '已拒绝',
        'disabled': '已禁用'
    };

    container.innerHTML = users.map(user => `
        <div class="user-item">
            <div class="user-info-row">
                <span class="user-username">${escapeHtml(user.username)}</span>
                <span class="user-email">${escapeHtml(user.email || '无邮箱')}</span>
                <span class="user-status">
                    <span class="user-status-badge ${user.status}">${statusMap[user.status] || user.status}</span>
                    ${user.role === 'admin' ? '<span class="user-status-badge" style="background: var(--accent-color);">管理员</span>' : ''}
                </span>
            </div>
            <div class="user-actions">
                ${user.status === 'pending' ? `
                    <button class="btn btn-small btn-primary" onclick="approveUser(${user.id})">通过</button>
                    <button class="btn btn-small btn-outline" onclick="rejectUser(${user.id})">拒绝</button>
                ` : ''}
                ${user.status === 'approved' && user.role !== 'admin' ? `
                    <button class="btn btn-small btn-outline" onclick="disableUser(${user.id})">禁用</button>
                ` : ''}
            </div>
        </div>
    `).join('');
}

window.approveUser = async function(userId) {
    try {
        const response = await fetch(`/api/admin/users/${userId}/approve`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({})
        });

        const data = await response.json();
        if (data.success) {
            showToast('审批通过');
            loadPendingUsers();
            loadAllUsers();
        } else {
            showToast(data.message || '操作失败');
        }
    } catch (error) {
        showToast('操作失败');
    }
};

window.rejectUser = async function(userId) {
    const reason = prompt('请输入拒绝原因（可选）:');
    if (reason === null) return;

    try {
        const response = await fetch(`/api/admin/users/${userId}/reject`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({ reason })
        });

        const data = await response.json();
        if (data.success) {
            showToast('已拒绝用户');
            loadPendingUsers();
            loadAllUsers();
        } else {
            showToast(data.message || '操作失败');
        }
    } catch (error) {
        showToast('操作失败');
    }
};

window.disableUser = async function(userId) {
    const reason = prompt('请输入禁用原因（可选）:');
    if (reason === null) return;

    try {
        const response = await fetch(`/api/admin/users/${userId}/disable`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-User-ID': state.user.id
            },
            body: JSON.stringify({ reason })
        });

        const data = await response.json();
        if (data.success) {
            showToast('已禁用用户');
            loadAllUsers();
        } else {
            showToast(data.message || '操作失败');
        }
    } catch (error) {
        showToast('操作失败');
    }
};

// ========================================
// 翻译历史记录功能
// ========================================

async function loadTranslationHistory() {
    if (!state.user) return;

    try {
        // 构建查询参数
        const params = new URLSearchParams();
        params.append('page', state.historyPage);
        params.append('limit', state.historyLimit);

        // 添加搜索关键词
        const keyword = document.getElementById('historySearchInput')?.value?.trim();
        if (keyword) {
            params.append('keyword', keyword);
        }

        // 添加用户筛选（管理员）
        const userFilter = document.getElementById('historyUserFilter')?.value;
        if (userFilter) {
            params.append('filter_username', userFilter);
        }

        const response = await fetch(
            `/api/history?${params.toString()}`,
            { headers: getAuthHeaders() }
        );

        const data = await response.json();

        if (data.success) {
            state.historyData = data.data.items;
            state.historyTotal = data.data.total;
            renderHistoryList(data.data);

            // 如果是管理员，加载用户列表
            if (state.user?.role === 'admin') {
                loadUserFilterOptions(data.data.items);
            }
        } else {
            console.error('加载历史记录失败:', data.error);
        }
    } catch (error) {
        console.error('加载历史记录失败:', error);
    }
}

// 加载用户筛选选项（管理员）
function loadUserFilterOptions(items) {
    const userFilter = document.getElementById('historyUserFilter');
    if (!userFilter) return;

    // 显示用户筛选下拉框
    userFilter.style.display = 'inline-block';

    // 提取唯一的用户名列表
    const usernames = [...new Set(items.map(item => item.username))];

    // 保存当前选中值
    const currentValue = userFilter.value;

    // 重建选项
    userFilter.innerHTML = '<option value="">所有用户</option>';
    usernames.forEach(username => {
        const option = document.createElement('option');
        option.value = username;
        option.textContent = username;
        userFilter.appendChild(option);
    });

    // 恢复选中值
    userFilter.value = currentValue;
}

function renderHistoryList(data) {
    const { items, total, page, limit } = data;

    if (items.length === 0) {
        elements.historyList.innerHTML = '<div class="history-empty">暂无翻译记录</div>';
        elements.historyPagination.style.display = 'none';
        return;
    }

    // 文件类型图标映射
    const fileIcons = {
        'docx': '📄',
        'doc': '📄',
        'xlsx': '📊',
        'xls': '📊',
        'xlsm': '📊',
        'pptx': '📽️',
        'pdf': '📕'
    };

    // 状态显示映射
    const statusMap = {
        'completed': { text: '已完成', class: 'completed' },
        'processing': { text: '处理中', class: 'processing' },
        'failed': { text: '失败', class: 'failed' }
    };

    elements.historyList.innerHTML = items.map(item => {
        const icon = fileIcons[item.file_type] || '📄';
        const status = statusMap[item.status] || { text: item.status, class: '' };
        const fileSize = formatFileSize(item.file_size);
        const date = new Date(item.created_at).toLocaleString('zh-CN');
        const modeText = item.mode === 'bilingual' ? '双语' : '译文';

        return `
            <div class="history-item">
                <div class="history-icon ${item.file_type}">${icon}</div>
                <div class="history-content">
                    <div class="history-filename">${escapeHtml(item.original_filename)}</div>
                    <div class="history-summary">${escapeHtml(item.summary || '无摘要')}</div>
                    <div class="history-meta">
                        <span>👤 ${escapeHtml(item.username)}</span>
                        <span>📅 ${date}</span>
                        <span>📦 ${fileSize}</span>
                        <span>📝 ${item.block_count || 0} 块</span>
                        <span>🔤 ${modeText}</span>
                    </div>
                </div>
                <div class="history-status ${status.class}">${status.text}</div>
                <div class="history-actions">
                    ${item.status === 'completed' ? `
                        <button class="btn btn-primary" onclick="downloadHistoryFile('${item.output_filename}')">下载</button>
                    ` : ''}
                    <button class="btn btn-ghost" onclick="deleteHistoryRecord(${item.id})">删除</button>
                </div>
            </div>
        `;
    }).join('');

    // 更新分页
    if (total > limit) {
        elements.historyPagination.style.display = 'flex';
        elements.paginationInfo.textContent = `第 ${page} 页 / 共 ${Math.ceil(total / limit)} 页`;
        elements.historyPrevBtn.disabled = page <= 1;
        elements.historyNextBtn.disabled = page * limit >= total;
    } else {
        elements.historyPagination.style.display = 'none';
    }
}

function formatFileSize(bytes) {
    if (!bytes || bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

window.downloadHistoryFile = async function(filename) {
    try {
        // 直接下载方式，避免blob URL警告
        const downloadUrl = `/api/download/${encodeURIComponent(filename)}`;
        let fullUrl = window.location.origin + downloadUrl;

        // 添加user_id参数用于认证
        fullUrl += `?user_id=${state.user.id}`;

        // 创建隐藏的iframe来下载
        const iframe = document.createElement('iframe');
        iframe.style.display = 'none';
        iframe.src = fullUrl;
        document.body.appendChild(iframe);

        // 3秒后移除iframe
        setTimeout(() => {
            if (iframe.parentNode) {
                document.body.removeChild(iframe);
            }
        }, 3000);

        showToast('开始下载');
    } catch (error) {
        console.error('下载失败:', error);
        showToast('下载失败');
    }
};

window.deleteHistoryRecord = async function(recordId) {
    if (!confirm('确定要删除这条记录吗？文件也将被删除。')) return;

    try {
        const response = await fetch(`/api/history/${recordId}`, {
            method: 'DELETE',
            headers: getAuthHeaders()
        });

        const data = await response.json();

        if (data.success) {
            showToast('记录已删除');
            loadTranslationHistory();
        } else {
            showToast(data.error || '删除失败');
        }
    } catch (error) {
        console.error('删除失败:', error);
        showToast('删除失败');
    }
};

// 启动应用
document.addEventListener('DOMContentLoaded', init);
