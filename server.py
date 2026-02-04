#!/usr/bin/env python3
"""
벤지 대시보드 서버 (Flask)
- 세션 기반 인증
- 인증 전: fake 페이지 (봇/크롤러 방지)
- 인증 후: 실제 대시보드
"""

from flask import Flask, send_from_directory, jsonify, request, session, redirect, url_for, render_template_string
from flask_cors import CORS
from pathlib import Path
import os
import secrets
from dotenv import load_dotenv
from functools import wraps

# .env 파일 로드
load_dotenv(Path(__file__).parent / '.env')

app = Flask(__name__)
CORS(app, supports_credentials=True)

# 세션 설정
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['SESSION_COOKIE_SECURE'] = False  # HTTPS면 True로
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 60 * 60 * 24 * 30  # 30일

# 경로 설정
DASHBOARD_DIR = Path(__file__).parent
TASKS_DIR = DASHBOARD_DIR.parent / "tasks"

# 인증 비밀번호 (.env에서 로드)
AUTH_PASSWORD = os.environ.get('DASHBOARD_PASSWORD', 'benji2026')

# 로그인 페이지 (심플하게 - ID + PW 세로 배치)
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta name="robots" content="noindex, nofollow">
    <title>Login</title>
    <style>
        body {
            font-family: -apple-system, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            margin: 0;
            background: #f0f0f0;
        }
        form {
            display: flex;
            flex-direction: column;
            gap: 8px;
            width: 160px;
        }
        input {
            padding: 8px 12px;
            border: 1px solid #ccc;
            border-radius: 4px;
            font-size: 14px;
            width: 100%;
            box-sizing: border-box;
        }
        button {
            padding: 8px 16px;
            background: #666;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }
        button:hover { background: #444; }
        .error { color: #c00; font-size: 12px; text-align: center; }
    </style>
</head>
<body>
    <div>
        <form method="POST" action="/login">
            <input type="text" name="username" placeholder="id" autofocus>
            <input type="password" name="password" placeholder="pw">
            <button type="submit">→</button>
        </form>
        {% if error %}<p class="error">×</p>{% endif %}
    </div>
</body>
</html>"""


def is_authenticated():
    """세션 인증 확인"""
    return session.get('authenticated', False)


def login_required(f):
    """인증 필요 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # API 요청이면 401
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            # 페이지 요청이면 로그인 페이지로
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    """로그인 페이지"""
    if request.method == 'POST':
        username = request.form.get('username', '').lower().strip()
        password = request.form.get('password', '')
        valid_users = ['rafy', 'ryan']
        
        if username in valid_users and password == AUTH_PASSWORD:
            # 성공: 실패 횟수 리셋
            session.pop('login_attempts', None)
            session.permanent = True
            session['authenticated'] = True
            session['username'] = username
            return redirect('/')
        
        # 실패: 횟수 증가
        attempts = session.get('login_attempts', 0) + 1
        session['login_attempts'] = attempts
        
        # 3번 실패시 리다이렉트
        if attempts >= 3:
            session.pop('login_attempts', None)
            return redirect('https://raom.kr')
        
        return render_template_string(LOGIN_PAGE, error=True)
    return render_template_string(LOGIN_PAGE, error=None)


@app.route('/logout')
def logout():
    """로그아웃"""
    session.clear()
    return redirect('/')


@app.route('/')
@login_required
def index():
    """대시보드 메인 페이지"""
    return send_from_directory(DASHBOARD_DIR, 'index.html')


@app.route('/dashboard-data.json')
@login_required
def dashboard_data():
    """대시보드 데이터 (인증 필요)"""
    return send_from_directory(DASHBOARD_DIR, 'dashboard-data.json')


@app.route('/<path:filename>')
def static_files(filename):
    """정적 파일 서빙 (CSS, JS 등은 인증 없이)"""
    # 데이터 파일은 인증 필요
    if filename.endswith('.json') and filename != 'package.json':
        if not is_authenticated():
            return jsonify({"error": "Unauthorized"}), 401
    return send_from_directory(DASHBOARD_DIR, filename)


@app.route('/api/task/<folder>/<filename>')
@login_required
def get_task_content(folder, filename):
    """작업 카드 마크다운 내용 반환 (인증 필요)"""
    try:
        # 보안: 경로 검증
        if '..' in folder or '..' in filename:
            return jsonify({"error": "Invalid path"}), 400
        
        # 허용된 폴더만
        allowed_folders = ['active', 'next', 'waiting', 'completed']
        if folder not in allowed_folders:
            return jsonify({"error": "Invalid folder"}), 400
        
        # 파일 읽기
        file_path = TASKS_DIR / folder / filename
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "content": content,
            "filename": filename,
            "folder": folder
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/doc/<path:doc_path>')
@login_required
def get_doc_content(doc_path):
    """문서 마크다운 내용 반환 (인증 필요)"""
    try:
        # 보안: 경로 검증
        if '..' in doc_path:
            return jsonify({"error": "Invalid path"}), 400
        
        # 허용된 문서 경로들
        base_dir = DASHBOARD_DIR.parent  # ~/clawd
        allowed_docs = {
            'youtube-books/CURRENT_SYSTEM_SUMMARY.md': base_dir / 'youtube-books' / 'CURRENT_SYSTEM_SUMMARY.md',
            'shorts/docs/book_recommendation_proposal.md': base_dir / 'shorts' / 'docs' / 'book_recommendation_proposal.md',
            'shorts/DEPLOY.md': base_dir / 'shorts' / 'DEPLOY.md',
            'knowledge/youtube.md': base_dir / 'knowledge' / 'youtube.md',
            'knowledge/infra.md': base_dir / 'knowledge' / 'infra.md',
        }
        
        if doc_path not in allowed_docs:
            return jsonify({"error": "Document not allowed"}), 403
        
        file_path = allowed_docs[doc_path]
        if not file_path.exists():
            return jsonify({"error": "File not found"}), 404
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            "content": content,
            "path": doc_path,
            "filename": file_path.name
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/health')
def health():
    """헬스체크 (인증 불필요)"""
    return jsonify({"status": "ok"})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    print(f"🚀 벤지 대시보드 서버 시작: http://0.0.0.0:{port}")
    print(f"🔐 인증 활성화됨 (비밀번호: .env의 DASHBOARD_PASSWORD)")
    app.run(host='0.0.0.0', port=port, debug=False)
