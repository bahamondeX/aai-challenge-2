import json
import os
import subprocess
import sys
import time
from datetime import datetime

import assemblyai as aai  # type: ignore
from assemblyai.streaming.v3 import BeginEvent  # type: ignore
from assemblyai.streaming.v3 import (StreamingClient, StreamingClientOptions,  # type: ignore
									 StreamingError, StreamingEvents,
									 StreamingParameters, TerminationEvent,
									 TurnEvent)
from dotenv import load_dotenv
from groq import Groq
from groq.types.chat.chat_completion_message_param import \
	ChatCompletionMessageParam
from groq.types.chat.chat_completion_tool_param import ChatCompletionToolParam
from pydantic import BaseModel, Field
from rich.console import Console
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.layout import Layout
from rich.align import Align

load_dotenv()

AAI_API_KEY = os.environ["AAI_API_KEY"]
SYS_MAPPING = {
	"linux": "Use Bash and apt. Example: apt install <package>",
	"darwin": "Use Zsh and Homebrew. Example: brew install <package>",
	"win32": "Use PowerShell and Chocolatey. Example: choco install <package>",
}

console = Console()


class ShellTool(BaseModel):
	@classmethod
	def tool_definition(cls) -> ChatCompletionToolParam:
		return {
			"type": "function",
			"function": {
				"name": "ShellTool",
				"description": "Execute a bash command and return the output",
				"parameters": {
					"type": "object",
					"properties": {
						"command": {
							"type": "string",
							"description": "The bash command to execute",
						}
					},
					"required": ["command"],
				},
			},
		}

	command: str = Field(description="The bash command to execute")

	def run(self) -> str:
		with console.status(f"[bold cyan]Executing: {self.command}"):
			result = subprocess.run(
				self.command,
				shell=True,
				capture_output=True,
				text=True,
			)
		
		if result.returncode != 0:
			console.print(f"[bold red]Error executing command:[/bold red] {self.command}")
			console.print(Panel(result.stderr.strip(), title="Error Output", border_style="red"))
			return f"Error: {result.stderr.strip()}"
		
		console.print(f"[bold green]✓ Command executed successfully:[/bold green] {self.command}")
		if result.stdout.strip():
			console.print(Panel(result.stdout.strip(), title="Command Output", border_style="green"))
		
		return result.stdout.strip()


class StreamingService(StreamingClient):
	messages: list[ChatCompletionMessageParam] = [{
		"role": "system",
		"content": "\n".join([
			f"You are llmOS, a natural language interface between the user and the operating system. which is {sys.platform}. {SYS_MAPPING[sys.platform]}.",
			"You must first check user input and then plan a sequence of shell commands to execute that are most suitable to attend user request.",
			"Then the commands will be executed one by one and you will be notified about the result of the commands execution.",
			"You must always use the tools provided to you to perform the tasks. You must not perform any task that is not related to the user request.",
			"If an ERROR occurs, you must first check the error message and then plan a new sequence of commands to fix the issue.",
			"You are a resolver. If you are totally unsure of what to do, ask the user for more information.",
			"For interacting with the OS, you will use `ShellTool` and wait for the result as a `system` message."
			"Use `$PWD/workspace` as the working directory for the content/code generated",
			"Use touch, mkdir, echo to generate the files and content."
		])
	}]

	def __init__(self, api_key: str):
		super().__init__(
			StreamingClientOptions(
				api_key=api_key,
				api_host="streaming.assemblyai.com",
			)
		)
		self.connect(
			StreamingParameters(
				sample_rate=44100, format_turns=False, max_turn_silence=3
			)
		)

	def __load__(self):
		return Groq()


def create_header():
	"""Create a fancy header for the application"""
	layout = Layout()
	layout.split_column(
		Layout(name="title", size=3),
		Layout(name="info", size=2)
	)
	
	title = Text("llmOS", style="bold magenta", justify="center")
	title.stylize("bold cyan", 0, 3)
	
	info_table = Table.grid(padding=1)
	info_table.add_column(justify="center")
	info_table.add_row(f"🖥️  Platform: {sys.platform}")
	info_table.add_row(f"🕐 Started: {datetime.now().strftime('%H:%M:%S')}")
	
	layout["title"].update(Align.center(title))
	layout["info"].update(Align.center(info_table))
	
	return Panel(layout, title="Natural Language OS Interface", border_style="bright_blue")


