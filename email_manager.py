"""
Alfred's Document Reader
Read, summarize, and analyze PDFs, text files, and articles.
"""
import os
import re
from groq import Groq

GROQ_CONFIG = os.path.expanduser("~/chief_config.txt")


def _get_groq():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        config = os.path.expanduser("~/chief_config.txt")
        if os.path.exists(config):
            with open(config) as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        key = line.strip().split("=", 1)[1]
    return Groq(api_key=key)


def read_pdf(filepath):
    """Extract text from a PDF file."""
    filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
    if not os.path.exists(filepath):
        # Try common locations
        for prefix in ["", os.path.expanduser("~/Desktop/"),
                       os.path.expanduser("~/Documents/"),
                       os.path.expanduser("~/Downloads/")]:
            full = os.path.join(prefix, filepath)
            if os.path.exists(full):
                filepath = full
                break
        else:
            return None, "File not found: " + filepath

    try:
        import PyPDF2
        with open(filepath, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            text = ""
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text.strip(), filepath
    except ImportError:
        try:
            import pdfplumber
            with pdfplumber.open(filepath) as pdf:
                text = ""
                for page in pdf.pages:
                    text += (page.extract_text() or "") + "\n"
            return text.strip(), filepath
        except ImportError:
            return None, "PDF reader not installed. Run: pip install PyPDF2"
    except Exception as e:
        return None, "Error reading PDF: " + str(e)


def read_text_file(filepath):
    """Read a text-based file."""
    filepath = os.path.expanduser(filepath.strip().strip('"').strip("'"))
    if not os.path.exists(filepath):
        for prefix in ["", os.path.expanduser("~/Desktop/"),
                       os.path.expanduser("~/Documents/"),
                       os.path.expanduser("~/Downloads/")]:
            full = os.path.join(prefix, filepath)
            if os.path.exists(full):
                filepath = full
                break
        else:
            return None, "File not found: " + filepath

    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            return f.read(), filepath
    except Exception as e:
        return None, "Error reading file: " + str(e)


def read_document(filepath):
    """Read any supported document type."""
    ext = os.path.splitext(filepath.strip().strip('"'))[-1].lower()
    if ext == '.pdf':
        return read_pdf(filepath)
    elif ext in ['.txt', '.md', '.csv', '.json', '.log', '.xml', '.html', '.py', '.js', '.css']:
        return read_text_file(filepath)
    elif ext in ['.docx', '.doc']:
        try:
            import docx
            filepath = os.path.expanduser(filepath.strip().strip('"'))
            doc = docx.Document(filepath)
            text = "\n".join([p.text for p in doc.paragraphs])
            return text, filepath
        except ImportError:
            return None, "Word reader not installed. Run: pip install python-docx"
        except Exception as e:
            return None, "Error: " + str(e)
    else:
        return read_text_file(filepath)


def summarize_text(text, instruction="Summarize this document concisely"):
    """Send text to LLM for analysis."""
    client = _get_groq()
    # Truncate to fit context window
    text = text[:6000]
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "You are Alfred Pennyworth. Analyze documents with precision and brevity."},
            {"role": "user", "content": instruction + "\n\n---\n" + text}
        ],
        max_tokens=500,
        temperature=0.3
    )
    return response.choices[0].message.content


def summarize_document(filepath):
    """Read and summarize a document."""
    text, result = read_document(filepath)
    if text is None:
        return result
    if len(text) < 50:
        return "The document appears to be empty or too short to summarize, Sir."
    summary = summarize_text(text, "Summarize this document. Highlight the key points in 3-5 sentences.")
    return "Summary of " + os.path.basename(result) + ":\n\n" + summary


def extract_key_points(filepath):
    """Extract key points from a document."""
    text, result = read_document(filepath)
    if text is None:
        return result
    return summarize_text(text, "Extract the 5 most important key points from this document. Be concise.")


def answer_about_document(filepath, question):
    """Answer a question about a document."""
    text, result = read_document(filepath)
    if text is None:
        return result
    return summarize_text(text, "Based on this document, answer: " + question)


# ── Intent Detection ──────────────────────────────────────────
def detect_document_command(message):
    msg = message.lower().strip()

    # Extract filepath from message
    filepath = None
    path_match = re.search(r'[A-Za-z]:\\[^\s"\']+\.\w+', message)
    if path_match:
        filepath = path_match.group()
    else:
        path_match = re.search(r'~/[^\s"\']+\.\w+', message)
        if path_match:
            filepath = path_match.group()
        else:
            path_match = re.search(r'[\w\-\.]+\.(?:pdf|txt|docx|doc|md|csv)', msg)
            if path_match:
                filepath = path_match.group()

    if not filepath:
        return (None, None)

    if any(w in msg for w in ["summarize", "summary of", "sum up", "tldr",
                               "what does it say", "what is this"]):
        return ("summarize", filepath)

    if any(w in msg for w in ["key points", "main points", "important points",
                               "highlights"]):
        return ("key_points", filepath)

    if any(w in msg for w in ["read ", "open ", "show me "]):
        return ("read", filepath)

    # Default to summarize if a file is mentioned
    if filepath:
        return ("summarize", filepath)

    return (None, None)


def execute_document_command(action, args):
    if action == "summarize":
        return summarize_document(args)
    elif action == "key_points":
        return extract_key_points(args)
    elif action == "read":
        text, path = read_document(args)
        if text:
            return text[:1000]
        return path
    return "Unknown document command"
