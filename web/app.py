"""
TransGuide Web 应用
提供翻译服务的 Web 界面
后端版本: v1.2.0 - 权限系统优化
"""

import os
import sys
import re
import json
import logging
import importlib
from datetime import datetime
from pathlib import Path
from functools import wraps

from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# 版本信息
APP_VERSION = 'v1.2.0'
CSS_VERSION = 'v2.2'
BUILD_TIME = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ========== 检查3: 强制重新加载模块 ==========
# 确保模块更新后能被重新加载
if 'modules.llm_client' in sys.modules:
    importlib.reload(sys.modules['modules.llm_client'])
if 'modules.llm_term_extractor' in sys.modules:
    importlib.reload(sys.modules['modules.llm_term_extractor'])

from modules import file_parser
from modules.term_db import TermDatabase
from modules.tm_db import TMDatabase
from modules.llm_client import LLMClient
from modules import file_exporter
from modules.logger import setup_logger
from modules.user_db import UserDatabase
from modules.bilingual_detector import detect_bilingual_pairs, BilingualDetector
from modules.llm_term_extractor import extract_terms_with_llm, LLMTermExtractor

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# 设置日志
logger = setup_logger('logs/web.log')

# 全局组件
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = BASE_DIR / 'data'
UPLOAD_DIR = BASE_DIR / 'uploads'
OUTPUT_DIR = BASE_DIR / 'output'

# 确保目录存在
DATA_DIR.mkdir(exist_ok=True)
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# 初始化组件
term_db = TermDatabase(str(DATA_DIR / 'terms.db'))
tm_db = TMDatabase(str(DATA_DIR / 'tm.db'))
user_db = UserDatabase(str(DATA_DIR / 'users.db'))


# 全局 LLM 客户端（延迟初始化）
_llm_client = None

