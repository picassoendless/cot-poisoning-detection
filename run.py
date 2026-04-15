
"""
run.py

Main runner for the CoT Poisoning Detection pipeline.
Reads config.yaml and orchestrates all layers.

Usage:
    python run.py                  # Run all enabled layers
    python run.py --layer 1        # Run only Layer 1
    python run.py --layer 2        # Run only Layer 2
    python run.py --layer 3        # Run only Layer 3 (LLM-as-Judge)
    python run.py --layer 1 2      # Run Layers 1 and 2
    python run.py --full           # Run the full-system evaluation (ensemble)
    python run.py --gateway        # Start the FastAPI inline gateway
    python run.py --test           # Run individual module tests
    python run.py --patterns       # Run pattern analysis on Tensor Trust data
"""

import argparse
import io
import os
import sys
import time
import yaml
from dotenv import load_dotenv

# Force UTF-8 output on Windows to avoid cp1252 encoding crashes
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'src'))
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'evaluation'))
load_dotenv(os.path.join(PROJECT_ROOT, '.env'), override=True)


def load_config(config_path=None):
    """Load configuration from YAML file."""
    path = config_path or os.path.join(PROJECT_ROOT, 'config.yaml')
    with open(path, 'r') as f:
        return yaml.safe_load(f)


def run_layer1(config):
    """Run Layer 1: Pattern Detection evaluation."""
    import importlib
    import evaluate_layer1 as el1
    importlib.reload(el1)

    l1 = config.get('layer1', {})
    sample_size = l1.get('eval_sample_size', 1000)
    targets = l1.get('targets', {})
    detection_target = targets.get('detection_rate', 70)
    latency_target = targets.get('latency_ms', 10)

    return el1.evaluate_layer1(
        sample_size=sample_size,
        detection_target=detection_target,
        latency_target=latency_target,
    )


def run_layer2(config):
    """Run Layer 2: Behavioral Drift Detection evaluation."""
    import importlib
    import evaluation_layer2 as el2
    importlib.reload(el2)

    l2 = config.get('layer2', {})
    targets = l2.get('targets', {})
    detection_target = targets.get('detection_rate', 85)
    latency_target = targets.get('latency_ms', 5)
    seed = l2.get('seed', 42)
    sample_cases = l2.get('sample_cases', None)

    return el2.evaluate_layer2(
        detection_target=detection_target,
        latency_target=latency_target,
        seed=seed,
        sample_cases=sample_cases,
    )


def run_layer3(config):
    """Run Layer 3: LLM-as-Judge evaluation."""
    import importlib
    import evaluate_layer3 as el3
    importlib.reload(el3)

    l3 = config.get('layer3', {})
    sample_cases = l3.get('sample_cases', 10)
    targets = l3.get('targets', {})
    recall_target = targets.get('recall', 85)
    seed = config.get('layer2', {}).get('seed', 42)

    return el3.evaluate_layer3(
        sample_cases=sample_cases,
        detection_target=recall_target,
        seed=seed,
    )


def run_full_system(config):
    """Run end-to-end evaluation of all three layers + ensemble."""
    import importlib
    import evaluate_full_system as efs
    importlib.reload(efs)

    fs = config.get('full_system', {})
    sample_cases = fs.get('sample_cases', 10)
    enable_layer3 = fs.get('enable_layer3', True)
    seed = config.get('layer2', {}).get('seed', 42)

    return efs.evaluate_full_system(
        sample_cases=sample_cases,
        seed=seed,
        enable_layer3=enable_layer3,
    )


def run_gateway(config):
    """Start the FastAPI inline gateway."""
    from gateway import run_gateway as _launch
    gw = config.get('gateway', {})
    host = gw.get('host', '0.0.0.0')
    port = int(gw.get('port', 8080))
    print(f"Starting gateway on http://{host}:{port} (POST /triage, GET /health)")
    _launch(host=host, port=port)


