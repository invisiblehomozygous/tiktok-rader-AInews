#!/bin/bash
#
# TikTok Feishu Radar - Thin Pipeline Runner
# Just workflow orchestration - all logic is in Python scripts
#
# Usage:
#   bash run_pipeline.sh           # Run all phases
#   bash run_pipeline.sh --phase2  # Start from Phase 2 (skip Phase 1)
#   bash run_pipeline.sh --phase3  # Start from Phase 3 (skip Phase 1 & 2)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BASE_DIR="$SCRIPT_DIR"
VENV_PYTHON="$BASE_DIR/.venv/bin/python3"

# Check virtual environment
if [ ! -f "$VENV_PYTHON" ]; then
    echo "ERROR: Virtual environment not found at $BASE_DIR/.venv"
    exit 1
fi

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Parse arguments
START_PHASE="all"  # Default: run all phases
RUN_PER_VIDEO=true  # Default: run per-video analysis (for bitable)

while [[ $# -gt 0 ]]; do
    case $1 in
        --phase2)
            START_PHASE="phase2"
            shift
            ;;
        --phase2-analysis)
            START_PHASE="phase2-analysis"
            shift
            ;;
        --phase2-per-video)
            START_PHASE="phase2-per-video"
            shift
            ;;
        --no-per-video)
            RUN_PER_VIDEO=false
            shift
            ;;
        --phase3)
            START_PHASE="phase3"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --phase2              Start from Phase 2 (skip Phase 1)"
            echo "  --phase2-analysis     Run only Phase 2.2 (category analysis, skip classification)"
            echo "  --phase2-per-video    Run only Phase 2.2.2 (per-video analysis, skip classification)"
            echo "  --no-per-video        Skip per-video analysis (bitable will not be updated)"
            echo "  --phase3              Start from Phase 3 (skip Phase 1 & 2)"
            echo "  --help, -h            Show this help message"
            echo ""
            echo "Examples:"
            echo "  $0                      # Run full pipeline with per-video analysis (default)"
            echo "  $0 --no-per-video        # Run full pipeline without per-video analysis"
            echo "  $0 --phase2             # Skip scraping, full analysis + push"
            echo "  $0 --phase2-analysis    # Skip classification, just category analysis + push"
            echo "  $0 --phase2-per-video   # Skip classification, just per-video analysis"
            echo "  $0 --phase3             # Only push existing report to Feishu"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Validate start phase requirements
validate_phase2_requirements() {
    if [ ! -f "$BASE_DIR/trend-scrap/tiktok-scraper/data/filtered-result.json" ]; then
        log_error "Phase 2 requires filtered-result.json from Phase 1"
        log_error "Run full pipeline first, or ensure data exists"
        exit 1
    fi
    log_info "Using existing data: filtered-result.json"
}

validate_phase2_analysis_requirements() {
    if [ ! -f "$BASE_DIR/skill_runs/category_map.json" ]; then
        log_error "Phase 2.2 (analysis) requires category_map.json from Phase 2.1"
        log_error "Run with --phase2 first, or ensure category_map.json exists"
        exit 1
    fi
    if [ ! -f "$BASE_DIR/trend-scrap/tiktok-scraper/data/filtered-result.json" ]; then
        log_error "Phase 2.2 requires filtered-result.json"
        exit 1
    fi
    log_info "Using existing category_map.json"
}

validate_phase2_per_video_requirements() {
    if [ ! -f "$BASE_DIR/skill_runs/category_map.json" ]; then
        log_error "Phase 2.2.2 (per-video analysis) requires category_map.json from Phase 2.1"
        log_error "Run with --phase2 first, or ensure category_map.json exists"
        exit 1
    fi
    if [ ! -f "$BASE_DIR/trend-scrap/tiktok-scraper/data/filtered-result.json" ]; then
        log_error "Phase 2.2.2 requires filtered-result.json"
        exit 1
    fi
    log_info "Using existing category_map.json"
}

validate_phase3_requirements() {
    if [ ! -f "$BASE_DIR/skill_runs/report.json" ]; then
        log_error "Phase 3 requires report.json from Phase 2"
        log_error "Run with --phase2 first, or ensure report exists"
        exit 1
    fi
    log_info "Using existing report: report.json"
}

