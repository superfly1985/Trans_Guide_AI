/**
 * TransGuide Web 应用
 * 极简风格的翻译工具
 */

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
    authToken: localStorage.getItem('authToken') || null
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
    downloadBtn: document.getElementById('downloadBtn'),
    translatingOverlay: document.getElementById('translatingOverlay'),

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
        const response = await fetch('/api/stats');
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
    
    try {
        const response = await fetch('/api/translate/text', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });
        
        const data = await response.json();
        
        if (data.success) {
            elements.targetText.value = data.translation;
            
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
    const formData = new FormData();
    formData.append('file', file);
    
    showToast('正在解析文件...');
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            state.uploadedFile = data.filename;
            state.fileBlocks = data.blocks;
            state.translations = {};
            
            renderFilePreview(data.filename, data.blocks);
            showToast(`成功解析 ${data.total} 个文本块`);
        } else {
            showToast('上传失败: ' + data.error);
        }
    } catch (error) {
        console.error('上传失败:', error);
        showToast('上传失败，请检查网络连接');
    }
}

function renderFilePreview(filename, blocks) {
    elements.filePreview.style.display = 'block';
    elements.previewFilename.textContent = filename.replace(/^\d{8}_\d{6}_/, '');
    
    // 禁用下载按钮
    if (elements.downloadBtn) {
        elements.downloadBtn.style.opacity = '0.5';
        elements.downloadBtn.style.pointerEvents = 'none';
        elements.downloadBtn.href = '#';
    }
    
    // 只显示前15个文本块
    const displayBlocks = blocks.slice(0, 15);
    const hasMore = blocks.length > 15;
    
    elements.previewList.innerHTML = displayBlocks.map(block => `
        <div class="preview-item" data-index="${block.index}">
            <span class="preview-index">${block.index + 1}</span>
            <div class="preview-text">${escapeHtml(block.text)}</div>
            <div class="preview-translation" id="translation-${block.index}">
                <em>等待翻译...</em>
            </div>
        </div>
    `).join('');
    
    if (hasMore) {
        elements.previewList.innerHTML += `
            <div class="preview-item" style="justify-content: center; color: var(--text-tertiary);">
                还有 ${blocks.length - 15} 个文本块...
            </div>
        `;
    }
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
    
    // 按字符数分批，每批最多 60000 字符（预留空间给提示词和响应）
    const MAX_BATCH_SIZE = 60000;
    const batches = createBatches(state.fileBlocks, MAX_BATCH_SIZE);
    console.log('[LLM链路] 批次数量:', batches.length, '各批次大小:', batches.map(b => b.length));
    
    let completed = 0;
    const total = state.fileBlocks.length;
    
    for (let batchIdx = 0; batchIdx < batches.length; batchIdx++) {
        const batch = batches[batchIdx];
        console.log(`[LLM链路] --- 批次 ${batchIdx + 1}/${batches.length} ---`);
        console.log('[LLM链路] 批次文本索引:', batch.map(b => b.index));
        
        try {
            showToast(`翻译批次 ${batchIdx + 1}/${batches.length}...`);
            
            const requestBody = { 
                texts: batch.map(b => ({ index: b.index, text: b.text }))
            };
            console.log('[LLM链路] 请求体大小:', JSON.stringify(requestBody).length, '字符');
            
            console.log('[LLM链路] 发送请求到 /api/translate/batch...');
            const startTime = performance.now();
            const response = await fetch('/api/translate/batch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody)
            });
            const endTime = performance.now();
            const duration = (endTime - startTime) / 1000;
            
            console.log('[LLM链路] 响应状态:', response.status, '耗时:', duration.toFixed(2), '秒');
            const data = await response.json();
            console.log('[LLM链路] 响应 success:', data.success, '翻译数量:', data.translations ? data.translations.length : 0, '耗时:', duration.toFixed(2), '秒');
            
            if (data.success && data.translations) {
                // 更新翻译结果
                for (const trans of data.translations) {
                    state.translations[trans.index] = trans.translation;
                    
                    // 更新预览
                    const transEl = document.getElementById(`translation-${trans.index}`);
                    if (transEl) {
                        transEl.textContent = trans.translation;
                    }
                }
                completed += batch.length;
                console.log('[LLM链路] 批次完成，累计完成:', completed, '/', total);
            } else {
                console.error('[LLM链路] 失败:', data.error);
                // 检查是否是额度用尽的错误
                if (data.quota_exceeded || (data.error && data.error.includes('额度已用尽'))) {
                    showToast('API额度已用尽，请等待5小时后重试');
                    // 中断翻译流程
                    break;
                } else {
                    showToast('翻译失败: ' + (data.error || '未知错误'));
                }
            }
        } catch (error) {
            console.error(`[LLM链路] 批次 ${batchIdx + 1} 异常:`, error);
            showToast(`批次 ${batchIdx + 1} 翻译失败`);
        }
    }
    
    console.log('[LLM链路] ========== 翻译流程结束，总翻译数:', Object.keys(state.translations).length, '==========');
    
    // 导出文件
    try {
        const response = await fetch('/api/translate/file', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                filename: state.uploadedFile,
                filepath: UPLOAD_DIR + '/' + state.uploadedFile,
                translations: state.translations,
                mode: elements.outputMode.value
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('翻译完成！');
            
            // 启用下载按钮
            if (elements.downloadBtn) {
                elements.downloadBtn.style.opacity = '1';
                elements.downloadBtn.style.pointerEvents = 'auto';
                elements.downloadBtn.href = data.download_url;
                elements.downloadBtn.download = state.uploadedFile.replace(/^\d{8}_\d{6}_/, '');
            }
        } else {
            showToast('导出失败: ' + data.error);
        }
    } catch (error) {
        console.error('导出失败:', error);
        showToast('导出失败，请重试');
    } finally {
        elements.translateFileBtn.disabled = false;
        elements.translateFileBtn.textContent = '翻译文件';
        
        // 隐藏加载遮罩
        if (elements.translatingOverlay) {
            elements.translatingOverlay.style.display = 'none';
        }
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

// 启动应用
document.addEventListener('DOMContentLoaded', init);
