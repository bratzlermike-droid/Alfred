"""
Alfred's Code Assistant
Read, write, debug, explain, and run Python code.
"""
import os
import re
import subprocess
import tempfile
import json
from groq import Groq

GROQ_CONFIG = os.path.expanduser("~/chief_config.txt")
CODE_MODEL = "llama-3.3-70b-versatile"


def _get_groq():
    """Get Groq client."""
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        config_path = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config_path):
            with open(config_path) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.strip().split("=", 1)[1]
    return Groq(api_key=key)


def _ask_code_llm(prompt, max_tokens=2000):
    """Send a coding prompt to Groq."""
    client = _get_groq()
    response = client.chat.completions.create(
        model=CODE_MODEL,
        messages=[
            {"role": "system", "content": "You are Alfred, an expert Python developer and coding assistant. "
             "Be concise and precise. When writing code, include only the code unless asked to explain. "
             "When debugging, identify the exact issue and provide the fix."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=max_tokens,
        temperature=0.2
    )
    return response.choices[0].message.content


def read_file(filepath):
    """Read a code file and return its contents."""
    filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
    if not os.path.exists(filepath):
        # Try common locations
        for prefix in ["", "C:/Users/ishal/", "C:/Users/ishal/Desktop/"]:
            full = os.path.join(prefix, filepath)
            if os.path.exists(full):
                filepath = full
                break
        else:
            return None, "File not found: " + filepath

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    return content, filepath


def explain_file(filepath):
    """Read a file and explain what it does."""
    content, path_or_error = read_file(filepath)
    if content is None:
        return path_or_error

    prompt = (
        "Explain what this Python code does in 3-5 sentences. "
        "Be concise and focus on the main purpose.\n\n"
        "```python\n" + content[:3000] + "\n```"
    )
    return _ask_code_llm(prompt, max_tokens=300)


def debug_error(error_text):
    """Analyze a Python error and suggest a fix."""
    prompt = (
        "I got this Python error. Explain what went wrong and how to fix it. "
        "Be concise — identify the cause and give the fix.\n\n"
        "Error:\n" + error_text
    )
    return _ask_code_llm(prompt, max_tokens=500)


def debug_file(filepath):
    """Read a file, find potential bugs, and suggest fixes."""
    content, path_or_error = read_file(filepath)
    if content is None:
        return path_or_error

    prompt = (
        "Review this Python code for bugs, issues, or improvements. "
        "List the top 3 issues and how to fix each one. Be concise.\n\n"
        "```python\n" + content[:3000] + "\n```"
    )
    return _ask_code_llm(prompt, max_tokens=600)


def write_code(description, filepath=None):
    """Generate code based on a description and optionally save to file."""
    prompt = (
        "Write Python code for the following. Output ONLY the code, no explanation.\n\n"
        "Request: " + description
    )
    code = _ask_code_llm(prompt, max_tokens=1500)

    # Extract code from markdown blocks if present
    if "```python" in code:
        code = code.split("```python")[1].split("```")[0].strip()
    elif "```" in code:
        code = code.split("```")[1].split("```")[0].strip()

    if filepath:
        filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
        return "Code written to " + filepath + ":\n\n" + code[:500]
    else:
        return code


def fix_file(filepath):
    """Read a file, fix all issues, and save it back."""
    content, resolved_path = read_file(filepath)
    if content is None:
        return resolved_path

    prompt = (
        "Fix all bugs and issues in this Python code. "
        "Output ONLY the complete fixed code, no explanation.\n\n"
        "```python\n" + content[:4000] + "\n```"
    )
    fixed = _ask_code_llm(prompt, max_tokens=2000)

    if "```python" in fixed:
        fixed = fixed.split("```python")[1].split("```")[0].strip()
    elif "```" in fixed:
        fixed = fixed.split("```")[1].split("```")[0].strip()

    # Save fixed version
    with open(resolved_path, 'w', encoding='utf-8') as f:
        f.write(fixed)
    return "Fixed and saved: " + resolved_path


def run_script(filepath):
    """Run a Python script and return the output."""
    filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
    if not os.path.exists(filepath):
        return "File not found: " + filepath

    try:
        result = subprocess.run(
            ["python", filepath],
            capture_output=True, text=True,
            timeout=15, cwd=os.path.dirname(filepath) or "."
        )
        output = ""
        if result.stdout:
            output += result.stdout.strip()
        if result.stderr:
            if output:
                output += "\n"
            output += "Errors:\n" + result.stderr.strip()
        return output if output else "Script ran successfully with no output."
    except subprocess.TimeoutExpired:
        return "Script timed out after 15 seconds."
    except Exception as e:
        return "Error running script: " + str(e)


def run_code(code):
    """Run inline Python code and return the output."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
        f.write(code)
        tmp_path = f.name

    try:
        result = subprocess.run(
            ["python", tmp_path],
            capture_output=True, text=True, timeout=15
        )
        output = ""
        if result.stdout:
            output += result.stdout.strip()
        if result.stderr:
            if output:
                output += "\n"
            output += "Errors:\n" + result.stderr.strip()
        return output if output else "Code ran successfully with no output."
    except subprocess.TimeoutExpired:
        return "Code timed out after 15 seconds."
    except Exception as e:
        return "Error: " + str(e)
    finally:
        os.unlink(tmp_path)


def open_in_editor(filepath):
    """Open a file in the default text editor."""
    filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
    if os.path.exists(filepath):
        os.startfile(filepath)
        return "Opened " + filepath
    return "File not found: " + filepath


# ── Intent Detection ──────────────────────────────────────────
def detect_code_command(message):
    """Detect code assistant commands."""
    msg = message.lower().strip()

    # Debug an error (user pastes error text)
    if any(w in msg for w in ["traceback", "error:", "exception:",
                               "syntaxerror", "nameerror", "typeerror",
                               "importerror", "attributeerror", "valueerror",
                               "indexerror", "keyerror"]):
        return ("debug_error", message)

    # Explain a file
    if any(w in msg for w in ["explain this file", "explain this code",
                               "what does this code do", "what does this file do"]):
        # Try to extract filepath
        filepath = _extract_filepath(msg)
        if filepath:
            return ("explain_file", filepath)
        return ("explain_code", message)

    # Debug/review a file
    if any(w in msg for w in ["debug this file", "review this file",
                               "check this file", "find bugs in"]):
        filepath = _extract_filepath(msg)
        if filepath:
            return ("debug_file", filepath)

    # Fix a file
    if any(w in msg for w in ["fix this file", "fix the file", "fix the code in"]):
        filepath = _extract_filepath(msg)
        if filepath:
            return ("fix_file", filepath)

    # Run a file
    if any(msg.startswith(w) for w in ["run ", "execute "]):
        filepath = _extract_filepath(msg)
        if filepath and filepath.endswith(".py"):
            return ("run_script", filepath)

    # Write code
    if any(msg.startswith(w) for w in ["write code", "write a script",
                                        "create a script", "write a program",
                                        "code me", "write python"]):
        desc = msg
        for trigger in ["write code to ", "write code for ", "write a script to ",
                        "write a script for ", "create a script to ",
                        "write a program to ", "code me ", "write python for ",
                        "write python to "]:
            if desc.startswith(trigger):
                desc = desc[len(trigger):]
                break
        return ("write_code", desc)

    # Open a file
    if any(msg.startswith(w) for w in ["edit ", "open file "]):
        filepath = _extract_filepath(msg)
        if filepath:
            return ("open_editor", filepath)

    # General code question
    if any(w in msg for w in ["how do i code", "how to code", "how do you write",
                               "python code for", "write me a function",
                               "help me code", "coding help"]):
        return ("code_question", message)

    return (None, None)


def _extract_filepath(text):
    """Try to extract a filepath from text."""
    # Look for paths with extensions
    match = re.search(r'[A-Za-z]:\\[^\s"\']+\.\w+', text)
    if match:
        return match.group()

    match = re.search(r'~/[^\s"\']+\.\w+', text)
    if match:
        return match.group()

    # Look for simple filenames
    match = re.search(r'[\w\-]+\.py', text)
    if match:
        return match.group()

    return None


def execute_code_command(action, args):
    """Execute a code assistant command."""
    if action == "debug_error":
        return debug_error(args)
    elif action == "explain_file":
        return explain_file(args)
    elif action == "explain_code":
        return _ask_code_llm("Explain this code:\n" + args, max_tokens=400)
    elif action == "debug_file":
        return debug_file(args)
    elif action == "fix_file":
        return fix_file(args)
    elif action == "run_script":
        return run_script(args)
    elif action == "write_code":
        return write_code(args)
    elif action == "open_editor":
        return open_in_editor(args)
    elif action == "code_question":
        return _ask_code_llm(args, max_tokens=500)
    return "Unknown code command"
