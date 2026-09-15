import json
from unittest.mock import Mock, patch

from core.models.base import ChatMessage
from core.models.llama_cpp import LlamaCppProvider


def test_llama_cpp_health_uses_local_server():
    provider = LlamaCppProvider()
    with patch('core.models.llama_cpp.requests.get') as get:
        get.return_value.ok = True
        assert provider.health() is True
        get.assert_called_once_with('http://127.0.0.1:8080/health', timeout=3)


def test_llama_cpp_chat_uses_openai_compatible_endpoint():
    provider = LlamaCppProvider()
    model_response = Mock()
    model_response.raise_for_status.return_value = None
    model_response.json.return_value = {'data': [{'id': 'trinity-phone'}]}
    chat_response = Mock()
    chat_response.raise_for_status.return_value = None
    chat_response.json.return_value = {'choices': [{'message': {'content': 'hello'}}]}
    with patch('core.models.llama_cpp.requests.get', return_value=model_response), patch(
        'core.models.llama_cpp.requests.post', return_value=chat_response
    ) as post:
        result = provider.chat([ChatMessage('user', 'hi')], 'trinity-phone')
    assert result == 'hello'
    assert post.call_args.args[0].endswith('/v1/chat/completions')
    assert post.call_args.kwargs['json']['model'] == 'trinity-phone'


def test_llama_cpp_stream_parses_sse():
    provider = LlamaCppProvider()
    model_response = Mock()
    model_response.raise_for_status.return_value = None
    model_response.json.return_value = {'data': [{'id': 'trinity-phone'}]}
    stream_response = Mock()
    stream_response.raise_for_status.return_value = None
    stream_response.__enter__ = Mock(return_value=stream_response)
    stream_response.__exit__ = Mock(return_value=False)
    stream_response.iter_lines.return_value = [
        'data: ' + json.dumps({'choices': [{'delta': {'content': 'Hel'}}]}),
        'data: ' + json.dumps({'choices': [{'delta': {'content': 'lo'}}]}),
        'data: [DONE]',
    ]
    with patch('core.models.llama_cpp.requests.get', return_value=model_response), patch(
        'core.models.llama_cpp.requests.post', return_value=stream_response
    ):
        assert ''.join(provider.stream_chat([ChatMessage('user', 'hi')], 'trinity-phone')) == 'Hello'
