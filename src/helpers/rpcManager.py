import os
import random
import asyncio
from functools import wraps
from typing import List, Callable, Any, TypeVar, cast

T = TypeVar('T')

class RpcManager:
    _instance = None
    _lock = asyncio.Lock()
    _rpcs: List[str] = []
    _current_index = 0
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RpcManager, cls).__new__(cls)
            cls._instance._load_rpcs()
        return cls._instance
    
    def _load_rpcs(self) -> None:
        try:
            with open("rpcs.txt", "r") as f:
                self._rpcs = [line.strip() for line in f if line.strip()]
                
            # Shuffle to balance load across endpoints
            random.shuffle(self._rpcs)
            
            print(f"Загружено {len(self._rpcs)} RPC из rpcs.txt")
        except Exception as e:
            print(f"❌ Ошибка при загрузке RPC: {str(e)}")
            self._rpcs = []
    
    async def get_next_rpc(self) -> str:
        if not self._rpcs:
            self._load_rpcs()
            if not self._rpcs:
                raise ValueError("Нет доступных RPC")
        
        async with self._lock:
            rpc = self._rpcs[self._current_index]
            self._current_index = (self._current_index + 1) % len(self._rpcs)
            return rpc
    
    @classmethod
    def with_rpc_rotation(cls, func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(self_arg, *args, **kwargs):
            rpc_manager = cls()
            rpc_url = await rpc_manager.get_next_rpc()
            
            # Replace the RPC URL in the kwargs if it exists
            if 'rpc_url' in kwargs:
                kwargs['rpc_url'] = rpc_url
            else:
                # Add as first non-self argument if the function expects it
                import inspect
                sig = inspect.signature(func)
                param_names = list(sig.parameters.keys())
                if len(param_names) > 1 and param_names[1] == 'rpc_url':
                    args = list(args)
                    if len(args) == 0:
                        args.append(rpc_url)
                    else:
                        args[0] = rpc_url
                    args = tuple(args)
                else:
                    # Just pass it as an additional kwarg
                    kwargs['rpc_url'] = rpc_url
            
            try:
                return await func(self_arg, *args, **kwargs)
            except Exception as e:
                print(f"Вызов RPC неудался {rpc_url}: {str(e)}")
                # Try one more time with a different RPC if available
                if len(rpc_manager._rpcs) > 1:
                    rpc_url = await rpc_manager.get_next_rpc()
                    if 'rpc_url' in kwargs:
                        kwargs['rpc_url'] = rpc_url
                    else:
                        args = list(args)
                        if len(args) == 0:
                            args.append(rpc_url)
                        else:
                            args[0] = rpc_url
                        args = tuple(args)
                    
                    return await func(self_arg, *args, **kwargs)
                raise
                
        return cast(Callable[..., Any], wrapper)
