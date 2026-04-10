import unittest

from app.database import should_bootstrap_schema
from app.security import create_access_token, decode_access_token
from app.services.ai_service import normalize_structured_chat
from app.services.behavior_modes import normalize_mode_key


class SchemaBootstrapTests(unittest.TestCase):
    def test_bootstrap_allowed_only_for_fresh_non_alembic_database(self):
        self.assertTrue(should_bootstrap_schema(set(), {"users", "chat_history"}))
        self.assertFalse(should_bootstrap_schema({"users"}, {"users", "chat_history"}))
        self.assertFalse(should_bootstrap_schema({"alembic_version"}, {"users", "chat_history"}))


class SecurityTests(unittest.TestCase):
    def test_access_token_round_trip(self):
        token = create_access_token(123)
        self.assertEqual(decode_access_token(token), "123")


class ChatStructureTests(unittest.TestCase):
    def test_normalize_structured_chat_fills_defaults(self):
        data = normalize_structured_chat(
            question="什么是操作系统的进程调度？",
            subject="操作系统",
            answer="进程调度是决定哪个进程获得 CPU 的机制。",
            structured={"topic": "进程调度"},
        )
        self.assertEqual(data["subject"], "操作系统")
        self.assertEqual(data["topic"], "进程调度")
        self.assertTrue(data["follow_ups"])
        self.assertTrue(data["pitfalls"])


class ModeTests(unittest.TestCase):
    def test_unknown_mode_falls_back_to_general(self):
        self.assertEqual(normalize_mode_key("unknown-mode"), "general")


if __name__ == "__main__":
    unittest.main()
