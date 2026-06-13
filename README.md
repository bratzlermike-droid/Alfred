"""
Chief PC Vision — see the screen and interact with it.
Uses Groq's vision model to understand what's on screen,
and pyautogui to click, type, and scroll.
"""
import pyautogui
import base64
import io
import os
import time
import re
import json
from PIL import Image, ImageGrab
from groq import Groq

# Safety settings for pyautogui
pyautogui.FAILSAFE = True  # move mouse to corner to abort
pyautogui.PAUSE = 0.3  # small delay between actions

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
VISION_MODEL = "llama-3.2-90b-vision-preview"


def get_groq_client():
    """Get or create Groq client."""
    if not GROQ_API_KEY:
        # Try to read from a local config
        config_path = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config_path):
            with open(config_path) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.strip().split("=", 1)[1]
                        return Groq(api_key=key)
    return Groq(api_key=GROQ_API_KEY)


def take_screenshot(region=None):
    """Capture the screen and return as PIL Image."""
    if region:
        img = ImageGrab.grab(bbox=region)
    else:
        img = ImageGrab.grab()
    return img


def image_to_base64(img, max_size=1024):
    """Convert PIL Image to base64, resized for the API."""
    # Resize to fit within max_size while keeping aspect ratio
    w, h = img.size
    if w > max_size or h > max_size:
        ratio = min(max_size / w, max_size / h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format='JPEG', quality=85)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


def ask_vision(prompt, img=None):
    """Send a prompt with an optional screenshot to the vision model."""
    client = get_groq_client()

    if img is None:
        img = take_screenshot()

    b64 = image_to_base64(img)

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/jpeg;base64," + b64
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
        }
    ]

    response = client.chat.completions.create(
        model=VISION_MODEL,
        messages=messages,
        max_tokens=500
    )

    return response.choices[0].message.content


def describe_screen():
    """Take a screenshot and describe what's on screen."""
    return ask_vision(
        "Describe what you see on this computer screen. "
        "Be concise — list the main application, any visible text or content, "
        "and what the user appears to be doing. 2-3 sentences max."
    )


def find_and_click(target):
    """Find an element on screen and click it."""
    prompt = (
        "I need to click on: '" + target + "'\n"
        "Look at this screenshot and tell me the approximate pixel coordinates "
        "where I should click. The screen resolution shown is the full screenshot size.\n"
        "Respond ONLY in this exact format: CLICK x y\n"
        "For example: CLICK 450 320\n"
        "If you cannot find the element, respond: NOT_FOUND"
    )

    img = take_screenshot()
    w, h = img.size
    response = ask_vision(prompt, img)

    if "NOT_FOUND" in response:
        return "Could not find '" + target + "' on screen"

    # Parse coordinates
    match = re.search(r'CLICK\s+(\d+)\s+(\d+)', response)
    if match:
        # Scale coordinates back to actual screen size
        # The vision model sees the resized image, so we need to scale
        x = int(match.group(1))
        y = int(match.group(2))

        # Clamp to screen bounds
        screen_w, screen_h = pyautogui.size()
        x = max(0, min(x, screen_w - 1))
        y = max(0, min(y, screen_h - 1))

        pyautogui.click(x, y)
        return "Clicked at (" + str(x) + ", " + str(y) + ")"

    return "Could not determine where to click"


def find_and_type(target, text):
    """Find a text field, click it, and type text."""
    result = find_and_click(target)
    if "Could not" in result:
        return result
    time.sleep(0.3)
    pyautogui.typewrite(text, interval=0.03) if text.isascii() else pyautogui.write(text)
    return "Typed '" + text + "' into " + target


def scroll_screen(direction="down", amount=5):
    """Scroll the screen up or down."""
    if direction == "up":
        pyautogui.scroll(amount)
        return "Scrolled up"
    else:
        pyautogui.scroll(-amount)
        return "Scrolled down"


def click_coordinates(x, y):
    """Click at specific screen coordinates."""
    pyautogui.click(x, y)
    return "Clicked at (" + str(x) + ", " + str(y) + ")"


def right_click(target=None):
    """Right-click at current position or on a target."""
    if target:
        result = find_and_click(target)
        if "Could not" in result:
            return result
        # Move back slightly and right-click
        x, y = pyautogui.position()
        pyautogui.rightClick(x, y)
        return "Right-clicked on " + target
    else:
        pyautogui.rightClick()
        return "Right-clicked"


def press_key(key):
    """Press a keyboard key or shortcut."""
    key = key.lower().strip()

    # Handle common shortcuts
    shortcuts = {
        "copy": ["ctrl", "c"],
        "paste": ["ctrl", "v"],
        "cut": ["ctrl", "x"],
        "undo": ["ctrl", "z"],
        "redo": ["ctrl", "y"],
        "save": ["ctrl", "s"],
        "select all": ["ctrl", "a"],
        "find": ["ctrl", "f"],
        "new tab": ["ctrl", "t"],
        "close tab": ["ctrl", "w"],
        "switch window": ["alt", "tab"],
        "minimize": ["win", "d"],
        "task view": ["win", "tab"],
    }

    if key in shortcuts:
        pyautogui.hotkey(*shortcuts[key])
        return "Pressed " + key
    else:
        pyautogui.press(key)
        return "Pressed " + key