def run_module_tests(config):
    """Run individual module test functions."""
    print("\n" + "=" * 60)
    print("MODULE TESTS")
    print("=" * 60)

    from pattern_detector import test_pattern_detector
    from poison_injector import test_poison_injector
    from risk_scorer import test_risk_scorer

    print("\n--- Pattern Detector ---")
    test_pattern_detector()

    print("\n--- Poison Injector ---")
    test_poison_injector()

    print("\n--- Risk Scorer ---")
    test_risk_scorer()

    # Only run LLM-dependent tests if API key is set
    if os.getenv('ANTHROPIC_API_KEY'):
        from llm_client import test_llm_client
        from behavioral_detector import test_behavioral_detector
        from llm_judge import test_llm_judge

        print("\n--- LLM Client ---")
        test_llm_client()

        print("\n--- Behavioral Detector ---")
        test_behavioral_detector()

        print("\n--- LLM Judge ---")
        test_llm_judge()
    else:
        print("\nSkipping LLM-dependent tests (ANTHROPIC_API_KEY not set)")


def run_pattern_analysis():
    """Run pattern analysis on Tensor Trust data."""
    from test_patterns import test_patterns
    test_patterns()


def main():
    parser = argparse.ArgumentParser(
        description='CoT Poisoning Detection Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                  Run all enabled layers
  python run.py --layer 1        Run only Layer 1 (pattern detection)
  python run.py --layer 2        Run only Layer 2 (behavioral drift)
  python run.py --layer 3        Run only Layer 3 (LLM-as-Judge)
  python run.py --layer 1 2 3    Run all three layers individually
  python run.py --full           Run full-system evaluation (ensemble)
  python run.py --gateway        Start FastAPI inline gateway
  python run.py --test           Run module self-tests
  python run.py --patterns       Run pattern hit-rate analysis
  python run.py --config my.yaml Use a custom config file
        """
    )
    parser.add_argument('--layer', nargs='+', type=int, choices=[1, 2, 3],
                        help='Which layer(s) to run (default: all enabled)')
    parser.add_argument('--full', action='store_true',
                        help='Run full-system evaluation (all layers + ensemble)')
    parser.add_argument('--gateway', action='store_true',
                        help='Start the FastAPI inline detection gateway')
    parser.add_argument('--test', action='store_true',
                        help='Run individual module tests')
    parser.add_argument('--patterns', action='store_true',
                        help='Run pattern analysis on Tensor Trust data')
    parser.add_argument('--config', type=str, default=None,
                        help='Path to config YAML (default: config.yaml)')

    args = parser.parse_args()

    # Load config
    config = load_config(args.config)

    model_cfg = config.get('model', {})
    print("=" * 60)
    print("CoT POISONING DETECTION PIPELINE")
    print("=" * 60)
    print(f"Model: {model_cfg.get('name', 'N/A')}")
    print(f"Temperature: {model_cfg.get('temperature', 'N/A')}")
    print()

    # Apply model config to environment so LLMTriageClient picks it up
    os.environ.setdefault('COT_MODEL', model_cfg.get('name', ''))
    os.environ.setdefault('COT_TEMPERATURE', str(model_cfg.get('temperature', 0.0)))
    os.environ.setdefault('COT_MAX_TOKENS', str(model_cfg.get('max_tokens', 500)))

    start = time.perf_counter()

    if args.test:
        run_module_tests(config)
    elif args.patterns:
        run_pattern_analysis()
    elif args.gateway:
        run_gateway(config)
    elif args.full:
        print("\n>>> FULL SYSTEM EVALUATION")
        print("=" * 60)
        run_full_system(config)
    else:
        layers = args.layer or []
        run_all = len(layers) == 0

        if run_all or 1 in layers:
            l1_cfg = config.get('layer1', {})
            if l1_cfg.get('enabled', True) or 1 in layers:
                print("\n>>> LAYER 1: Pattern Detection")
                print("=" * 60)
                run_layer1(config)

        if run_all or 2 in layers:
            l2_cfg = config.get('layer2', {})
            if l2_cfg.get('enabled', True) or 2 in layers:
                print("\n>>> LAYER 2: Behavioral Drift Detection")
                print("=" * 60)
                run_layer2(config)

        if run_all or 3 in layers:
            l3_cfg = config.get('layer3', {})
            if l3_cfg.get('enabled', False) or 3 in layers:
                print("\n>>> LAYER 3: LLM-as-Judge")
                print("=" * 60)
                run_layer3(config)

    elapsed = time.perf_counter() - start
    print(f"\nTotal pipeline time: {elapsed:.2f}s")
    print("Done.")


if __name__ == "__main__":
    main()
