# Contributing to File Sharing Server

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help others learn and grow

## How to Contribute

### Reporting Bugs

1. Check existing issues to avoid duplicates
2. Provide a clear description of the bug
3. Include steps to reproduce
4. Share environment details (Python version, OS, etc.)

### Suggesting Enhancements

1. Use a clear, descriptive title
2. Provide a detailed description of the suggested enhancement
3. Explain why this enhancement would be useful
4. List any alternative solutions you've considered

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Test thoroughly
5. Commit with clear messages
6. Push and create a Pull Request

## Development Setup

```bash
# Clone the repository
git clone <repo>
cd file-sharing-server

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install in development mode
pip install -e .

# Run tests (if available)
python -m pytest
```

## Code Style

- Follow PEP 8 guidelines
- Use meaningful variable names
- Add docstrings to functions
- Comment complex logic

## Commit Messages

- Use clear, concise commit messages
- Start with a verb (Add, Fix, Update, etc.)
- Reference issues when applicable: "Fix #123"

## Testing

Before submitting a PR:
- Test on multiple Python versions (3.9+)
- Test on different operating systems if possible
- Ensure no breaking changes

## Questions?

Open an issue with the `[QUESTION]` prefix or start a discussion.

Thank you for contributing!
