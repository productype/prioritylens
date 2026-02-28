"""
Lean defensive test suite - 15 critical tests.

Focused on essential error handling and edge cases that actually matter in production:
- Input validation (4 tests)
- Error recovery (3 tests)
- File operations safety (3 tests)
- Strategy/alignment (2 tests)
- Progress tracking (2 tests)
- API key (1 test)
"""

import unittest
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestInputValidation(unittest.TestCase):
    """Test input validation - 4 critical tests"""

    def setUp(self):
        """Create temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_missing_input_file(self):
        """Test error when input file doesn't exist"""
        with patch('sys.argv', ['main.py', 'nonexistent.json', '--no-alignment']):
            with patch('sys.stdout', new=StringIO()) as output:
                with self.assertRaises(SystemExit) as cm:
                    from main import main
                    main()

                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Input file not found", output.getvalue())

    def test_invalid_json_format(self):
        """Test error when file contains invalid JSON"""
        with open('invalid.json', 'w') as f:
            f.write("not valid json {")

        with patch('sys.argv', ['main.py', 'invalid.json', '--no-alignment']):
            with patch('sys.stdout', new=StringIO()) as output:
                with self.assertRaises(SystemExit) as cm:
                    from main import main
                    main()

                self.assertEqual(cm.exception.code, 1)
                self.assertIn("Invalid JSON", output.getvalue())

    def test_wrong_structure(self):
        """Test error when JSON is not an array"""
        with open('wrong.json', 'w') as f:
            json.dump({"id": "1", "text": "feedback"}, f)

        with patch('sys.argv', ['main.py', 'wrong.json', '--no-alignment']):
            with patch('sys.stdout', new=StringIO()) as output:
                with self.assertRaises(SystemExit) as cm:
                    from main import main
                    main()

                self.assertEqual(cm.exception.code, 1)
                self.assertIn("must contain a JSON array", output.getvalue())

    def test_missing_required_fields(self):
        """Test error when items missing required fields (id, text, etc.)"""
        # Missing 'id'
        with open('missing_id.json', 'w') as f:
            json.dump([{"text": "feedback", "source": "test"}], f)

        with patch('sys.argv', ['main.py', 'missing_id.json', '--no-alignment']):
            with patch('sys.stdout', new=StringIO()) as output:
                with self.assertRaises(SystemExit) as cm:
                    from main import main
                    main()

                self.assertEqual(cm.exception.code, 1)
                output_text = output.getvalue()
                self.assertIn("missing required fields", output_text)
                self.assertIn("id", output_text)


