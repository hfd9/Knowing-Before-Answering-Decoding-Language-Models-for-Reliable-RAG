"""Run the frozen candidate on a corrected amount-plus-dates distractor."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2] / 'scripts'))
import query_determinacy_typed_holdout as experiment

experiment.PACK = HERE
experiment.main()
