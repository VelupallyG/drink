# main.py: Auto-check transcriptions and send to Gemini if updated, terminates on successful dispense
import google.generativeai as genai
import time
import os
from dotenv import load_dotenv
import asyncio
from tool_definitions import dispense_drink

# --- Configuration ---
load_dotenv()
api_key = os.getenv("API_KEY")
genai.configure(api_key=api_key)

# Tool mapping with drink dispenser
available_tools = {
    "dispense_drink": dispense_drink
}

# System prompt for Gemini
SYSTEM_PROMPT = """You are an AI assistant controlling physical devices...

IMPORTANT: When someone expresses thirst or wants a drink in ANY way, immediately use the dispense_drink() function. Do NOT ask questions or provide alternatives - just dispense the drink.

Examples of when to dispense a drink:
- "I'm thirsty"
- "I need a drink" 
- "Give me something to drink"
- "I want water"
- "I could use a drink"
- "Wish I had a drink"
- "I'm parched"
- "Get me a beverage"
- Any mention of being thirsty or wanting liquid refreshment

Your role is to take action, not to explain limitations. If someone wants a drink, dispense it immediately using the available tool.

If the user does not mention the word - drink or thirst; however, do not call any tool at your disposal.
"""

async def run_gemini_conversation(user_prompt: str):
    """
    Handles a single, stateless conversation with Gemini to execute a tool.
    If a successful dispense is triggered, the program will exit immediately.
    """
    print(f"\n--- New Request ---")
    print(f"USER: {user_prompt}")
    
    full_prompt = f"{SYSTEM_PROMPT}\n\nUser request: {user_prompt}"
    
    model = genai.GenerativeModel(
        model_name='gemini-1.5-flash-latest',
        tools=[dispense_drink]
    )
    
    response = model.generate_content(full_prompt)
    
    try:
        function_call = response.candidates[0].content.parts[0].function_call
        if function_call:
            function_name = function_call.name
            args = function_call.args or {}
            print(f"GEMINI: Wants to call '{function_name}' with args: {dict(args)}")
            
            function_to_call = available_tools.get(function_name)
            if function_to_call:
                call_result = function_to_call(**dict(args))

                if asyncio.iscoroutine(call_result):
                    result = await call_result
                else:
                    result = call_result

                print(f"Function result: {result}")

                # ✅ Terminate if dispense was successful
                if result == True:
                    print("✅ Successful dispense detected. Terminating to prevent repeated triggers.")
                    exit(0)
                    
                    # Create flag to stop further processing
                    with open("dispense_done.flag", "w") as f:
                        f.write("done")

            else:
                print(f"ERROR: Unknown function '{function_name}'")
        else:
            print(f"GEMINI: No function call triggered.")
    except (AttributeError, IndexError):
        try:
            print(f"GEMINI: Responded with text: '{response.text}'")
        except Exception:
            print(f"GEMINI: Non-text response received.")

def get_last_line(file_path):
    """
    Returns the last non-empty line from the specified file.
    """
    with open(file_path, 'r') as file:
        lines = [line.strip() for line in file if line.strip()]
        if lines:
            return lines[-1]
    return None

async def main():
    print("=== Drink Dispensing Assistant Ready! ===")
    print("=== Will monitor 'transcriptions/transcriptions.txt' for updates... ===\n")
    
    transcript_path = os.path.join("transcriptions", "transcriptions.txt")
    last_mtime = None
    last_processed_line = ""

    while True:
        if os.path.exists(transcript_path):
            mtime = os.path.getmtime(transcript_path)
            if last_mtime is None or mtime != last_mtime:
                last_mtime = mtime
                latest_line = get_last_line(transcript_path)
                if latest_line and latest_line != last_processed_line:
                    last_processed_line = latest_line
                    await run_gemini_conversation(latest_line)
        await asyncio.sleep(0.5)  # Faster polling for responsiveness

# --- Entry point ---
if __name__ == "__main__":
    asyncio.run(main())