def get_llm_client():
    """获取 LLM 客户端（线程安全）"""
    global _llm_client
    if _llm_client is None:
        try:
            logger.info("初始化 LLM 客户端...")
            _llm_client = LLMClient()
            logger.info("LLM 客户端初始化成功")
        except Exception as e:
            logger.error(f"LLM 客户端初始化失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            _llm_client = None
    return _llm_client

# 启动时检查配置
logger.info("=" * 60)
logger.info("检查 LLM 配置...")
config_path = BASE_DIR / 'config.json'
if config_path.exists():
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    api_config = config.get('api', {})
    logger.info(f"config.json 中的 base_url: {api_config.get('base_url', '未设置')}")
    logger.info(f"config.json 中的 model_name: {api_config.get('model_name', '未设置')}")
    logger.info(f"config.json 中的 api_key 存在: {bool(api_config.get('api_key'))}")
logger.info("=" * 60)

# 翻译提示词模板 - 英译中
TRANSLATION_PROMPT = """你是一个专业的技术文档翻译助手。

【翻译要求】
1. 保持原文的格式和结构
2. 使用专业、准确的技术术语
3. 确保翻译流畅自然
4. 保留原文中的数字、符号、单位

【术语约束】
翻译时必须使用以下术语对照：
{terms}

【参考翻译记忆】
{tm_examples}

请翻译以下内容：

{text}

译文："""

# 翻译提示词模板 - 中译英
TRANSLATION_PROMPT_ZH2EN = """你是一个专业的技术文档翻译助手。请将以下中文内容翻译成英文。

【翻译要求】
1. 保持原文的格式和结构
2. 使用专业、准确的技术术语
3. 确保翻译流畅自然，符合英文技术文档表达习惯
4. 保留原文中的数字、符号、单位
5. 使用简洁、专业的英文表达，避免口语化

【术语约束】
翻译时请参考以下术语对照（中文 -> 英文）：
{terms}

【参考翻译记忆】
{tm_examples}

请翻译以下内容：

{text}

English Translation:"""


def allowed_file(filename, allowed_extensions):
    """检查文件是否允许上传"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def login_required(f):
    """登录验证装饰器 - 支持Header或URL参数传递user_id"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 优先从Header获取，其次从URL参数获取
        user_id = request.headers.get('X-User-ID') or request.args.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        user = user_db.get_user_by_id(int(user_id))
        if not user or user['status'] != 'approved':
            return jsonify({'success': False, 'error': '账号未通过审批'}), 403

        return f(*args, **kwargs)
    return decorated_function


def admin_required(f):
    """管理员权限验证装饰器 - 仅管理员可访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        user = user_db.get_user_by_id(int(user_id))
        if not user or user['role'] != 'admin':
            return jsonify({'success': False, 'error': '需要管理员权限'}), 403

        return f(*args, **kwargs)
    return decorated_function


def manager_required(f):
    """主管及以上权限验证装饰器 - 管理员和主管可访问"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录'}), 401

        user = user_db.get_user_by_id(int(user_id))
        if not user or user['role'] not in ['admin', 'manager']:
            return jsonify({'success': False, 'error': '需要主管及以上权限'}), 403

        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """主页面"""
    return render_template('index.html')


# ========== 版本检查接口 ==========
@app.route('/api/version')
def get_version():
    """获取版本信息"""
    return jsonify({
        'success': True,
        'backend': APP_VERSION,
        'css': CSS_VERSION,
        'build_time': BUILD_TIME
    })


# ========== 检查4: 添加简单测试路由 ==========
@app.route('/api/test/llm')
def test_llm():
    """测试 LLM 连接"""
    try:
        logger.info("=" * 60)
        logger.info("收到 LLM 测试请求")
        
        # 检查 LLM 客户端状态
        client = get_llm_client()
        if not client:
            logger.error("LLM 客户端未初始化")
            return jsonify({
                'success': False,
                'error': 'LLM 客户端未初始化',
                'llm_client_exists': False
            })
        
        # 检查可用性
        is_available = client.is_available()
        logger.info(f"LLM is_available(): {is_available}")
        
        # 尝试简单调用
        test_prompt = "Hello, respond with 'OK' only."
        logger.info(f"发送测试提示词: {test_prompt}")
        
        try:
            response = client.generate(test_prompt, max_tokens=10)
            logger.info(f"收到测试响应: {response}")
            return jsonify({
                'success': True,
                'llm_client_exists': True,
                'is_available': is_available,
                'test_response': response,
                'message': 'LLM 连接正常'
            })
        except Exception as e:
            logger.error(f"LLM 测试调用失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return jsonify({
                'success': False,
                'llm_client_exists': True,
                'is_available': is_available,
                'error': str(e),
                'traceback': traceback.format_exc()
            })
    except Exception as e:
        logger.error(f"LLM 测试路由异常: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


@app.route('/api/test/term-extract')
def test_term_extract():
    """测试术语提取功能"""
    try:
        logger.info("=" * 60)
        logger.info("收到术语提取测试请求")
        
        client = get_llm_client()
        if not client:
            return jsonify({
                'success': False,
                'error': 'LLM 客户端未初始化'
            })
        
        # 测试文本
        test_text = """
        Work Instruction 作业指导书
        Process Release 过程放行
        Quality Assurance 质量保证
        Checkpoints 检查点
        Series Production 批量生产
        """
        
        logger.info(f"测试文本: {test_text}")
        logger.info("调用 extract_terms_with_llm...")
        
        # 调用术语提取
        terms = extract_terms_with_llm(test_text, client, max_terms=10)
        
        logger.info(f"提取到 {len(terms)} 个术语")
        for i, term in enumerate(terms):
            logger.info(f"  术语 {i+1}: {term.get('english')} -> {term.get('chinese')}")
        
        return jsonify({
            'success': True,
            'terms_count': len(terms),
            'terms': terms,
            'test_text': test_text
        })
    except Exception as e:
        logger.error(f"术语提取测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        })


# ========================================
# 历史文件导入 API
# ========================================
# 术语库 API
# ========================================

@app.route('/api/terms')
@login_required
def get_terms():
    """获取所有术语"""
    try:
        terms = term_db.get_all_terms_with_details()
        return jsonify({'success': True, 'terms': terms})
    except Exception as e:
        logger.error(f"获取术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/search')
@login_required
def search_terms():
    """搜索术语"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': True, 'terms': []})
        
        terms = term_db.search_terms(query)
        return jsonify({'success': True, 'terms': terms})
    except Exception as e:
        logger.error(f"搜索术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms', methods=['POST'])
@login_required
def add_term():
    """添加新术语"""
    try:
        data = request.json
        source = data.get('source', '').strip()
        target = data.get('target', '').strip()
        category = data.get('category', '').strip()
        tags = data.get('tags', '').strip()
        notes = data.get('notes', '').strip()
        
        if not source or not target:
            return jsonify({'success': False, 'error': '英文术语和中文译法不能为空'})
        
        success = term_db.add_term(source, target, category=category, tags=tags, notes=notes)
        if success:
            return jsonify({'success': True, 'message': '术语添加成功'})
        else:
            return jsonify({'success': False, 'error': '术语添加失败'})
    except Exception as e:
        logger.error(f"添加术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/<source>', methods=['PUT'])
@login_required
def update_term(source):
    """更新术语"""
    try:
        data = request.json
        target = data.get('target')
        category = data.get('category')
        tags = data.get('tags')
        notes = data.get('notes')
        
        success = term_db.update_term(source, target=target, category=category, 
                                       tags=tags, notes=notes)
        if success:
            return jsonify({'success': True, 'message': '术语更新成功'})
        else:
            return jsonify({'success': False, 'error': '术语更新失败'})
    except Exception as e:
        logger.error(f"更新术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/<source>', methods=['DELETE'])
@login_required
def delete_term(source):
    """删除术语"""
    try:
        success = term_db.delete_term(source)
        if success:
            return jsonify({'success': True, 'message': '术语删除成功'})
        else:
            return jsonify({'success': False, 'error': '术语删除失败'})
    except Exception as e:
        logger.error(f"删除术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/categories')
@login_required
def get_term_categories():
    """获取所有分类"""
    try:
        categories = term_db.get_categories()
        return jsonify({'success': True, 'categories': categories})
    except Exception as e:
        logger.error(f"获取分类失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/categories', methods=['POST'])
@login_required
def add_term_category():
    """添加分类"""
    try:
        data = request.json
        name = data.get('name', '').strip()
        description = data.get('description', '').strip()
        
        if not name:
            return jsonify({'success': False, 'error': '分类名称不能为空'})
        
        success = term_db.add_category(name, description)
        if success:
            return jsonify({'success': True, 'message': '分类添加成功'})
        else:
            return jsonify({'success': False, 'error': '分类已存在或添加失败'})
    except Exception as e:
        logger.error(f"添加分类失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/categories/<name>', methods=['DELETE'])
@login_required
def delete_term_category(name):
    """删除分类"""
    try:
        success = term_db.delete_category(name)
        if success:
            return jsonify({'success': True, 'message': '分类删除成功'})
        else:
            return jsonify({'success': False, 'error': '分类删除失败'})
    except Exception as e:
        logger.error(f"删除分类失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/terms/export')
@login_required
def export_terms():
    """导出术语到CSV"""
    try:
        category = request.args.get('category')
        import tempfile
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', 
                                         delete=False, encoding='utf-8') as f:
            temp_path = f.name
        
        success = term_db.export_to_csv(temp_path, category)
        if success:
            return send_file(temp_path, as_attachment=True, 
                           download_name=f'terms_{datetime.now().strftime("%Y%m%d")}.csv')
        else:
            return jsonify({'success': False, 'error': '导出失败'})
    except Exception as e:
        logger.error(f"导出术语失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 用户认证 API
# ========================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        email = data.get('email', '').strip()

        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码不能为空'})

        # 空邮箱转为None，避免唯一性冲突
        email = email if email else None

        result = user_db.register(username, password, email)
        return jsonify(result)
    except Exception as e:
        logger.error(f"注册失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录"""
    try:
        data = request.json
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()

        if not username or not password:
            return jsonify({'success': False, 'error': '用户名和密码不能为空'})

        # 获取客户端信息
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')

        result = user_db.login(username, password, ip_address, user_agent)
        return jsonify(result)
    except Exception as e:
        logger.error(f"登录失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/user')
def get_current_user():
    """获取当前登录用户信息"""
    try:
        user_id = request.headers.get('X-User-ID')
        if not user_id:
            return jsonify({'success': False, 'error': '未登录'})

        user = user_db.get_user_by_id(int(user_id))
        if not user:
            return jsonify({'success': False, 'error': '用户不存在'})

        return jsonify({'success': True, 'user': user})
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/auth/refresh', methods=['POST'])
def refresh_auth():
    """通过refresh_token自动登录"""
    try:
        data = request.json
        refresh_token = data.get('refresh_token', '').strip()

        if not refresh_token:
            return jsonify({'success': False, 'error': '缺少refresh_token'})

        user = user_db.refresh_token_login(refresh_token)
        if not user:
            return jsonify({'success': False, 'error': '登录已过期，请重新登录'})

        return jsonify({'success': True, 'user': user, 'message': '自动登录成功'})
    except Exception as e:
        logger.error(f"刷新登录失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/user/settings', methods=['PUT'])
@login_required
def update_user_settings():
    """用户修改个人设置（邮箱和密码）"""
    try:
        user_id = int(request.headers.get('X-User-ID'))
        data = request.json

        if not data:
            return jsonify({'success': False, 'error': '请求数据不能为空'})

        old_password = (data.get('old_password') or '').strip()
        new_email = (data.get('new_email') or '').strip() or None
        new_password = (data.get('new_password') or '').strip() or None

        # 验证参数
        if not old_password:
            return jsonify({'success': False, 'error': '请输入当前密码'})

        if new_password and len(new_password) < 6:
            return jsonify({'success': False, 'error': '新密码至少需要6个字符'})

        # 调用数据库方法
        result = user_db.update_user_settings(
            user_id=user_id,
            old_password=old_password,
            new_email=new_email,
            new_password=new_password
        )

        if result['success']:
            logger.info(f"用户 {user_id} 更新了个人设置")
            return jsonify({'success': True, 'message': result['message']})
        else:
            return jsonify({'success': False, 'error': result['message']})

    except Exception as e:
        logger.error(f"更新用户设置失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 翻译历史记录辅助函数
# ========================================

def generate_output_filename(original_name: str, mode: str, user_id: int) -> str:
    """
    生成简洁的输出文件名
    格式: 原文件名_YYYYMMDD_NN.xxx 或 原文件名_YYYYMMDD_NNT.xxx (仅译文)
    """
    from datetime import datetime

    stem = Path(original_name).stem
    suffix = Path(original_name).suffix

    # 清理原文件名（只去除危险字符，保留点和连字符）
    stem = re.sub(r'[<>:"/\\|?*]', '_', stem)[:40]  # 只保留40字符，保留点和连字符

    date_str = datetime.now().strftime('%Y%m%d')

    # 查询当天该用户已有多少个文件
    count = user_db.get_user_today_file_count(user_id, date_str)
    seq = f"{count + 1:02d}"

    mode_suffix = "T" if mode == "target_only" else ""

    return f"{stem}_{date_str}_{seq}{mode_suffix}{suffix}"


def extract_summary(blocks: list, translations: dict = None, max_chars: int = 50) -> str:
    """
    提取文本摘要，优先使用中文翻译内容
    1. 优先从翻译后的内容中提取中文标题
    2. 如果没有翻译，则从原文中提取
    """
    texts = []

    # 如果有翻译，优先使用翻译后的中文内容
    if translations:
        for block in blocks:
            idx = block.get('index')
            if idx in translations:
                # 使用翻译后的内容
                translated_text = translations[idx]
                if translated_text:
                    texts.append(translated_text)
            else:
                # 没有翻译的使用原文
                text = block.get('text', '')
                if text:
                    texts.append(text)
    else:
        # 没有翻译，使用原文
        texts = [b.get('text', '') for b in blocks if b.get('text')]

    # 合并文本
    full_text = ' '.join(texts)

    # 去除多余空格，取前 N 个字符
    summary = ' '.join(full_text.split())[:max_chars]

    # 如果截断了，加省略号
    if len(full_text) > max_chars:
        summary += '...'

    return summary


@app.route('/api/auth/password', methods=['PUT'])
@login_required
def change_password():
    """修改密码"""
    try:
        user_id = int(request.headers.get('X-User-ID'))
        data = request.json
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')

        if not old_password or not new_password:
            return jsonify({'success': False, 'error': '原密码和新密码不能为空'})

        result = user_db.change_password(user_id, old_password, new_password)
        return jsonify(result)
    except Exception as e:
        logger.error(f"修改密码失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 用户管理 API (管理员)
# ========================================

@app.route('/api/admin/users/pending')
@admin_required
def get_pending_users():
    """获取待审批用户列表"""
    try:
        users = user_db.get_pending_users()
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"获取待审批用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users')
@admin_required
def get_all_users():
    """获取所有用户列表"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        users = user_db.get_all_users(admin_id)
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f"获取用户列表失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>/approve', methods=['POST'])
@admin_required
def approve_user(user_id):
    """审批通过用户"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        data = request.json or {}
        reason = data.get('reason', '')

        result = user_db.approve_user(user_id, admin_id, reason)
        return jsonify(result)
    except Exception as e:
        logger.error(f"审批用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>/reject', methods=['POST'])
@admin_required
def reject_user(user_id):
    """拒绝用户"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        data = request.json or {}
        reason = data.get('reason', '')

        result = user_db.reject_user(user_id, admin_id, reason)
        return jsonify(result)
    except Exception as e:
        logger.error(f"拒绝用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>/disable', methods=['POST'])
@admin_required
def disable_user(user_id):
    """禁用用户"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        data = request.json or {}
        reason = data.get('reason', '')

        result = user_db.disable_user(user_id, admin_id, reason)
        return jsonify(result)
    except Exception as e:
        logger.error(f"禁用用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@admin_required
def reset_user_password(user_id):
    """重置用户密码"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        data = request.json
        new_password = data.get('new_password', '')

        if not new_password or len(new_password) < 6:
            return jsonify({'success': False, 'error': '新密码至少需要6个字符'})

        result = user_db.reset_password(user_id, admin_id, new_password)
        return jsonify(result)
    except Exception as e:
        logger.error(f"重置密码失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>', methods=['PUT'])
@admin_required
def update_user(user_id):
    """编辑用户信息"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        data = request.json

        email = data.get('email', '').strip()
        role = data.get('role', '').strip()
        password = data.get('password', '').strip()

        # 空邮箱转为None，避免唯一性冲突
        email = email if email else None

        # 验证角色
        if role not in ['user', 'manager', 'admin']:
            return jsonify({'success': False, 'error': '无效的角色'})

        # 更新用户信息
        result = user_db.update_user(user_id, admin_id, email=email, role=role, password=password)
        return jsonify(result)
    except Exception as e:
        logger.error(f"更新用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/users/<int:user_id>/enable', methods=['POST'])
@admin_required
def enable_user(user_id):
    """启用用户"""
    try:
        admin_id = int(request.headers.get('X-User-ID'))
        result = user_db.enable_user(user_id, admin_id)
        return jsonify(result)
    except Exception as e:
        logger.error(f"启用用户失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/stats')
@login_required
def get_stats():
    """获取统计数据"""
    try:
        # 获取术语数量
        terms = term_db.get_all_terms()
        terms_count = len(terms)

        # 获取翻译记忆统计
        tm_stats = tm_db.get_stats()

        return jsonify({
            'success': True,
            'stats': {
                'terms_count': terms_count,
                'tm_count': tm_stats.get('total_segments', 0),
                'duplicates': tm_stats.get('duplicate_segments', 0),
                'source_files': tm_stats.get('source_files', 0)
            }
        })
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 管理员统计 API
# ========================================

@app.route('/api/admin/stats/overview')
@manager_required
def get_admin_stats_overview():
    """获取管理员统计概览"""
    try:
        # 获取系统概览
        overview = user_db.get_system_overview()

        # 获取术语统计
        terms = term_db.get_all_terms()
        terms_count = len(terms)
        term_stats = term_db.get_stats()

        # 获取LLM统计
        llm_stats = user_db.get_llm_usage_stats(days=30)

        # 获取翻译记忆统计
        tm_stats = tm_db.get_stats()

        return jsonify({
            'success': True,
            'data': {
                'users': {
                    'total': overview['users']['total'],
                    'new_today': overview['users']['new_today'],
                    'active_7d': overview['users']['active_7d'],
                    'active_30d': overview['users']['active_30d'],
                    'pending': overview['users']['pending']
                },
                'files': {
                    'total': overview['files']['total'],
                    'today': overview['files']['today'],
                    'this_month': overview['files']['this_month']
                },
                'terms': {
                    'total': terms_count,
                    'categories': term_stats.get('category_count', 0)
                },
                'llm': {
                    'total_calls': llm_stats['total_calls'],
                    'today_calls': llm_stats['today_calls'],
                    'total_tokens': llm_stats['total_tokens'],
                    'avg_response_time': llm_stats['avg_response_time'],
                    'error_rate': llm_stats['error_rate']
                },
                'tm': {
                    'total': tm_stats.get('total', 0),
                    'source_files': tm_stats.get('source_files', 0)
                }
            }
        })
    except Exception as e:
        logger.error(f"获取统计概览失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/stats/trend')
@manager_required
def get_admin_stats_trend():
    """获取趋势数据"""
    try:
        days = request.args.get('days', 30, type=int)
        metrics = request.args.getlist('metrics') or ['files', 'llm_calls']

        result = {
            'dates': [],
            'series': []
        }

        # 获取日期列表
        conn = user_db._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT date(created_at) as date
            FROM translation_history
            WHERE created_at >= date('now', '-{} days')
            ORDER BY date
        """.format(days))
        dates = [row[0] for row in cursor.fetchall()]
        result['dates'] = dates

        # 文件统计趋势
        if 'files' in metrics:
            cursor.execute("""
                SELECT date(created_at) as date, COUNT(*) as count
                FROM translation_history
                WHERE created_at >= date('now', '-{} days')
                GROUP BY date(created_at)
                ORDER BY date
            """.format(days))
            file_data = {row[0]: row[1] for row in cursor.fetchall()}
            result['series'].append({
                'name': '翻译文件数',
                'data': [file_data.get(d, 0) for d in dates]
            })

        # LLM调用趋势
        if 'llm_calls' in metrics:
            cursor.execute("""
                SELECT date(created_at) as date, COUNT(*) as count
                FROM llm_usage
                WHERE created_at >= date('now', '-{} days')
                GROUP BY date(created_at)
                ORDER BY date
            """.format(days))
            llm_data = {row[0]: row[1] for row in cursor.fetchall()}
            result['series'].append({
                'name': 'LLM调用',
                'data': [llm_data.get(d, 0) for d in dates]
            })

        conn.close()

        return jsonify({'success': True, 'data': result})
    except Exception as e:
        logger.error(f"获取趋势数据失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/admin/stats/detail')
@manager_required
def get_admin_stats_detail():
    """获取详细统计数据"""
    try:
        stat_type = request.args.get('type', 'users')
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)

        if stat_type == 'users':
            # 获取用户活跃度排行
            conn = user_db._get_connection()
            cursor = conn.cursor()

            # 总数
            cursor.execute("SELECT COUNT(*) FROM users")
            total = cursor.fetchone()[0]

            # 用户列表及统计
            cursor.execute("""
                SELECT
                    u.id,
                    u.username,
                    u.email,
                    u.role,
                    u.status,
                    u.created_at,
                    u.last_login,
                    COUNT(h.id) as file_count
                FROM users u
                LEFT JOIN translation_history h ON u.id = h.user_id
                GROUP BY u.id
                ORDER BY file_count DESC
                LIMIT ? OFFSET ?
            """, (limit, (page - 1) * limit))

            items = []
            for row in cursor.fetchall():
                items.append({
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'role': row[3],
                    'status': row[4],
                    'created_at': row[5],
                    'last_login': row[6],
                    'file_count': row[7]
                })

            conn.close()

            return jsonify({
                'success': True,
                'data': {
                    'total': total,
                    'page': page,
                    'limit': limit,
                    'items': items
                }
            })

        elif stat_type == 'files':
            # 获取翻译历史
            result = user_db.get_translation_history(page=page, limit=limit)
            return jsonify({'success': True, 'data': result})

        elif stat_type == 'llm':
            # 获取LLM使用详情
            conn = user_db._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM llm_usage")
            total = cursor.fetchone()[0]

            cursor.execute("""
                SELECT
                    l.id,
                    l.user_id,
                    u.username,
                    l.operation_type,
                    l.model_name,
                    l.total_tokens,
                    l.response_time_ms,
                    l.status,
                    l.created_at
                FROM llm_usage l
                LEFT JOIN users u ON l.user_id = u.id
                ORDER BY l.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, (page - 1) * limit))

            items = []
            for row in cursor.fetchall():
                items.append({
                    'id': row[0],
                    'user_id': row[1],
                    'username': row[2],
                    'operation_type': row[3],
                    'model_name': row[4],
                    'total_tokens': row[5],
                    'response_time_ms': row[6],
                    'status': row[7],
                    'created_at': row[8]
                })

            conn.close()

            return jsonify({
                'success': True,
                'data': {
                    'total': total,
                    'page': page,
                    'limit': limit,
                    'items': items
                }
            })

        else:
            return jsonify({'success': False, 'error': '未知的统计类型'})

    except Exception as e:
        logger.error(f"获取详细统计失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 翻译记忆 API
# ========================================
# 历史文件导入 API
# ========================================

@app.route('/api/import/upload', methods=['POST'])
@login_required
def upload_import_file():
    """上传历史翻译文件进行分析"""
    # ========== 检查1: 添加详细日志确认执行路径 ==========
    print("=" * 60, flush=True)
    print("【UPLOAD】收到文件上传请求", flush=True)
    logger.info("=" * 60)
    logger.info("【检查1】收到文件上传请求")
    
    try:
        if 'file' not in request.files:
            logger.error("请求中没有文件")
            return jsonify({'success': False, 'error': '没有文件'})
        
        file = request.files['file']
        if file.filename == '':
            logger.error("文件名为空")
            return jsonify({'success': False, 'error': '文件名为空'})
        
        # 保存文件
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = UPLOAD_DIR / filename
        file.save(str(filepath))
        
        logger.info(f"上传历史文件: {filepath}")
        
        # 解析文件
        try:
            blocks, format_info = file_parser.parse_file(str(filepath))
            logger.info(f"文件解析成功，共 {len(blocks)} 个文本块")
        except ValueError as e:
            logger.error(f"文件解析失败: {e}")
            return jsonify({'success': False, 'error': str(e)})
        
        if not blocks:
            logger.error("文件为空或无法解析")
            return jsonify({'success': False, 'error': '无法解析文件或文件为空'})
        
        # 使用智能双语对检测器（仅用于参考，不用于术语提取）
        pairs, analysis = detect_bilingual_pairs(blocks, None)
        
        logger.info(f"文档分析: {analysis}")
        
        # 使用 LLM 提取专业术语
        llm_terms = []
        client = get_llm_client()
        llm_available = client is not None and client.is_available()
        print(f"[DEBUG] LLM 可用性检查: {llm_available}", flush=True)
        logger.info(f"LLM 可用性检查: {llm_available}")
        
        if llm_available:
            print("[DEBUG] 使用 LLM 提取术语...", flush=True)
            logger.info("使用 LLM 提取术语...")
            # 合并所有文本内容
            full_text = '\n'.join([block['text'] for block in blocks if len(block['text'].strip()) > 5])
            print(f"[DEBUG] 准备发送给 LLM 的文本长度: {len(full_text)} 字符", flush=True)
            logger.info(f"准备发送给 LLM 的文本长度: {len(full_text)} 字符")
            
            try:
                print(f"[DEBUG] 调用 extract_terms_with_llm...", flush=True)
                llm_terms = extract_terms_with_llm(full_text, client, max_terms=15)
                print(f"[DEBUG] LLM 提取到 {len(llm_terms)} 个术语", flush=True)
                logger.info(f"LLM 提取到 {len(llm_terms)} 个术语")
            except Exception as e:
                print(f"[DEBUG] LLM 术语提取失败: {e}", flush=True)
                logger.error(f"LLM 术语提取失败: {e}")
                import traceback
                traceback.print_exc()
                logger.error(traceback.format_exc())
        else:
            print("[DEBUG] LLM 不可用，无法提取术语", flush=True)
            logger.warning("LLM 不可用，无法提取术语")
        
        # 如果没有检测到内容，给出提示
        detection_message = ""
        if len(llm_terms) == 0 and len(pairs) == 0:
            detection_message = "未检测到有效内容。请确保文件包含英文和中文对照内容。"
        elif len(llm_terms) == 0:
            detection_message = "未提取到术语，但检测到双语对。"
        
        return jsonify({
            'success': True,
            'filename': filename,
            'filepath': str(filepath),
            'pairs': pairs[:20],
            'total_pairs': len(pairs),
            'potential_terms': llm_terms[:30],
            'total_terms': len(llm_terms),
            'analysis': analysis,
            'message': detection_message,
            'llm_used': client is not None and client.is_available()
        })
        
    except Exception as e:
        logger.error(f"上传历史文件失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/import/process', methods=['POST'])
@login_required
def process_import():
    """处理导入，将术语和翻译记忆存入数据库"""
    try:
        data = request.json
        filename = data.get('filename')
        filepath = data.get('filepath')
        selected_pairs = data.get('pairs', [])
        selected_terms = data.get('terms', [])
        
        if not filepath or not os.path.exists(filepath):
            return jsonify({'success': False, 'error': '文件不存在'})
        
        # 如果没有提供选择的数据，重新解析
        if not selected_pairs:
            blocks, _ = file_parser.parse_file(filepath)
            pairs = []
            for i in range(0, len(blocks) - 1, 2):
                en_block = blocks[i]
                next_block = blocks[i + 1] if i + 1 < len(blocks) else None
                
                en_text = en_block['text'].strip()
                zh_text = next_block['text'].strip() if next_block else ''
                
                en_chars = len(re.findall(r'[a-zA-Z]', en_text))
                zh_chars = len(re.findall(r'[\u4e00-\u9fff]', zh_text))
                
                if en_chars > 5 and zh_chars > 2:
                    pairs.append({
                        'source': en_text,
                        'target': zh_text
                    })
            selected_pairs = pairs
        
        # 导入用户选择的术语（从 LLM 提取的术语列表）
        imported_terms = 0
        if selected_terms:
            for term in selected_terms:
                english = term.get('english', '').strip()
                chinese = term.get('chinese', '').strip()
                category = term.get('category', '').strip() or '未分类'
                
                if english and chinese:
                    success = term_db.add_term(
                        english, 
                        chinese, 
                        category=category,
                        notes=f"从 {filename} 提取"
                    )
                    if success:
                        imported_terms += 1
        
        # 可选：导入翻译记忆（句段对）
        imported_segments = 0
        if selected_pairs:
            segments = [(pair['source'], pair['target']) for pair in selected_pairs[:50]]
            tm_stats = tm_db.add_segments_batch(segments, filename)
            imported_segments = tm_stats.get('added', 0) + tm_stats.get('updated', 0)
        
        logger.info(f"导入完成: {imported_terms} 术语, {imported_segments} 句段")
        
        return jsonify({
            'success': True,
            'imported_terms': imported_terms,
            'imported_segments': imported_segments
        })
        
    except Exception as e:
        logger.error(f"处理导入失败: {e}")
        return jsonify({'success': False, 'error': str(e)})




@app.route('/api/memory')
@login_required
def get_memory():
    """获取翻译记忆"""
    try:
        # 获取最近的翻译记忆
        try:
            import sqlite3
            conn = sqlite3.connect(str(DATA_DIR / 'tm.db'))
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, original, translation, created_at FROM translation_memory ORDER BY created_at DESC LIMIT 100"
            )
            rows = cursor.fetchall()
            conn.close()
            
            memory_list = [
                {'id': row[0], 'source': row[1], 'target': row[2], 'created_at': row[3]}
                for row in rows
            ]
        except Exception as e:
            logger.error(f"查询翻译记忆失败: {e}")
            memory_list = []
        
        return jsonify({'success': True, 'memory': memory_list})
    except Exception as e:
        logger.error(f"获取翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/search')
@login_required
def search_memory():
    """搜索翻译记忆"""
    try:
        query = request.args.get('q', '')
        if not query:
            return jsonify({'success': True, 'memory': []})
        
        # 使用向量搜索
        results = tm_db.search_similar(query, top_k=20)
        return jsonify({'success': True, 'memory': results})
    except Exception as e:
        logger.error(f"搜索翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/duplicates')
@login_required
def get_duplicate_memory():
    """获取重复句段"""
    try:
        duplicates = tm_db.find_duplicates(threshold=0.95)
        return jsonify({'success': True, 'duplicates': duplicates})
    except Exception as e:
        logger.error(f"获取重复句段失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/duplicates/merge', methods=['POST'])
@login_required
def merge_duplicates():
    """合并重复句段"""
    try:
        data = request.json
        keep_id = data.get('keep_id')
        remove_ids = data.get('remove_ids', [])
        
        if not keep_id or not remove_ids:
            return jsonify({'success': False, 'error': '参数不完整'})
        
        tm_db.merge_duplicates(keep_id, remove_ids)
        return jsonify({'success': True, 'message': '合并成功'})
    except Exception as e:
        logger.error(f"合并重复句段失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/cleanup', methods=['POST'])
@login_required
def cleanup_memory():
    """清理低质量句段"""
    try:
        deleted = tm_db.cleanup_low_quality(min_length=10, max_length=1000)
        return jsonify({'success': True, 'deleted': deleted})
    except Exception as e:
        logger.error(f"清理翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/add', methods=['POST'])
@login_required
def add_memory():
    """手动添加翻译记忆"""
    try:
        data = request.json
        original = data.get('original', '').strip()
        translation = data.get('translation', '').strip()

        if not original or not translation:
            return jsonify({'success': False, 'error': '原文和译文不能为空'})

        # 添加到翻译记忆库，来源标记为 Manual_Input
        success, status = tm_db.add_segment(original, translation, 'Manual_Input')
        if success:
            return jsonify({'success': True, 'message': status})
        else:
            return jsonify({'success': False, 'error': status})
    except Exception as e:
        logger.error(f"添加翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/<int:memory_id>', methods=['PUT'])
@login_required
def update_memory(memory_id):
    """更新翻译记忆"""
    try:
        # 检查权限（只允许admin和manager编辑）
        user_id = request.headers.get('X-User-ID')
        user = user_db.get_user_by_id(int(user_id))
        if not user or user['role'] not in ['admin', 'manager']:
            return jsonify({'success': False, 'error': '权限不足'}), 403
        
        data = request.json
        source = data.get('source', '').strip()
        target = data.get('target', '').strip()
        
        if not source or not target:
            return jsonify({'success': False, 'error': '原文和译文不能为空'})
        
        import sqlite3
        conn = sqlite3.connect(str(DATA_DIR / 'tm.db'))
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE translation_memory SET original = ?, translation = ?, updated_at = ? WHERE id = ?",
            (source, target, datetime.now(), memory_id)
        )
        conn.commit()
        updated = cursor.rowcount
        conn.close()
        
        if updated > 0:
            return jsonify({'success': True, 'message': '更新成功'})
        else:
            return jsonify({'success': False, 'error': '记忆不存在'})
    except Exception as e:
        logger.error(f"更新翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/memory/<int:memory_id>', methods=['DELETE'])
@login_required
def delete_memory(memory_id):
    """删除翻译记忆"""
    try:
        # 检查权限（只允许admin和manager删除）
        user_id = request.headers.get('X-User-ID')
        user = user_db.get_user_by_id(int(user_id))
        if not user or user['role'] not in ['admin', 'manager']:
            return jsonify({'success': False, 'error': '权限不足'}), 403
        
        import sqlite3
        conn = sqlite3.connect(str(DATA_DIR / 'tm.db'))
        cursor = conn.cursor()
        cursor.execute("DELETE FROM translation_memory WHERE id = ?", (memory_id,))
        conn.commit()
        deleted = cursor.rowcount
        conn.close()
        
        if deleted > 0:
            return jsonify({'success': True, 'message': '删除成功'})
        else:
            return jsonify({'success': False, 'error': '记忆不存在'})
    except Exception as e:
        logger.error(f"删除翻译记忆失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 翻译 API
# ========================================

@app.route('/api/translate/text', methods=['POST'])
@login_required
def translate_text():
    """翻译文本"""
    try:
        data = request.json
        text = data.get('text', '').strip()
        direction = data.get('direction', 'en2zh')  # 翻译方向：en2zh 或 zh2en
        
        if not text:
            return jsonify({'success': True, 'translation': '', 'source': 'empty'})
        
        # 根据翻译方向检查输入语言
        if direction == 'zh2en':
            # 中译英：检查是否包含足够的中文字符
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
            if chinese_chars < 2:
                return jsonify({
                    'success': True,
                    'translation': text,
                    'source': 'non_chinese'
                })
        else:
            # 英译中（默认）：检查是否包含足够的英文字符
            english_chars = len(re.findall(r'[a-zA-Z]', text))
            if english_chars < 5:
                return jsonify({
                    'success': True,
                    'translation': text,
                    'source': 'non_english'
                })
        
        # 检索术语（根据方向调整匹配逻辑，使用上下文推断）
        from modules.context_resolver import ContextResolver
        all_terms = term_db.get_all_terms()
        if direction == 'zh2en':
            # 中译英：匹配中文术语，返回英文
            matched_terms = {zh: en for en, zh in all_terms.items()
                            if zh in text}
        else:
            # 英译中：匹配英文术语，使用上下文推断选择最合适的译词
            matched_terms = {}
            for en, zh in all_terms.items():
                if en.lower() in text.lower():
                    # 如果有多个译词（用 | 分隔），根据上下文选择
                    if '|' in zh:
                        translations = zh.split('|')
                        best_translation = ContextResolver.resolve(en, translations, text)
                        matched_terms[en] = best_translation
                    else:
                        matched_terms[en] = zh
        
        # 检索TM
        tm_matches = tm_db.search_similar(text, top_k=1)
        if tm_matches and tm_matches[0].get('similarity', 0) >= 0.85:
            return jsonify({
                'success': True,
                'translation': tm_matches[0]['translation'],
                'terms_used': matched_terms,
                'source': 'tm',
                'similarity': tm_matches[0].get('similarity', 0)
            })
        
        # LLM翻译
        client = get_llm_client()
        if not client:
            return jsonify({
                'success': False,
                'error': 'LLM 未配置，无法翻译'
            })
        
        terms_str = "\n".join([f"  - {k} -> {v}" for k, v in matched_terms.items()]) if matched_terms else "无"
        tm_examples_str = ""
        if tm_matches:
            tm_examples_str = f"原文: {tm_matches[0]['source']}\n译文: {tm_matches[0]['translation']}"
        else:
            tm_examples_str = "无"
        
        # 根据方向选择提示词模板
        if direction == 'zh2en':
            prompt = TRANSLATION_PROMPT_ZH2EN.format(
                text=text,
                terms=terms_str,
                tm_examples=tm_examples_str
            )
        else:
            prompt = TRANSLATION_PROMPT.format(
                text=text,
                terms=terms_str,
                tm_examples=tm_examples_str
            )
        
        response = client.generate(prompt)
        
        # 清理响应
        translation = re.sub(r'</think>.*?</think>', '', response, flags=re.DOTALL).strip()
        translation = translation.replace('译文：', '').replace('译文:', '').strip()
        
        return jsonify({
            'success': True,
            'translation': translation,
            'terms_used': matched_terms,
            'source': 'llm'
        })
        
    except Exception as e:
        logger.error(f"翻译失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/translate/batch', methods=['POST'])
@login_required
def translate_batch():
    """批量翻译文本"""
    try:
        data = request.json
        texts = data.get('texts', [])
        start_index = data.get('start_index', 0)  # 新增：起始索引偏移
        direction = data.get('direction', 'en2zh')  # 翻译方向：en2zh 或 zh2en
        file_type = data.get('file_type', '')  # 文件类型，用于预设领域

        logger.info(f"收到批量翻译请求，文本数量: {len(texts)}, 起始索引: {start_index}, 方向: {direction}, 文件类型: {file_type}")
        
        if not texts:
            return jsonify({'success': False, 'error': '没有文本需要翻译'})
        
        # 构建批量翻译提示词
        batch_text = []
        for item in texts:
            idx = item.get('index', 0)
            text = item.get('text', '')
            batch_text.append(f"[BLOCK_{idx}]\n{text}")
        
        combined_text = '\n\n---\n\n'.join(batch_text)
        logger.info(f"合并文本长度: {len(combined_text)} 字符")
        
        # 检索术语（使用上下文推断选择最合适的译词）
        from modules.context_resolver import ContextResolver

        # 根据文件类型预设领域上下文
        domain_hint = None
        if file_type in ['xlsx', 'xls', 'xlsm']:
            domain_hint = 'excel'
        elif file_type in ['docx', 'doc']:
            # 文档类型需要更多上下文判断，暂不预设
            domain_hint = None

        # 合并所有文本用于领域推断
        combined_context_for_domain = ' '.join([item.get('text', '') for item in texts])
        if domain_hint:
            combined_context_for_domain = f"{domain_hint} {combined_context_for_domain}"

        all_terms = term_db.get_all_terms()
        matched_terms = {}
        for item in texts:
            text = item.get('text', '')
            for en, zh in all_terms.items():
                if en.lower() in text.lower():
                    # 如果有多个译词（用 | 分隔），根据上下文选择
                    if '|' in zh:
                        translations = zh.split('|')
                        # 使用合并的上下文（包含文件类型预设）进行推断
                        best_translation = ContextResolver.resolve(en, translations, combined_context_for_domain)
                        matched_terms[en] = best_translation
                    else:
                        matched_terms[en] = zh

        logger.info(f"匹配术语数量: {len(matched_terms)}")
        
        # LLM翻译
        client = get_llm_client()
        logger.info(f"LLM 客户端: {client}")
        if not client:
            return jsonify({'success': False, 'error': 'LLM 未配置，无法翻译'})
        
        terms_str = "\n".join([f"  - {k} -> {v}" for k, v in matched_terms.items()]) if matched_terms else "无"
        
        # 根据翻译方向构建不同的提示词
        if direction == 'zh2en':
            # 中译英
            prompt = f"""你是一个专业的技术文档翻译助手。请将中文翻译成英文。

【翻译要求】
1. 保持原文的格式和结构
2. 使用专业、准确的技术术语
3. 确保翻译流畅自然，符合英文技术文档表达习惯
4. 保留原文中的数字、符号、单位
5. 使用简洁、专业的英文表达，避免口语化

【术语约束】
翻译时请参考以下术语对照（中文 -> 英文）：
{terms_str}

【待翻译文本】
以下文本按 [BLOCK_X] 标记分隔，请保持标记不变，只翻译标记后的内容：

{combined_text}

【输出格式】
请**严格按照以下格式**返回翻译结果，**每个 [BLOCK_X] 必须单独一行，不能合并多个块**：

[BLOCK_0]
English translation 0

[BLOCK_1]
English translation 1

[BLOCK_2]
English translation 2

**重要规则：**
1. 每个 [BLOCK_X] 标记必须单独一行
2. 不要合并多个块（如 [BLOCK_9-BLOCK_26] 是错误的）
3. 必须翻译所有块，不能跳过任何块
4. 保持 [BLOCK_X] 标记不变，只翻译标记后的内容
5. 输出必须是英文，不要包含中文原文
"""
        else:
            # 英译中（默认）
            prompt = f"""你是一个专业的技术文档翻译助手。

【翻译要求】
1. 保持原文的格式和结构
2. 使用专业、准确的技术术语
3. 确保翻译流畅自然
4. 保留原文中的数字、符号、单位

【术语约束】
翻译时必须使用以下术语对照：
{terms_str}

【待翻译文本】
以下文本按 [BLOCK_X] 标记分隔，请保持标记不变，只翻译标记后的内容：

{combined_text}

【输出格式】
请**严格按照以下格式**返回翻译结果，**每个 [BLOCK_X] 必须单独一行，不能合并多个块**：

[BLOCK_0]
翻译后的内容0

[BLOCK_1]
翻译后的内容1

[BLOCK_2]
翻译后的内容2

**重要规则：**
1. 每个 [BLOCK_X] 标记必须单独一行
2. 不要合并多个块（如 [BLOCK_9-BLOCK_26] 是错误的）
3. 必须翻译所有块，不能跳过任何块
4. 保持 [BLOCK_X] 标记不变，只翻译标记后的内容
"""
        
        logger.info("[后端] 开始调用 LLM 生成翻译...")
        logger.info(f"[后端] 提示词长度: {len(prompt)} 字符")
        logger.info(f"[后端] 提示词预览: {prompt[:300]}...")
        
        response = client.generate(prompt)
        logger.info(f"[后端] LLM 响应长度: {len(response)} 字符")
        logger.info(f"[后端] LLM 完整响应:\n{response}")
        
        # 检查空响应
        if not response or len(response.strip()) == 0:
            logger.error("[后端] LLM 返回空响应，可能是 API 额度用尽或网络问题")
            return jsonify({
                'success': False, 
                'error': 'LLM 返回空响应，请检查 API 额度或网络连接',
                'quota_exceeded': True
            })
        
        logger.info(f"[后端] LLM 响应开头: {response[:100]}")
        logger.info(f"[后端] LLM 响应结尾: {response[-100:] if len(response) > 100 else response}")
        
        # 清理 think 标签（MiniMax 模型会添加）
        # 注意：只移除标签本身，不移除标签之间的内容（因为翻译内容在标签内）
        response_cleaned = re.sub(r'^\s*<think>\s*', '', response, flags=re.DOTALL).strip()
        response_cleaned = re.sub(r'\s*</think>\s*$', '', response_cleaned, flags=re.DOTALL).strip()
        if response_cleaned != response:
            logger.info(f"[后端] 清理 think 标签后响应长度: {len(response_cleaned)} 字符")
        
        # 解析响应，提取每个块的翻译
        translations = []
        blocks = response_cleaned.split('[BLOCK_')
        logger.info(f"[后端] 分割后块数量: {len(blocks)}")
        
        for i, block in enumerate(blocks):
            block = block.strip()
            if not block:
                logger.info(f"[后端] 块 {i}: 为空，跳过")
                continue
            
            # 查找块编号和内容
            match = re.match(r'(\d+)\](.*?)(?=\[BLOCK_|$)', block, re.DOTALL)
            if match:
                idx = int(match.group(1))
                translation = match.group(2).strip()
                logger.info(f"[后端] 块 {i}: 索引={idx}, 原始长度={len(translation)}")
                
                # 清理翻译内容
                translation = re.sub(r'</think>.*?</think>', '', translation, flags=re.DOTALL).strip()
                translation = translation.replace('译文：', '').replace('译文:', '').strip()
                translation = translation.replace('---', '').strip()
                
                logger.info(f"[后端] 块 {i}: 清理后长度={len(translation)}, 内容={translation[:50]}...")
                
                # 应用起始索引偏移
                adjusted_idx = idx + start_index
                translations.append({
                    'index': adjusted_idx,
                    'translation': translation
                })
            else:
                logger.info(f"[后端] 块 {i}: 未匹配到索引，内容={block[:50]}...")
        
        # 计算最后成功翻译的索引
        last_index = translations[-1]['index'] if translations else -1
        expected_count = len(texts)
        actual_count = len(translations)
        
        logger.info(f"[后端] 翻译完成: 期望 {expected_count} 个块, 实际 {actual_count} 个块, 最后索引 {last_index}")
        
        return jsonify({
            'success': True,
            'translations': translations,
            'last_index': last_index,  # 新增：最后成功翻译的块索引
            'expected_count': expected_count,  # 新增：期望翻译的块数量
            'actual_count': actual_count,  # 新增：实际翻译的块数量
            'terms_used': matched_terms
        })
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"批量翻译失败: {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        
        # 检查是否是额度用尽的错误
        if "API额度已用尽" in error_msg:
            return jsonify({'success': False, 'error': 'API额度已用尽，请等待5小时后重试', 'quota_exceeded': True})
        
        return jsonify({'success': False, 'error': error_msg})


# ========================================
# 文件翻译 API
# ========================================

@app.route('/api/upload', methods=['POST'])
@login_required
def upload_file():
    """上传待翻译文件"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有文件'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名为空'})

        # 保存原始文件名
        original_filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        # 保存文件时使用时间戳前缀避免冲突
        storage_filename = f"{timestamp}_{original_filename}"
        filepath = UPLOAD_DIR / storage_filename
        file.save(str(filepath))
        
        logger.info(f"上传文件: {filepath}")
        
        # 调试：检查文件扩展名
        import os
        ext = os.path.splitext(str(filepath))[1].lower()
        logger.info(f"[调试] 文件扩展名: '{ext}'")
        logger.info(f"[调试] file_parser 模块路径: {file_parser.__file__}")
        
        # 解析文件
        blocks, format_info = file_parser.parse_file(str(filepath))
        
        if not blocks:
            return jsonify({'success': False, 'error': '无法解析文件或文件为空'})
        
        # 构建索引到坐标的映射（用于Excel导出）
        index_mapping = {}
        is_china_sheet = format_info.get('special_structure') == 'china_sheet'
        
        for block in blocks:
            idx = block['index']
            if 'sheet' in block:
                # Excel文件
                index_mapping[idx] = (block['sheet'], block['row'], block['col'])
            elif 'slide' in block:
                # PPT文件
                index_mapping[idx] = ('ppt', block['slide'], block.get('shape_id', 0))
        
        return jsonify({
            'success': True,
            'filename': storage_filename,  # 存储用的文件名（带时间戳）
            'original_filename': original_filename,  # 原始文件名
            'filepath': str(filepath),
            'blocks': blocks,  # 返回所有块用于翻译
            'total': len(blocks),
            'index_mapping': index_mapping,  # 返回坐标映射
            'is_china_sheet': is_china_sheet  # 标记是否为特殊结构
        })
        
    except Exception as e:
        logger.error(f"上传文件失败: {e}")
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/translate/file', methods=['POST'])
@login_required
def translate_file():
    """翻译文件 - 重新解析完整文件并应用翻译，并记录历史"""
    try:
        data = request.json
        filename = data.get('filename')  # 存储用的文件名（带时间戳）
        original_filename = data.get('original_filename', filename)  # 原始文件名
        translations = data.get('translations', {})
        mode = data.get('mode', 'bilingual')

        # 获取当前用户信息
        user_id = int(request.headers.get('X-User-ID', 0))
        user = user_db.get_user_by_id(user_id)
        username = user['username'] if user else 'unknown'

        logger.info(f"导出文件请求: {filename}, 原始文件名: {original_filename}, 翻译条目数: {len(translations)}, 用户: {username}")

        # 使用存储的文件名构建完整路径
        filepath = UPLOAD_DIR / filename
        logger.info(f"[导出调试] 文件路径: {filepath}, 是否存在: {filepath.exists()}")

        if not filepath.exists():
            return jsonify({'success': False, 'error': f'文件不存在: {filepath}'})

        # 重新解析完整文件，获取所有文本块
        logger.info("[导出调试] 重新解析完整文件...")
        all_blocks, format_info = file_parser.parse_file(str(filepath))
        logger.info(f"[导出调试] 完整文件包含 {len(all_blocks)} 个文本块")

        # 提取摘要
        summary = extract_summary(all_blocks, max_chars=50)
        logger.info(f"[导出调试] 文件摘要: {summary}")

        # 计算总字符数
        total_chars = sum(len(b.get('text', '')) for b in all_blocks)

        # 处理翻译字典
        # 前端可能发送两种格式：
        # 1. 整数索引: {"0": "翻译", "1": "翻译"}
        # 2. 坐标格式（中国表）: {"中国,1,2": "翻译", ...}
        translations_int = {}
        coord_translations = {}  # 用于中国表的坐标格式

        for key, value in translations.items():
            # 检查是否是坐标格式 (sheet,row,col)
            if ',' in str(key) and str(key).count(',') == 2:
                # 坐标格式，直接保存
                coord_translations[key] = value
            else:
                # 尝试转换为整数索引
                try:
                    translations_int[int(key)] = value
                except (ValueError, TypeError):
                    translations_int[key] = value

        logger.info(f"[导出调试] 翻译字典包含 {len(translations_int)} 个索引翻译, {len(coord_translations)} 个坐标翻译")
        logger.info(f"[导出调试] 翻译键示例: {list(translations_int.keys())[:10]}...")
        if coord_translations:
            logger.info(f"[导出调试] 坐标翻译键示例: {list(coord_translations.keys())[:5]}...")

        # 构建完整的翻译映射（包含所有文本块）
        full_translation_map = {}
        for block in all_blocks:
            idx = block['index']
            if idx in translations_int:
                full_translation_map[idx] = translations_int[idx]
            else:
                if mode == 'target_only':
                    full_translation_map[idx] = block['text']

        logger.info(f"[导出调试] 完整翻译映射包含 {len(full_translation_map)} 个条目")

        # 生成新的输出文件名（短格式），使用原始文件名
        output_filename = generate_output_filename(original_filename, mode, user_id)
        output_path = OUTPUT_DIR / output_filename

        # 获取文件类型
        ext = Path(original_filename).suffix.lower()
        file_type = ext[1:] if ext.startswith('.') else ext
        is_china_sheet = data.get('is_china_sheet', False)

        # 创建历史记录（状态为 processing）
        record_id = user_db.create_translation_record(
            user_id=user_id,
            username=username,
            original_filename=original_filename,
            output_filename=output_filename,
            file_type=file_type,
            summary=summary,
            block_count=len(all_blocks),
            total_chars=total_chars,
            mode=mode,
            file_path=str(output_path)
        )
        logger.info(f"[导出调试] 创建历史记录 ID: {record_id}")

        try:
            # 执行导出
            if ext in ['.docx', '.doc']:
                success = file_exporter.export_word_simple(
                    filepath, full_translation_map, str(output_path), mode
                )
            elif ext in ['.xlsx', '.xls', '.xlsm']:
                excel_translations = {}

                # 如果有坐标格式的翻译（中国表），直接使用
                if coord_translations:
                    for key, value in coord_translations.items():
                        parts = key.split(',')
                        if len(parts) == 3:
                            sheet, row, col = parts[0], int(parts[1]), int(parts[2])
                            excel_translations[(sheet, row, col)] = value
                    logger.info(f"[导出调试] 使用坐标翻译，共 {len(excel_translations)} 个")
                else:
                    # 使用索引映射
                    for key, value in full_translation_map.items():
                        block = next((b for b in all_blocks if b['index'] == key), None)
                        if block and 'sheet' in block:
                            excel_translations[(block['sheet'], block['row'], block['col'])] = value
                    logger.info(f"[导出调试] 使用索引映射翻译，共 {len(excel_translations)} 个")

                success = file_exporter.export_excel_simple(
                    filepath, excel_translations, str(output_path), mode, is_china_sheet
                )
            elif ext == '.pptx':
                success = file_exporter.export_pptx(
                    filepath, full_translation_map, str(output_path), mode
                )
            else:
                user_db.complete_translation_record(record_id, 0, '不支持的文件类型')
                return jsonify({'success': False, 'error': '不支持的文件类型'})

            if success:
                # 获取文件大小
                file_size = output_path.stat().st_size if output_path.exists() else 0

                # 使用翻译后的内容重新提取摘要（中文）
                chinese_summary = extract_summary(all_blocks, full_translation_map, max_chars=50)
                logger.info(f"[导出调试] 中文摘要: {chinese_summary}")

                user_db.complete_translation_record(record_id, file_size, summary=chinese_summary)
                logger.info(f"[导出调试] 翻译完成，文件大小: {file_size} 字节")

                return jsonify({
                    'success': True,
                    'download_url': f'/api/download/{output_filename}',
                    'history_id': record_id
                })
            else:
                user_db.complete_translation_record(record_id, 0, '导出失败')
                return jsonify({'success': False, 'error': '导出失败'})

        except Exception as export_error:
            user_db.complete_translation_record(record_id, 0, str(export_error))
            raise

    except Exception as e:
        logger.error(f"翻译文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/download/<filename>')
@login_required
def download_file(filename):
    """下载翻译后的文件"""
    try:
        filepath = OUTPUT_DIR / filename
        logger.info(f"[下载调试] 请求下载: {filename}")
        logger.info(f"[下载调试] 完整路径: {filepath}")
        logger.info(f"[下载调试] 文件存在: {filepath.exists()}")

        if filepath.exists():
            logger.info(f"[下载调试] 文件大小: {filepath.stat().st_size} 字节")
            return send_file(str(filepath), as_attachment=True)
        else:
            # 列出输出目录中的文件
            if OUTPUT_DIR.exists():
                files = list(OUTPUT_DIR.iterdir())
                logger.info(f"[下载调试] 输出目录中的文件: {[f.name for f in files]}")
            return jsonify({'success': False, 'error': '文件不存在'})
    except Exception as e:
        logger.error(f"下载文件失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


# ========================================
# 翻译历史记录 API
# ========================================

@app.route('/api/history', methods=['GET'])
@login_required
def get_translation_history():
    """获取翻译历史列表，支持模糊搜索和用户筛选 - 所有用户可查看所有历史"""
    try:
        user_id = int(request.headers.get('X-User-ID', 0))
        user = user_db.get_user_by_id(user_id)

        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        limit = request.args.get('limit', 20, type=int)
        status = request.args.get('status', None)
        keyword = request.args.get('keyword', None)  # 模糊搜索关键词
        username = request.args.get('filter_username', None)  # 按用户名筛选

        # 所有用户都可以查看所有历史，通过用户名筛选
        target_user_id = None

        result = user_db.get_translation_history(
            user_id=target_user_id,
            page=page,
            limit=limit,
            status=status,
            keyword=keyword,
            username=username
        )

        # 添加下载链接
        for item in result['items']:
            item['download_url'] = f"/api/download/{item['output_filename']}"

        return jsonify({'success': True, 'data': result})

    except Exception as e:
        logger.error(f"获取翻译历史失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/history/<int:record_id>', methods=['GET'])
@login_required
def get_translation_record(record_id):
    """获取单条翻译记录详情"""
    try:
        user_id = int(request.headers.get('X-User-ID', 0))
        user = user_db.get_user_by_id(user_id)

        record = user_db.get_translation_record(record_id)

        if not record:
            return jsonify({'success': False, 'error': '记录不存在'})

        # 检查权限（只能看自己的，管理员可以看所有）
        if user.get('role') != 'admin' and record['user_id'] != user_id:
            return jsonify({'success': False, 'error': '无权访问此记录'})

        # 添加下载链接
        record['download_url'] = f"/api/download/{record['output_filename']}"

        return jsonify({'success': True, 'data': record})

    except Exception as e:
        logger.error(f"获取翻译记录详情失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/history/<int:record_id>', methods=['DELETE'])
@login_required
def delete_translation_record(record_id):
    """删除翻译记录"""
    try:
        user_id = int(request.headers.get('X-User-ID', 0))
        user = user_db.get_user_by_id(user_id)

        # 获取记录信息
        record = user_db.get_translation_record(record_id)
        if not record:
            return jsonify({'success': False, 'error': '记录不存在'})

        # 检查权限（只能删除自己的，管理员可以删除所有）
        if user.get('role') != 'admin' and record['user_id'] != user_id:
            return jsonify({'success': False, 'error': '无权删除此记录'})

        # 删除物理文件
        filepath = Path(record['file_path'])
        if filepath.exists():
            filepath.unlink()
            logger.info(f"[历史记录] 删除文件: {filepath}")

        # 删除数据库记录
        user_db.delete_translation_record(record_id)

        return jsonify({'success': True, 'message': '记录已删除'})

    except Exception as e:
        logger.error(f"删除翻译记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)})


if __name__ == '__main__':
    # 从环境变量读取端口，默认 5555
    port = int(os.environ.get('PORT', 5555))
    # 从环境变量读取主机，默认 0.0.0.0（支持内外网访问）
    host = os.environ.get('HOST', '0.0.0.0')
    # 从环境变量读取调试模式，默认 False
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    logger.info(f"启动 Web 服务: {host}:{port} (debug={debug})")
    logger.info(f"本地访问: http://127.0.0.1:{port}")
    logger.info(f"局域网访问: http://<本机IP>:{port}")
    app.run(host=host, port=port, debug=debug, threaded=True)
