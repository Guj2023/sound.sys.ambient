from wrapper import SonicPiWrapper
from openai import OpenAI
import time
import os
import re
# Configuration similar to what might come from VS Code settings
config = {
    'sonicPiRootDirectory': '/Applications/Sonic Pi.app/Contents/Resources',
    'invertStereo': False,
    'forceMono': False,
    'safeMode': True,
    'logClearOnRun': True
}

wrapper = SonicPiWrapper(config)

# Initialize OpenAI API
client = OpenAI(
    # This is the default and can be omitted
    api_key=os.environ.get("OPENAI_API_KEY"),
)


# Example callbacks
def log_callback(message):
    print(f"LOG: {message}")


def cue_callback(cue_name, cue_value):
    print(f"CUE: {cue_name} = {cue_value}")


def run_started(run_id):
    print(f"Run started: {run_id}")


def run_ended(run_id):
    print(f"Run ended: {run_id}")


def wash_ai_response(response):
    """
    Extracts and returns all code blocks (between triple backticks) from the OpenAI response.
    Concatenates them with newlines if multiple code blocks exist.
    """
    # Find all code blocks between triple backticks
    code_blocks = re.findall(r"```(?:[a-zA-Z0-9]*)?\n(.*?)```", response, re.DOTALL)
    # Join all code blocks with newlines
    return "\n\n".join(code_blocks).strip()


def read_samples_file():
    samples_path = os.path.join(os.path.dirname(__file__), "samples.txt")
    with open(samples_path, "r", encoding="utf-8") as f:
        return f.read()


# Set callbacks
wrapper.set_log_callback(log_callback)
wrapper.set_cue_callback(cue_callback)
wrapper.set_run_started_callback(run_started)
wrapper.set_run_ended_callback(run_ended)

if wrapper.start_server():
    # Use OpenAI API to get Sonic Pi code
    prompt = input("What you want to hear;)\n: ")
    response = client.responses.create(
        model="gpt-4o",
        instructions="You are a programer and music producer. You will generate Sonic Pi code."
        "Here are some sample sounds you can use(Notice these sample are not built in, so don't add : before them):\n\n"
        "slow_rain, thunder, gun, heavy_rain, peaceful_rain, summer_night, forest_bugs\n\n"
        "Here is a snippet of Sonic Pi code about how to write a live loop:\n\n"
        "'''\n"
        "live_loop :rain1 do\n"
        "sample slow_rain, attack: 5, release: 5, amp: 1.2\n"
        "sleep 25\n"
        "end\n"
        "'''\n\n",
        input=prompt,
    )
    header = read_samples_file()
    code = wash_ai_response(response.output_text)
    code = header + "\n" + code
    # Print the code to be run
    print("Generated Sonic Pi code\n", code)
    wrapper.run_code(code)
    # Keep script running to receive messages
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        wrapper.shutdown()
        print("\nShutting down...")
