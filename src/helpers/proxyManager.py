import os
import random
from functools import wraps
from typing import List, Optional, Callable, Any, Dict, Union
import aiohttp
import asyncio

class ProxyManager:
    _instance = None
    _proxies: List[str] = []
    _current_index: int = 0
    _max_retries: int = 5
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ProxyManager, cls).__new__(cls)
            cls._instance._load_proxies()
        return cls._instance
    
    def _load_proxies(self) -> None:
        try:
            with open("proxies.txt", "r") as f:
                self._proxies = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            
            # Remove trailing colons if present
            self._proxies = [proxy[:-1] if proxy.endswith(':') else proxy for proxy in self._proxies]
            
            random.shuffle(self._proxies)
            print(f"Загружено {len(self._proxies)} проксей")
        except FileNotFoundError:
            self._proxies = []
    
    def get_proxy(self) -> Optional[str]:
        if not self._proxies:
            return None
        
        proxy = self._proxies[self._current_index]
        self._current_index = (self._current_index + 1) % len(self._proxies)
        return proxy
    
    def refresh_proxies(self) -> None:
        self._load_proxies()
        self._current_index = 0
    
    def set_max_retries(self, max_retries: int) -> None:
        self._max_retries = max_retries
    
    async def execute_with_proxy_rotation(
        self, 
        session: aiohttp.ClientSession,
        url: str,
        method: str = "GET",
        headers: Dict[str, str] = None,
        params: Dict[str, str] = None,
        json_data: Dict = None,
        initial_proxy: str = None,
        status_check: Callable[[int], bool] = None
    ) -> Dict:
        retries = 0
        current_proxy = initial_proxy or self.get_proxy()
        
        # Default status check function (considers 200 as success)
        if status_check is None:
            status_check = lambda status: status == 200
        
        while retries < self._max_retries:
            try:
                kwargs = {
                    "headers": headers,
                    "params": params
                }
                
                if json_data is not None:
                    kwargs["json"] = json_data
                
                if current_proxy:
                    kwargs["proxy"] = current_proxy
                
                # Choose the appropriate HTTP method
                if method.upper() == "GET":
                    request_method = session.get
                elif method.upper() == "POST":
                    request_method = session.post
                elif method.upper() == "PUT":
                    request_method = session.put
                elif method.upper() == "DELETE":
                    request_method = session.delete
                else:
                    request_method = session.get
                
                async with request_method(url, **kwargs) as response:
                    print(response.status)

                    data = await response.json()

                    
                    # If we got a 429 (Too Many Requests) error
                    if response.status == 429:
                        print(f"❌ Получена ошибка 429 с прокси {current_proxy}. Меняем прокси...")
                        # Get the next proxy
                        current_proxy = self.get_proxy()
                        
                        if not current_proxy:
                            print("Нет больше доступных прокси")
                            break
                            
                        retries += 1
                        await asyncio.sleep(0.5)
                        continue
                    
                    # Check if the status code is considered successful
                    if not status_check(response.status):
                        error_message = data.get('message', 'Unknown error')
                        raise Exception(f"❌ Ошибка: {response.status} - {error_message}")
                    
                    # Success! Return the data
                    proxy_info = f" (используем прокси: {current_proxy})" if current_proxy else " (нет проксей)"
                    print(f"Запрос успешно выполнен{proxy_info}")
                    return data
                    
            except Exception as e:
                print(f"❌ Ошибка с прокси {current_proxy}: {str(e)}")
                # Try next proxy on any error
                current_proxy = self.get_proxy()
                
                if not current_proxy:
                    print("Нет больше доступных прокси после ошибки")
                    break
                    
                retries += 1
        
    @staticmethod
    def with_proxy(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            proxy_manager = ProxyManager()
            proxy_url = proxy_manager.get_proxy()
            
            if not proxy_url:
                return await func(*args, **kwargs)
            
            # Find the session parameter or create a new one
            session = None
            for arg in args:
                if isinstance(arg, aiohttp.ClientSession):
                    session = arg
                    break
            
            if 'session' in kwargs:
                session = kwargs['session']
            
            if not session:
                # If there's no session in args or kwargs,
                # we'll handle session creation and cleanup
                connector = aiohttp.TCPConnector(ssl=False)
                
                async with aiohttp.ClientSession(connector=connector) as new_session:
                    # Pass the proxy URL directly to the session method
                    kwargs['session'] = new_session
                    kwargs['proxy_url'] = proxy_url
                    
                    return await func(*args, **kwargs)
            else:
                # If a session is provided, we'll just add the proxy to kwargs
                kwargs['proxy_url'] = proxy_url
                return await func(*args, **kwargs)
        
        return wrapper
