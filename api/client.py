from __future__ import annotations
from pathlib import Path
import re
import os
import requests
import typing as tp
import asyncio as aio
from yt_dlp import YoutubeDL # type: ignore
from groq._utils._proxy import LazyProxy
from dataclasses import dataclass, field
from assemblyai.streaming.v3 import BeginEvent, StreamingClientOptions, TurnEvent, TerminationEvent, StreamingError, StreamingClient, StreamingEvents, StreamingParameters	 # type: ignore
from .typedefs import YoutubeInfo
from .utils import format_audio_from_youtube_stream_url

@dataclass
class YoutubeClient(LazyProxy[YoutubeDL]):
	cookiefile:Path = field(default=Path(__file__).parent / "cookies.txt")
	format:str = field(default="bestaudio/best")
	quiet:bool = field(default=True)
	nocolor:bool = field(default=True)
	noprogress:bool = field(default=True)
	no_warnings:bool = field(default=True)
	noplaylist:bool = field(default=True)
	download:bool = field(default=False)

	def __load__(self) -> YoutubeDL:
		return YoutubeDL(
			params={
				"format": self.format,
				"noplaylist": self.noplaylist,
				"noprogress": self.noprogress,
				"nocolor": self.nocolor,
				"quiet": self.quiet,
				"no_warnings": self.no_warnings,
				"cookiefile": self.cookiefile
			}
		)

	@classmethod
	def fetch(cls, * , url:str) -> YoutubeInfo:
		info = cls.__load__().extract_info(url, download=False) # type: ignore
		return YoutubeInfo.model_validate(info)

	def search(self, * , query:str) -> tp.Generator[YoutubeInfo, None, None]:
		response = requests.get(f"https://www.youtube.com/results?search_query={query}")
		response.raise_for_status()
		pattern = re.compile(r"/watch\?v=([a-zA-Z0-9_-]+)")
		matches = set(pattern.findall(response.text))
		with self.__load__() as ydl:
			for match in matches:
				try:
					info = ydl.extract_info(f"https://www.youtube.com/watch?v={match}", download=False) # type: ignore
					yield YoutubeInfo.model_validate(info)
				except Exception as e:
					print(e)
					continue
	def stream(self, * , url:str):
		info = self.fetch(url=url)
		stream_url = info.url
		for chunk in format_audio_from_youtube_stream_url(stream_url):
			yield chunk

@dataclass
class StreamingService(StreamingClient,tp.Iterator[bytes]):
	url:str
	params:StreamingClientOptions = field(default_factory=lambda: StreamingClientOptions(api_key=os.environ["AAI_API_KEY"]))
	queue:aio.Queue[BeginEvent | TurnEvent | TerminationEvent | StreamingError] = field(default_factory=aio.Queue[BeginEvent | TurnEvent | TerminationEvent | StreamingError])
	client:YoutubeClient = field(default_factory=YoutubeClient)

	def __post_init__(self: "StreamingService"):
		super().__init__(self.params)
		self.on(StreamingEvents.Begin, self.on_begin) # type: ignore
		self.on(StreamingEvents.Turn, self.on_turn) # type: ignore
		self.on(StreamingEvents.Termination, self.on_termination) # type: ignore
		self.on(StreamingEvents.Error, self.on_error) # type: ignore
		self.connect(
			StreamingParameters(
				sample_rate=16000,
				format_turns=True
			)
		)

	def on_begin(self: StreamingService, event: "BeginEvent"):
		self.queue.put_nowait(event)
	def on_turn(self: StreamingService, event: TurnEvent):
		self.queue.put_nowait(event)

	def on_termination(self: StreamingService, event: TerminationEvent):
		self.queue.put_nowait(event)
	def on_error(self: StreamingService, event: StreamingError):
		self.queue.put_nowait(event)

	def __iter__(self: StreamingService) -> tp.Iterator[bytes]:
		for chunk in self.client.stream(url=self.url):
			yield chunk

	def __next__(self: StreamingService) -> bytes:
		return next(self.client.stream(url=self.url))

	def __call__(self: StreamingService):
		return self.stream(self.client.stream(url=self.url))

	def __del__(self: StreamingService):
		self.disconnect()