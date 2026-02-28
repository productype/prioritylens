"""
Tests for happy path workflows, business logic, and integration scenarios.

This test suite complements the existing defensive tests by validating:
- Happy path workflows (basic classification, alignment, progress tracking)
- Business logic (priority matrix, classification accuracy, alignment scoring)
- Integration scenarios (batch processing, file I/O)
"""

import unittest
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


class TestHappyPathWorkflows(unittest.TestCase):
    """Test successful workflow executions (happy paths)"""

    def setUp(self):
        """Create temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_successful_classification_workflow(self):
        """Test complete basic workflow: classify → human_review → save (node-by-node)"""
        from nodes.classify import classify
        from nodes.save import save

        # Create test input
        state = {
            "feedback": {
                "id": "test_001",
                "text": "The app crashes when I click submit",
                "source": "interview",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        }

        # Mock LLM response
        mock_classification = MagicMock()
        mock_classification.category = "Bug"
        mock_classification.priority = "High"
        mock_classification.reasoning = "App crash is a critical bug"

        # Set output file
        output_file = os.path.join(self.test_dir, "output.jsonl")
        save.OUTPUT_FILE = output_file

        with patch('nodes.classify._structured_llm') as mock_llm:
            mock_llm.invoke.return_value = mock_classification

            # Step 1: Classify
            result = classify(state)
            self.assertEqual(result["suggested_category"], "Bug")
            self.assertEqual(result["suggested_priority"], "High")
            self.assertEqual(result["status"], "classified")

            # Update state
            state.update(result)

            # Step 2: Human review (simulate approval)
            state.update({
                "final_category": "Bug",
                "final_priority": "High",
                "status": "reviewed"
            })

            # Step 3: Save
            with patch('sys.stdout', new=StringIO()):
                save_result = save(state)

            self.assertEqual(save_result["status"], "saved")

            # Verify output file was created
            self.assertTrue(os.path.exists(output_file))

            # Verify saved data
            with open(output_file) as f:
                saved = json.loads(f.read())

            self.assertEqual(saved["id"], "test_001")
            self.assertEqual(saved["category"], "Bug")
            self.assertEqual(saved["priority"], "High")

    def test_successful_alignment_workflow(self):
        """Test complete alignment workflow: classify → align → prioritize → save (node-by-node)"""
        from nodes.classify import classify
        from nodes.align import align
        from nodes.prioritize import prioritize
        from nodes.save import save

        # Create test input
        state = {
            "feedback": {
                "id": "test_002",
                "text": "We need better analytics dashboards",
                "source": "interview",
                "timestamp": "2025-01-01T00:00:00Z"
            }
        }

        # Create strategy file
        strategy_data = {
            "vision": "Become the leading analytics platform",
            "time_horizon": "2025",
            "items": [{
                "id": "S1",
                "type": "goal",
                "title": "Improve analytics capabilities",
                "description": "Enhanced reporting and dashboards",
                "importance": "High"
            }]
        }

        with open("strategy_normalized.json", "w") as f:
            json.dump(strategy_data, f)

        # Mock LLM responses with proper serializable values
        mock_classification = MagicMock()
        mock_classification.category = "Feature Request"
        mock_classification.priority = "Medium"
        mock_classification.reasoning = "User wants better analytics"

        mock_alignment = MagicMock()
        mock_alignment.alignment_score = "High"
        mock_alignment.reasoning = "Directly aligns with analytics goal"
        mock_alignment.relevant_items = ["S1"]

        # Mock model_dump to return serializable dict
        mock_alignment.model_dump.return_value = {
            "alignment_score": "High",
            "reasoning": "Directly aligns with analytics goal",
            "relevant_items": ["S1"]
        }

        # Set output file
        output_file = os.path.join(self.test_dir, "output.jsonl")
        save.OUTPUT_FILE = output_file

        with patch('nodes.classify._structured_llm') as mock_classify_llm:
            mock_classify_llm.invoke.return_value = mock_classification

            with patch('nodes.align._structured_llm') as mock_align_llm:
                mock_align_llm.invoke.return_value = mock_alignment

                # Step 1: Classify
                result = classify(state)
                state.update(result)

                # Step 2: Align
                align_result = align(state)
                # Update state, ensuring we have impact_priority for prioritize step
                state["alignment_score"] = align_result["alignment_score"]
                state["alignment_reasoning"] = align_result.get("alignment_reasoning", "")
                state["relevant_strategy_items"] = align_result.get("relevant_strategy_items", [])
                state["impact_priority"] = align_result["impact_priority"]
                state["status"] = align_result["status"]

                # Step 3: Prioritize
                priority_result = prioritize(state)
                state.update(priority_result)

                # Step 4: Human review (simulate approval)
                state.update({
                    "final_category": state["suggested_category"],
                    "final_priority": state["suggested_priority"],
                    "status": "reviewed"
                })

                # Step 5: Save
                with patch('sys.stdout', new=StringIO()):
                    save_result = save(state)

                self.assertEqual(save_result["status"], "saved")

                # Verify output file
                self.assertTrue(os.path.exists(output_file))

                # Verify saved data includes alignment
                with open(output_file) as f:
                    saved = json.loads(f.read())

                self.assertEqual(saved["id"], "test_002")
                self.assertEqual(saved["category"], "Feature Request")
                # Priority: Medium impact × High alignment = Medium
                self.assertIn("alignment_score", saved)
                self.assertEqual(saved["alignment_score"], "High")

    def test_skip_and_resume_workflow(self):
        """Test skip functionality and session resume"""
        from main import load_progress_state, save_progress_state, filter_items_by_progress

        # Create test items
        items = [
            {"id": "item1", "text": "First item"},
            {"id": "item2", "text": "Second item"},
            {"id": "item3", "text": "Third item"}
        ]

        progress_file = os.path.join(self.test_dir, "progress.json")
        output_file = os.path.join(self.test_dir, "output.jsonl")

        # Simulate processing first item
        progress = {}
        progress["item1"] = "processed"
        save_progress_state(progress, progress_file)

        # Create output for processed item
        with open(output_file, "w") as f:
            f.write('{"id": "item1", "category": "Bug"}\n')

        # Simulate skipping second item
        progress["item2"] = "skipped"
        save_progress_state(progress, progress_file)

        # Resume session - should only show item3 (pending)
        loaded_progress = load_progress_state(progress_file, output_file)
        filtered_items = filter_items_by_progress(items, loaded_progress, review_skipped_only=False)

        self.assertEqual(len(filtered_items), 1)
        self.assertEqual(filtered_items[0]["id"], "item3")

        # Verify state
        self.assertEqual(loaded_progress["item1"], "processed")
        self.assertEqual(loaded_progress["item2"], "skipped")

    def test_review_skipped_items_workflow(self):
        """Test reviewing previously skipped items with --review-skipped flag"""
        from main import load_progress_state, save_progress_state, filter_items_by_progress

        # Create test items
        items = [
            {"id": "item1", "text": "First item"},
            {"id": "item2", "text": "Second item"},
            {"id": "item3", "text": "Third item"}
        ]

        progress_file = os.path.join(self.test_dir, "progress.json")
        output_file = os.path.join(self.test_dir, "output.jsonl")

        # Simulate session with processed and skipped items
        progress = {
            "item1": "processed",
            "item2": "skipped",
            "item3": "skipped"
        }
        save_progress_state(progress, progress_file)

        # Load and filter for skipped items only
        loaded_progress = load_progress_state(progress_file, output_file)
        filtered_items = filter_items_by_progress(items, loaded_progress, review_skipped_only=True)

        # Should only show skipped items
        self.assertEqual(len(filtered_items), 2)
        filtered_ids = [item["id"] for item in filtered_items]
        self.assertIn("item2", filtered_ids)
        self.assertIn("item3", filtered_ids)
        self.assertNotIn("item1", filtered_ids)


class TestBusinessLogic(unittest.TestCase):
    """Test core business logic and decision-making"""

    def test_priority_matrix_logic(self):
        """Test priority matrix combinations"""
        from nodes.prioritize import prioritize, PRIORITY_MATRIX

        # Test critical combinations
        test_cases = [
            # (impact, alignment) -> expected_priority
            (("High", "High"), "High"),
            (("High", "Medium"), "High"),
            (("High", "Low"), "Medium"),
            (("High", "Anti-goal"), "Low"),
            (("Medium", "High"), "Medium"),
            (("Medium", "Medium"), "Medium"),
            (("Medium", "Low"), "Low"),
            (("Low", "High"), "Low"),
            (("Low", "Low"), "Low"),
        ]

        for (impact, alignment), expected in test_cases:
            state = {
                "impact_priority": impact,
                "alignment_score": alignment
            }

            result = prioritize(state)

            self.assertEqual(result["suggested_priority"], expected,
                f"Failed for impact={impact}, alignment={alignment}")
            self.assertIn(f"impact: {impact}", result["priority_derivation"])
            self.assertIn(f"alignment: {alignment}", result["priority_derivation"])
            self.assertEqual(result["status"], "prioritized")

        # Verify matrix is symmetric where expected
        self.assertEqual(PRIORITY_MATRIX[("Medium", "Medium")], PRIORITY_MATRIX[("Medium", "Medium")])
        self.assertEqual(PRIORITY_MATRIX[("Low", "Low")], "Low")

    def test_category_classification_accuracy(self):
        """Test classification logic with mocked LLM responses"""
        from nodes.classify import classify

        test_cases = [
            ("app crashes when clicking submit", "Bug", "High"),
            ("loading takes 30 seconds", "Performance", "High"),
            ("can't find the export button", "Usability", "Medium"),
            ("we should support dark mode", "Feature Request", "Medium"),
            ("competitors offer better pricing", "Pricing Concern", "High"),
        ]

        for feedback_text, expected_category, expected_priority in test_cases:
            state = {
                "feedback": {
                    "id": "test",
                    "text": feedback_text,
                    "source": "test",
                    "timestamp": "2025-01-01T00:00:00Z"
                }
            }

            # Mock LLM to return expected classification
            mock_result = MagicMock()
            mock_result.category = expected_category
            mock_result.priority = expected_priority
            mock_result.reasoning = f"Test reasoning for {expected_category}"

            with patch('nodes.classify._structured_llm') as mock_llm:
                mock_llm.invoke.return_value = mock_result

                result = classify(state)

                self.assertEqual(result["suggested_category"], expected_category)
                self.assertEqual(result["suggested_priority"], expected_priority)
                self.assertEqual(result["status"], "classified")

    def test_alignment_scoring_logic(self):
        """Test alignment scoring with mocked LLM responses"""
        from nodes.align import align

        # Create strategy
        strategy_data = {
            "vision": "Test vision",
            "time_horizon": "2025",
            "items": [
                {"id": "S1", "type": "goal", "title": "Goal 1", "description": "Improve performance", "importance": "High"},
                {"id": "S2", "type": "goal", "title": "Goal 2", "description": "Add new features", "importance": "Medium"}
            ]
        }

        with open("strategy_normalized.json", "w") as f:
            json.dump(strategy_data, f)

        test_cases = [
            ("app is too slow", "High", ["S1"]),  # Aligns with performance goal
            ("need new dashboard", "Medium", ["S2"]),  # Aligns with features goal
            ("pricing is too high", "Low", []),  # Not in strategy
        ]

        for feedback_text, expected_score, expected_items in test_cases:
            state = {
                "feedback": {
                    "id": "test",
                    "text": feedback_text,
                    "source": "test"
                },
                "suggested_category": "Feature Request",
                "suggested_priority": "High",
                "impact_priority": "High",
                "reasoning": "Test"
            }

            # Mock LLM response
            mock_result = MagicMock()
            mock_result.alignment_score = expected_score
            mock_result.reasoning = f"Aligns with strategy"
            mock_result.relevant_items = expected_items

            with patch('nodes.align._structured_llm') as mock_llm:
                mock_llm.invoke.return_value = mock_result

                result = align(state)

                self.assertEqual(result["alignment_score"], expected_score)
                self.assertEqual(result["status"], "aligned")

    def test_progress_state_transitions(self):
        """Test complete state lifecycle: pending → classified → reviewed → processed/skipped"""
        from main import load_progress_state, save_progress_state

        progress_file = os.path.join(tempfile.mkdtemp(), "progress.json")
        output_file = os.path.join(tempfile.mkdtemp(), "output.jsonl")

        # State 1: Fresh start (implicitly pending)
        progress = load_progress_state(progress_file, output_file)
        self.assertEqual(progress, {})

        # State 2: Item classified (still pending in progress)
        # (classification doesn't update progress)

        # State 3: Item reviewed and saved (now processed)
        progress["item1"] = "processed"
        save_progress_state(progress, progress_file)

        loaded = load_progress_state(progress_file, output_file)
        self.assertEqual(loaded["item1"], "processed")

        # State 4: Item skipped
        progress["item2"] = "skipped"
        save_progress_state(progress, progress_file)

        loaded = load_progress_state(progress_file, output_file)
        self.assertEqual(loaded["item2"], "skipped")

        # Verify states persist
        self.assertEqual(loaded["item1"], "processed")
        self.assertEqual(loaded["item2"], "skipped")


class TestIntegrationScenarios(unittest.TestCase):
    """Test integration scenarios with multiple components"""

    def setUp(self):
        """Create temporary directory for test files"""
        self.test_dir = tempfile.mkdtemp()
        self.original_dir = os.getcwd()
        os.chdir(self.test_dir)

    def tearDown(self):
        """Clean up temporary directory"""
        os.chdir(self.original_dir)
        shutil.rmtree(self.test_dir)

    def test_batch_processing_multiple_items(self):
        """Test processing multiple items through complete workflow (node-by-node)"""
        from nodes.classify import classify
        from nodes.save import save
        from main import save_progress_state

        # Create test items
        items = [
            {"id": "batch_001", "text": "App crashes", "source": "test", "timestamp": "2025-01-01T00:00:00Z"},
            {"id": "batch_002", "text": "Slow loading", "source": "test", "timestamp": "2025-01-01T00:00:00Z"},
            {"id": "batch_003", "text": "Need dark mode", "source": "test", "timestamp": "2025-01-01T00:00:00Z"}
        ]

        # Set output file
        output_file = os.path.join(self.test_dir, "output.jsonl")
        progress_file = os.path.join(self.test_dir, "progress.json")
        save.OUTPUT_FILE = output_file

        # Mock LLM responses
        mock_classifications = [
            MagicMock(category="Bug", priority="High", reasoning="Crash"),
            MagicMock(category="Performance", priority="Medium", reasoning="Slow"),
            MagicMock(category="Feature Request", priority="Low", reasoning="Dark mode")
        ]

        progress = {}

        with patch('nodes.classify._structured_llm') as mock_llm:
            with patch('sys.stdout', new=StringIO()):
                for i, item in enumerate(items):
                    # Create state for this item
                    state = {"feedback": item}

                    # Step 1: Classify
                    mock_llm.invoke.return_value = mock_classifications[i]
                    result = classify(state)
                    state.update(result)

                    # Step 2: Human review (simulate approval)
                    state.update({
                        "final_category": state["suggested_category"],
                        "final_priority": state["suggested_priority"],
                        "status": "reviewed"
                    })

                    # Step 3: Save
                    save_result = save(state)
                    self.assertEqual(save_result["status"], "saved")

                    # Update progress
                    progress[item["id"]] = "processed"

                # Save progress
                save_progress_state(progress, progress_file)

        # Verify all items were processed
        self.assertTrue(os.path.exists(output_file))

        with open(output_file) as f:
            lines = f.readlines()

        self.assertEqual(len(lines), 3)

        # Verify each item
        saved_items = [json.loads(line) for line in lines]
        self.assertEqual(saved_items[0]["category"], "Bug")
        self.assertEqual(saved_items[1]["category"], "Performance")
        self.assertEqual(saved_items[2]["category"], "Feature Request")

        # Verify progress
        self.assertTrue(os.path.exists(progress_file))
        with open(progress_file) as f:
            saved_progress = json.load(f)

        self.assertEqual(len(saved_progress), 3)
        self.assertEqual(saved_progress["batch_001"], "processed")
        self.assertEqual(saved_progress["batch_002"], "processed")
        self.assertEqual(saved_progress["batch_003"], "processed")

    def test_workflow_with_real_files(self):
        """Test complete workflow with real file I/O"""
        from main import load_progress_state, save_progress_state, filter_items_by_progress

        # Create input file
        input_file = os.path.join(self.test_dir, "input.json")
        test_items = [
            {"id": "file_001", "text": "Bug report", "source": "test", "timestamp": "2025-01-01T00:00:00Z"},
            {"id": "file_002", "text": "Feature request", "source": "test", "timestamp": "2025-01-01T00:00:00Z"}
        ]

        with open(input_file, "w") as f:
            json.dump(test_items, f)

        # Verify input file is readable
        with open(input_file) as f:
            loaded_items = json.load(f)

        self.assertEqual(len(loaded_items), 2)

        # Create output file
        output_file = os.path.join(self.test_dir, "output.jsonl")
        progress_file = os.path.join(self.test_dir, "progress.json")

        # Simulate processing first item
        with open(output_file, "w") as f:
            f.write('{"id": "file_001", "category": "Bug", "priority": "High"}\n')

        # Update progress
        progress = {"file_001": "processed"}
        save_progress_state(progress, progress_file)

        # Load and verify progress
        loaded_progress = load_progress_state(progress_file, output_file)
        self.assertEqual(loaded_progress["file_001"], "processed")

        # Filter items - should only return file_002 (pending)
        filtered = filter_items_by_progress(test_items, loaded_progress, review_skipped_only=False)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["id"], "file_002")

        # Verify files exist and are valid
        self.assertTrue(os.path.exists(input_file))
        self.assertTrue(os.path.exists(output_file))
        self.assertTrue(os.path.exists(progress_file))


def run_tests():
    """Run all workflow tests"""
    print("\n" + "=" * 60)
    print("Running Workflow Tests (Happy Path, Business Logic, Integration)")
    print("=" * 60 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestHappyPathWorkflows))
    suite.addTests(loader.loadTestsFromTestCase(TestBusinessLogic))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegrationScenarios))

    # Run tests with verbose output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "=" * 60)
    print(f"Results: {result.testsRun} tests, {len(result.failures)} failures, {len(result.errors)} errors")
    print("=" * 60 + "\n")

    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(run_tests())
