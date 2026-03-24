from pyinstrument import Profiler

async def profile_middleware(request, call_next):
    profiler = Profiler()
    profiler.start()
    response = await call_next(request)
    profiler.stop()
    print(profiler.output_text(unicode=True, color=True))
    return response