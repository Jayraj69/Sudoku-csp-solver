"""Download the benchmark sets named in the proposal (run once, needs internet).

    python scripts/fetch_data.py            # Norvig easy50 / top95 / hardest -> data/
    kaggle datasets download -d radcliffe/3-million-sudoku-puzzles-with-ratings -p data --unzip

Then benchmark them (added on top of the built-in instance families):
    python -m sudoku_csp.benchmark --extra data/top95.txt --extra-label norvig-top95 --extra-n 95
    python -m sudoku_csp.benchmark --extra data/sudoku-3m.csv --extra-label kaggle --extra-n 100
"""
import os
import urllib.request

FILES = {"easy50.txt": "https://norvig.com/easy50.txt",
         "top95.txt": "https://norvig.com/top95.txt",
         "hardest.txt": "https://norvig.com/hardest.txt"}

os.makedirs("data", exist_ok=True)
for fname, url in FILES.items():
    dest = os.path.join("data", fname)
    try:
        urllib.request.urlretrieve(url, dest)
        n = sum(1 for l in open(dest) if l.strip())
        print(f"OK   {fname}: {n} non-empty lines")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL {fname}: {e}")
