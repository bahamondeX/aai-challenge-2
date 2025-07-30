import json

from yt_dlp import YoutubeDL # type: ignore
from groq._utils._proxy import LazyProxy
from api.typedefs import YoutubeInfo


class YoutubeClient(LazyProxy[YoutubeDL]):
	def __load__(self) -> YoutubeDL:
		return YoutubeDL(
			params={
				"format": "bestaudio/best",
				"noplaylist": True,
				"noprogress": True,
				"nocolor": True,
				"quiet": True,
				"no_warnings": True,
				"cookiefile": "cookies.txt"
			}
		)
