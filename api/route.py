from fastapi import APIRouter, Query, Body
from sse_starlette.sse import EventSourceResponse
from pydantic import BaseModel
from groq import AsyncGroq
import os
from fastapi.responses import PlainTextResponse
from .client import StreamingService, YoutubeClient
from .typedefs import TranslationRequest

router = APIRouter(prefix="/api",tags=["api"])
client = YoutubeClient()
gq = AsyncGroq(api_key=os.environ["GROQ_API_KEY"])

def route():
	@router.get("/transcribe")
	async def stream(url: str=Query(...)):
		service = StreamingService(url=url)
		async def generator():
			while True:
				try:
					chunk = await service.queue.get()
					if isinstance(chunk,BaseModel):
						yield chunk.model_dump_json()
					else:
						yield str(chunk)
				except Exception as e:
					yield f"error: {e}"
		return EventSourceResponse(generator())


	@router.get("/search")
	async def search(query: str=Query(...)):
		async def generator():
			for video in client.search(query=query):
				yield video.model_dump_json()
		return EventSourceResponse(generator())


	@router.post("/translate")
	async def translate(request: TranslationRequest = Body(...)):
		response = await gq.chat.completions.create(
			model="moonshotai/kimi-k2-instruct",
			messages=[
				{"role": "system", "content": f"You are an expert translator. Translate the user's input into '{request.language}'. The text is often from academic or technical lectures, so ensure precise and contextually appropriate translation of all domain-specific terminology. For incomplete or partial inputs, provide a literal translation without adding or inferring content."},
				{"role": "user", "content": request.text}
			]
		)
		content = response.choices[0].message.content
		assert content is not None
		return PlainTextResponse(content)

	return router