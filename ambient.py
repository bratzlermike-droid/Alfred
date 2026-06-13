"""
Alfred's Autonomous Agent
Give a goal, Alfred plans and executes multi-step tasks.
Uses all available tools: web search, code, files, PC control.
"""
import os
import re
import json
import time
import requests
from groq import Groq

GROQ_CONFIG = os.path.expanduser("~/chief_config.txt")
AGENT_MODEL = "llama-3.3-70b-versatile"
SERVER_URL = os.environ.get("ALFRED_SERVER_URL", "http://localhost:8000")
AUTH_TOKEN = "Bearer " + os.environ.get("ALFRED_AUTH_TOKEN", "change-me-in-env")
MAX_STEPS = 8


def _get_groq():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        config_path = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config_path):
            with open(config_path) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.strip().split("=", 1)[1]
    return Groq(api_key=key)


AGENT_SYSTEM = """You are Alfred, an autonomous AI agent. You receive a goal and must accomplish it step by step.

Available actions (respond with EXACTLY one per turn):

ACTION: search | ARGS: query
  Search the web for information.

ACTION: write_file | ARGS: filepath
CONTENT:
(file content here)
END_CONTENT
  Write content to a file.

ACTION: read_file | ARGS: filepath
  Read a file's contents.

ACTION: run_python | ARGS: description
CODE:
(python code here)
END_CODE
  Run Python code and get the output.

ACTION: open_app | ARGS: app_name
  Open an application.

ACTION: report | ARGS: none
RESULT:
(your final report/answer to the user)
END_RESULT
  Deliver the final result. Use this when the task is complete.

Rules:
- Execute ONE action per turn. You will see the result, then decide the next action.
- Always end with a "report" action to deliver the final result.
- Be efficient — use the minimum steps needed.
- If a step fails, try an alternative approach.
- Never repeat a failed action more than once.
"""


def _parse_action(response):
    """Parse the agent's response into an action."""
    text = response.strip()

    # Parse ACTION line
    action_match = re.search(r'ACTION:\s*(\w+)\s*\|\s*ARGS:\s*(.*)', text)
    if not action_match:
        return None, None, None

    action = action_match.group(1).strip()
    args = action_match.group(2).strip()

    # Parse CONTENT block (for write_file)
    content = None
    content_match = re.search(r'CONTENT:\n(.*?)\nEND_CONTENT', text, re.DOTALL)
    if content_match:
        content = content_match.group(1)

    # Parse CODE block (for run_python)
    code_match = re.search(r'CODE:\n(.*?)\nEND_CODE', text, re.DOTALL)
    if code_match:
        content = code_match.group(1)

    # Parse RESULT block (for report)
    result_match = re.search(r'RESULT:\n(.*?)\nEND_RESULT', text, re.DOTALL)
    if result_match:
        content = result_match.group(1)

    return action, args, content


def _execute_action(action, args, content):
    """Execute a single agent action and return the result."""

    if action == "search":
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.text(args, max_results=5))
            if not results:
                return "No results found for: " + args
            output = ""
            for i, r in enumerate(results, 1):
                output += str(i) + ". " + r.get("title", "") + "\n"
                output += "   " + r.get("body", "") + "\n\n"
            return output.strip()
        except Exception as e:
            return "Search error: " + str(e)

    elif action == "write_file":
        try:
            filepath = os.path.expanduser(args.strip().strip('"').strip("'"))
            os.makedirs(os.path.dirname(filepath) or '.', exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content or "")
            return "File written: " + filepath
        except Exception as e:
            return "Write error: " + str(e)

    elif action == "read_file":
        try:
            filepath = os.path.expanduser(args.strip().strip('"').strip("'"))
            if not os.path.exists(filepath):
                return "File not found: " + filepath
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                text = f.read()
            return text[:3000]
        except Exception as e:
            return "Read error: " + str(e)

    elif action == "run_python":
        try:
            import subprocess
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py',
                                             delete=False, encoding='utf-8') as f:
                f.write(content or "")
                tmp = f.name
            result = subprocess.run(
                ["python", tmp], capture_output=True,
                text=True, timeout=30
            )
            os.unlink(tmp)
            output = ""
            if result.stdout:
                output += result.stdout.strip()
            if result.stderr:
                if output:
                    output += "\n"
                output += "Error: " + result.stderr.strip()
            return output if output else "Code ran with no output."
        except subprocess.TimeoutExpired:
            return "Code timed out after 30 seconds."
        except Exception as e:
            return "Run error: " + str(e)

    elif action == "open_app":
        try:
            from pc_control import open_app
            return open_app(args)
        except Exception as e:
            return "App error: " + str(e)

    elif action == "report":
        return content or args

    return "Unknown action: " + action


def run_agent(goal, callbacks=None):
    """
    Run the autonomous agent with a goal.
    callbacks dict:
      - on_step(step_num, action, args): called before each step
      - on_result(step_num, result): called after each step
      - on_complete(final_report): called when done
    """
    client = _get_groq()
    messages = [
        {"role": "system", "content": AGENT_SYSTEM},
        {"role": "user", "content": "GOAL: " + goal}
    ]

    steps = []
    final_report = None

    for step in range(MAX_STEPS):
        # Ask the agent what to do next
        try:
            response = client.chat.completions.create(
                model=AGENT_MODEL,
                messages=messages,
                max_tokens=1500,
                temperature=0.3
            )
            reply = response.choices[0].message.content
        except Exception as e:
            final_report = "Agent error: " + str(e)
            break

        # Parse the action
        action, args, content = _parse_action(reply)

        if not action:
            # Model didn't follow format — try to salvage
            final_report = reply
            break

        # Notify callback
        if callbacks and "on_step" in callbacks:
            callbacks["on_step"](step + 1, action, args)

        # Check if done
        if action == "report":
            final_report = content or args
            if callbacks and "on_result" in callbacks:
                callbacks["on_result"](step + 1, final_report)
            break

        # Execute the action
        result = _execute_action(action, args, content)
        steps.append({
            "step": step + 1,
            "action": action,
            "args": args,
            "result": result[:1000]
        })

        if callbacks and "on_result" in callbacks:
            callbacks["on_result"](step + 1, action + ": " + result[:200])

        # Feed result back to the agent
        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": "RESULT of " + action + ":\n" + result[:2000] + "\n\nContinue with the next action, or use 'report' if the task is complete."})

        time.sleep(0.5)

    if final_report is None:
        final_report = "I was unable to complete the task within " + str(MAX_STEPS) + " steps, Sir."

    if callbacks and "on_complete" in callbacks:
        callbacks["on_complete"](final_report)

    return final_report, steps


# ── Intent Detection ──────────────────────────────────────────
def detect_agent_command(message):
    """Detect if this is a complex multi-step task for the autonomous agent."""
    msg = message.lower().strip()

    triggers = [
        "research ", "investigate ", "find out everything about ",
        "write a report on ", "write a report about ",
        "analyze ", "compare ", "build me ",
        "create a ", "make a ", "put together ",
        "figure out ", "look into ", "deep dive ",
        "compile ", "gather information on ",
        "write an essay ", "write an article ",
        "plan ", "design ", "draft ",
    ]

    if any(msg.startswith(t) for t in triggers):
        return ("agent", message)

    # Also trigger on explicit agent requests
    if any(w in msg for w in ["step by step", "autonomous", "work on this",
                               "handle this for me", "take care of"]):
        return ("agent", message)

    return (None, None)
