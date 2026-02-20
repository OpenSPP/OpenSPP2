#!/bin/bash
# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
#
# Run integration tests for spp_aggregation with MIS demo data.
#
# This script installs both spp_aggregation and spp_mis_demo_v2 to enable
# comprehensive integration testing with realistic demo data.
#
# Usage:
#   ./spp_aggregation/tests/run_integration_tests.sh
#
# Options:
#   --unit-only     Run unit tests only (skip demo data generation)
#   --verbose       Show detailed test output
#   --help          Show this help message

set -e

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

# Default options
UNIT_ONLY=0

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --unit-only)
            UNIT_ONLY=1
            shift
            ;;
        --verbose)
            # Verbose flag for future use (currently not implemented)
            shift
            ;;
        --help)
            echo "Run integration tests for spp_aggregation"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --unit-only     Run unit tests only (skip demo data)"
            echo "  --verbose       Show detailed test output"
            echo "  --help          Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                    # Run full integration tests with demo data"
            echo "  $0 --unit-only        # Run unit tests only (faster)"
            echo "  $0 --verbose          # Show detailed output"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Run '$0 --help' for usage information"
            exit 1
            ;;
    esac
done

# Change to repo root
cd "$REPO_ROOT"

# Run tests
if [ $UNIT_ONLY -eq 1 ]; then
    echo "=========================================="
    echo "Running UNIT tests for spp_aggregation"
    echo "=========================================="
    echo ""
    echo "Integration tests will be skipped (spp_mis_demo_v2 not installed)"
    echo ""

    ./scripts/test_single_module.sh spp_aggregation

else
    echo "=========================================="
    echo "Running INTEGRATION tests for spp_aggregation"
    echo "=========================================="
    echo ""
    echo "This will:"
    echo "  - Install spp_aggregation + spp_mis_demo_v2"
    echo "  - Generate ~50 household groups with members"
    echo "  - Run 100+ tests including integration scenarios"
    echo "  - Test k-anonymity, performance, privacy protection"
    echo ""
    echo "Expected duration: 3-5 minutes"
    echo ""
    read -p "Continue? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Cancelled."
        exit 0
    fi

    # Run with both modules
    ./scripts/test_single_module.sh spp_aggregation,spp_mis_demo_v2
fi

# Show summary
echo ""
echo "=========================================="
echo "Test run complete!"
echo "=========================================="
echo ""

if [ $UNIT_ONLY -eq 0 ]; then
    echo "Integration tests were executed with demo data."
    echo ""
    echo "Test coverage:"
    echo "  ✓ Area-based aggregation (hierarchical)"
    echo "  ✓ Multi-dimensional breakdowns (2D, 3D)"
    echo "  ✓ K-anonymity suppression"
    echo "  ✓ Cache behavior"
    echo "  ✓ Privacy protection (differencing attacks)"
    echo "  ✓ Spatial aggregation (GPS coordinates)"
    echo "  ✓ Performance testing"
else
    echo "Unit tests completed."
    echo ""
    echo "To run full integration tests with demo data:"
    echo "  $0"
fi

echo ""