def on_begin(self: StreamingService, event: BeginEvent):
	console.clear()
	console.print(create_header())
	console.print(f"[bold green]🎤 Session started:[/bold green] {event.id}")
	console.print("[dim]Listening for voice commands... Speak now![/dim]")


def on_turn(self: StreamingService, event: TurnEvent):
	self.set_params(StreamingParameters(
				sample_rate=44100, format_turns=False, max_turn_silence=3
			))
	if event.end_of_turn:
		# Display user input
		user_panel = Panel(
			event.transcript,
			title="🎙️  User Input",
			border_style="yellow",
			padding=(1, 2)
		)
		console.print(user_panel)
		
		self.messages.append({"role": "user", "content": event.transcript})
		client = self.__load__()
		
		# Show processing status
		with console.status("[bold cyan]🤖 Processing your request..."):
			time.sleep(1)
			response = client.chat.completions.create(
				model="moonshotai/kimi-k2-instruct",
				messages=self.messages,
				stream=True,
				tools=[ShellTool.tool_definition()],
				tool_choice="auto",
			)
		
		full_content = ""
		response_text = Text()
		
		# Create a live display for streaming response
		with Live(Panel(response_text, title="🤖 AI Response", border_style="cyan"), refresh_per_second=10) as live:
			for chunk in response:
				if chunk.choices[0].delta.tool_calls:
					tool_calls = chunk.choices[0].delta.tool_calls
					if tool_calls:
						for tool_call in tool_calls:
							if (
								tool_call.function
								and tool_call.function.name
								and tool_call.function.arguments
							):
								tool_call_args = json.loads(tool_call.function.arguments)
								if tool_call.function.name == "ShellTool":
									instance = ShellTool(**tool_call_args)
									self.messages.append(
										{"role": "assistant", "content": instance.command}
									)
									
									# Update live display to show command execution
									live.update(Panel(
										f"[bold yellow]⚡ Executing command:[/bold yellow] {instance.command}",
										title="🛠️  Command Execution",
										border_style="yellow"
									))
									
									result = instance.run()
									self.messages.append(
										{"role": "system", "content": result}
									)

				if chunk.choices[0].delta.content:
					content = chunk.choices[0].delta.content
					full_content += content
					response_text.append(content)
					live.update(Panel(response_text, title="🤖 AI Response", border_style="cyan"))

		if full_content:
			self.messages.append({"role": "assistant", "content": full_content})
		
		# Add separator
		console.print("\n" + "─" * 80 + "\n")


def on_terminated(self: StreamingService, event: TerminationEvent):
	termination_info = Table.grid(padding=1)
	termination_info.add_column(justify="left")
	termination_info.add_row(f"⏱️  Duration: {event.audio_duration_seconds:.1f} seconds")
	termination_info.add_row(f"📊 Messages: {len(self.messages)}")
	termination_info.add_row(f"🕐 Ended: {datetime.now().strftime('%H:%M:%S')}")
	
	console.print(Panel(
		termination_info,
		title="🔚 Session Terminated",
		border_style="red",
		padding=(1, 2)
	))


def on_error(self: StreamingService, error: StreamingError):
	console.print(Panel(
		f"[bold red]Error:[/bold red] {error}",
		title="❌ Streaming Error",
		border_style="red"
	))


def main():
	try:
		console.print("[bold green]🚀 Initializing llmOS...[/bold green]")
		
		client = StreamingService(AAI_API_KEY)
		client.on(StreamingEvents.Begin, on_begin)  # type: ignore
		client.on(StreamingEvents.Turn, on_turn)  # type: ignore
		client.on(StreamingEvents.Termination, on_terminated)  # type: ignore
		client.on(StreamingEvents.Error, on_error)  # type: ignore

		try:
			client.stream(aai.extras.MicrophoneStream(sample_rate=44100))
		except KeyboardInterrupt:
			console.print("\n[bold yellow]👋 Goodbye![/bold yellow]")
		finally:
			client.disconnect(terminate=True)
	
	except Exception as e:
		console.print(Panel(
			f"[bold red]Fatal Error:[/bold red] {e}",
			title="❌ Application Error",
			border_style="red"
		))


if __name__ == "__main__":
	main()