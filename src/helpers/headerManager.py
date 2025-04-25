import json
import os
from functools import wraps
from typing import Callable, Dict, List, Any, Optional
import random

class HeaderManager:
    _instance = None
    _headers: List[Dict[str, str]] = []
    _current_index = 0
    _failed_headers = set()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HeaderManager, cls).__new__(cls)
            cls._instance._load_headers()
        return cls._instance
    
    def _load_headers(self) -> None:
        try:
            headers_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'db', 'headers.json')
            with open(headers_path, 'r') as f:
                self._headers = json.load(f)
        except Exception as e:
            print(f"❌ Ошибка при загрузке заголовков: {str(e)}")
            self._headers = []
    
    def get_next_header(self) -> Optional[Dict[str, str]]:
        if not self._headers:
            return None
        
        # Skip headers that have failed with 401
        for _ in range(len(self._headers)):
            header = self._headers[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._headers)
            
            # Skip headers that have recently failed with 401
            header_id = self._get_header_id(header)
            if header_id not in self._failed_headers:
                return header
                
        # If all headers are marked as failed, reset failed headers and try again
        if self._failed_headers:
            print("❌ Все заголовки с ошибкой 401, сбрасываю слежку за плохими заголовками")
            self._failed_headers.clear()
            return self.get_next_header()
        return None
    
    def _get_header_id(self, header: Dict[str, str]) -> str:
        auth = header.get('authorization', '')
        token = header.get('x-csrf-token', '')
        return f"{auth}:{token}"
    
    def mark_header_failed(self, header: Dict[str, str]) -> None:
        if header:
            header_id = self._get_header_id(header)
            self._failed_headers.add(header_id)
            print(f"Отметил заголовок как плохой из за 401 ошибки. Всего плохих заголовков: {len(self._failed_headers)}")
    
    def get_random_header(self) -> Optional[Dict[str, str]]:
        if not self._headers:
            return None
            
        return random.choice(self._headers)

def with_rotating_headers(use_random: bool = False):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            header_manager = HeaderManager()
            
            # Get a header based on strategy
            if use_random:
                headers = header_manager.get_random_header()
            else:
                headers = header_manager.get_next_header()
            
            if 'headers' not in kwargs:
                kwargs['headers'] = headers
            elif headers:  # If headers exist in kwargs, update them
                kwargs['headers'].update(headers)
            
            result = await func(*args, **kwargs)
            
            if result is None and kwargs.get('headers'):
                # Check if the caller indicated a 401 unauthorized error
                if getattr(wrapper, '_last_error_was_401', False):
                    # Mark the current header as failed
                    header_manager.mark_header_failed(kwargs.get('headers'))
                    # Reset the flag
                    wrapper._last_error_was_401 = False
            
            return result
        
        # Add a property to track 401 errors
        wrapper._last_error_was_401 = False
        
        # Add method to signal 401 error
        def set_401_error():
            wrapper._last_error_was_401 = True
        
        wrapper.set_401_error = set_401_error
        
        return wrapper
    return decorator

def handle_401_error(func_or_headers):
    if isinstance(func_or_headers, dict):
        # It's a header dict
        HeaderManager().mark_header_failed(func_or_headers)
    else:
        if hasattr(func_or_headers, 'set_401_error'):
            func_or_headers.set_401_error()
        else:
            raise ValueError("Функция не использует декоратор @with_rotating_headers")
