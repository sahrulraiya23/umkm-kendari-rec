import google.generativeai as genai
import inspect
print('version', getattr(genai, '__version__', 'unknown'))
print('start_chat sig', inspect.signature(genai.GenerativeModel.start_chat))
print('GenModel attrs', [m for m in dir(genai.GenerativeModel) if not m.startswith('_')])
print('Chat methods placeholder to inspect later')
