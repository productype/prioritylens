#!/bin/bash
# Test runner for PriorityLens bug fixes

set -e

echo "================================"
echo "PriorityLens - Test Suite"
echo "================================"
echo ""

# Activate virtual environment if it exists
if [ -d ".venv" ]; then
    echo "Activating virtual environment..."
    source .venv/bin/activate
fi

echo ""
echo "Running Defensive Tests (15 critical tests)..."
echo "================================"
python tests/test_defensive.py

echo ""
echo "Running Workflow Tests (10 tests)..."
echo "================================"
python tests/test_workflows.py

echo ""
echo "================================"
echo "All tests completed successfully!"
echo "================================"
