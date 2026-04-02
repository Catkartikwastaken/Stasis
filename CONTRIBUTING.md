# Contributing to STASIS

Thank you for considering contributing to STASIS! This document outlines the guidelines for contributing.

## How to Contribute

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-feature`)
3. **Commit** your changes (`git commit -m 'Add amazing feature'`)
4. **Push** to the branch (`git push origin feature/amazing-feature`)
5. **Open** a Pull Request

## Code Standards

### Firmware (Arduino/C++)
- Use `#pragma once` in all headers
- Keep magic numbers in `config.h`
- Use non-blocking `millis()` timers
- Comment complex logic

### Python Backend
- Follow PEP 8
- Use type hints where practical
- Wrap all UART I/O in try/except
- Use environment variables for config

### React Dashboard
- Functional components only
- Use React hooks
- Zustand for state management
- Tailwind CSS for styling

## Reporting Issues

Use GitHub Issues with:
- Clear title
- Steps to reproduce
- Expected vs actual behavior
- Screenshots if applicable

## License

By contributing, you agree your contributions are licensed under MIT.