class TestErrorRecovery(unittest.TestCase):
    """Test error recovery - 3 critical tests"""

    def setUp(self):
        """Set up test state"""
        self.test_state = {
            "feedback": {
                "id": "test_001",
                "text": "Test feedback",
                "source": "test",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        }

    def test_api_retry_success(self):
        """Test retry succeeds on second attempt"""
        from nodes.classify import classify
        from anthropic import APIError

        mock_result = MagicMock()
        mock_result.category = "Bug"
        mock_result.priority = "High"
        mock_result.reasoning = "Test"

        mock_error = APIError.__new__(APIError)
        mock_error.message = "API Error"

        with patch('nodes.classify._structured_llm') as mock_llm:
            mock_llm.invoke.side_effect = [mock_error, mock_result]

            with patch('builtins.input', return_value='r'):
                with patch('sys.stdout', new=StringIO()):
                    result = classify(self.test_state)

                    self.assertEqual(result["status"], "classified")
                    self.assertEqual(mock_llm.invoke.call_count, 2)

    def test_max_retries_exhausted(self):
        """Test gives up after max retries"""
        from nodes.classify import classify, MAX_RETRIES
        from anthropic import RateLimitError

        mock_error = RateLimitError.__new__(RateLimitError)
        mock_error.message = "Rate limit"

        with patch('nodes.classify._structured_llm') as mock_llm:
            mock_llm.invoke.side_effect = mock_error

            with patch('builtins.input', side_effect=['r', 'r', 's']):
                with patch('sys.stdout', new=StringIO()):
                    result = classify(self.test_state)

                    self.assertEqual(result["status"], "skipped")
                    self.assertEqual(mock_llm.invoke.call_count, MAX_RETRIES)

    def test_unexpected_error_handling(self):
        """Test handles unexpected (non-API) errors gracefully"""
        from nodes.classify import classify

        with patch('nodes.classify._structured_llm') as mock_llm:
            mock_llm.invoke.side_effect = ValueError("Unexpected error")

            with patch('builtins.input', return_value='s'):
                with patch('sys.stdout', new=StringIO()):
                    result = classify(self.test_state)

                    self.assertEqual(result["status"], "skipped")


class TestFileOperationsSafety(unittest.TestCase):
    """Test file operations safety - 3 critical tests"""

    def setUp(self):
        """Create temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

        self.test_state = {
            "feedback": {"id": "test_001", "text": "Test", "source": "test"},
            "final_category": "Bug",
            "final_priority": "High",
            "reasoning": "Test"
        }

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_fallback_to_recovery_file(self):
        """Test fallback when primary file fails"""
        from nodes.save import save, OUTPUT_FILE

        # Make primary file unwritable
        Path(OUTPUT_FILE).touch()
        os.chmod(OUTPUT_FILE, 0o444)

        with patch('sys.stdout', new=StringIO()):
            result = save(self.test_state)

        self.assertEqual(result["status"], "saved_to_fallback")
        self.assertTrue(os.path.exists(f"{OUTPUT_FILE}.recovery.jsonl"))

        # Verify content
        with open(f"{OUTPUT_FILE}.recovery.jsonl") as f:
            saved = json.loads(f.read())
        self.assertEqual(saved["id"], "test_001")

    def test_emergency_save(self):
        """Test emergency save when both primary and fallback fail"""
        from nodes.save import save, OUTPUT_FILE

        # Make directory read-only
        test_subdir = os.path.join(self.test_dir, 'readonly')
        os.makedirs(test_subdir)
        readonly_output = os.path.join(test_subdir, 'output.jsonl')

        with patch('nodes.save.OUTPUT_FILE', readonly_output):
            os.chmod(test_subdir, 0o555)

            with patch('sys.stdout', new=StringIO()):
                result = save(self.test_state)

            self.assertEqual(result["status"], "saved_to_emergency")

            # Find emergency file
            emergency_files = [f for f in os.listdir('.') if f.startswith('emergency_save_')]
            self.assertEqual(len(emergency_files), 1)

            with open(emergency_files[0]) as f:
                saved = json.load(f)
            self.assertEqual(saved["id"], "test_001")

    def test_save_failure_user_choice(self):
        """Test user can abort or continue when all saves fail"""
        from nodes.save import save

        # Test abort
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with patch('builtins.input', return_value='a'):
                with patch('sys.stdout', new=StringIO()):
                    with self.assertRaises(SystemExit):
                        save(self.test_state)

        # Test continue
        with patch('builtins.open', side_effect=IOError("Disk full")):
            with patch('builtins.input', return_value='c'):
                with patch('sys.stdout', new=StringIO()):
                    result = save(self.test_state)
                    self.assertEqual(result["status"], "save_failed")


class TestStrategyAlignment(unittest.TestCase):
    """Test strategy and alignment - 2 critical tests"""

    def setUp(self):
        """Create temporary directory"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_missing_strategy_graceful_fallback(self):
        """Test alignment disabled when strategy file missing"""
        from main import ensure_strategy_normalized

        with patch('sys.stdout', new=StringIO()) as output:
            result = ensure_strategy_normalized(force_disable=False)

            self.assertFalse(result)
            self.assertIn("No strategy file found", output.getvalue())
            self.assertIn("Strategic alignment disabled", output.getvalue())

    def test_normalization_error_handling(self):
        """Test handles normalization failures gracefully"""
        from main import ensure_strategy_normalized

        os.makedirs('business_docs', exist_ok=True)
        Path('business_docs/strategy.md').write_text("# Strategy")

        # Test SystemExit
        with patch('normalize_strategy.normalize_strategy', side_effect=SystemExit(1)):
            with patch('sys.stdout', new=StringIO()) as output:
                result = ensure_strategy_normalized(force_disable=False)

                self.assertFalse(result)
                self.assertIn("Strategy normalization failed", output.getvalue())

        # Test unexpected exception
        with patch('normalize_strategy.normalize_strategy', side_effect=ValueError("Error")):
            with patch('sys.stdout', new=StringIO()) as output:
                result = ensure_strategy_normalized(force_disable=False)

                self.assertFalse(result)
                self.assertIn("Unexpected error", output.getvalue())


class TestProgressTracking(unittest.TestCase):
    """Test progress tracking - 2 critical tests"""

    def test_progress_persistence(self):
        """Test progress save/load round trip works"""
        from main import load_progress_state, save_progress_state

        with tempfile.TemporaryDirectory() as tmpdir:
            progress_file = os.path.join(tmpdir, "progress.json")
            output_file = os.path.join(tmpdir, "output.jsonl")

            # Save progress
            original = {"item1": "processed", "item2": "skipped", "item3": "pending"}
            save_progress_state(original, progress_file)

            # Load it back
            loaded = load_progress_state(progress_file, output_file)

            self.assertEqual(loaded, original)
            self.assertTrue(os.path.exists(progress_file))

    def test_filter_by_progress_state(self):
        """Test filtering items by pending vs skipped state"""
        from main import filter_items_by_progress

        items = [
            {"id": "item1", "text": "Test 1"},
            {"id": "item2", "text": "Test 2"},
            {"id": "item3", "text": "Test 3"},
        ]

        progress = {"item1": "processed", "item2": "skipped"}

        # Test pending mode
        pending = filter_items_by_progress(items, progress, review_skipped_only=False)
        pending_ids = [item["id"] for item in pending]
        self.assertEqual(pending_ids, ["item3"])

        # Test skipped mode
        skipped = filter_items_by_progress(items, progress, review_skipped_only=True)
        skipped_ids = [item["id"] for item in skipped]
        self.assertEqual(skipped_ids, ["item2"])


class TestAPIKey(unittest.TestCase):
    """Test API key validation - 1 critical test"""

    def test_api_key_required(self):
        """Test missing API key causes early exit with clear error"""
        original_env = os.environ.copy()
        os.environ.pop("ANTHROPIC_API_KEY", None)

        try:
            with patch('dotenv.load_dotenv'):
                with patch('sys.argv', ['main.py', 'test.json', '--no-alignment']):
                    with patch('sys.stdout', new=StringIO()) as output:
                        if 'main' in sys.modules:
                            del sys.modules['main']

                        with self.assertRaises(SystemExit) as cm:
                            from main import main
                            main()

                        self.assertEqual(cm.exception.code, 1)
                        output_text = output.getvalue()
                        self.assertIn("ANTHROPIC_API_KEY", output_text)
                        self.assertIn("not set", output_text)
        finally:
            os.environ.clear()
            os.environ.update(original_env)


def run_tests():
    """Run all defensive tests"""
    print("\n" + "=" * 60)
    print("Running Defensive Tests (15 Critical Tests)")
    print("=" * 60 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestInputValidation))
    suite.addTests(loader.loadTestsFromTestCase(TestErrorRecovery))
    suite.addTests(loader.loadTestsFromTestCase(TestFileOperationsSafety))
    suite.addTests(loader.loadTestsFromTestCase(TestStrategyAlignment))
    suite.addTests(loader.loadTestsFromTestCase(TestProgressTracking))
    suite.addTests(loader.loadTestsFromTestCase(TestAPIKey))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"Results: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60 + "\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
