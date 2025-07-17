import json
import os
import subprocess
import sys
import time

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

load_dotenv()

AAI_API_KEY = os.environ["AAI_API_KEY"]
SYS_MAPPING = {
    "linux": "Use Bash and apt. Example: apt install <package>",
    "darwin": "Use Zsh and Homebrew. Example: brew install <package>",
    "win32": "Use PowerShell and Chocolatey. Example: choco install <package>",
}


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
        result = subprocess.run(
            self.command,
            shell=True,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return f"Error: {result.stderr.strip()}"
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
			"Use `$CWD/workspace` as the working directory for the content/code generated"
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
                sample_rate=16000, format_turns=True, max_turn_silence=3
            )
        )

    def __load__(self):
        return Groq()


def on_begin(self: StreamingService, event: BeginEvent):
    print(f"Session started: {event.id}")
    self.messages.append({"role": "system", "content": "You are a helpful assistant."})


def on_turn(self: StreamingService, event: TurnEvent):
    print(event.transcript, end="", flush=True)
    if event.end_of_turn and not event.turn_is_formatted:
        print("-" * 100)
        self.messages.append({"role": "user", "content": event.transcript})
        client = self.__load__()
        time.sleep(1)
        response = client.chat.completions.create(
            model="moonshotai/kimi-k2-instruct",
            messages=self.messages,
            stream=True,
            tools=[ShellTool.tool_definition()],
            tool_choice="auto",
        )
        full_content = ""
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
                                print(f"Executing command: {instance.command}")
                                result = instance.run()
                                self.messages.append(
                                    {"role": "system", "content": result}
                                )
                                print(result)

            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content

                print(content, end="", flush=True)
                full_content += content

        print()
        self.messages.append({"role": "assistant", "content": full_content})


def on_terminated(self: StreamingService, event: TerminationEvent):
    print(
        f"Session terminated: {event.audio_duration_seconds} seconds of audio processed"
    )


def on_error(self: StreamingService, error: StreamingError): ...


def main():
    client = StreamingService(AAI_API_KEY)
    client.on(StreamingEvents.Begin, on_begin)  # type: ignore
    client.on(StreamingEvents.Turn, on_turn)  # type: ignore
    client.on(StreamingEvents.Termination, on_terminated)  # type: ignore
    client.on(StreamingEvents.Error, on_error)  # type: ignore

    try:
        client.stream(aai.extras.MicrophoneStream(sample_rate=16000))
    finally:
        client.disconnect(terminate=True)


if __name__ == "__main__":
    main()
