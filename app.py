from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import json
import os
import requests
import time
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'daiptalk_secret_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# 存储在线用户信息
online_users = {}
# 聊天房间
chat_room = 'daiptalk_room'

# 加载配置
config = {
    'server_addresses': [
        {'name': '本地服务器', 'url': 'http://localhost:5000'},
        {'name': '备用服务器1', 'url': 'http://192.168.1.100:5000'},
        {'name': '备用服务器2', 'url': 'http://192.168.1.101:5000'}
    ]
}

# 保存配置到文件
def save_config():
    with open('config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 加载配置文件
def load_config():
    global config
    if os.path.exists('config.json'):
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                config = json.load(f)
        except:
            pass

load_config()
save_config()

@app.route('/')
def index():
    return render_template('login.html')

@app.route('/chat')
def chat():
    username = request.args.get('username')
    server = request.args.get('server')
    if not username:
        return redirect('/')
    return render_template('chat.html', username=username, server=server)

@app.route('/config')
def get_config():
    return jsonify(config)

@app.route('/redirect/<path:path>')
def redirect(path):
    return redirect(path)

@socketio.on('connect')
def handle_connect():
    print('客户端连接')

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    username = None
    for user, user_sid in online_users.items():
        if user_sid == sid:
            username = user
            break
    if username:
        del online_users[username]
        emit('user_left', {'username': username, 'online_users': list(online_users.keys())},
             room=chat_room, broadcast=True)
        leave_room(chat_room)
        print(f'{username} 离开聊天室')

@socketio.on('join')
def handle_join(data):
    username = data['username']
    # 检查昵称是否已存在
    if username in online_users:
        emit('join_error', {'message': '昵称已存在，请选择其他昵称'})
        return
    
    online_users[username] = request.sid
    join_room(chat_room)
    
    # 发送欢迎消息
    emit('welcome', {'message': f'欢迎 {username} 加入聊天室！', 'online_users': list(online_users.keys())},
         room=chat_room, broadcast=True)
    
    print(f'{username} 加入聊天室')

@socketio.on('send_message')
def handle_message(data):
    username = data['username']
    message = data['message']
    
    # 处理@电影功能
    if message.startswith('@电影'):
        try:
            # 使用固定的解析地址
            parsed_url = "https://jx.m3u8.tv/jiexi/?url=2"
            # 发送带iframe的消息
            emit('new_message', {
                'username': username,
                'message': f'<div class="movie-container"><h4>电影播放</h4><iframe src="{parsed_url}" frameborder="0" width="100%" height="300px"></iframe></div>',
                'is_movie': True
            }, room=chat_room, broadcast=True)
        except Exception as e:
            emit('new_message', {
                'username': username,
                'message': '电影解析失败，请检查URL格式',
                'is_movie': False
            }, room=chat_room, broadcast=True)
    # 处理@川小农功能
    elif message.startswith('@川小农'):
        # 提取用户的问题，如果只有@川小农没有问题，也能正常回复
        if len(message.split(' ', 1)) > 1:
            question = message.split(' ', 1)[1].strip()
        else:
            question = ''
        
        print(f'接收到@川小农请求，问题: "{question}"')
        
        # 首先发送用户的原始消息到聊天界面
        emit('new_message', {
            'username': username,
            'message': message,
            'is_movie': False
        }, room=chat_room, broadcast=True)
        
        try:
            # 模拟AI回复（实际应用中可以接入真实的大模型API）
            ai_response = get_ai_response(question)
            print(f'川小农回复: "{ai_response}"')
            
            # 立即发送回复，不延迟
            # 注意：使用room参数时不需要broadcast=True，会自动广播给房间内所有人
            socketio.emit('new_message', {
                'username': '川小农',
                'message': ai_response,
                'is_movie': False
            }, room=chat_room)
        except Exception as e:
            error_msg = f'抱歉，我现在有点忙，请稍后再试。错误: {str(e)}'
            print(f'AI响应错误: {e}')
            # 使用room参数时不需要broadcast=True
            socketio.emit('new_message', {
                'username': '川小农',
                'message': error_msg,
                'is_movie': False
            }, room=chat_room)
    # 处理@其他用户
    elif '@' in message:
        # 简单的@功能实现
        emit('new_message', {
            'username': username,
            'message': message,
            'is_movie': False
        }, room=chat_room, broadcast=True)
    # 普通消息
    else:
        emit('new_message', {
            'username': username,
            'message': message,
            'is_movie': False
        }, room=chat_room, broadcast=True)

# 模拟AI回复函数
def get_ai_response(question):
    """
    获取AI回复
    在实际应用中，可以替换为调用真实的大模型API
    """
    # 确保question是字符串类型
    question = str(question) if question else ''
    
    # 简单的预设回复列表
    default_responses = [
        "您好！我是川小农，很高兴为您服务。请问有什么可以帮助您的吗？",
        "这个问题很有意思，让我想想...",
        "感谢您的提问，我会尽力为您解答。",
        "这是一个很好的观点，我同意您的看法。",
        "根据我的理解，您想了解的是...",
        "抱歉，这个问题我还需要学习一下。",
        "您说得对，我们确实应该考虑这个方面。"
    ]
    
    # 增强的关键词回复匹配，添加更多关键词
    keyword_responses = {
        '你好': '你好！很高兴见到你！',
        '您好': '您好！有什么可以帮助您的吗？',
        '你是谁': '我是川小农，一个智能聊天助手。',
        '介绍自己': '我是川小农，您的智能聊天伙伴，随时为您提供帮助！',
        '谢谢': '不客气！能够帮助你我很开心。',
        '感谢': '不用谢，这是我应该做的。',
        '再见': '再见！期待下次与你交流。',
        '拜拜': '拜拜！有需要随时找我。',
        '天气': f'今天天气真不错！适合出去走走。',
        '时间': f'现在的时间是 {time.strftime("%Y-%m-%d %H:%M:%S")}',
        '帮助': '我可以回答问题、聊天、提供建议。试试@川小农 你好 吧！',
        '功能': '我支持聊天对话、时间查询、简单问答等功能。',
        '你能做什么': '我可以和您聊天、回答简单问题、提供帮助信息等。',
        'AI': '是的，我是一个基于人工智能技术的聊天助手。'
    }
    
    # 如果问题为空，返回欢迎语
    if not question.strip():
        return "您好！我是川小农，很高兴为您服务。请问有什么可以帮助您的吗？"
    
    # 检查是否有关键词匹配
    for keyword, response in keyword_responses.items():
        if keyword in question:
            return response
    
    # 随机选择一个默认回复
    response = random.choice(default_responses)
    return response

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)