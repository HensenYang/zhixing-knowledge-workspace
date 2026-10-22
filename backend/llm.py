"""Server-side, text-only adapter for OpenAI-compatible Chat Completions APIs."""
from dataclasses import dataclass, field
import os
from typing import Literal
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

router = APIRouter(prefix='/api/llm', tags=['LLM'])


@dataclass(frozen=True)
class LLMConfig:
    api_key: str = field(repr=False)
    base_url: str
    model: str
    timeout: int
    max_output_tokens: int
    token_parameter: str


def configuration():
    values = {name: os.environ.get(name, '').strip() for name in
              ('LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL')}
    missing = [name for name, value in values.items() if not value]
    if missing:
        return None, missing, None
    try:
        url = urlsplit(values['LLM_BASE_URL'])
        if (not url.hostname or url.username or url.password or url.query or url.fragment
                or url.scheme not in ('http', 'https')
                or (url.scheme == 'http' and url.hostname not in ('localhost', '127.0.0.1', '::1'))):
            raise ValueError
        # Accessing port also validates malformed port values.
        url.port
        httpx.URL(values['LLM_BASE_URL'])
        if not values['LLM_API_KEY'].isascii():
            raise ValueError
        if any(any(ord(char) < 32 or ord(char) == 127 for char in value) for value in values.values()):
            raise ValueError
        timeout = int(os.environ.get('LLM_TIMEOUT_SECONDS', '60'))
        maximum = int(os.environ.get('LLM_MAX_OUTPUT_TOKENS', '1024'))
        parameter = os.environ.get('LLM_TOKEN_PARAMETER', 'max_completion_tokens').strip()
        if not 1 <= timeout <= 120 or not 1 <= maximum <= 8192:
            raise ValueError
        if parameter not in ('max_completion_tokens', 'max_tokens'):
            raise ValueError
    except (ValueError, httpx.InvalidURL):
        return None, [], 'LLM 配置无效，请检查 API 地址、超时、输出上限与令牌参数；远程地址需使用 HTTPS。'
    return LLMConfig(values['LLM_API_KEY'], values['LLM_BASE_URL'].rstrip('/'),
                     values['LLM_MODEL'], timeout, maximum, parameter), [], None


def require_configuration():
    config, missing, error = configuration()
    if config is None:
        raise HTTPException(503, error or f"LLM 尚未配置，请在后端 .env 设置：{', '.join(missing)}，然后重启后端。")
    return config


class ChatMessage(BaseModel):
    role: Literal['system', 'user', 'assistant']
    content: str = Field(min_length=1, max_length=10000)


class ChatInput(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=32)

    @model_validator(mode='after')
    def validate_messages(self):
        if not any(message.role == 'user' for message in self.messages):
            raise ValueError('至少需要一条用户消息。')
        if any(not message.content.strip() for message in self.messages):
            raise ValueError('消息不能为空白。')
        if sum(len(message.content) for message in self.messages) > 60000:
            raise ValueError('消息总长度不能超过 60000 字符。')
        return self


async def complete(config, messages):
    payload = {'model': config.model, 'messages': messages, 'stream': False,
               config.token_parameter: config.max_output_tokens}
    try:
        async with httpx.AsyncClient(timeout=config.timeout, follow_redirects=False) as client:
            response = await client.post(config.base_url + '/chat/completions',
                                         headers={'Authorization': 'Bearer ' + config.api_key}, json=payload)
    except httpx.TimeoutException:
        raise HTTPException(504, '模型服务响应超时，请稍后重试或调整后端超时配置。') from None
    except httpx.RequestError:
        raise HTTPException(502, '无法连接模型服务，请检查后端网络与 API 地址。') from None
    # Never relay provider error bodies: they may contain credentials or prompts.
    if response.status_code in (401, 403):
        raise HTTPException(502, '模型服务拒绝认证或访问，请检查后端 API Key 和模型权限。')
    if response.status_code == 429:
        raise HTTPException(429, '模型服务限流或额度不足，请稍后重试并检查服务商额度。')
    if not 200 <= response.status_code < 300:
        raise HTTPException(502, '模型请求失败，请检查模型名、API 地址和接口参数兼容性。')
    try:
        data = response.json()
        choice = data['choices'][0]
        content = choice['message']['content']
        if not isinstance(content, str) or not content.strip():
            raise ValueError
        usage = data.get('usage') or {}
        usage = {key: value for key, value in usage.items()
                 if key in ('prompt_tokens', 'completion_tokens', 'total_tokens')
                 and type(value) is int and value >= 0}
        finish_reason = choice.get('finish_reason')
        if finish_reason not in ('stop', 'length', 'content_filter', 'tool_calls', 'function_call', None):
            finish_reason = None
    except (ValueError, KeyError, IndexError, TypeError, AttributeError):
        raise HTTPException(502, '模型服务未返回有效文本，请检查接口兼容性或提高输出令牌上限。') from None
    return {'model': config.model, 'content': content, 'usage': usage, 'finish_reason': finish_reason}


@router.get('/status')
def status():
    config, missing, error = configuration()
    return {'configured': config is not None, 'api_key_configured': bool(os.environ.get('LLM_API_KEY', '').strip()),
            'protocol': 'OpenAI-compatible Chat Completions',
            'base_url': config.base_url if config else None, 'model': config.model if config else None,
            'missing': missing, 'error': error}


@router.post('/test')
async def test_connection():
    config = require_configuration()
    result = await complete(config, [{'role': 'user', 'content': 'Reply with OK.'}])
    return {'ok': True, **result}


@router.post('/chat')
async def chat(data: ChatInput):
    return await complete(require_configuration(), [message.model_dump() for message in data.messages])
