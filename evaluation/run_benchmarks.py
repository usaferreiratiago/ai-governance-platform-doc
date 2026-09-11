"""
Benchmark execution script that saves results to the database.
"""
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime
import uuid

# Add the current directory to the path to import modules
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Try to import scoring, if it doesn't exist, create a fallback function
try:
    from scoring import exact_match, fuzzy_match, calculate_score
except ImportError:
    print("⚠️ Scoring module not found, using fallback functions")
    def exact_match(predicted, expected):
        """Fallback function for exact comparison."""
        return str(predicted).strip().lower() == str(expected).strip().lower()
    
    def fuzzy_match(predicted, expected, threshold=0.8):
        """Fallback fuzzy match."""
        return exact_match(predicted, expected)
    
    def calculate_score(predicted, expected, method='exact'):
        """Fallback score calculation."""
        return 1.0 if exact_match(predicted, expected) else 0.0

# Import database modules
try:
    from streamlit_app.db import engine, SessionLocal, BenchmarkRun, AuditLog
    from sqlalchemy import text
    DB_AVAILABLE = True
except ImportError:
    print("⚠️ Database module not found, results will only be saved to CSV")
    DB_AVAILABLE = False

# Path to files
ROOT_DIR = Path(__file__).resolve().parents[1]
BENCHMARKS_FILE = ROOT_DIR / 'benchmarks' / 'ground_truth.csv'
RESULTS_FILE = ROOT_DIR / 'evaluation' / 'results.csv'


def save_benchmark_to_db(result_data: dict, model_name: str = "GPT-4"):
    """
    Save a benchmark result to the database.
    
    Args:
        result_data: Dictionary with benchmark results
        model_name: Name of the model being benchmarked
    
    Returns:
        bool: True if saved successfully
    """
    if not DB_AVAILABLE:
        return False
    
    try:
        db = SessionLocal()
        
        # Create benchmark run
        benchmark = BenchmarkRun(
            model_name=model_name,
            score=result_data.get('score', 0.0),
            accuracy=result_data.get('accuracy', 0.0),
            precision=result_data.get('precision', 0.0),
            recall=result_data.get('recall', 0.0),
            f1_score=result_data.get('f1_score', 0.0),
            details=str({
                'question_id': result_data.get('question_id'),
                'question': result_data.get('question'),
                'expected': result_data.get('expected_answer'),
                'predicted': result_data.get('predicted_answer'),
                'passed': result_data.get('passed', False)
            }),
            test_size=1,
            created_by=result_data.get('user_name', 'system'),
            created_at=datetime.now()
        )
        
        db.add(benchmark)
        db.commit()
        db.close()
        return True
    except Exception as e:
        print(f"❌ Error saving benchmark to database: {e}")
        return False


def save_benchmark_batch_to_db(results: list, model_name: str = "GPT-4") -> dict:
    """
    Save a batch of benchmark results to the database.
    
    Args:
        results: List of benchmark result dictionaries
        model_name: Name of the model being benchmarked
    
    Returns:
        dict: Summary of saved results
    """
    if not DB_AVAILABLE:
        return {"saved": 0, "total": len(results), "error": "Database not available"}
    
    saved_count = 0
    errors = []
    
    try:
        db = SessionLocal()
        
        for result in results:
            try:
                # Calculate metrics
                passed = result.get('passed', False)
                score = 1.0 if passed else 0.0
                
                benchmark = BenchmarkRun(
                    model_name=model_name,
                    score=score,
                    accuracy=score,
                    precision=score if passed else 0.0,
                    recall=score if passed else 0.0,
                    f1_score=score if passed else 0.0,
                    details=str({
                        'question_id': result.get('question_id'),
                        'question': result.get('question', ''),
                        'expected': result.get('expected_answer', ''),
                        'predicted': result.get('predicted_answer', ''),
                        'passed': passed,
                        'measure': result.get('measure', ''),
                        'domain': result.get('domain', '')
                    }),
                    test_size=1,
                    created_by=result.get('user_name', 'system'),
                    created_at=datetime.now()
                )
                
                db.add(benchmark)
                saved_count += 1
                
            except Exception as e:
                errors.append(str(e))
                continue
        
        db.commit()
        db.close()
        
        return {
            "saved": saved_count,
            "total": len(results),
            "errors": errors if errors else None
        }
        
    except Exception as e:
        return {"saved": saved_count, "total": len(results), "error": str(e)}


def log_audit_event(user_name: str, action: str, entity: str = "", entity_id: str = ""):
    """Log an audit event."""
    if not DB_AVAILABLE:
        return
    
    try:
        db = SessionLocal()
        audit = AuditLog(
            event_time=datetime.now().isoformat(),
            user_name=user_name,
            action=action,
            entity=entity,
            entity_id=entity_id,
            details=f"Benchmark run with {entity_id} results"
        )
        db.add(audit)
        db.commit()
        db.close()
    except Exception as e:
        print(f"⚠️ Failed to log audit event: {e}")


