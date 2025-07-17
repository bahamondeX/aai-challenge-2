import json
import os
import pathlib
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
from markdown_normalization import extract_codeblocks

load_dotenv()

AAI_API_KEY = os.environ["AAI_API_KEY"]
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

# Enhanced system configurations
SYS_MAPPING = {
	"linux": {
		"shell": "bash",
		"package_manager": "apt",
		"install_cmd": "sudo apt update && sudo apt install -y",
		"search_cmd": "apt search",
		"info_cmd": "apt show",
		"remove_cmd": "sudo apt remove -y",
		"update_cmd": "sudo apt update && sudo apt upgrade -y",
		"python_cmd": "python3",
		"pip_cmd": "pip3"
	},
	"darwin": {
		"shell": "zsh",
		"package_manager": "brew",
		"install_cmd": "brew install",
		"search_cmd": "brew search",
		"info_cmd": "brew info",
		"remove_cmd": "brew uninstall",
		"update_cmd": "brew update && brew upgrade",
		"python_cmd": "python3",
		"pip_cmd": "pip3"
	},
	"win32": {
		"shell": "powershell",
		"package_manager": "choco",
		"install_cmd": "choco install -y",
		"search_cmd": "choco search",
		"info_cmd": "choco info",
		"remove_cmd": "choco uninstall -y",
		"update_cmd": "choco upgrade all -y",
		"python_cmd": "python",
		"pip_cmd": "pip"
	}
}

# Configuration class for better management
class Config:
	MODEL = "moonshotai/kimi-k2-instruct"  # Better model for reasoning
	MAX_TOKENS = 4096
	TEMPERATURE = 0.1
	WORKSPACE_DIR = "workspace"
	SAMPLE_RATE = 48000 if sys.platform == "darwin" else 16000
	MAX_TURN_SILENCE = 2
	STREAMING_CHUNK_SIZE = 1024

console = Console()


class ShellTool(BaseModel):
	@classmethod
	def tool_definition(cls) -> ChatCompletionToolParam:
		sys_config = SYS_MAPPING.get(sys.platform, SYS_MAPPING["linux"])
		return {
			"type": "function",
			"function": {
				"name": "ShellTool",
				"description": f"Execute shell commands on {sys.platform} using {sys_config['shell']}. Returns output or error messages.",
				"parameters": {
					"type": "object",
					"properties": {
						"command": {
							"type": "string",
							"description": f"Shell command to execute. Use {sys_config['shell']} syntax for {sys.platform}",
						},
						"working_dir": {
							"type": "string",
							"description": "Working directory for command execution, all scripts and code generated must be saved here.",
							"default": Config.WORKSPACE_DIR
						},
						"timeout": {
							"type": "integer",
							"description": "Command timeout in seconds",
							"default": 30
						}
					},
					"required": ["command"],
				},
			},
		}

	command: str = Field(description="Shell command to execute")
	working_dir: str = Field(default=Config.WORKSPACE_DIR, description="Working directory")
	timeout: int = Field(default=30, description="Command timeout")

	def run(self) -> str:
		# Ensure workspace directory exists
		os.makedirs(self.working_dir, exist_ok=True)
		
		with console.status(f"[bold cyan]Executing: {self.command}"):
			try:
				result = subprocess.run(
					self.command,
					shell=True,
					capture_output=True,
					text=True,
					cwd=self.working_dir,
					timeout=self.timeout,
					env=dict(os.environ, PYTHONPATH=os.getcwd())
				)
				code_blocks = extract_codeblocks(result.stdout)
				if code_blocks:
					code_file = pathlib.Path(self.working_dir)/"workspace"/f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.md"
					code_file.write_text(code_blocks)
					return f"Code blocks saved to {code_file}"
				else:
					return result.stdout.strip()
			except subprocess.TimeoutExpired:
				error_msg = f"Command timed out after {self.timeout} seconds"
				console.print(f"[bold red]⏰ Timeout:[/bold red] {self.command}")
				console.print(Panel(error_msg, title="Timeout Error", border_style="red"))
				return f"Error: {error_msg}"
		
		if result.returncode != 0:
			console.print(f"[bold red]❌ Command failed:[/bold red] {self.command}")
			console.print(Panel(result.stderr.strip(), title="Error Output", border_style="red"))
			return f"Error (exit code {result.returncode}): {result.stderr.strip()}"
		
		console.print(f"[bold green]✅ Command executed successfully:[/bold green] {self.command}")
		if result.stdout.strip():
			console.print(Panel(result.stdout.strip(), title="Command Output", border_style="green"))
		
		return result.stdout.strip() if result.stdout.strip() else "Command executed successfully (no output)"


