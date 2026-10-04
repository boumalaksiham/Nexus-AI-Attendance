"""Startup and password regression tests; biometric inference is not exercised."""
import importlib
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
import bcrypt


class StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.previous_directory = os.getcwd()
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(cls.root))
        os.chdir(cls.temp.name)
        # A face_recognition import stub isolates startup/auth checks from native
        # camera dependencies. No face-recognition behavior is certified here.
        cls.face_patch = patch.dict(sys.modules, {"face_recognition": types.ModuleType("face_recognition")})
        cls.env_patch = patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-not-used", "FLASK_SECRET_KEY": "test-session-secret"})
        cls.face_patch.start()
        cls.env_patch.start()
        cls.module = importlib.import_module("app")
        cls.client = cls.module.app.test_client()

    @classmethod
    def tearDownClass(cls):
        cls.module.conn.close()
        cls.env_patch.stop()
        cls.face_patch.stop()
        os.chdir(cls.previous_directory)
        cls.temp.cleanup()

    def test_public_home_and_protected_password_route(self):
        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get("/").status_code, 200)
        self.assertEqual(self.client.post("/change-password").status_code, 302)

    def test_password_change_checks_hash_and_stores_new_hash(self):
        with self.module.connect_db() as conn:
            conn.execute("DELETE FROM students WHERE enrollment = 'TEST'")
            conn.execute("INSERT INTO students(enrollment,name,email,password) VALUES(?,?,?,?)",
                         ("TEST", "Test", "test@example.invalid", bcrypt.hashpw(b"old-password", bcrypt.gensalt()).decode()))
        with self.client.session_transaction() as session:
            session["student_id"] = "TEST"
        self.client.post("/change-password", data={"old_password": "wrong", "new_password": "new-password"})
        with self.module.connect_db() as conn:
            before = conn.execute("SELECT password FROM students WHERE enrollment='TEST'").fetchone()[0]
        self.assertTrue(bcrypt.checkpw(b"old-password", before.encode()))
        self.client.post("/change-password", data={"old_password": "old-password", "new_password": "new-password"})
        with self.module.connect_db() as conn:
            after = conn.execute("SELECT password FROM students WHERE enrollment='TEST'").fetchone()[0]
        self.assertNotEqual(after, "new-password")
        self.assertTrue(bcrypt.checkpw(b"new-password", after.encode()))

    def test_embeddings_keep_owner_for_variable_capture_counts(self):
        import json
        import recognize_student_face as recognition
        with self.module.connect_db() as conn:
            conn.execute("INSERT INTO students(enrollment,name,face_encoding,email,password) VALUES(?,?,?,'test' || ?,'unused')", ("A", "A", json.dumps([[0.0]*128]), "A"))
            conn.execute("INSERT INTO students(enrollment,name,face_encoding,email,password) VALUES(?,?,?,'test' || ?,'unused')", ("B", "B", json.dumps([[1.0]*128, [2.0]*128]), "B"))
            conn.execute("INSERT INTO student_classes(enrollment,class_id) VALUES(?,?)", ("A", 999))
            conn.execute("INSERT INTO student_classes(enrollment,class_id) VALUES(?,?)", ("B", 999))
        vectors, owners = recognition.load_class_encodings(999)
        self.assertEqual(vectors.shape, (3, 128))
        self.assertEqual(owners, ["A", "B", "B"])
        self.assertEqual(recognition.load_class_encodings(-1)[0].shape, (0, 128))


if __name__ == "__main__":
    unittest.main()
