# Contributing to Enhanced MCP Server

Thank you for your interest in contributing! We welcome all contributions that improve the project.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/yourusername/claude_code-coding-mcp.git
   cd claude_code-coding-mcp
   ```
3. Run the development setup:
   ```bash
   ./one_click_setup.sh
   # Choose option 4 (Development Install)
   ```

## Development Guidelines

### Code Style
- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add comments for complex logic
- Keep functions small and focused

### Security Requirements
- **NEVER** commit API keys or credentials
- Always use placeholders in example code
- Test with mock API responses when possible
- Review your changes for accidental key exposure

### Testing
- Add tests for new features
- Ensure existing tests pass
- Test with multiple AI providers
- Verify context persistence works correctly

## Submitting Changes

1. Create a feature branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Add feature: description"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/your-feature-name
   ```

4. Open a Pull Request with:
   - Clear description of changes
   - Any relevant issue numbers
   - Screenshots if applicable
   - Test results

## Pull Request Checklist

- [ ] No API keys or secrets in code
- [ ] Tests pass locally
- [ ] Documentation updated if needed
- [ ] Code follows project style
- [ ] Commit messages are clear

## Reporting Issues

When reporting issues, please include:
- Your operating system
- Python version
- Claude Code version
- Steps to reproduce
- Error messages (without API keys!)

## Feature Requests

We love new ideas! When requesting features:
- Explain the use case
- Describe expected behavior
- Provide examples if possible
- Consider implementation approach

## Questions?

Feel free to open a discussion for:
- General questions
- Implementation advice
- Feature discussions
- Community support

Thank you for contributing!