class StreamingService(StreamingClient):
	def __init__(self, api_key: str):
		super().__init__(
			StreamingClientOptions(
				api_key=api_key,
				api_host="streaming.assemblyai.com",
			)
		)
		self.connect(
			StreamingParameters(
				sample_rate=Config.SAMPLE_RATE, 
				format_turns=True, 
				max_turn_silence=Config.MAX_TURN_SILENCE
			)
		)
		self.messages: list[ChatCompletionMessageParam] = self._initialize_system_prompt()

	def _initialize_system_prompt(self) -> list[ChatCompletionMessageParam]:
		sys_config = SYS_MAPPING.get(sys.platform, SYS_MAPPING["linux"])
		current_dir = os.getcwd()
		
		system_prompt = f"""You are llmOS, an advanced natural language operating system interface.

## SYSTEM INFORMATION
- Platform: {sys.platform}
- Shell: {sys_config['shell']}
- Package Manager: {sys_config['package_manager']}
- Working Directory: {current_dir}
- Workspace: {Config.WORKSPACE_DIR}/
- Python Command: {sys_config['python_cmd']}
- Pip Command: {sys_config['pip_cmd']}

## CORE CAPABILITIES
You can execute shell commands to:
- File/directory operations (create, read, write, delete, move, copy)
- Package management ({sys_config['install_cmd']}, {sys_config['remove_cmd']})
- System information (ps, top, df, free, uname)
- Network operations (ping, curl, wget)
- Development tasks (git, npm, pip, compilation)
- Process management (kill, jobs, nohup)
- Text processing (grep, sed, awk, sort)

## BEHAVIOR GUIDELINES
1. **Safety First**: Never execute destructive commands without explicit user confirmation
2. **Efficiency**: Use single commands when possible, chain operations intelligently
3. **Error Handling**: If a command fails, analyze the error and suggest alternatives
4. **Workspace Management**: Use {Config.WORKSPACE_DIR}/ for user-generated content
5. **Confirmation**: Ask for clarification on ambiguous requests
6. **Documentation**: Explain complex operations briefly
7. **Security**: Avoid commands that could compromise system security

## COMMAND EXECUTION STRATEGY
1. Parse user intent carefully
2. Plan command sequence logically
3. Execute commands incrementally
4. Validate results before proceeding
5. Handle errors gracefully with alternatives
6. Provide meaningful feedback

## COMMON PATTERNS
- Save all the files and content generated in the workspace directory.
- Install package: {sys_config['install_cmd']} <package>
- Create project: mkdir project && cd project && {sys_config['python_cmd']} -m venv venv
- Git operations: git init, git add, git commit, git push
- File operations: touch, echo, cat, ls, find
- System monitoring: ps aux, df -h, free -h, top

## RESTRICTIONS
- No system-critical modifications without explicit permission
- No access to sensitive directories (/etc, /root, system32)
- No network attacks or malicious activities
- No permanent system configuration changes without approval

Always use ShellTool for command execution. Be helpful, efficient, and safe."""

		return [{
			"role": "system",
			"content": system_prompt
		}]

	def __load__(self):
		return Groq(api_key=GROQ_API_KEY)


def create_header():
	"""Create a fancy header for the application"""
	layout = Layout()
	layout.split_column(
		Layout(name="title", size=3),
		Layout(name="info", size=3)
	)
	
	title = Text("llmOS", style="bold magenta", justify="center")
	title.stylize("bold cyan", 0, 5)
	
	sys_config = SYS_MAPPING.get(sys.platform, SYS_MAPPING["linux"])
	info_table = Table.grid(padding=1)
	info_table.add_column(justify="center")
	info_table.add_row(f"🖥️  Platform: {sys.platform}")
	info_table.add_row(f"🐚 Shell: {sys_config['shell']}")
	info_table.add_row(f"📦 Package Manager: {sys_config['package_manager']}")
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
		sample_rate=Config.SAMPLE_RATE, 
		format_turns=True, 
		max_turn_silence=Config.MAX_TURN_SILENCE
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
		with console.status("[bold cyan]🧠 Analyzing request and planning commands..."):
			time.sleep(1)
			response = client.chat.completions.create(
				model=Config.MODEL,
				messages=self.messages,
				max_tokens=Config.MAX_TOKENS,
				temperature=Config.TEMPERATURE,
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
								try:
									tool_call_args = json.loads(tool_call.function.arguments)
									if tool_call.function.name == "ShellTool":
										instance = ShellTool(**tool_call_args)
										self.messages.append(
											{"role": "assistant", "content": f"Executing: {instance.command}"}
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
								except json.JSONDecodeError as e:
									console.print(f"[bold red]Error parsing tool call:[/bold red] {e}")
								except Exception as e:
									console.print(f"[bold red]Error executing tool:[/bold red] {e}")

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
			client.stream(aai.extras.MicrophoneStream(sample_rate=Config.SAMPLE_RATE))
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