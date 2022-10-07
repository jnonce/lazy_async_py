
import asyncio
from functools import cache, wraps
import inspect
from typing import Awaitable, Callable, Concatenate, Generator, Generic, ParamSpec, Type, TypeVar


T = TypeVar("T")
P = ParamSpec("P")


class _LazyTask(Awaitable[T]):
    """
    Create a task only when awaited for the first time.
    This avoids creating tasks until we're sure it will be used at least once.
    """

    def __init__(self, task: Awaitable[T]) -> None:
        super().__init__()
        self._inner_obj: Awaitable[T] = task

    def __await__(self) -> Generator[None, None, T]:
        current_obj = self._inner_obj

        if not isinstance(current_obj, asyncio.Task):
            current_obj = asyncio.create_task(current_obj)
            self._inner_obj = current_obj

        return current_obj.__await__()


class _BaseWrapper(Generic[T]):
    def __init__(self, task: Awaitable[T]) -> None:
        super().__init__()
        self._obj = _LazyTask(task)


def _make_BaseWrapper_async_fn(
    fn: Callable[Concatenate[_BaseWrapper[T], P], Awaitable[T]]
) -> Callable[Concatenate[_BaseWrapper[T], P], Awaitable[T]]:
    """
    Wrap a member function so that we first resolve the object
    (from _LazyTask) and then call and await the actual member.
    """

    if not callable(fn):
        return fn
    if not inspect.iscoroutinefunction(fn):
        raise ValueError(fn)

    @wraps(fn)
    async def trampoline(self: _BaseWrapper[T], *args: P.args, **kwargs: P.kwargs) -> T:
        obj = await self._obj
        return await fn.__get__(obj)(*args, **kwargs)

    return trampoline


@cache
def _make_wrapper_cls(typ: type) -> Type[_BaseWrapper]:
    properties = {
        name: _make_BaseWrapper_async_fn(getattr(typ, name))
        for name in dir(typ)
        if not name.startswith("__")
    }

    wrapper_cls: Type[_BaseWrapper] = type(
        typ.__name__ + "__syncwrap",
        (_BaseWrapper,),
        properties,
    )

    return wrapper_cls


def lazy_async(fn: Callable[P, Awaitable[T]]) -> Callable[P, T]:
    """
    Remove one level of async behavior.

    ## Example code

    ```
    class Greeter:
        async def hello(self, name: str) -> None:
            await asyncio.sleep(0.1)
            print(f"Hello {name}")

    @lazy_async
    async def get_greeter() -> Greeter:
        print("Getting the greeter")
        await asyncio.sleep(0.1)
        return Greeter()

    async def main():
        print("Startup")
        b = get_greeter()  # notice this is not async anymore
        print("Got the greeter")
        await b.hello("George")
        await b.hello("Ringo")
    ```

    ## Example Output
    ```
    Startup
    Got the greeter
    Getting the greeter
    Hello George
    Hello Ringo
    ```
    """

    typ = inspect.signature(fn).return_annotation
    if typ == inspect.Signature.empty:
        raise TypeError("Missing type annotation for function")

    wrapper_cls: Type[_BaseWrapper] = _make_wrapper_cls(typ)

    @wraps(fn)
    def handler(*args: P.args, **kwargs: P.kwargs) -> T:
        task = fn(*args, **kwargs)
        return wrapper_cls(task)  # type: ignore

    return handler
