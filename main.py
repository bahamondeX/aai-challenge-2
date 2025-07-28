import asyncio
import os
import re
import subprocess
import typing as tp
import threading
import queue
from concurrent.futures import ThreadPoolExecutor, Future
import requests
import yt_dlp  # type: ignore

from assemblyai.streaming.v3 import ( # type: ignore
	BeginEvent, StreamingClient, StreamingClientOptions,
	StreamingError, StreamingEvents, StreamingParameters,
	TerminationEvent, TurnEvent
)
from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
from sse_starlette.sse import EventSourceResponse

load_dotenv()

AAI_API_KEY = os.environ["AAI_API_KEY"]

BASE_YDL_OPTIONS = {
	"format": "bestaudio/best",
	"noplaylist": True,
	"quiet": True,
	"cookies": "cookies.txt"
}

CHUNK_SIZE = 32768
PCM_BUFFER_SIZE = 1600
PCM_MIN_BUFFER = 1600
PCM_MAX_BUFFER = 32000
TS_PREFETCH_COUNT = 3

app = FastAPI()


# ---------------- YouTube Utils ----------------

def get_stream_url(url: str) -> str:
	opts = BASE_YDL_OPTIONS.copy()
	with yt_dlp.YoutubeDL(opts) as ydl:
		info = ydl.extract_info(url, download=False)  # type: ignore
		stream_url = info["url"]  # type: ignore
		logger.info(f"Stream URL: {stream_url}")
		return stream_url # type: ignore


def get_ts_segments(url: str) -> tp.Generator[str, None, None]:
	try:
		stream_url = get_stream_url(url)
		response = requests.get(stream_url, timeout=10)
		response.raise_for_status()
	except requests.RequestException as e:
		raise RuntimeError(f"Failed to get TS stream: {e}")

	base_url = response.url.rsplit("/", 1)[0]
	seen: set[str] = set()
	for line in response.text.splitlines():
		if line and not line.startswith("#") and line.endswith(".ts"):
			ts_url = line if line.startswith("http") else f"{base_url}/{line}"
			if ts_url not in seen:
				seen.add(ts_url)
				yield ts_url


def search_youtube_videos(query: str) -> tp.Generator[str, None, None]:
	response = requests.get(f"https://www.youtube.com/results?search_query={query}")
	response.raise_for_status()
	pattern = re.compile(r"/watch\?v=([a-zA-Z0-9_-]+)")
	matches = set(pattern.findall(response.text))
	for match in matches:
		yield f"https://www.youtube.com/watch?v={match}"


# ---------------- Audio Handlers ----------------

def get_audio_stream_pcm_s16le_optimized(url: str) -> tp.Generator[bytes, None, None]:
	stream_url = get_stream_url(url)

	process = subprocess.Popen([
		"ffmpeg", "-i", "pipe:0", "-f", "s16le", "-acodec", "pcm_s16le",
		"-ac", "1", "-ar", "16000", "-bufsize", "64k", "-loglevel", "quiet", "pipe:1"
	], stdin=subprocess.PIPE, stdout=subprocess.PIPE, bufsize=0)

	data_queue = queue.Queue[tp.Optional[bytes]](maxsize=10)
	error_flag = threading.Event()

	def stream_input():
		try:
			with requests.get(stream_url, stream=True, timeout=30) as r:
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


def get_live_audio_optimized(url: str) -> tp.Generator[bytes, None, None]:
	segment_queue = queue.Queue[tp.Optional[Future[tp.Generator[bytes, None, None]]]](maxsize=TS_PREFETCH_COUNT)  # type: ignore
	executor = ThreadPoolExecutor(max_workers=2)

	def fetch_segments():
		try:
			for ts_url in get_ts_segments(url):
				if segment_queue.qsize() < TS_PREFETCH_COUNT:
					future = executor.submit(fetch_single_segment, ts_url)
					segment_queue.put(future)
		except Exception as e:
			logger.error(f"Segment fetching error: {e}")
		finally:
			segment_queue.put(None)

	def fetch_single_segment(ts_url: str) -> tp.Generator[bytes, None, None]:
		return get_audio_stream_pcm_s16le_optimized(ts_url)

	threading.Thread(target=fetch_segments, daemon=True).start()

	while True:
		try:
			future = segment_queue.get(timeout=10)
			if future is None:
				break
			segment_generator = future.result(timeout=30)
			for chunk in segment_generator:
				yield chunk
		except (queue.Empty, Exception) as e:
			logger.error(f"Live stream error: {e}")
			break


def handler(url: str, is_live: bool = False) -> tp.Generator[bytes, None, None]:
	return get_live_audio_optimized(url) if is_live else get_audio_stream_pcm_s16le_optimized(url)


# ---------------- Transcription ----------------

def on_begin(self: StreamingClient, event: BeginEvent):
	logger.info(f"Begin event: {event}")


def on_turn(self: StreamingClient, event: TurnEvent):
	self.queue.put_nowait(event)  # type: ignore


def on_termination(self: StreamingClient, event: TerminationEvent):
	logger.info(f"Termination event: {event}")


def on_error(self: StreamingClient, event: StreamingError):
	logger.error(f"Error event: {event}")


async def transcriber(url: str, is_live: bool = False):
	client = StreamingClient(StreamingClientOptions(api_key=AAI_API_KEY))
	client.queue = asyncio.Queue[TurnEvent]()  # type: ignore

	client.on(StreamingEvents.Begin, on_begin)  # type: ignore
	client.on(StreamingEvents.Turn, on_turn)  # type: ignore
	client.on(StreamingEvents.Termination, on_termination)  # type: ignore
	client.on(StreamingEvents.Error, on_error)  # type: ignore

	client.connect(StreamingParameters(sample_rate=16000))

	async def stream_audio():
		try:
			await asyncio.get_event_loop().run_in_executor(
				None, lambda: client.stream(handler(url, is_live))
			)
		except Exception as e:
			logger.error(f"Streaming error: {e}")

	asyncio.create_task(stream_audio())

	while True:
		try:
			data = await client.queue.get()  # type: ignore
			content = data.model_dump_json()
			yield content
		except asyncio.TimeoutError:
			logger.warning("Transcription timeout")
			break
		except Exception as e:
			logger.error(f"Transcription error: {e}")
			break


# ---------------- API Routes ----------------

@app.get("/api/search")
def search(query: str):
	return {"videos": list(search_youtube_videos(query))}


@app.get("/api/stream")
async def stream(
	url: str,
	is_live: bool = Query(default=False)
):
	return EventSourceResponse(transcriber(url, is_live))


# ---------------- Frontend SPA Mount ----------------

app.mount("/", StaticFiles(directory="dist", html=True), name="static")

@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
	return FileResponse("dist/index.html")