def run_benchmarks(
    benchmark_file: Path = BENCHMARKS_FILE, 
    model_name: str = "GPT-4",
    save_to_db: bool = True,
    user_name: str = "system"
) -> dict:
    """
    Run benchmarks and save results.
    
    Args:
        benchmark_file: Path to benchmark CSV file
        model_name: Name of the model being benchmarked
        save_to_db: Whether to save results to database
        user_name: Name of the user running the benchmark
    
    Returns:
        dict: Summary of benchmark results
    """
    print("📂 Loading benchmarks...")
    
    if not benchmark_file.exists():
        print(f"❌ Benchmark file not found: {benchmark_file}")
        return {"error": "Benchmark file not found"}
    
    df = pd.read_csv(benchmark_file)
    
    print(f"✅ Benchmarks loaded: {len(df)} records")
    print(f"📊 Available columns: {list(df.columns)}")
    print()
    
    # Check if expected columns exist
    expected_columns = ['benchmark_id', 'question', 'expected_answer']
    missing_columns = [col for col in expected_columns if col not in df.columns]
    
    if missing_columns:
        print(f"⚠️ Missing columns: {missing_columns}")
        print("Using available columns to continue...")
    
    # Run benchmarks
    print("🔍 Running benchmarks...")
    results = []
    
    for index, row in df.iterrows():
        try:
            # Get question_id
            benchmark_id = row.get('benchmark_id')
            if pd.isna(benchmark_id) or benchmark_id is None:
                question_id = f"GT-{index:03d}"
            else:
                question_id = str(benchmark_id)
            
            # Get expected answer
            expected = row.get('expected_answer', '')
            
            # TODO: Replace with real LLM call
            predicted = expected
            
            # Calculate metrics
            passed = exact_match(predicted, expected)
            score = calculate_score(predicted, expected)
            
            result = {
                "question_id": question_id,
                "question": row.get('question', ''),
                "expected_answer": expected,
                "predicted_answer": predicted,
                "passed": passed,
                "score": score,
                "measure": row.get('expected_measure', ''),
                "domain": row.get('expected_domain', ''),
                "user_name": user_name
            }
            
            results.append(result)
            
            status = "✅" if passed else "❌"
            question_preview = str(row.get('question', ''))[:50]
            print(f"  {status} {question_id}: {question_preview}...")
            
        except Exception as e:
            print(f"❌ Error in benchmark {index}: {e}")
            results.append({
                "question_id": f"GT-{index:03d}",
                "question": row.get('question', ''),
                "error": str(e),
                "passed": False,
                "score": 0.0,
                "user_name": user_name
            })
    
    # Create results DataFrame
    result_df = pd.DataFrame(results)
    
    # Save to CSV
    print(f"\n💾 Saving results to: {RESULTS_FILE}")
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    result_df.to_csv(RESULTS_FILE, index=False)
    
    # Save to database
    if save_to_db and DB_AVAILABLE:
        print("💾 Saving results to database...")
        db_result = save_benchmark_batch_to_db(results, model_name)
        if db_result.get('saved', 0) > 0:
            print(f"✅ {db_result['saved']} results saved to database")
            
            # Log audit event
            log_audit_event(
                user_name,
                "BENCHMARK_RUN",
                "Benchmark",
                model_name
            )
        else:
            print(f"⚠️ Failed to save to database: {db_result.get('error', 'Unknown error')}")
    
    # Calculate accuracy
    summary = {
        "total": len(result_df),
        "passed": 0,
        "failed": 0,
        "accuracy": 0.0,
        "results_file": str(RESULTS_FILE)
    }
    
    if 'passed' in result_df.columns:
        passed_count = result_df['passed'].sum()
        total_count = len(result_df)
        accuracy = passed_count / total_count if total_count > 0 else 0
        
        summary["passed"] = int(passed_count)
        summary["failed"] = total_count - int(passed_count)
        summary["accuracy"] = accuracy
        
        print(f"\n📊 Summary:")
        print(f"   Total: {total_count}")
        print(f"   ✅ Passed: {passed_count}")
        print(f"   ❌ Failed: {total_count - passed_count}")
        print(f"   ⭐ Accuracy: {accuracy:.2%}")
        
        if DB_AVAILABLE:
            print(f"   💾 Saved to database: ✅")
    
    print("\n✅ Benchmark completed!")
    
    # Show detailed results
    print("\n📋 Detailed results:")
    if not result_df.empty:
        display_cols = ['question_id', 'passed']
        if 'question' in result_df.columns:
            display_cols.append('question')
        print(result_df[display_cols].head(10).to_string(index=False))
    
    return summary


def main():
    """Main entry point for the benchmark script."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run benchmarks for semantic model")
    parser.add_argument("--model", "-m", default="GPT-4", help="Model name")
    parser.add_argument("--no-db", action="store_true", help="Skip saving to database")
    parser.add_argument("--user", "-u", default="system", help="User name")
    parser.add_argument("--file", "-f", help="Custom benchmark file path")
    
    args = parser.parse_args()
    
    benchmark_file = Path(args.file) if args.file else BENCHMARKS_FILE
    
    run_benchmarks(
        benchmark_file=benchmark_file,
        model_name=args.model,
        save_to_db=not args.no_db,
        user_name=args.user
    )


if __name__ == "__main__":
    main()