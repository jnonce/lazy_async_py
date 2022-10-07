
import asyncio
from lazy_import import lazy_async


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


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    loop.run_until_complete(main())
