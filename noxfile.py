"""Nox configuration for Local-First To-Do application."""

import nox
from nox import Session

# Python versions to test against
PYTHON_VERSIONS = ["3.10", "3.11", "3.12"]
# Default Python version for development
DEFAULT_PYTHON = "3.10"

# Package locations
PACKAGE_DIR = "src"
TEST_DIR = "tests"


@nox.session(python=DEFAULT_PYTHON)
def lint(session: Session) -> None:
    """Run static analysis with ruff and mypy."""
    session.install("-e", ".[lint]")
    
    # Run ruff for linting and formatting
    session.run("ruff", "check", PACKAGE_DIR, TEST_DIR, "--fix")
    session.run("ruff", "format", PACKAGE_DIR, TEST_DIR)
    
    # Run mypy for type checking
    session.run("mypy", PACKAGE_DIR)


@nox.session(python=PYTHON_VERSIONS)
def test(session: Session) -> None:
    """Run the test suite."""
    session.install("-e", ".[test]")
    
    # Run pytest with coverage
    session.run(
        "pytest",
        "--cov=local_first_todo",
        "--cov-report=term-missing",
        "--cov-report=html",
        "--cov-fail-under=85",  # Start with 85% coverage requirement
        *session.posargs
    )


@nox.session(python=DEFAULT_PYTHON)
def test_fast(session: Session) -> None:
    """Run fast tests only (excluding slow, perf, fuzz, browser markers)."""
    session.install("-e", ".[test]")
    
    session.run(
        "pytest",
        "-m", "not slow and not perf and not fuzz and not browser",
        "--cov=local_first_todo",
        "--cov-report=term-missing",
        *session.posargs
    )


@nox.session(python=DEFAULT_PYTHON)
def test_perf(session: Session) -> None:
    """Run performance tests."""
    session.install("-e", ".[test]")
    
    session.run("pytest", "-m", "perf", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def test_slow(session: Session) -> None:
    """Run slow tests."""
    session.install("-e", ".[test]")
    
    session.run("pytest", "-m", "slow", *session.posargs)


@nox.session(python=DEFAULT_PYTHON)
def coverage(session: Session) -> None:
    """Generate coverage reports."""
    session.install("coverage[toml]")
    
    # Generate coverage report
    session.run("coverage", "report", "--show-missing")
    session.run("coverage", "html")
    
    # Show coverage statistics
    session.log("Coverage report generated in htmlcov/")


@nox.session(python=DEFAULT_PYTHON)
def safety(session: Session) -> None:
    """Check for security vulnerabilities in dependencies."""
    session.install("safety", "pip-audit")
    
    # Check for known security vulnerabilities
    session.run("safety", "check", "--json")
    session.run("pip-audit", "--format=json")


@nox.session(python=DEFAULT_PYTHON)
def docs_lint(session: Session) -> None:
    """Lint documentation files."""
    # This is a placeholder for future documentation linting
    # In Phase 12, we'll add markdown-lint, codespell, etc.
    session.log("Documentation linting will be implemented in Phase 12")


@nox.session(python=DEFAULT_PYTHON)
def clean(session: Session) -> None:
    """Clean up build artifacts and cache files."""
    import shutil
    from pathlib import Path
    
    # Directories to clean
    dirs_to_clean = [
        ".pytest_cache",
        ".mypy_cache",
        ".coverage",
        "htmlcov",
        "dist",
        "build",
        "__pycache__",
        ".nox",
    ]
    
    for dir_name in dirs_to_clean:
        path = Path(dir_name)
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
                session.log(f"Removed directory: {path}")
            else:
                path.unlink()
                session.log(f"Removed file: {path}")
    
    # Clean up Python cache files
    for path in Path(".").rglob("__pycache__"):
        shutil.rmtree(path)
        session.log(f"Removed cache directory: {path}")
    
    for path in Path(".").rglob("*.pyc"):
        path.unlink()
        session.log(f"Removed bytecode file: {path}")


@nox.session(python=DEFAULT_PYTHON, name="ci-setup")
def ci_setup(session: Session) -> None:
    """Verify CI setup and run basic checks."""
    session.install("-e", ".[dev]")
    
    # Check that all tools are available
    session.run("python", "--version")
    session.run("pytest", "--version")
    session.run("mypy", "--version")
    session.run("ruff", "--version")
    
    session.log("✅ CI setup verification completed successfully")


# Default session for developers
nox.options.sessions = ["lint", "test_fast"] 