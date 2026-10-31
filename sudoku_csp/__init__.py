"""Sudoku as a Constraint Satisfaction Problem (FAI PBL, ECSCT24301)."""
from .board import (InvalidPuzzle, get_spec, parse, validate, is_solution,
                    to_string, pretty, name)
from .solvers import ALGORITHMS, make_solver, Result

__all__ = ["InvalidPuzzle", "get_spec", "parse", "validate", "is_solution", "to_string",
           "pretty", "name", "ALGORITHMS", "make_solver", "Result"]
__version__ = "1.0.0"
