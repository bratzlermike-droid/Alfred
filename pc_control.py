"""
Alfred's Long-term Memory System
Categorized storage: facts, schedule, preferences.
Date-aware recall with deduplication and expiration.
"""
import chromadb
from chromadb.utils import embedding_functions
import datetime
import os

MEMORY_DIR = os.path.expanduser("~/chief/memory_store")


class ChiefMemory:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=MEMORY_DIR)
        self.embedder = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )

        # Separate collections for different memory types
        self.facts = self.client.get_or_create_collection(
            name="facts", embedding_function=self.embedder
        )
        self.schedule = self.client.get_or_create_collection(
            name="schedule", embedding_function=self.embedder
        )
        self.conversations = self.client.get_or_create_collection(
            name="conversations", embedding_function=self.embedder
        )

    def _today(self):
        from datetime import timezone, timedelta
        pacific = timezone(timedelta(hours=-7))
        return datetime.datetime.now(pacific)

    def _is_duplicate(self, collection, text, threshold=0.85):
        """Check if a similar entry already exists."""
        if collection.count() == 0:
            return False
        results = collection.query(
            query_texts=[text],
            n_results=1
        )
        if results and results["distances"] and results["distances"][0]:
            # Lower distance = more similar. Threshold ~0.3 means very similar.
            if results["distances"][0][0] < 0.3:
                return True
        return False

    def remember_fact(self, fact, source="user"):
        """Store a fact about the user. Skips duplicates."""
        if self._is_duplicate(self.facts, fact):
            return "already_known"
        fact_id = "fact_" + self._today().strftime("%Y%m%d_%H%M%S_%f")
        self.facts.add(
            documents=[fact],
            metadatas=[{
                "source": source,
                "stored_date": self._today().strftime("%Y-%m-%d"),
                "timestamp": self._today().isoformat(),
                "type": "fact"
            }],
            ids=[fact_id]
        )
        return fact_id

    def remember_schedule(self, item, date_str=None):
        """Store a schedule item with a specific date."""
        if date_str is None:
            date_str = self._today().strftime("%Y-%m-%d")
        if self._is_duplicate(self.schedule, item):
            return "already_scheduled"
        item_id = "sched_" + self._today().strftime("%Y%m%d_%H%M%S_%f")
        self.schedule.add(
            documents=[item],
            metadatas=[{
                "event_date": date_str,
                "stored_date": self._today().strftime("%Y-%m-%d"),
                "timestamp": self._today().isoformat(),
                "type": "schedule"
            }],
            ids=[item_id]
        )
        return item_id

    def remember_conversation(self, summary, user_message, chief_reply):
        """Store a conversation summary."""
        if self._is_duplicate(self.conversations, summary):
            return "already_stored"
        conv_id = "conv_" + self._today().strftime("%Y%m%d_%H%M%S_%f")
        self.conversations.add(
            documents=[summary],
            metadatas=[{
                "user_message": user_message[:300],
                "chief_reply": chief_reply[:300],
                "stored_date": self._today().strftime("%Y-%m-%d"),
                "timestamp": self._today().isoformat(),
                "type": "conversation"
            }],
            ids=[conv_id]
        )
        return conv_id

    def cleanup_old_schedule(self):
        """Remove schedule items older than 7 days."""
        if self.schedule.count() == 0:
            return 0
        all_items = self.schedule.get()
        cutoff = (self._today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d")
        to_delete = []
        for doc_id, meta in zip(all_items["ids"], all_items["metadatas"]):
            event_date = meta.get("event_date", "")
            if event_date and event_date < cutoff:
                to_delete.append(doc_id)
        if to_delete:
            self.schedule.delete(ids=to_delete)
        return len(to_delete)

    def recall(self, query, n_results=3):
        """Search memory with date context. Returns formatted string."""
        self.cleanup_old_schedule()
        now = self._today()
        today_str = now.strftime("%Y-%m-%d")
        today_name = now.strftime("%A, %B %d, %Y")

        parts = []

        # Search facts
        if self.facts.count() > 0:
            results = self.facts.query(
                query_texts=[query],
                n_results=min(n_results, self.facts.count())
            )
            if results["documents"][0]:
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    parts.append("Fact: " + doc)

        # Search schedule
        if self.schedule.count() > 0:
            results = self.schedule.query(
                query_texts=[query],
                n_results=min(n_results, self.schedule.count())
            )
            if results["documents"][0]:
                for doc, meta in zip(results["documents"][0], results["metadatas"][0]):
                    event_date = meta.get("event_date", "")
                    if event_date == today_str:
                        day_label = "today"
                    elif event_date == (now + datetime.timedelta(days=1)).strftime("%Y-%m-%d"):
                        day_label = "tomorrow"
                    elif event_date < today_str:
                        day_label = "past (" + event_date + ")"
                    else:
                        day_label = event_date
                    parts.append("Schedule (" + day_label + "): " + doc)

        if not parts:
            return ""

        context = "\n[MEMORY — today is " + today_name + "]\n"
        context += "\n".join(parts[:4])
        return context

    def get_all_facts(self):
        """Get all stored facts."""
        if self.facts.count() == 0:
            return []
        all_facts = self.facts.get()
        return [
            {"content": doc, "date": meta.get("stored_date", "")}
            for doc, meta in zip(all_facts["documents"], all_facts["metadatas"])
        ]

    def get_all_schedule(self):
        """Get all schedule items."""
        if self.schedule.count() == 0:
            return []
        all_items = self.schedule.get()
        return [
            {"content": doc, "event_date": meta.get("event_date", "")}
            for doc, meta in zip(all_items["documents"], all_items["metadatas"])
        ]

    def forget_all(self):
        """Clear all memories."""
        for name in ["facts", "schedule", "conversations"]:
            try:
                self.client.delete_collection(name)
            except:
                pass
        self.facts = self.client.get_or_create_collection(
            name="facts", embedding_function=self.embedder
        )
        self.schedule = self.client.get_or_create_collection(
            name="schedule", embedding_function=self.embedder
        )
        self.conversations = self.client.get_or_create_collection(
            name="conversations", embedding_function=self.embedder
        )
        return "All memories cleared."

    def get_stats(self):
        return {
            "total_facts": self.facts.count(),
            "total_schedule": self.schedule.count(),
            "total_conversations": self.conversations.count()
        }


def detect_memory_intent(message):
    """Check if the user wants to store or recall a memory."""
    msg = message.lower().strip()

    # Store a schedule item
    schedule_triggers = [
        "i have a ", "i have an ", "my appointment",
        "my meeting", "i'm going to ", "im going to ",
        "schedule for ", "on monday ", "on tuesday ",
        "on wednesday ", "on thursday ", "on friday ",
        "on saturday ", "on sunday ", "next week ",
        "this weekend ",
    ]
    if any(msg.startswith(w) or w in msg for w in schedule_triggers):
        if any(w in msg for w in ["appointment", "meeting", "session",
                                   "interview", "class", "event",
                                   "dinner", "lunch", "doctor",
                                   "dentist", "therapy", "workout"]):
            return ("store_schedule", message)

    # Store a fact
    if any(msg.startswith(w) for w in [
        "remember that", "remember my", "remember i",
        "don't forget", "keep in mind", "note that",
        "my name is", "i am ", "i like", "i love",
        "i prefer", "i live", "i work"
    ]):
        return ("store", message)

    # List memories
    if any(w in msg for w in [
        "what do you know about me", "list my info",
        "show my memories", "what have i told you",
        "show my schedule", "my schedule"
    ]):
        return ("list", message)

    # Recall
    if any(w in msg for w in [
        "do you remember", "what's my", "what is my",
        "who am i", "what do you remember"
    ]):
        return ("recall", message)

    # Clear memory
    if any(w in msg for w in [
        "forget everything", "clear your memory",
        "erase my data", "delete my memories"
    ]):
        return ("forget", message)

    return (None, None)