def analyze_and_act(instruction):
    """
    Send a screenshot with an instruction to the vision model.
    The model decides what action to take.
    """
    prompt = (
        "You are controlling a computer. The user wants: '" + instruction + "'\n\n"
        "Look at this screenshot and decide what to do.\n"
        "Respond with ONE action in this exact format:\n"
        "- CLICK x y (click at coordinates)\n"
        "- TYPE text (type this text)\n"
        "- KEY keyname (press a key like enter, tab, escape)\n"
        "- HOTKEY key1 key2 (press a shortcut like ctrl c)\n"
        "- SCROLL up/down (scroll the page)\n"
        "- DESCRIBE (just describe what you see)\n"
        "- DONE message (task is complete, explain what happened)\n\n"
        "Respond with ONLY the action line, nothing else."
    )

    img = take_screenshot()
    response = ask_vision(prompt, img)
    response = response.strip()

    # Parse and execute the action
    if response.startswith("CLICK"):
        match = re.search(r'CLICK\s+(\d+)\s+(\d+)', response)
        if match:
            x, y = int(match.group(1)), int(match.group(2))
            screen_w, screen_h = pyautogui.size()
            x = max(0, min(x, screen_w - 1))
            y = max(0, min(y, screen_h - 1))
            pyautogui.click(x, y)
            return "Clicked at (" + str(x) + ", " + str(y) + ")"

    elif response.startswith("TYPE"):
        text = response[5:].strip()
        pyautogui.typewrite(text, interval=0.03) if text.isascii() else pyautogui.write(text)
        return "Typed: " + text

    elif response.startswith("KEY"):
        key = response[4:].strip()
        pyautogui.press(key)
        return "Pressed " + key

    elif response.startswith("HOTKEY"):
        keys = response[7:].strip().split()
        pyautogui.hotkey(*keys)
        return "Pressed " + " + ".join(keys)

    elif response.startswith("SCROLL"):
        direction = response[7:].strip().lower()
        return scroll_screen(direction)

    elif response.startswith("DESCRIBE"):
        return describe_screen()

    elif response.startswith("DONE"):
        return response[5:].strip()

    return response


# ── Intent Detection ──────────────────────────────────────────
def detect_vision_command(message):
    """
    Detect if a message needs screen vision.
    Returns (action, args) or (None, None).
    """
    msg = message.lower().strip()

    # Describe screen
    if any(w in msg for w in ["what's on my screen", "whats on my screen",
                               "what is on my screen", "what do you see",
                               "look at my screen", "describe my screen",
                               "what am i looking at", "read my screen",
                               "what's on screen", "whats on screen",
                               "can you see my screen", "see my screen",
                               "what do i have open", "whats on the screen"]):
        return ("describe", None)

    # Click on something
    if any(w in msg for w in ["click on", "click the", "press the",
                               "tap on", "tap the", "hit the"]):
        target = msg
        for trigger in ["click on ", "click the ", "press the ",
                        "tap on ", "tap the ", "hit the "]:
            target = target.replace(trigger, "")
        target = target.strip()
        if target:
            return ("click", target)

    # Type something
    if msg.startswith("type ") or "type in " in msg:
        text = msg
        for trigger in ["type in ", "type "]:
            if text.startswith(trigger):
                text = text[len(trigger):]
                break
        return ("type_text", text.strip())

    # Scroll
    if any(w in msg for w in ["scroll down", "scroll up", "page down", "page up"]):
        direction = "up" if "up" in msg else "down"
        return ("scroll", direction)

    # Press key / shortcut
    if any(msg.startswith(w) for w in ["press ", "hit "]):
        key = msg
        for trigger in ["press ", "hit "]:
            if key.startswith(trigger):
                key = key[len(trigger):]
                break
        return ("press_key", key.strip())

    # General vision instruction (catch-all for complex tasks)
    if any(w in msg for w in ["on my screen", "on the screen",
                               "find the", "look for", "where is the"]):
        return ("analyze", msg)

    return (None, None)


def execute_vision_command(action, args):
    """Execute a vision command."""
    if action == "describe":
        return describe_screen()
    elif action == "click":
        return find_and_click(args)
    elif action == "type_text":
        # Type at current cursor position
        pyautogui.typewrite(args, interval=0.03) if args.isascii() else pyautogui.write(args)
        return "Typed: " + args
    elif action == "scroll":
        return scroll_screen(args)
    elif action == "press_key":
        return press_key(args)
    elif action == "analyze":
        return analyze_and_act(args)
    return "Unknown vision command"
