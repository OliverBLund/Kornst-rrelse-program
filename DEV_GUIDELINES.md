# Development Guidelines

## Core Principles

### 1. Clean Code Philosophy
- **ALWAYS clean up unused dead code** - avoid technical debt at all costs
- Remove unused imports, functions, variables, and files immediately
- If code is commented out for more than 1 commit, delete it
- Use version control instead of commented code for history

### 2. Solution Priority Order
1. **Reuse existing code** - check what's already available first
2. **Extend existing functionality** - modify rather than duplicate
3. **Simple solutions** - choose the most straightforward approach
4. **Create new code** - only when necessary

### 3. Implementation Standards
- **Single Responsibility** - each function/class does one thing well
- **Clear naming** - variables and functions should be self-documenting
- **Minimal dependencies** - don't add libraries unless essential
- **Progressive enhancement** - build incrementally, test each step

### 4. Code Hygiene Checklist
Before any commit:
- [ ] Remove all unused imports
- [ ] Delete commented-out code blocks
- [ ] Remove unused variables and functions
- [ ] Check for duplicate logic that can be consolidated
- [ ] Verify all new code is actually being used
- [ ] Clean up temporary test files and debug code

### 5. Architecture Decisions
- **Favor composition over inheritance**
- **Use existing PyQt patterns** from the codebase
- **Leverage existing data structures** (GrainSizeData, ValidationMessage)
- **Extend existing systems** rather than creating parallel ones

### 6. File Organization
- Keep related functionality together
- Remove empty or nearly-empty files
- Consolidate similar utilities
- Maintain clear module boundaries

## Specific to This Project

### UI Development
- Reuse existing styling from main_window.py and control_panel.py
- Extend existing tab system rather than creating new widgets
- Use established color scheme and fonts

### Data Processing
- Build on existing DataLoader and GrainSizeData classes
- Reuse validation system (ValidationMessage, ValidationSeverity)
- Extend rather than replace existing CSV parsing logic

### Error Handling
- Use established error reporting patterns
- Leverage existing logging infrastructure
- Maintain consistency with current user feedback systems

---

**Remember: Every line of code is a liability. Write only what you need, delete what you don't use, and always clean up after yourself.**