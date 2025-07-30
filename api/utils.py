import typing as tp
import itertools as it
import asyncio as aio
from pydantic import HttpUrl
import typing_extensions as tpe
from loguru import logger
import subprocess
import queue
import threading
import requests

CHUNK_SIZE = 32768
PCM_BUFFER_SIZE = 1600
PCM_MIN_BUFFER = 1600
PCM_MAX_BUFFER = 32000

T = tp.TypeVar("T")
P = tpe.ParamSpec("P")

def chunk(iterable:tp.Iterable[T], size:int) -> tp.Iterator[T]:
	iterator = iter(iterable)
	while True:	
		chunk = list[T](it.islice(iterator, size))
		if not chunk:
			return it.chain(chunk)
		for item in chunk:
			yield item

def asyncify(func:tp.Callable[P,T]) -> tp.Callable[P,tp.Coroutine[None,None,T]]:
	async def wrapper(*args:P.args, **kwargs:P.kwargs) -> T:
		return await aio.to_thread(func, *args, **kwargs)
	return wrapper

def format_audio_from_youtube_stream_url(stream_url: HttpUrl) -> tp.Generator[bytes, None, None]:
    process = subprocess.Popen([
        "ffmpeg", "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
        "-ac", "1", "-ar", "16000", "-bufsize", "64k", "-loglevel", "quiet", "pipe:1"
    ], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)

    data_queue = queue.Queue[tp.Optional[bytes]](maxsize=10)
    error_flag = threading.Event()

    def stream_input():
        try:
            with requests.get(stream_url.unicode_string(), stream=True, timeout=30) as r:
                for chunk in r.iter_content(CHUNK_SIZE):
                    if chunk and not error_flag.is_set():
                        if process.stdin:
                            process.stdin.write(chunk)
                            process.stdin.flush()
        except Exception as e:
            logger.error(f"Input stream error: {e}")
            error_flag.set()
        finally:
            try:
                if process.stdin:
                    process.stdin.close()
            except:
                pass

    def read_output():
        try:
            buffer = b""
            while not error_flag.is_set():
                chunk = process.stdout.read(PCM_BUFFER_SIZE) if process.stdout else b""
                if not chunk:
                    if buffer:
                        data_queue.put(buffer)
                    break
                buffer += chunk
                while len(buffer) >= PCM_MIN_BUFFER:
                    send_size = min(len(buffer), PCM_MAX_BUFFER)
                    data_queue.put(buffer[:send_size])
                    buffer = buffer[send_size:]
        except Exception as e:
            logger.error(f"Output read error: {e}")
        finally:
            data_queue.put(None)

    threading.Thread(target=stream_input, daemon=True).start()
    threading.Thread(target=read_output, daemon=True).start()

    while True:
        try:
            chunk = data_queue.get(timeout=5)
            if chunk is None:
                break
            yield chunk
        except queue.Empty:
            if error_flag.is_set():
                break
            continue

    process.terminate()
    process.wait()