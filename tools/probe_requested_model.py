"""Check the configured language-model endpoint without exposing credentials."""
import json
from pathlib import Path
from openai import OpenAI

root = Path(__file__).resolve().parents[1]
provider = json.loads((root / 'config.json').read_text(encoding='utf-8'))['ai_providers']['highlight_finder']
client = OpenAI(api_key=provider['api_key'], base_url=provider['base_url'], timeout=45, max_retries=0)
try:
    response = client.chat.completions.create(
        model='gpt-6.1-sol', reasoning_effort='xhigh',
        messages=[{'role': 'user', 'content': 'Reply with the word OK.'}],
        max_completion_tokens=128)
    result = {'ok': True, 'returned_model': response.model,
              'requested_model': 'gpt-6.1-sol', 'reasoning_effort': 'xhigh',
              'text': response.choices[0].message.content}
except Exception as exc:
    message = str(exc).replace(provider['api_key'], '[redacted]')
    result = {'ok': False, 'type': type(exc).__name__, 'status': getattr(exc, 'status_code', None), 'error': message[:700]}
print(json.dumps(result, ensure_ascii=False))