# Main pipeline - just workflow, no logic
main() {
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local run_dir="$BASE_DIR/skill_runs/$timestamp"
    mkdir -p "$run_dir"

    log_info "=========================================="
    log_info "TikTok Feishu Radar Pipeline - $timestamp"
    log_info "Start phase: $START_PHASE"
    log_info "=========================================="

    # ========== Stage 1: Update product manual prompt ==========
    if [ "$START_PHASE" = "all" ]; then
        log_info "Stage 1: Updating product manual prompt..."
        "$VENV_PYTHON" "$BASE_DIR/scripts/update_prompt_with_product_manual.py" || {
            log_error "Stage 1 failed"
            exit 1
        }
        log_info "✅ Stage 1 complete"
    else
        log_warn "Skipping Stage 1 (product manual update)"
    fi

    # ========== Phase 1: Scrape + Validate ==========
    if [ "$START_PHASE" = "all" ]; then
        log_info "Phase 1: Scraping and validating..."
        "$VENV_PYTHON" "$BASE_DIR/scripts/phase1_scrape.py" || {
            log_error "Phase 1 failed"
            exit 1
        }
        log_info "✅ Phase 1 complete"
    else
        log_warn "Skipping Phase 1 (scraping)"
        validate_phase2_requirements
    fi

    # ========== Phase 2: Generate Report ==========
    if [ "$START_PHASE" = "all" ] || [ "$START_PHASE" = "phase2" ] || [ "$START_PHASE" = "phase2-analysis" ] || [ "$START_PHASE" = "phase2-per-video" ]; then
        
        # Step 2.1: Classification (skip if --phase2-analysis or --phase2-per-video)
        if [ "$START_PHASE" = "phase2-analysis" ] || [ "$START_PHASE" = "phase2-per-video" ]; then
            log_warn "Skipping Phase 2.1 (classification)"
            validate_phase2_analysis_requirements
        else
            log_info "Phase 2.1: Classifying videos..."
            "$VENV_PYTHON" "$BASE_DIR/scripts/phase2_classify.py" \
                --output "$BASE_DIR/skill_runs/category_map.json" \
                --max-retries 3 || {
                log_error "Phase 2.1 (classification) failed"
                exit 1
            }
            log_info "✅ Phase 2.1 complete"
        fi
        
        # Step 2.2: Analysis (2.2.1 and 2.2.2 run in parallel when both needed)
        local run_category=false
        local run_per_video=false
        
        # Determine which analyses to run
        if [ "$START_PHASE" != "phase2-per-video" ]; then
            run_category=true
        fi
        if [ "$RUN_PER_VIDEO" = true ] || [ "$START_PHASE" = "phase2-per-video" ]; then
            run_per_video=true
        fi
        
        # Run analyses (parallel if both needed)
        if [ "$run_category" = true ] && [ "$run_per_video" = true ]; then
            # Both needed - run in parallel
            log_info "Phase 2.2: Running category and per-video analysis in parallel..."
            
            log_info "  [2.2.1] Starting category analysis..."
            "$VENV_PYTHON" "$BASE_DIR/scripts/phase2_analyze.py" \
                --category-map "$BASE_DIR/skill_runs/category_map.json" \
                --output "$BASE_DIR/skill_runs/report.json" \
                --max-retries 3 > "$run_dir/phase2_2_1.log" 2>&1 &
            local pid_category=$!
            
            log_info "  [2.2.2] Starting per-video analysis..."
            "$VENV_PYTHON" "$BASE_DIR/scripts/phase2_analyze_per_video.py" \
                --category-map "$BASE_DIR/skill_runs/category_map.json" \
                --output "$BASE_DIR/skill_runs/report_per_video.json" \
                --max-retries 3 > "$run_dir/phase2_2_2.log" 2>&1 &
            local pid_per_video=$!
            
            # Wait for both to complete
            log_info "  Waiting for both analyses to complete..."
            local exit_category=0
            local exit_per_video=0
            
            wait $pid_category
            exit_category=$?
            
            wait $pid_per_video
            exit_per_video=$?
            
            # Check results
            if [ $exit_category -ne 0 ]; then
                log_error "Phase 2.2.1 (category analysis) failed"
                cat "$run_dir/phase2_2_1.log"
                exit 1
            fi
            log_info "  ✅ 2.2.1 category analysis complete"
            
            if [ $exit_per_video -ne 0 ]; then
                log_error "Phase 2.2.2 (per-video analysis) failed"
                cat "$run_dir/phase2_2_2.log"
                exit 1
            fi
            log_info "  ✅ 2.2.2 per-video analysis complete"
            
        elif [ "$run_category" = true ]; then
            # Only category analysis
            log_info "Phase 2.2.1: Analyzing categories..."
            "$VENV_PYTHON" "$BASE_DIR/scripts/phase2_analyze.py" \
                --category-map "$BASE_DIR/skill_runs/category_map.json" \
                --output "$BASE_DIR/skill_runs/report.json" \
                --max-retries 3 || {
                log_error "Phase 2.2.1 (category analysis) failed"
                exit 1
            }
            log_info "✅ Phase 2.2.1 complete"
            
        elif [ "$run_per_video" = true ]; then
            # Only per-video analysis
            log_info "Phase 2.2.2: Analyzing videos individually..."
            "$VENV_PYTHON" "$BASE_DIR/scripts/phase2_analyze_per_video.py" \
                --category-map "$BASE_DIR/skill_runs/category_map.json" \
                --output "$BASE_DIR/skill_runs/report_per_video.json" \
                --max-retries 3 || {
                log_error "Phase 2.2.2 (per-video analysis) failed"
                exit 1
            }
            log_info "✅ Phase 2.2.2 complete"
        fi
        
        log_info "✅ Phase 2 complete"
    else
        log_warn "Skipping Phase 2 (analysis)"
        validate_phase3_requirements
    fi

    # ========== Phase 3: Build and Push Feishu Card ==========
    if [ "$START_PHASE" = "all" ] || [ "$START_PHASE" = "phase2" ] || [ "$START_PHASE" = "phase3" ]; then
        log_info "Phase 3: Building and pushing Feishu card..."
        
        # Check if per-video report exists for bitable
        PER_VIDEO_ARG=""
        if [ -f "$BASE_DIR/skill_runs/report_per_video.json" ]; then
            PER_VIDEO_ARG="--report-per-video $BASE_DIR/skill_runs/report_per_video.json"
            log_info "Using per-video report for bitable (10 rows)"
        else
            log_warn "Per-video report not found - bitable will be skipped"
            log_warn "Run with default options to generate per-video analysis"
        fi
        
        "$VENV_PYTHON" "$BASE_DIR/scripts/phase3_push.py" \
            --report "$BASE_DIR/skill_runs/report.json" \
            --raw "$BASE_DIR/trend-scrap/tiktok-scraper/data/filtered-result.json" \
            --card-output "$run_dir/feishu_card.json" \
            $PER_VIDEO_ARG || {
            log_error "Phase 3 failed"
            exit 1
        }
        log_info "✅ Phase 3 complete"
    fi

    log_info "=========================================="
    log_info "✅ Pipeline complete!"
    log_info "=========================================="
}

main "$@"
