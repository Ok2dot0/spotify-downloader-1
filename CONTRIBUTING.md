# Contributing to Spotify Album Downloader and Burner

Thank you for considering contributing to this project! Here's how you can help.

## Development Setup

1. Fork and clone the repository:
   ```bash
   git clone https://github.com/yourusername/spotify-downloader.git
   cd spotify-downloader
   ```

2. Create a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. Set up pre-commit hooks (optional but recommended):
   ```bash
   pip install pre-commit
   pre-commit install
   ```

## Coding Standards

This project follows these coding standards:
- Code formatting with Black (line length 100)
- Import sorting with isort (Black-compatible profile)
- Linting with flake8
- Type hints are encouraged for new code

## Testing

Write tests for new features and ensure existing tests pass:
```bash
pytest
```

For coverage report:
```bash
pytest --cov=./ --cov-report=term-missing
```

## Pull Request Process

1. Create a branch for your changes
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit with descriptive messages

3. Run the tests to ensure they pass
   ```bash
   pytest
   ```

4. Make sure your code is formatted correctly
   ```bash
   black .
   isort .
   flake8 .
   ```

5. Push your branch and create a Pull Request

6. In your PR description, explain your changes and link any relevant issues

## Code of Conduct

Please respect our [Code of Conduct](CODE_OF_CONDUCT.md) in all interactions.

## License

By contributing to this project, you agree that your contributions will be licensed under the project's [MIT License](LICENSE).